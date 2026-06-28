#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_motion_probe}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_motion_probe.usda}"
SETTLE_STEPS="${SETTLE_STEPS:-80}"
RENDER_STEPS="${RENDER_STEPS:-20}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-600}"

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_motion_probe.py" \
  --overwrite \
  --gui \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --settle-steps "${SETTLE_STEPS}" \
  --render-steps "${RENDER_STEPS}" \
  --keep-open-seconds "${KEEP_OPEN_SECONDS}"
