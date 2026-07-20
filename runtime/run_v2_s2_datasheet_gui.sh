#!/usr/bin/env bash
# GUI twin of run_v2_s2_datasheet.sh — s2_datasheet_runner.py unchanged.
#
# Default smoke: one distance pass (p1). Full formal sequence:
#   FORMAL=1 bash runtime/run_v2_s2_datasheet_gui.sh
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ISAACSIM="$ROOT/app/python.sh"
EXEC="$ROOT/scripts/gui_formal_exec.py"
SCRIPT="$ROOT/scripts/s2_datasheet_runner.py"
BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_s2_datasheet_gui}"
FORMAL="${FORMAL:-0}"
mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"
echo "=== V2 S2 datasheet GUI $(date -Is) formal=$FORMAL ===" | tee -a "$LOG"

run_or_skip() {
  local label="$1" result_file="$2"
  shift 2
  if [ -f "$result_file" ]; then
    echo "[SKIP] $label" | tee -a "$LOG"
    return 0
  fi
  echo "[RUN GUI] $label" | tee -a "$LOG"
  bash "$ISAACSIM" "$EXEC" "$SCRIPT" "$@" 2>&1 | tee -a "$LOG"
}

if [ "$FORMAL" = "1" ]; then
  for pid in p1 p2 p3; do
    run_or_skip "distance pass-id=$pid" \
      "$BASE_OUT/distance_$pid/points.csv" \
      --mode distance --pass-id "$pid" --output-dir "$BASE_OUT" \
      --n-settle 40 --n-measure 12
  done
  run_or_skip "distance tableh" \
    "$BASE_OUT/distance_tableh/points.csv" \
    --mode distance --pass-id tableh --target-height table --output-dir "$BASE_OUT" \
    --n-settle 40 --n-measure 12
  run_or_skip "lateral" \
    "$BASE_OUT/lateral/points.csv" \
    --mode lateral --output-dir "$BASE_OUT" --n-settle 40 --n-measure 12
  for i in $(seq -w 1 10); do
    pid="r${i}"
    run_or_skip "repeat $pid" \
      "$BASE_OUT/repeat_$pid/points.csv" \
      --mode repeat --pass-id "$pid" --output-dir "$BASE_OUT" \
      --n-settle 40 --n-measure 12
  done
  python3 "$ROOT/scripts/analyze_s2_datasheet.py" --scan-dir "$BASE_OUT" 2>&1 | tee -a "$LOG"
else
  run_or_skip "distance pass-id=p1 (smoke)" \
    "$BASE_OUT/distance_p1/points.csv" \
    --mode distance --pass-id p1 --output-dir "$BASE_OUT" \
    --n-settle 40 --n-measure 12
  echo "Smoke done. Full S2 GUI: FORMAL=1 bash runtime/run_v2_s2_datasheet_gui.sh" | tee -a "$LOG"
fi
echo "=== S2 GUI complete $(date -Is) ===" | tee -a "$LOG"
