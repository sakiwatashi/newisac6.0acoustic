#!/usr/bin/env bash
# V2 D1.5 1-DOF closed-loop approach, UR10e arm-carried sensor.
#
# D1.5 takes D1's validated three-arm closed-loop-approach protocol
# (scripts/d1_approach_runner.py, runtime/run_v2_d1_approach.sh) and swaps
# the "flying sensor" for a UR10e arm-carried sensor (IK-solved tool0 motion
# + kinematic joint writes instead of a bare xformOp:translate rewrite). See
# scripts/d15_arm_approach_runner.py's module docstring for the full design
# rationale (skeleton provenance, sensor-mount choice, anti-branch-jump
# measures, the two per-step geometry audits).
#
# Runs scripts/d15_arm_approach_runner.py in its four modes (probe, closed,
# blind, open) and then scripts/analyze_d15_arm_approach.py to adjudicate the
# pre-registered criteria below.
#
# Pre-registered criteria (written here BEFORE this script is ever run
# against real data; the analyzer computes these, this shell script only
# invokes it and gates on the probe result):
#
#   d05_arm_mount_valid   : probe-mode live regression of peak_sample_idx vs
#                           true_distance_3d_m (arm swept, target fixed) has
#                           r >= 0.99 AND zero posture_violation / sensor_
#                           pose_violation rows across the probe sweep.
#                           Gates whether closed/blind/open even run (see
#                           ABORT branch below).
#   d15_tracking_r_ge_0.9 : r(stop_sensor_x_actual, target_x) over the CLOSED
#                           arm's VALID episodes >= 0.9.
#   d15_beats_blind       : closed arm's stop_error RMSE (valid episodes
#                           only) is lower than blind's, AND a Welch
#                           two-sample t-test on the two arms' stop_error
#                           samples has p < 0.05.
#   d15_posture_clean     : total invalid episodes across closed+blind+open
#                           == 0.
#
# Sequence:
#   1. probe                                  (D0.5 arm-mount validation)
#      -> grep PROBE_RESULT r=<r> ... n_posture_violations=<k>
#         n_sensor_pose_violations=<k2> from its log; ABORT (exit 1) unless
#         r >= 0.99 AND both violation counts are 0 -- see the two
#         diagnostic branches below for what to try next.
#   2. closed, blind, open sessions           (each SKIP-if-exists, resumable)
#   3. scripts/analyze_d15_arm_approach.py --scan-dir "$BASE_OUT" | tee -a run.log
#
# Resumable: each step is SKIPPED if its expected result file already exists
# under BASE_OUT, so a partially-completed run (e.g. GPU budget cut short)
# can be re-invoked and will only run the remaining steps.
#
# Usage: bash runtime/run_v2_d15_arm_approach.sh

set -e

ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/d15_arm_approach_runner.py
ANALYZER=/home/lab109/song/isaacsim6.0/scripts/analyze_d15_arm_approach.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/v2_d15_arm_approach

N_EPISODES=30
SEED=20260708
STANDOFF=0.35
STEP=0.05
MAX_STEPS=40
SENSOR_OFFSET=0.25
PROBE_R_MIN=0.99

mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"

echo "=== V2 D1.5 arm-carried approach sweep — $(date) ===" | tee -a "$LOG"
echo "BASE_OUT=$BASE_OUT" | tee -a "$LOG"
echo "pre-registered criteria: d05_arm_mount_valid, d15_tracking_r_ge_0.9, d15_beats_blind, d15_posture_clean" | tee -a "$LOG"
echo "reference: scripts/d15_arm_approach_runner.py module docstring (full design + criteria text)" | tee -a "$LOG"
echo | tee -a "$LOG"

# run_or_skip <step-label> <result-file> <isaacsim-args...>
run_or_skip() {
    local label="$1"
    local result_file="$2"
    shift 2
    if [ -f "$result_file" ]; then
        echo "[SKIP] $label (found $result_file)" | tee -a "$LOG"
        return 0
    fi
    echo "[RUN]  $label" | tee -a "$LOG"
    "$ISAACSIM" "$SCRIPT" "$@" 2>&1 | tee -a "$LOG"
}

# ── 1. probe (D0.5 arm-mount validation) ──────────────────────────────────────
PROBE_LOG="$BASE_OUT/probe_stdout.log"
PROBE_RESULT_FILE="$BASE_OUT/probe/points.csv"
if [ -f "$PROBE_RESULT_FILE" ] && [ -f "$PROBE_LOG" ]; then
    echo "[SKIP] probe (found $PROBE_RESULT_FILE)" | tee -a "$LOG"
else
    echo "[RUN]  probe" | tee -a "$LOG"
    "$ISAACSIM" "$SCRIPT" --mode probe --output-dir "$BASE_OUT" --sensor-offset "$SENSOR_OFFSET" \
        2>&1 | tee "$PROBE_LOG" | tee -a "$LOG"
