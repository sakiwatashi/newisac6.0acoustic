#!/usr/bin/env bash
# D4 Track B — short in-sim PPO smoke (acoustic approach + gripper).
# Pattern mirrors lab/run_rl_distance_in_sim.sh
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-${HOST_ROOT}/IsaacLab}"
LAB_DIR="${HOST_ROOT}/lab"
OUTPUT_DIR="${OUT:-${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/v2_d4_ppo_grasp_smoke}}"
# Resolve relative OUT against HOST_ROOT (not IsaacLab cwd)
if [[ "${OUTPUT_DIR}" != /* ]]; then
  OUTPUT_DIR="${HOST_ROOT}/${OUTPUT_DIR}"
fi
MAX_ITERATIONS="${ITERS:-${MAX_ITERATIONS:-5}}"
NUM_STEPS_PER_ENV="${STEPS:-${NUM_STEPS_PER_ENV:-16}}"
SAVE_INTERVAL="${SAVE:-${SAVE_INTERVAL:-5}}"
NUM_ENVS="${NUM_ENVS:-1}"
SEED="${SEED:-20260716}"
CHECKPOINT="${CHECKPOINT:-}"
RESUME_ITERATION="${RESUME_ITERATION:-0}"
# ACOUSTIC_ONLY=1 → policy obs without true_range (8-D); reward may still use true
ACOUSTIC_ONLY="${ACOUSTIC_ONLY:-0}"
# CLOSE_FT=1 → boost close/hold rewards (resume approach policy → learn close)
CLOSE_FT="${CLOSE_FT:-0}"
# PURE_REWARD=1 → no true_range in reward (d_hat-only shaping)
PURE_REWARD="${PURE_REWARD:-0}"
BLIND_EXTRA=()
if [ "${BLIND:-0}" = "1" ]; then
  BLIND_EXTRA+=(--blind-acoustic)
  OUTPUT_DIR="${OUTPUT_DIR}_blind"
fi
MODE_EXTRA=()
if [ "${ACOUSTIC_ONLY}" = "1" ]; then
  MODE_EXTRA+=(--acoustic-only-obs)
fi
if [ "${CLOSE_FT}" = "1" ]; then
  MODE_EXTRA+=(--close-finetune)
fi
if [ "${PURE_REWARD}" = "1" ]; then
  MODE_EXTRA+=(--no-true-reward)
fi
CKPT_EXTRA=()
if [ -n "${CHECKPOINT}" ]; then
  # Resolve relative checkpoint against HOST_ROOT
  if [[ "${CHECKPOINT}" != /* ]]; then
    CHECKPOINT="${HOST_ROOT}/${CHECKPOINT}"
  fi
  CKPT_EXTRA+=(--checkpoint "${CHECKPOINT}")
  if [ "${RESUME_ITERATION}" = "1" ]; then
    CKPT_EXTRA+=(--resume-iteration)
  fi
fi

# shellcheck source=/dev/null
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

mkdir -p "${OUTPUT_DIR}" "${HOST_ROOT}/logs" "${HOST_ROOT}/runtime/locks"
LOG_PATH="${OUTPUT_DIR}/run.log"
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"

export PYTHONPATH="${LAB_DIR}:${HOST_ROOT}/scripts:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

LOCK_FILE="${HOST_ROOT}/runtime/locks/lab_rl_acoustic_grasp.lock"
if [[ -f "${LOCK_FILE}" ]]; then
  stale_pid="$(cat "${LOCK_FILE}" 2>/dev/null || true)"
  if [[ -n "${stale_pid}" ]] && kill -0 "${stale_pid}" 2>/dev/null; then
    echo "Another D4-B train is active (pid=${stale_pid}). Stop it first: kill ${stale_pid}" >&2
    exit 1
  fi
fi

echo "=== D4 Track B PPO smoke $(date -Is) ===" | tee "${LOG_PATH}"
echo "  Output:     ${OUTPUT_DIR}" | tee -a "${LOG_PATH}"
echo "  Task:       Isaac-Ur10RtxAcousticGrasp-Direct-v0" | tee -a "${LOG_PATH}"
echo "  Iterations: ${MAX_ITERATIONS}" | tee -a "${LOG_PATH}"
echo "  Steps/env:  ${NUM_STEPS_PER_ENV}" | tee -a "${LOG_PATH}"
echo "  Blind:      ${BLIND:-0}" | tee -a "${LOG_PATH}"
echo "  AcousticOnlyObs: ${ACOUSTIC_ONLY}" | tee -a "${LOG_PATH}"
echo "  CloseFinetune:   ${CLOSE_FT}" | tee -a "${LOG_PATH}"
echo "  PureReward:      ${PURE_REWARD}" | tee -a "${LOG_PATH}"
echo "  Checkpoint: ${CHECKPOINT:-none}" | tee -a "${LOG_PATH}"

cd "${ISAACLAB_ROOT}"
echo $$ > "${LOCK_FILE}"
trap 'rm -f "${LOCK_FILE}"' EXIT

./isaaclab.sh -p "${LAB_DIR}/train_rl_acoustic_grasp.py" \
  --headless \
  --experience "${SIM_EXPERIENCE}" \
  --num-envs "${NUM_ENVS}" \
  --max-iterations "${MAX_ITERATIONS}" \
  --num-steps-per-env "${NUM_STEPS_PER_ENV}" \
  --save-interval "${SAVE_INTERVAL}" \
  --seed "${SEED}" \
  --output-dir "${OUTPUT_DIR}" \
  "${BLIND_EXTRA[@]}" \
  "${MODE_EXTRA[@]}" \
  "${CKPT_EXTRA[@]}" \
  2>&1 | tee -a "${LOG_PATH}"
train_status=${PIPESTATUS[0]}

if [[ "${train_status}" -ne 0 ]]; then
  echo "D4-B training failed (exit ${train_status}). See ${LOG_PATH}" >&2
  exit "${train_status}"
fi

echo "Done. Summary: ${OUTPUT_DIR}/train_summary.json" | tee -a "${LOG_PATH}"
