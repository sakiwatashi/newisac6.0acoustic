#!/usr/bin/env bash
# Episode-level eval for D4 Track B PPO checkpoint.
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-${HOST_ROOT}/IsaacLab}"
LAB_DIR="${HOST_ROOT}/lab"

CKPT="${CHECKPOINT:-${HOST_ROOT}/runtime/outputs/v2_d4_ppo_grasp_rl_tune/rsl_rl_logs/model_99.pt}"
EPISODES="${EPISODES:-30}"
SEED="${SEED:-20260717}"
OUT="${OUT:-}"
EXTRA=()
if [ -n "${OUT}" ]; then
  if [[ "${OUT}" != /* ]]; then OUT="${HOST_ROOT}/${OUT}"; fi
  EXTRA+=(--output-dir "${OUT}")
fi
if [ "${STOCHASTIC:-0}" = "1" ]; then
  EXTRA+=(--stochastic)
fi
if [ "${ACOUSTIC_ONLY:-0}" = "1" ]; then
  EXTRA+=(--acoustic-only-obs)
fi
if [ "${BLIND:-0}" = "1" ]; then
  EXTRA+=(--blind-acoustic)
fi

# shellcheck source=/dev/null
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

export PYTHONPATH="${LAB_DIR}:${HOST_ROOT}/scripts:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"

mkdir -p "${HOST_ROOT}/runtime/locks" "${HOST_ROOT}/logs"
LOCK_FILE="${HOST_ROOT}/runtime/locks/lab_rl_acoustic_grasp_eval.lock"
if [[ -f "${LOCK_FILE}" ]]; then
  stale_pid="$(cat "${LOCK_FILE}" 2>/dev/null || true)"
  if [[ -n "${stale_pid}" ]] && kill -0 "${stale_pid}" 2>/dev/null; then
    echo "Eval lock held by pid=${stale_pid}" >&2
    exit 1
  fi
fi

echo "=== D4-B PPO episode eval $(date -Is) ==="
echo "  Checkpoint: ${CKPT}"
echo "  Episodes:   ${EPISODES}"
echo "  Seed:       ${SEED}"

cd "${ISAACLAB_ROOT}"
echo $$ > "${LOCK_FILE}"
trap 'rm -f "${LOCK_FILE}"' EXIT

./isaaclab.sh -p "${LAB_DIR}/eval_rl_acoustic_grasp.py" \
  --headless \
  --experience "${SIM_EXPERIENCE}" \
  --checkpoint "${CKPT}" \
  --episodes "${EPISODES}" \
  --seed "${SEED}" \
  "${EXTRA[@]}"
