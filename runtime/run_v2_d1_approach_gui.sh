#!/usr/bin/env bash
# GUI twin of run_v2_d1_approach.sh — d1_approach_runner.py unchanged.
#
# Default smoke: closed arm, 2 episodes (skip probe gate for quick view).
# Full formal (probe + closed/blind/open n=30):
#   FORMAL=1 bash runtime/run_v2_d1_approach_gui.sh
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ISAACSIM="$ROOT/app/python.sh"
EXEC="$ROOT/scripts/gui_formal_exec.py"
SCRIPT="$ROOT/scripts/d1_approach_runner.py"
BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_d1_approach_gui}"
FORMAL="${FORMAL:-0}"
N_EPISODES="${N_EPISODES:-2}"
SEED="${SEED:-20260708}"
STANDOFF=0.35
STEP=0.05
MAX_STEPS=40
PROBE_R_MIN=0.99
mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"
echo "=== V2 D1 approach GUI $(date -Is) formal=$FORMAL ===" | tee -a "$LOG"

run_gui() {
  echo "[RUN GUI] $*" | tee -a "$LOG"
  bash "$ISAACSIM" "$EXEC" "$SCRIPT" "$@" 2>&1 | tee -a "$LOG"
}

if [ "$FORMAL" = "1" ]; then
  N_EPISODES="${N_EPISODES_FORMAL:-30}"
  PROBE_LOG="$BASE_OUT/probe_stdout.log"
  if [ ! -f "$BASE_OUT/probe/points.csv" ]; then
    run_gui --mode probe --output-dir "$BASE_OUT" | tee "$PROBE_LOG"
  fi
  for mode in closed blind open; do
    if [ -f "$BASE_OUT/$mode/episodes.csv" ]; then
      echo "[SKIP] $mode" | tee -a "$LOG"
      continue
    fi
    run_gui --mode "$mode" --output-dir "$BASE_OUT" \
      --n-episodes "$N_EPISODES" --seed "$SEED" \
      --standoff "$STANDOFF" --step "$STEP" --max-steps "$MAX_STEPS"
  done
  python3 "$ROOT/scripts/analyze_d1_approach.py" --scan-dir "$BASE_OUT" 2>&1 | tee -a "$LOG"
else
  MODE="${MODE:-closed}"
  run_gui --mode "$MODE" --output-dir "$BASE_OUT" \
    --n-episodes "$N_EPISODES" --seed "$SEED" \
    --standoff "$STANDOFF" --step "$STEP" --max-steps "$MAX_STEPS"
  echo "Smoke done (mode=$MODE n=$N_EPISODES). Full: FORMAL=1 bash $0" | tee -a "$LOG"
fi
echo "=== D1 GUI complete $(date -Is) ===" | tee -a "$LOG"
