#!/usr/bin/env bash
# GUI twin of run_v2_d2v2_formal.sh — d2v2_formal_runner.py unchanged.
#
# Default smoke: closed + --smoke. Full three-arm n=30:
#   FORMAL=1 bash runtime/run_v2_d2v2_formal_gui.sh
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ISAACSIM="$ROOT/app/python.sh"
EXEC="$ROOT/scripts/gui_formal_exec.py"
SCRIPT="$ROOT/scripts/d2v2_formal_runner.py"
BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_d2v2_formal_gui}"
FORMAL="${FORMAL:-0}"
mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"
echo "=== V2 D2v2 formal GUI $(date -Is) formal=$FORMAL ===" | tee -a "$LOG"

run_gui() {
  echo "[RUN GUI] $*" | tee -a "$LOG"
  bash "$ISAACSIM" "$EXEC" "$SCRIPT" "$@" 2>&1 | tee -a "$LOG"
}

if [ "$FORMAL" = "1" ]; then
  for ARM in closed blind open; do
    if [ -f "$BASE_OUT/$ARM/episodes.csv" ]; then
      echo "--- $ARM skip ---" | tee -a "$LOG"
      continue
    fi
    run_gui --arm "$ARM" --output-dir "$BASE_OUT"
  done
  python3 "$ROOT/scripts/analyze_d2v2.py" --scan-dir "$BASE_OUT" 2>&1 | tee -a "$LOG"
else
  ARM="${ARM:-closed}"
  run_gui --arm "$ARM" --output-dir "$BASE_OUT" --smoke
  echo "Smoke done (arm=$ARM). Full: FORMAL=1 bash $0" | tee -a "$LOG"
fi
echo "=== D2 GUI complete $(date -Is) ===" | tee -a "$LOG"
