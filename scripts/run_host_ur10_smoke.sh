#!/usr/bin/env bash
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${ISAAC_ACOUSTIC_PROJECT:-/home/lab109/song/isaac_acoustic_research}"
SMOKE_SCRIPT="${SMOKE_SCRIPT:-${PROJECT}/scripts/official_rtx_acoustic_ur10_smoke.py}"

SCENE_MODE="${SCENE_MODE:-articulated}"
SOURCE_INPUT_SCENE="${INPUT_SCENE:-${PROJECT}/scenes/ur10_ee_articulated_debug/ur10_ee_articulated_debug_1m.usda}"
HOST_INPUT_SCENE="${HOST_INPUT_SCENE:-${HOST_ROOT}/runtime/scenes/ur10_ee_articulated_debug_1m_host.usda}"
INPUT_SCENE="${SOURCE_INPUT_SCENE}"
OUTPUT_DIR="${HOST_ROOT}/runtime/outputs/ur10_smoke"
OUTPUT_STAGE="${HOST_ROOT}/runtime/scenes/ur10_official_acoustic_smoke_host.usda"

mkdir -p "${OUTPUT_DIR}" "${HOST_ROOT}/runtime/scenes"

if [[ "${SCENE_MODE}" == "articulated" ]]; then
  perl -0pe "s#/workspace/isaac_acoustic_research#${PROJECT}#g" "${SOURCE_INPUT_SCENE}" > "${HOST_INPUT_SCENE}"
  INPUT_SCENE="${HOST_INPUT_SCENE}"
fi

exec "${SCRIPT_DIR}/run_host_python.sh" \
  "${SMOKE_SCRIPT}" \
  --scene-mode "${SCENE_MODE}" \
  --input-scene "${INPUT_SCENE}" \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --gui-use-timeline \
  "$@"