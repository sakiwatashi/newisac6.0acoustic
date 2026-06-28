#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_target_placement_scan}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_target_placement_scan.usda}"
SAMPLES="${SAMPLES:-220}"
SETTLE_STEPS="${SETTLE_STEPS:-6}"
TARGET_X_VALUES="${TARGET_X_VALUES:-0.4 0.8 1.2 1.6 2.0 2.4 2.8}"

# shellcheck disable=SC2086
"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_target_placement_scan.py" \
  --overwrite \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --samples "${SAMPLES}" \
  --settle-steps "${SETTLE_STEPS}" \
  --target-x-values ${TARGET_X_VALUES}
