#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_motion_acoustic}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_motion_acoustic.usda}"
SETTLE_STEPS="${SETTLE_STEPS:-80}"
CAPTURE_FRAMES="${CAPTURE_FRAMES:-80}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-600}"

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_motion_acoustic_capture.py" \
  --overwrite \
  --gui \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --settle-steps "${SETTLE_STEPS}" \
  --capture-frames "${CAPTURE_FRAMES}" \
  --keep-open-seconds "${KEEP_OPEN_SECONDS}"
