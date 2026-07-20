#!/usr/bin/env bash
# GUI twin of lab/run_d4_sm_policy_hookup.sh — eval_sm_policy_hookup.py unchanged.
#
#   bash lab/run_d4_sm_policy_hookup_gui.sh
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-${HOST_ROOT}/IsaacLab}"
LAB_DIR="${HOST_ROOT}/lab"
EXEC="${HOST_ROOT}/scripts/gui_formal_exec.py"

CKPT="${CHECKPOINT:-${HOST_ROOT}/runtime/outputs/v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt}"
EPISODES="${EPISODES:-3}"
SEED="${SEED:-20260717}"
OUT="${OUT:-${HOST_ROOT}/runtime/outputs/v2_d4_sm_policy_hookup_gui}"

# shellcheck source=/dev/null
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

export PYTHONPATH="${LAB_DIR}:${HOST_ROOT}/scripts:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"

mkdir -p "${OUT}"
echo "=== D4 SM policy hookup GUI $(date -Is) ==="
echo "  Checkpoint: ${CKPT}"
echo "  Episodes:   ${EPISODES}"
echo "  Output:     ${OUT}"

cd "${ISAACLAB_ROOT}"
./isaaclab.sh -p "${EXEC}" "${LAB_DIR}/eval_sm_policy_hookup.py" \
  --experience "${SIM_EXPERIENCE}" \
  --checkpoint "${CKPT}" \
  --episodes "${EPISODES}" \
  --seed "${SEED}" \
  --output-dir "${OUT}"
