#!/usr/bin/env bash
# V2 D1 1-DOF closed-loop approach (docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md
# Section 7, "D1: 1-DOF closed-loop approach", and the D1 spec draft at the
# end of docs/plan_v2/reports/S2_datasheet_report.md).
#
# Runs scripts/d1_approach_runner.py in its four modes (probe, closed, blind,
# open) and then scripts/analyze_d1_approach.py to adjudicate the
# pre-registered criteria below.
#
# Pre-registered criteria (rule 4-3: written here BEFORE this script is ever
# run against real data; the analyzer computes these, this shell script only
# invokes it and gates on the probe result):
#
#   d0_sensor_motion_valid : probe-mode live regression of peak_sample_idx vs
#                            true_distance_3d_m (sensor swept, target fixed)
#                            has r >= 0.99. Gates whether closed/blind/open
#                            even run (see ABORT branch below).
#   d1_tracking_r_ge_0.9   : r(stop_sensor_x, target_x) over the CLOSED arm's
#                            episodes >= 0.9.
#   d1_beats_blind         : closed arm's stop_error RMSE
#                            (|stop_oracle_horiz_dist - standoff|) is lower
#                            than blind's, AND a Welch two-sample t-test on
#                            the two arms' stop_error samples has p < 0.05.
#
# Sequence:
#   1. probe                                  (D0 sensor-motion validation)
#      -> grep PROBE_RESULT r=<r> from its log; r < 0.99 => ABORT, exit 1
#         (fallback: report back to the lead agent that sensor-mid-session
#         motion is NOT validated, and that D1 must be redesigned around
#         moving the whole rig instead of the sensor prim alone -- see
#         V2_HANDOFF_FOR_NEXT_AI.md Section 5.1's "single session single
#         cell" architecture note for why that was the earlier fallback).
#   2. closed, blind, open sessions           (each SKIP-if-exists, resumable)
#   3. scripts/analyze_d1_approach.py --scan-dir "$BASE_OUT" | tee -a run.log
#
# Resumable: each step is SKIPPED if its expected result file already exists
# under BASE_OUT, so a partially-completed run (e.g. GPU budget cut short)
# can be re-invoked and will only run the remaining steps.
#
# Usage: bash runtime/run_v2_d1_approach.sh

set -e

ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/d1_approach_runner.py
ANALYZER=/home/lab109/song/isaacsim6.0/scripts/analyze_d1_approach.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/v2_d1_approach

N_EPISODES=30
SEED=20260708
STANDOFF=0.35
STEP=0.05
MAX_STEPS=40
PROBE_R_MIN=0.99

mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"

echo "=== V2 D1 approach sweep — $(date) ===" | tee -a "$LOG"
echo "BASE_OUT=$BASE_OUT" | tee -a "$LOG"
echo "pre-registered criteria: d0_sensor_motion_valid, d1_tracking_r_ge_0.9, d1_beats_blind" | tee -a "$LOG"
echo "reference: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 7; docs/plan_v2/reports/S2_datasheet_report.md D1 draft" | tee -a "$LOG"
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

# ── 1. probe (D0 sensor-motion validation) ────────────────────────────────────
PROBE_LOG="$BASE_OUT/probe_stdout.log"
PROBE_RESULT_FILE="$BASE_OUT/probe/points.csv"
if [ -f "$PROBE_RESULT_FILE" ] && [ -f "$PROBE_LOG" ]; then
    echo "[SKIP] probe (found $PROBE_RESULT_FILE)" | tee -a "$LOG"
else
    echo "[RUN]  probe" | tee -a "$LOG"
    "$ISAACSIM" "$SCRIPT" --mode probe --output-dir "$BASE_OUT" 2>&1 | tee "$PROBE_LOG" | tee -a "$LOG"
fi

PROBE_LINE=$(grep -o 'PROBE_RESULT r=[^ ]* slope=[^ ]*' "$PROBE_LOG" | tail -n1 || true)
if [ -z "$PROBE_LINE" ]; then
    echo | tee -a "$LOG"
    echo "ABORT: no PROBE_RESULT line found in $PROBE_LOG -- probe run did not complete." | tee -a "$LOG"
    echo "Fallback: sensor-mid-session motion validity is UNKNOWN. Do not assume it works." | tee -a "$LOG"
    echo "Report back to the lead agent; consider the 'move the whole rig, not just the" | tee -a "$LOG"
    echo "sensor prim' fallback design (V2_HANDOFF_FOR_NEXT_AI.md Section 5.1)." | tee -a "$LOG"
    exit 1
fi
echo "$PROBE_LINE" | tee -a "$LOG"

PROBE_R=$(echo "$PROBE_LINE" | sed -n 's/.*PROBE_RESULT r=\([^ ]*\) slope=.*/\1/p')
PROBE_R_OK=$(python3 -c "
import math
try:
    r = float('$PROBE_R')
except ValueError:
    r = float('nan')
print('1' if (not math.isnan(r) and r >= $PROBE_R_MIN) else '0')
")

if [ "$PROBE_R_OK" != "1" ]; then
    echo | tee -a "$LOG"
    echo "ABORT: probe r=$PROBE_R < required $PROBE_R_MIN -- sensor mid-session motion is" | tee -a "$LOG"
    echo "NOT validated (D0 failed). closed/blind/open will NOT run." | tee -a "$LOG"
    echo "Fallback: redesign D1 around moving the whole rig (sensor+arm together) rather" | tee -a "$LOG"
    echo "than rewriting only the sensor prim's xformOp:translate mid-session; report this" | tee -a "$LOG"
    echo "back to the lead agent before writing any more D1 code." | tee -a "$LOG"
    exit 1
fi
echo "probe r=$PROBE_R >= $PROBE_R_MIN -- sensor mid-session motion validated, proceeding." | tee -a "$LOG"
echo | tee -a "$LOG"

# ── 2. closed / blind / open (paired: same --seed => same target positions) ──
for mode in closed blind open; do
    run_or_skip "mode=$mode" \
        "$BASE_OUT/$mode/episodes.csv" \
        --mode "$mode" --output-dir "$BASE_OUT" \
        --n-episodes "$N_EPISODES" --seed "$SEED" \
        --standoff "$STANDOFF" --step "$STEP" --max-steps "$MAX_STEPS"
done

# ── 3. offline analysis + adjudication ────────────────────────────────────────
echo | tee -a "$LOG"
if [ -f "$BASE_OUT/d1_summary.json" ]; then
    echo "[SKIP] analysis (found $BASE_OUT/d1_summary.json)" | tee -a "$LOG"
else
    echo "[RUN]  analysis" | tee -a "$LOG"
    python3 "$ANALYZER" --scan-dir "$BASE_OUT" | tee -a "$LOG"
fi

echo | tee -a "$LOG"
echo "=== V2 D1 approach sweep complete — $(date) ===" | tee -a "$LOG"
