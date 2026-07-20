#!/usr/bin/env bash
# GUI twin of run_v2_d4_sm_grasp.sh — headless SM runner + d3 formal unchanged.
# Uses scripts/d4_acoustic_grasp_sm_runner_gui.py → gui_formal_exec → d3_grasp_runner.
#
#   bash runtime/run_v2_d4_sm_grasp_gui.sh              # smoke closed
#   FORMAL=1 bash runtime/run_v2_d4_sm_grasp_gui.sh     # closed/blind/open full
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/runtime/outputs/v2_d4_sm_grasp_gui}"
LOG="$OUT/run.log"
FORMAL="${FORMAL:-0}"
SMOKE=1
NO_WELD=0
for a in "$@"; do
  case "$a" in
    --smoke) SMOKE=1 ;;
    --no-smoke) SMOKE=0 ;;
    --no-weld|--friction) NO_WELD=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done
if [ "$FORMAL" = "1" ]; then SMOKE=0; fi
mkdir -p "$OUT"
echo "=== run_v2_d4_sm_grasp_gui $(date -Is) formal=$FORMAL smoke=$SMOKE ===" | tee -a "$LOG"

EXTRA=()
if [ "$SMOKE" -eq 1 ]; then EXTRA+=(--smoke); fi
if [ "$NO_WELD" -eq 1 ]; then EXTRA+=(--no-weld-on-stall); else EXTRA+=(--weld-on-stall); fi

MODES=(closed)
if [ "$FORMAL" = "1" ]; then MODES=(closed blind open); fi

for mode in "${MODES[@]}"; do
  if [ -f "$OUT/$mode/episodes.csv" ] && [ "$SMOKE" -eq 0 ]; then
    echo "skip $mode" | tee -a "$LOG"
    continue
  fi
  echo "--- GUI $mode ---" | tee -a "$LOG"
  python3 "$ROOT/scripts/d4_acoustic_grasp_sm_runner_gui.py" \
    --mode "$mode" --output-dir "$OUT" \
    --python "$ROOT/app/python.sh" \
    "${EXTRA[@]}" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    echo "ABORT mode=$mode rc=$rc" | tee -a "$LOG"
    exit "$rc"
  fi
done

python3 "$ROOT/scripts/analyze_d4_sm_grasp.py" --scan-dir "$OUT" 2>&1 | tee -a "$LOG" || true
echo "=== D4 SM GUI complete $(date -Is) ===" | tee -a "$LOG"
