#!/usr/bin/env bash
# V2 S2 datasheet sweep (docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 6, "S2: datasheet").
#
# Runs scripts/s2_datasheet_runner.py over the three S2 sweeps (distance,
# lateral, repeat) and then scripts/analyze_s2_datasheet.py to adjudicate
# the pre-registered criteria below.
#
# Pre-registered criteria (rule 4-3: written here BEFORE this script is ever
# run against real data; the analyzer computes these, this shell script only
# invokes it):
#
#   distance_r_ge_0.95      : Pearson r(peak_idx, true_distance_3d_m), over
#                             the combined p1-p3 distance passes (rows with
#                             stationarity_ok == False excluded), >= 0.95.
#   lateral_monotonic_ge_0.9: |Spearman rho(balance, y_offset_m)| >= 0.9 over
#                             the 13-point lateral sweep.
#   repeat_cv_lt_5pct       : CV(early_energy) = std/mean over the 10 repeat
#                             trials of the same point < 0.05 (5%).
#
# The distance_tableh pass (--target-height table) and its r value are
# INFORMATIONAL ONLY (printed as "INFO table_height_r", not adjudicated).
#
# Sequence:
#   1. distance x3  --pass-id p1/p2/p3          (boresight height, default)
#   2. distance x1  --pass-id tableh --target-height table
#   3. lateral  x1
#   4. repeat   x10 --pass-id r01..r10
#   5. scripts/analyze_s2_datasheet.py --scan-dir "$BASE_OUT"
#
# Resumable: each step is SKIPPED if its expected result file already exists
# under BASE_OUT, so a partially-completed run (e.g. GPU budget cut short)
# can be re-invoked and will only run the remaining steps.
#
# Usage: bash runtime/run_v2_s2_datasheet.sh

set -e

ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/s2_datasheet_runner.py
ANALYZER=/home/lab109/song/isaacsim6.0/scripts/analyze_s2_datasheet.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/v2_s2_datasheet

mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"

echo "=== V2 S2 datasheet sweep — $(date) ===" | tee -a "$LOG"
echo "BASE_OUT=$BASE_OUT" | tee -a "$LOG"
echo "pre-registered criteria: distance_r_ge_0.95, lateral_monotonic_ge_0.9, repeat_cv_lt_5pct" | tee -a "$LOG"
echo "reference: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 6, S2" | tee -a "$LOG"
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

# ── 1. distance x3 (boresight height) ─────────────────────────────────────────
for pid in p1 p2 p3; do
    run_or_skip "distance pass-id=$pid" \
        "$BASE_OUT/distance_$pid/points.csv" \
        --mode distance --pass-id "$pid" --output-dir "$BASE_OUT" \
        --n-settle 40 --n-measure 12
done

# ── 2. distance x1, target on table top (informational) ──────────────────────
run_or_skip "distance pass-id=tableh (target-height=table)" \
    "$BASE_OUT/distance_tableh/points.csv" \
    --mode distance --pass-id tableh --target-height table --output-dir "$BASE_OUT" \
    --n-settle 40 --n-measure 12

# ── 3. lateral x1 ──────────────────────────────────────────────────────────────
run_or_skip "lateral" \
    "$BASE_OUT/lateral/points.csv" \
    --mode lateral --output-dir "$BASE_OUT" \
    --n-settle 40 --n-measure 12

# ── 4. repeat x10 ──────────────────────────────────────────────────────────────
for i in $(seq -w 1 10); do
    pid="r$i"
    run_or_skip "repeat pass-id=$pid" \
        "$BASE_OUT/repeat_$pid/point.json" \
        --mode repeat --pass-id "$pid" --output-dir "$BASE_OUT" \
        --n-settle 40 --n-measure 12
done

# ── 5. offline analysis + adjudication ────────────────────────────────────────
echo | tee -a "$LOG"
if [ -f "$BASE_OUT/datasheet_summary.json" ]; then
    echo "[SKIP] analysis (found $BASE_OUT/datasheet_summary.json)" | tee -a "$LOG"
else
    echo "[RUN]  analysis" | tee -a "$LOG"
    python3 "$ANALYZER" --scan-dir "$BASE_OUT" | tee -a "$LOG"
fi

echo | tee -a "$LOG"
echo "=== V2 S2 datasheet sweep complete — $(date) ===" | tee -a "$LOG"
