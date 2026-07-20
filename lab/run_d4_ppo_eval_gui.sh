#!/usr/bin/env bash
# GUI twin of lab/run_d4_ppo_eval.sh — eval_rl_acoustic_grasp.py logic unchanged.
# Forces AppLauncher headless=False via gui_formal_exec transform (no --headless).
#
#   bash lab/run_d4_ppo_eval_gui.sh
#   EPISODES=5 bash lab/run_d4_ppo_eval_gui.sh
#   CHECKPOINT=path/to/model_49.pt bash lab/run_d4_ppo_eval_gui.sh
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
OUT="${OUT:-${HOST_ROOT}/runtime/outputs/v2_d4_ppo_eval_gui}"
EXTRA=()
if [ -n "${OUT}" ]; then
  if [[ "${OUT}" != /* ]]; then OUT="${HOST_ROOT}/${OUT}"; fi
  EXTRA+=(--output-dir "${OUT}")
fi
if [ "${STOCHASTIC:-0}" = "1" ]; then EXTRA+=(--stochastic); fi
if [ "${ACOUSTIC_ONLY:-0}" = "1" ]; then EXTRA+=(--acoustic-only-obs); fi
if [ "${BLIND:-0}" = "1" ]; then EXTRA+=(--blind-acoustic); fi

# shellcheck source=/dev/null
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

export PYTHONPATH="${LAB_DIR}:${HOST_ROOT}/scripts:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"

mkdir -p "${HOST_ROOT}/runtime/locks" "${OUT}"
LOCK_FILE="${HOST_ROOT}/runtime/locks/lab_rl_acoustic_grasp_eval_gui.lock"
if [[ -f "${LOCK_FILE}" ]]; then
  stale_pid="$(cat "${LOCK_FILE}" 2>/dev/null || true)"
  if [[ -n "${stale_pid}" ]] && kill -0 "${stale_pid}" 2>/dev/null; then
    echo "Eval GUI lock held by pid=${stale_pid}" >&2
    exit 1
  fi
fi

echo "=== D4-B PPO episode eval GUI $(date -Is) ==="
echo "  Checkpoint: ${CKPT}"
echo "  Episodes:   ${EPISODES}"
echo "  Seed:       ${SEED}"
echo "  Output:     ${OUT}"
echo "  (headless formal: lab/run_d4_ppo_eval.sh — unchanged)"

cd "${ISAACLAB_ROOT}"
echo $$ > "${LOCK_FILE}"
trap 'rm -f "${LOCK_FILE}"' EXIT

# Route through gui_formal_exec so set_defaults(headless=True) flips to False.
# Do NOT pass --headless.
./isaaclab.sh -p "${EXEC}" "${LAB_DIR}/eval_rl_acoustic_grasp.py" \
  --experience "${SIM_EXPERIENCE}" \
  --checkpoint "${CKPT}" \
  --episodes "${EPISODES}" \
  --seed "${SEED}" \
  "${EXTRA[@]}"
