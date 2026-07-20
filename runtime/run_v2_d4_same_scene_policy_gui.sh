#!/usr/bin/env bash
# GUI twin of run_v2_d4_same_scene_policy.sh — d3_grasp_runner + policy unchanged.
#
#   bash runtime/run_v2_d4_same_scene_policy_gui.sh           # smoke n=2
#   N_EP=5 bash runtime/run_v2_d4_same_scene_policy_gui.sh
#   FORMAL=1 bash runtime/run_v2_d4_same_scene_policy_gui.sh # n=90
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FORMAL="${FORMAL:-0}"
OUT="${OUT:-$ROOT/runtime/outputs/v2_d4_same_scene_policy_gui}"
CKPT="${CHECKPOINT:-$ROOT/runtime/outputs/v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt}"
N_EP="${N_EP:-2}"
SEED="${SEED:-20260718}"
PY="${PY:-$ROOT/app/python.sh}"
EXEC="$ROOT/scripts/gui_formal_exec.py"
if [ "$FORMAL" = "1" ]; then
  N_EP="${N_EP_FORMAL:-90}"
  OUT="${OUT_FORMAL:-$ROOT/runtime/outputs/v2_d4_same_scene_policy_gui_n90}"
fi
for a in "$@"; do
  case "$a" in
    --smoke) N_EP=2; OUT="${OUT}_smoke" ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done
case "$OUT" in
  *v2_d3_grasp_r3*|*v2_d4_sm_grasp_n30*)
    echo "ABORT: refuse canonical formal dirs: $OUT" >&2
    exit 2
    ;;
esac
mkdir -p "$OUT"
LOG="$OUT/run.log"
echo "=== D4 same-scene policy GUI $(date -Is) n=$N_EP ===" | tee "$LOG"
echo "  OUT=$OUT CKPT=$CKPT" | tee -a "$LOG"

if [ ! -f "$CKPT" ]; then
  echo "ABORT: checkpoint missing: $CKPT" | tee -a "$LOG"
  exit 1
fi

bash "$PY" "$EXEC" "$ROOT/scripts/d3_grasp_runner.py" \
  --mode closed \
  --output-dir "$OUT" \
  --n-episodes "$N_EP" \
  --seed "$SEED" \
  --standoff 0.35 \
  --step 0.05 \
  --max-steps "${MAX_STEPS:-60}" \
  --sensor-offset 0.25 \
  --target-x-min 1.00 \
  --target-x-max 1.15 \
  --weld-on-stall \
  --lift-up-step 0.002 \
  --policy-checkpoint "$CKPT" \
  --policy-max-step 0.05 \
  --policy-close-slack 0.10 \
  2>&1 | tee -a "$LOG"

rc=${PIPESTATUS[0]}
echo "=== runner exit $rc $(date -Is) ===" | tee -a "$LOG"
exit "$rc"
