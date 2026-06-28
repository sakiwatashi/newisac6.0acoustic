#!/usr/bin/env bash
# Play trained in-sim RSL-RL checkpoint — GUI by default (omit --headless).
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-${HOST_ROOT}/IsaacLab}"
LAB_DIR="${HOST_ROOT}/lab"
OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/lab_rl_distance_in_sim_long_v3}"
STEPS="${STEPS:-128}"
REAL_TIME="${REAL_TIME:-1}"
HEADLESS="${HEADLESS:-0}"
STOCHASTIC="${STOCHASTIC:-0}"

# shellcheck source=/home/lab109/song/isaacsim6.0/scripts/env_host_isolated.sh
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

if [[ -z "${CHECKPOINT:-}" ]]; then
  CHECKPOINT="$(find "${OUTPUT_DIR}" -maxdepth 1 -name 'model_*.pt' 2>/dev/null | sort -V | tail -1 || true)"
fi
if [[ -n "${CHECKPOINT:-}" ]]; then
  if [[ "${CHECKPOINT}" != /* ]]; then
    CHECKPOINT="${HOST_ROOT}/${CHECKPOINT#./}"
  fi
  CHECKPOINT="$(realpath -e "${CHECKPOINT}")"
fi
if [[ -z "${CHECKPOINT}" || ! -f "${CHECKPOINT}" ]]; then
  echo "No checkpoint found. Set CHECKPOINT= or train first:" >&2
  echo "  MAX_ITERATIONS=30 bash lab/run_rl_distance_in_sim.sh" >&2
  exit 1
fi

export PYTHONPATH="${LAB_DIR}:${HOST_ROOT}/scripts:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"

HEADLESS_ARGS=()
if [[ "${HEADLESS}" == "1" ]]; then
  HEADLESS_ARGS=(--headless)
fi

REAL_TIME_ARGS=()
if [[ "${REAL_TIME}" == "1" ]]; then
  REAL_TIME_ARGS=(--real-time)
fi

STOCHASTIC_ARGS=()
if [[ "${STOCHASTIC}" == "1" ]]; then
  STOCHASTIC_ARGS=(--stochastic)
fi

echo "Lab Phase 5 in-sim RSL-RL play (viewport)"
echo "  Checkpoint: ${CHECKPOINT}"
echo "  Steps:      ${STEPS}"
echo "  Headless:   ${HEADLESS} (0 = Isaac Sim GUI)"
echo "  Real-time:  ${REAL_TIME}"
echo "  Stochastic: ${STOCHASTIC}"

cd "${ISAACLAB_ROOT}"
./isaaclab.sh -p "${LAB_DIR}/play_rl_distance_in_sim.py" \
  "${HEADLESS_ARGS[@]}" \
  --experience "${SIM_EXPERIENCE}" \
  --checkpoint "${CHECKPOINT}" \
  --steps "${STEPS}" \
  "${REAL_TIME_ARGS[@]}" \
  "${STOCHASTIC_ARGS[@]}"