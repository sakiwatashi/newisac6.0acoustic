#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_continuous_motion_acoustic_target_x1p6_gui}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_continuous_motion_acoustic_target_x1p6_gui.usda}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-600}"
STEPS="${STEPS:-160}"

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_continuous_motion_acoustic_capture.py" \
  --overwrite \
  --gui \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --fixed-target-position 1.6 0.16 0.05 \
  --start-joints -0.106522443 -1.15874359 1.48938424 -2.0414641 -1.10226154 0 \
  --end-joints 0.35472081 -2.32998337 0.519737004 -1.67143138 -1.39517211 0 \
  --steps "${STEPS}" \
  --settle-steps 40 \
  --substeps-per-sample 2 \
  --min-samples 80 \
  --keep-open-seconds "${KEEP_OPEN_SECONDS}"
