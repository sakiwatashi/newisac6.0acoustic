#!/usr/bin/env bash
# V2 D3.0 pre-registered gate sweep: g1 (bar detectable) / g2 (bar ranging) /
# m3b_target / m3b_sensor (mover-effect A/B).
#
# Runs scripts/d3_gates_runner.py in its four modes, IN ORDER, each in its
# own GPU session. This shell script does NOT adjudicate anything -- per
# docs/plan_v2/d3/plan.md 步 1.5 ("判準只寫不算"), the pre-registered
# criteria (g1_object_detectable, g2_object_ranging, m3b_mover_effect_null)
# are computed offline by the main agent (plan.md 步 2), never here and
# never inside d3_gates_runner.py itself.
#
# Sequence: g1 -> g2 -> m3b_target -> m3b_sensor. Each mode's log is teed to
# both its own per-mode log file and the combined run.log; if any mode exits
# non-zero, this script prints a diagnostic block and ABORTs (remaining
# modes do not run) -- resume by re-invoking this script (already-completed
# modes are skipped, see run_or_skip below).
#
# Usage:
#   bash runtime/run_v2_d3_gates.sh              # full (non-smoke) run, all 4 modes
#   bash runtime/run_v2_d3_gates.sh --smoke       # smoke run (reduced points/cells)

set -e

ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/d3_gates_runner.py

SMOKE_FLAG=""
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/v2_d3_gates
if [ "${1:-}" = "--smoke" ]; then
    SMOKE_FLAG="--smoke"
    BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/v2_d3_gates_smoke
fi

mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"

echo "=== V2 D3.0 gate sweep — $(date) ===" | tee -a "$LOG"
echo "BASE_OUT=$BASE_OUT  smoke=${SMOKE_FLAG:-no}" | tee -a "$LOG"
echo "pre-registered criteria: g1_object_detectable, g2_object_ranging, m3b_mover_effect_null" | tee -a "$LOG"
echo "reference: scripts/d3_gates_runner.py module docstring (full criteria text); adjudication happens offline (docs/plan_v2/d3/plan.md 步 2), NOT in this script." | tee -a "$LOG"
echo | tee -a "$LOG"

# run_mode <mode> <result-file-relative-to-mode-dir>
run_mode() {
    local mode="$1"
    local result_rel="$2"
    local mode_dir="$BASE_OUT/$mode"
    local mode_log="$mode_dir/stdout.log"
    local result_file="$mode_dir/$result_rel"

    if [ -f "$result_file" ] && [ -f "$mode_dir/meta.json" ]; then
        echo "[SKIP] mode=$mode (found $result_file)" | tee -a "$LOG"
        return 0
    fi

    mkdir -p "$mode_dir"
    echo "[RUN]  mode=$mode" | tee -a "$LOG"
    set +e
    "$ISAACSIM" "$SCRIPT" --mode "$mode" --output-dir "$BASE_OUT" $SMOKE_FLAG 2>&1 | tee "$mode_log" | tee -a "$LOG"
    local status=${PIPESTATUS[0]}
    set -e

    if [ "$status" -ne 0 ]; then
        echo | tee -a "$LOG"
        echo "ABORT: mode=$mode exited with status=$status." | tee -a "$LOG"
        echo "Diagnostic tail ($mode_log, last 40 lines):" | tee -a "$LOG"
        tail -n 40 "$mode_log" | tee -a "$LOG"
        echo | tee -a "$LOG"
        echo "Remaining modes will NOT run. Fix the failure above and re-invoke this" | tee -a "$LOG"
        echo "script -- already-completed modes (result file + meta.json present)" | tee -a "$LOG"
        echo "are skipped automatically." | tee -a "$LOG"
        exit 1
    fi

    if [ ! -f "$result_file" ]; then
        echo | tee -a "$LOG"
        echo "ABORT: mode=$mode exited 0 but expected result file is missing: $result_file" | tee -a "$LOG"
        echo "Diagnostic tail ($mode_log, last 40 lines):" | tee -a "$LOG"
        tail -n 40 "$mode_log" | tee -a "$LOG"
        exit 1
    fi
    echo "[OK]   mode=$mode -> $result_file" | tee -a "$LOG"
    echo | tee -a "$LOG"
}

run_mode "g1"         "gates_g1.json"
run_mode "g2"          "g2_points.csv"
run_mode "m3b_target"   "m3b_target_points.csv"
run_mode "m3b_sensor"   "m3b_sensor_points.csv"

echo | tee -a "$LOG"
echo "=== V2 D3.0 gate sweep complete — $(date) ===" | tee -a "$LOG"
echo "All 4 modes' raw outputs are under $BASE_OUT/<mode>/. Adjudication (plan.md 步 2) is a separate, offline, main-agent step -- this script performs NO pass/fail judgement." | tee -a "$LOG"
