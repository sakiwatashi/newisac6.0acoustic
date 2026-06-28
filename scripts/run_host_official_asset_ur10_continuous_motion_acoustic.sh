#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_continuous_motion_acoustic}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_continuous_motion_acoustic.usda}"
START_POSE="${START_POSE:-reach_forward}"
END_POSE="${END_POSE:-reach_right}"
STEPS="${STEPS:-120}"
SETTLE_STEPS="${SETTLE_STEPS:-40}"
SUBSTEPS_PER_SAMPLE="${SUBSTEPS_PER_SAMPLE:-2}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-600}"

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_continuous_motion_acoustic_capture.py" \
  --overwrite \
  --gui \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --start-pose "${START_POSE}" \
  --end-pose "${END_POSE}" \
  --steps "${STEPS}" \
  --settle-steps "${SETTLE_STEPS}" \
  --substeps-per-sample "${SUBSTEPS_PER_SAMPLE}" \
  --keep-open-seconds "${KEEP_OPEN_SECONDS}"
