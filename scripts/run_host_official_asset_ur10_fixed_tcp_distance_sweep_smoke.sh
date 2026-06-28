#!/usr/bin/env bash
# Headless smoke for Geometry Passport v1.0 fixed-TCP distance sweep.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_fixed_tcp_distance_sweep_smoke}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_fixed_tcp_distance_sweep_smoke.usda}"
MATERIAL_CONDITION="${MATERIAL_CONDITION:-B}"

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_fixed_tcp_distance_sweep.py" \
  --overwrite \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --distance-waypoints 0.5 1.0 1.5 2.0 2.5 3.0 \
  --samples-per-distance 2 \
  --settle-steps 20 \
  --target-settle-steps 10 \
  --substeps-per-sample 1 \
  --min-samples 6 \
  --max-ee-motion-m 0.02 \
  --material-condition "${MATERIAL_CONDITION}" \
  --keep-open-seconds 0