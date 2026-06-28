#!/usr/bin/env bash
# Headless checkpoint comparison for in-sim RSL-RL distance policy.
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-${HOST_ROOT}/IsaacLab}"
LAB_DIR="${HOST_ROOT}/lab"
OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/lab_rl_distance_in_sim_long_v3}"
STEPS="${STEPS:-64}"

# shellcheck source=/home/lab109/song/isaacsim6.0/scripts/env_host_isolated.sh
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

if [[ -z "${CHECKPOINTS:-}" ]]; then
  CHECKPOINTS=(
    "${OUTPUT_DIR}/model_100.pt"
    "${OUTPUT_DIR}/model_199.pt"
  )
fi

RESOLVED=()
for ckpt in "${CHECKPOINTS[@]}"; do
  if [[ "${ckpt}" != /* ]]; then
    ckpt="${HOST_ROOT}/${ckpt#./}"
  fi
  RESOLVED+=("$(realpath -e "${ckpt}")")
done

export PYTHONPATH="${LAB_DIR}:${HOST_ROOT}/scripts:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"

echo "Lab Phase 5 in-sim RSL-RL eval (headless)"
echo "  Checkpoints: ${RESOLVED[*]}"
echo "  Steps:       ${STEPS}"

cd "${ISAACLAB_ROOT}"
./isaaclab.sh -p "${LAB_DIR}/eval_rl_distance_in_sim.py" \
  --headless \
  --experience "${SIM_EXPERIENCE}" \
  --steps "${STEPS}" \
  --checkpoints "${RESOLVED[@]}"