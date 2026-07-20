#!/usr/bin/env bash
# GUI twin of run_v2_d15_arm_approach.sh — d15_arm_approach_runner.py unchanged.
#
# Default smoke: closed, 2 episodes. Full formal:
#   FORMAL=1 bash runtime/run_v2_d15_arm_approach_gui.sh
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ISAACSIM="$ROOT/app/python.sh"
EXEC="$ROOT/scripts/gui_formal_exec.py"
SCRIPT="$ROOT/scripts/d15_arm_approach_runner.py"
BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_d15_arm_approach_gui}"
FORMAL="${FORMAL:-0}"
N_EPISODES="${N_EPISODES:-2}"
SEED="${SEED:-20260708}"
mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"
echo "=== V2 D1.5 arm approach GUI $(date -Is) formal=$FORMAL ===" | tee -a "$LOG"

run_gui() {
  echo "[RUN GUI] $*" | tee -a "$LOG"
  bash "$ISAACSIM" "$EXEC" "$SCRIPT" "$@" 2>&1 | tee -a "$LOG"
}

COMMON=(--output-dir "$BASE_OUT" --standoff 0.35 --step 0.05 --max-steps 40 --sensor-offset 0.25)

if [ "$FORMAL" = "1" ]; then
  N_EPISODES="${N_EPISODES_FORMAL:-30}"
  if [ ! -f "$BASE_OUT/probe/points.csv" ]; then
    run_gui --mode probe "${COMMON[@]}"
  fi
  for mode in closed blind open; do
    if [ -f "$BASE_OUT/$mode/episodes.csv" ]; then
      echo "[SKIP] $mode" | tee -a "$LOG"
      continue
    fi
    run_gui --mode "$mode" "${COMMON[@]}" \
      --n-episodes "$N_EPISODES" --seed "$SEED"
  done
  python3 "$ROOT/scripts/analyze_d15_arm_approach.py" --scan-dir "$BASE_OUT" 2>&1 | tee -a "$LOG"
else
  MODE="${MODE:-closed}"
  run_gui --mode "$MODE" "${COMMON[@]}" \
    --n-episodes "$N_EPISODES" --seed "$SEED"
  echo "Smoke done. Full: FORMAL=1 bash $0" | tee -a "$LOG"
fi
echo "=== D1.5 GUI complete $(date -Is) ===" | tee -a "$LOG"
