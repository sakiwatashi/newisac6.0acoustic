#!/usr/bin/env bash
# Open-loop dynamic approach calibration sweep (UR10e+Robotiq).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10e_dynamic_approach_calibration_v1}"
TRIAL_ID="${TRIAL_ID:-9}"
SPAWN_SEED="${SPAWN_SEED:-20260629}"
GUI="${GUI:-0}"

ARGS=(
  "${SCRIPT_DIR}/official_asset_ur10_dynamic_approach_calibration_sweep.py"
  --overwrite
  --output-dir "${OUTPUT_DIR}"
  --trial-id "${TRIAL_ID}"
  --spawn-seed "${SPAWN_SEED}"
)

if [[ "${GUI}" == "1" ]]; then
  ARGS+=(--gui)
fi

"${SCRIPT_DIR}/run_host_python.sh" "${ARGS[@]}"