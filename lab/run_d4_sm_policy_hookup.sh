#!/usr/bin/env bash
# D4 ④ — SM state machine + Track-B policy hookup eval.
# Default: acoustic_close_ft model_49 (8-D acoustic-only policy, true-scaffold train).
#
#   bash lab/run_d4_sm_policy_hookup.sh
#   EPISODES=5 bash lab/run_d4_sm_policy_hookup.sh   # smoke
#   BLIND=1 bash lab/run_d4_sm_policy_hookup.sh      # control
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-${HOST_ROOT}/IsaacLab}"
LAB_DIR="${HOST_ROOT}/lab"

CKPT="${CHECKPOINT:-${HOST_ROOT}/runtime/outputs/v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt}"
EPISODES="${EPISODES:-20}"
SEED="${SEED:-20260717}"
OUT="${OUT:-${HOST_ROOT}/runtime/outputs/v2_d4_sm_policy_hookup}"
if [[ "${OUT}" != /* ]]; then OUT="${HOST_ROOT}/${OUT}"; fi

EXTRA=()
if [ "${STOCHASTIC:-0}" = "1" ]; then EXTRA+=(--stochastic); fi
# Default acoustic-only (matches close_ft). SCAFFOLD=1 for 9-D.
if [ "${SCAFFOLD:-0}" != "1" ]; then
  EXTRA+=(--acoustic-only-obs)
fi
if [ "${BLIND:-0}" = "1" ]; then
  EXTRA+=(--blind-acoustic)
  OUT="${OUT}_blind"
fi

# shellcheck source=/dev/null
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

export PYTHONPATH="${LAB_DIR}:${HOST_ROOT}/scripts:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"

mkdir -p "${OUT}" "${HOST_ROOT}/runtime/locks" "${HOST_ROOT}/logs"
LOCK_FILE="${HOST_ROOT}/runtime/locks/lab_rl_acoustic_grasp_eval.lock"
if [[ -f "${LOCK_FILE}" ]]; then
  stale_pid="$(cat "${LOCK_FILE}" 2>/dev/null || true)"
  if [[ -n "${stale_pid}" ]] && kill -0 "${stale_pid}" 2>/dev/null; then
    echo "Eval lock held by pid=${stale_pid}" >&2
    exit 1
  fi
fi

echo "=== D4 ④ SM+policy hookup $(date -Is) ===" | tee "${OUT}/run.log"
echo "  Checkpoint: ${CKPT}" | tee -a "${OUT}/run.log"
echo "  Episodes:   ${EPISODES}" | tee -a "${OUT}/run.log"
echo "  Output:     ${OUT}" | tee -a "${OUT}/run.log"
echo "  Blind:      ${BLIND:-0}" | tee -a "${OUT}/run.log"

cd "${ISAACLAB_ROOT}"
echo $$ > "${LOCK_FILE}"
trap 'rm -f "${LOCK_FILE}"' EXIT

./isaaclab.sh -p "${LAB_DIR}/eval_sm_policy_hookup.py" \
  --headless \
  --experience "${SIM_EXPERIENCE}" \
  --checkpoint "${CKPT}" \
  --episodes "${EPISODES}" \
  --seed "${SEED}" \
  --output-dir "${OUT}" \
  "${EXTRA[@]}" \
  2>&1 | tee -a "${OUT}/run.log"

echo "Done. Summary: ${OUT}/sm_policy_hookup_summary.json" | tee -a "${OUT}/run.log"
