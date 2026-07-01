#!/usr/bin/env bash
# Isolated Robotiq physics grasp pilot (no ultrasonic).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10e_robotiq_physics_grasp_pilot_v1}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10e_robotiq_physics_grasp_pilot_v1.usda}"
TRIAL_ID="${TRIAL_ID:-9}"
SPAWN_SEED="${SPAWN_SEED:-20260629}"
TOOL0_ABOVE_WRENCH_TOP_M="${TOOL0_ABOVE_WRENCH_TOP_M:-0.02}"
WRENCH_Y_SCALE_M="${WRENCH_Y_SCALE_M:-0.08}"
GUI="${GUI:-0}"
PRE_START_WAIT_SECONDS="${PRE_START_WAIT_SECONDS:-15}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-120}"

ARGS=(
  "${SCRIPT_DIR}/official_asset_ur10_robotiq_physics_grasp_pilot.py"
  --overwrite
  --output-dir "${OUTPUT_DIR}"
  --output-stage "${OUTPUT_STAGE}"
  --trial-id "${TRIAL_ID}"
  --spawn-seed "${SPAWN_SEED}"
  --tool0-above-wrench-top-m "${TOOL0_ABOVE_WRENCH_TOP_M}"
  --wrench-y-scale-m "${WRENCH_Y_SCALE_M}"
)

if [[ "${GUI}" == "1" ]]; then
  ARGS+=(
    --gui
    --keep-open-seconds "${KEEP_OPEN_SECONDS}"
    --gui-pre-start-wait-seconds "${PRE_START_WAIT_SECONDS}"
  )
fi

"${SCRIPT_DIR}/run_host_python.sh" "${ARGS[@]}"