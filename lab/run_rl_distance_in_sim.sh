#!/usr/bin/env bash
# Isaac Lab Phase 5 — in-sim RSL-RL PPO smoke (DirectRLEnv + RTX GMO).
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-${HOST_ROOT}/IsaacLab}"
LAB_DIR="${HOST_ROOT}/lab"
OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/lab_rl_distance_in_sim_v1}"
MAX_ITERATIONS="${MAX_ITERATIONS:-200}"
NUM_STEPS_PER_ENV="${NUM_STEPS_PER_ENV:-32}"
SAVE_INTERVAL="${SAVE_INTERVAL:-50}"
NUM_ENVS="${NUM_ENVS:-1}"
LOG_SUFFIX="${LOG_SUFFIX:-}"
PPO_VARIANT="${PPO_VARIANT:-v3}"
ENV_VARIANT="${ENV_VARIANT:-v3}"

# shellcheck source=/home/lab109/song/isaacsim6.0/scripts/env_host_isolated.sh
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

mkdir -p "${OUTPUT_DIR}" "${HOST_ROOT}/logs"
LOG_PATH="${HOST_ROOT}/logs/lab_rl_distance_in_sim_v1${LOG_SUFFIX}.log"
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"

export PYTHONPATH="${LAB_DIR}:${HOST_ROOT}/scripts:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

LOCK_FILE="${HOST_ROOT}/runtime/locks/lab_rl_distance_in_sim.lock"
mkdir -p "$(dirname "${LOCK_FILE}")"
if [[ -f "${LOCK_FILE}" ]]; then
  stale_pid="$(cat "${LOCK_FILE}" 2>/dev/null || true)"
  if [[ -n "${stale_pid}" ]] && kill -0 "${stale_pid}" 2>/dev/null; then
    echo "Another in-sim RL run is active (pid=${stale_pid}). Stop it first:" >&2
    echo "  kill ${stale_pid}" >&2
    exit 1
  fi
fi

echo "Lab Phase 5 in-sim RSL-RL smoke"
echo "  Isaac Lab:  ${ISAACLAB_ROOT}"
echo "  Output:     ${OUTPUT_DIR}"
echo "  Task:       Isaac-Ur10RtxAcousticDistance-Direct-v0"
echo "  Iterations:      ${MAX_ITERATIONS}"
echo "  Steps per env:   ${NUM_STEPS_PER_ENV}"
echo "  Save interval:   ${SAVE_INTERVAL}"
echo "  Num envs:        ${NUM_ENVS}"
echo "  PPO variant:     ${PPO_VARIANT}"
echo "  Env variant:     ${ENV_VARIANT}"

cd "${ISAACLAB_ROOT}"
echo $$ > "${LOCK_FILE}"
trap 'rm -f "${LOCK_FILE}"' EXIT

./isaaclab.sh -p "${LAB_DIR}/train_rl_distance_in_sim.py" \
  --headless \
  --experience "${SIM_EXPERIENCE}" \
  --num-envs "${NUM_ENVS}" \
  --max-iterations "${MAX_ITERATIONS}" \
  --num-steps-per-env "${NUM_STEPS_PER_ENV}" \
  --save-interval "${SAVE_INTERVAL}" \
  --output-dir "${OUTPUT_DIR}" \
  --ppo-variant "${PPO_VARIANT}" \
  --env-variant "${ENV_VARIANT}" \
  2>&1 | tee "${LOG_PATH}"
train_status=${PIPESTATUS[0]}

if [[ "${train_status}" -ne 0 ]]; then
  echo "In-sim RL training failed (exit ${train_status}). See ${LOG_PATH}" >&2
  exit "${train_status}"
fi

# Copy latest run logs to project output dir for thesis artifacts.
LATEST_RUN="$(find "${ISAACLAB_ROOT}/logs/rsl_rl/ur10_rtx_acoustic_distance_direct" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1 || true)"
if [[ -n "${LATEST_RUN}" ]]; then
  rsync -a --delete "${LATEST_RUN}/" "${OUTPUT_DIR}/"
  echo "Synced training logs to ${OUTPUT_DIR}"
fi

echo "Done. Log: ${LOG_PATH}"