fi

PROBE_LINE=$(grep -o 'PROBE_RESULT r=[^ ]* slope=[^ ]* n_posture_violations=[^ ]* n_sensor_pose_violations=[^ ]*' "$PROBE_LOG" | tail -n1 || true)
if [ -z "$PROBE_LINE" ]; then
    echo | tee -a "$LOG"
    echo "ABORT: no PROBE_RESULT line found in $PROBE_LOG -- probe run did not complete." | tee -a "$LOG"
    echo "Fallback: arm-carried sensor motion validity is UNKNOWN. Do not assume it works." | tee -a "$LOG"
    echo "Report back to the lead agent before writing any more D1.5 code." | tee -a "$LOG"
    exit 1
fi
echo "$PROBE_LINE" | tee -a "$LOG"

PROBE_R=$(echo "$PROBE_LINE" | sed -n 's/.*PROBE_RESULT r=\([^ ]*\) slope=.*/\1/p')
PROBE_N_POSTURE=$(echo "$PROBE_LINE" | sed -n 's/.*n_posture_violations=\([^ ]*\) n_sensor_pose_violations=.*/\1/p')
PROBE_N_SENSOR_POSE=$(echo "$PROBE_LINE" | sed -n 's/.*n_sensor_pose_violations=\([^ ]*\)$/\1/p')

PROBE_GATE_OK=$(python3 -c "
import math
try:
    r = float('$PROBE_R')
except ValueError:
    r = float('nan')
try:
    n_posture = int('$PROBE_N_POSTURE')
except ValueError:
    n_posture = -1
try:
    n_sensor_pose = int('$PROBE_N_SENSOR_POSE')
except ValueError:
    n_sensor_pose = -1
ok = (not math.isnan(r)) and r >= $PROBE_R_MIN and n_posture == 0 and n_sensor_pose == 0
print('1' if ok else '0')
")

if [ "$PROBE_GATE_OK" != "1" ]; then
    echo | tee -a "$LOG"
    echo "ABORT: D0.5 gate failed -- r=$PROBE_R (need >= $PROBE_R_MIN), " \
         "n_posture_violations=$PROBE_N_POSTURE, n_sensor_pose_violations=$PROBE_N_SENSOR_POSE (both need == 0)." \
         | tee -a "$LOG"
    echo "closed/blind/open will NOT run. Diagnostic guidance:" | tee -a "$LOG"
    echo "  - If r is low: the sensor mount's transform may not be propagating through the" | tee -a "$LOG"
    echo "    IK-solved arm motion as expected, or the sensor sits in the gripper/wrist's" | tee -a "$LOG"
    echo "    own acoustic shadow. Try --sensor-offset 0.35 (further from the wrist) before" | tee -a "$LOG"
    echo "    concluding the arm-carried design itself is invalid." | tee -a "$LOG"
    echo "  - If either violation count is > 0: the fixed geometry/seed pose is putting a" | tee -a "$LOG"
    echo "    link through the floor/table, or the sensor mount is not landing at the" | tee -a "$LOG"
    echo "    intended (0.65 m, +X-forward) pose within tolerance. Re-examine the table" | tee -a "$LOG"
    echo "    position, SENSOR_X_START_M, or the SEED_POSES_RAD warm-start seed before" | tee -a "$LOG"
    echo "    re-running -- do not just re-run and hope." | tee -a "$LOG"
    echo "Report this back to the lead agent before writing any more D1.5 code." | tee -a "$LOG"
    exit 1
fi
echo "probe r=$PROBE_R >= $PROBE_R_MIN and violations=0 -- arm-carried sensor motion validated, proceeding." | tee -a "$LOG"
echo | tee -a "$LOG"

# ── 2. closed / blind / open (paired: same --seed => same target positions) ──
for mode in closed blind open; do
    run_or_skip "mode=$mode" \
        "$BASE_OUT/$mode/episodes.csv" \
        --mode "$mode" --output-dir "$BASE_OUT" \
        --n-episodes "$N_EPISODES" --seed "$SEED" \
        --standoff "$STANDOFF" --step "$STEP" --max-steps "$MAX_STEPS" \
        --sensor-offset "$SENSOR_OFFSET"
done

# ── 3. offline analysis + adjudication ────────────────────────────────────────
echo | tee -a "$LOG"
if [ -f "$BASE_OUT/d15_summary.json" ]; then
    echo "[SKIP] analysis (found $BASE_OUT/d15_summary.json)" | tee -a "$LOG"
else
    echo "[RUN]  analysis" | tee -a "$LOG"
    python3 "$ANALYZER" --scan-dir "$BASE_OUT" | tee -a "$LOG"
fi

echo | tee -a "$LOG"
echo "=== V2 D1.5 arm-carried approach sweep complete — $(date) ===" | tee -a "$LOG"
