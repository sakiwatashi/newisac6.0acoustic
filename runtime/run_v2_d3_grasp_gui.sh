#!/usr/bin/env bash
# GUI twin of run_v2_d3_grasp.sh — d3_grasp_runner.py unchanged.
#
# Default smoke: closed arm, --smoke (1 ep). Full formal g3 + three arms:
#   FORMAL=1 bash runtime/run_v2_d3_grasp_gui.sh
#   MODE=blind N_EPISODES=3 bash runtime/run_v2_d3_grasp_gui.sh
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ISAACSIM="$ROOT/app/python.sh"
EXEC="$ROOT/scripts/gui_formal_exec.py"
SCRIPT="$ROOT/scripts/d3_grasp_runner.py"
BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_d3_grasp_gui}"
FORMAL="${FORMAL:-0}"
MODE="${MODE:-closed}"
mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"
echo "=== V2 D3 grasp GUI $(date -Is) formal=$FORMAL ===" | tee -a "$LOG"
echo "BASE_OUT=$BASE_OUT (canonical r3 / headless formal dirs untouched)" | tee -a "$LOG"

run_gui() {
  echo "[RUN GUI] $*" | tee -a "$LOG"
  bash "$ISAACSIM" "$EXEC" "$SCRIPT" "$@" 2>&1 | tee -a "$LOG"
}

if [ "$FORMAL" = "1" ]; then
  if [ "${SKIP_G3:-0}" != "1" ]; then
    run_gui --mode g3 --output-dir "$BASE_OUT"
  fi
  for ARM in closed blind open; do
    if [ -f "$BASE_OUT/$ARM/episodes.csv" ]; then
      echo "--- $ARM skip ---" | tee -a "$LOG"
      continue
    fi
    run_gui --mode "$ARM" --output-dir "$BASE_OUT"
  done
  if [ -f "$ROOT/scripts/analyze_d3_grasp.py" ]; then
    python3 "$ROOT/scripts/analyze_d3_grasp.py" --scan-dir "$BASE_OUT" 2>&1 | tee -a "$LOG" || true
  fi
else
  EXTRA=(--mode "$MODE" --output-dir "$BASE_OUT" --smoke)
  if [ -n "${N_EPISODES:-}" ]; then
    EXTRA+=(--n-episodes "$N_EPISODES")
  fi
  run_gui "${EXTRA[@]}"
  echo "Smoke done (mode=$MODE). Full: FORMAL=1 bash $0" | tee -a "$LOG"
fi
echo "=== D3 grasp GUI complete $(date -Is) ===" | tee -a "$LOG"
