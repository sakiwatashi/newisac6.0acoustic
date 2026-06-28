#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_workspace_scan}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_workspace_scan.usda}"
SAMPLES="${SAMPLES:-160}"
SETTLE_STEPS="${SETTLE_STEPS:-8}"
SEED="${SEED:-109}"

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_workspace_scan.py" \
  --overwrite \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --samples "${SAMPLES}" \
  --settle-steps "${SETTLE_STEPS}" \
  --seed "${SEED}"
