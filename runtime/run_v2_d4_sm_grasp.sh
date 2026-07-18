#!/usr/bin/env bash
# D4 Track A: three-arm acoustic + grasp SM.
# Default weld-on-stall (D4-7; g0 friction-only failed). Does not touch r3.
#
#   bash runtime/run_v2_d4_sm_grasp.sh                 # full closed/blind/open + weld
#   bash runtime/run_v2_d4_sm_grasp.sh --smoke         # 1 ep per arm
#   bash runtime/run_v2_d4_sm_grasp.sh --no-weld       # friction probe column
#   bash runtime/run_v2_d4_sm_grasp.sh --analyze-only
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/runtime/outputs/v2_d4_sm_grasp}"
LOG="$OUT/run.log"
PY="$ROOT/app/python.sh"
SMOKE=0
NO_WELD=0
ANALYZE_ONLY=0
for a in "$@"; do
  case "$a" in
    --smoke) SMOKE=1 ;;
    --no-weld|--friction) NO_WELD=1 ;;
    --analyze-only) ANALYZE_ONLY=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done
mkdir -p "$OUT"
echo "=== run_v2_d4_sm_grasp $(date -Is) smoke=$SMOKE no_weld=$NO_WELD ===" | tee -a "$LOG"

EXTRA=()
if [ "$SMOKE" -eq 1 ]; then EXTRA+=(--smoke); fi
if [ "$NO_WELD" -eq 1 ]; then EXTRA+=(--no-weld-on-stall); else EXTRA+=(--weld-on-stall); fi

if [ "$ANALYZE_ONLY" -eq 0 ]; then
  for mode in closed blind open; do
    if [ -f "$OUT/$mode/episodes.csv" ] && [ "$SMOKE" -eq 0 ]; then
      echo "skip $mode (episodes.csv exists)" | tee -a "$LOG"
      continue
    fi
    echo "--- $mode ---" | tee -a "$LOG"
    python3 "$ROOT/scripts/d4_acoustic_grasp_sm_runner.py" \
      --mode "$mode" --output-dir "$OUT" --python "$PY" \
      "${EXTRA[@]}" 2>&1 | tee -a "$LOG"
    rc=${PIPESTATUS[0]}
    if [ "$rc" -ne 0 ]; then
      echo "ABORT mode=$mode rc=$rc" | tee -a "$LOG"
      exit "$rc"
    fi
  done
fi

echo "--- analyze ---" | tee -a "$LOG"
python3 "$ROOT/scripts/analyze_d4_sm_grasp.py" --scan-dir "$OUT" 2>&1 | tee -a "$LOG"
exit ${PIPESTATUS[0]}
