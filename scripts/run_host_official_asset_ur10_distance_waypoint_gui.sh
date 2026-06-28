#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_distance_waypoint_acoustic_gui}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_distance_waypoint_acoustic_gui.usda}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-600}"
PLANNER_SAMPLES="${PLANNER_SAMPLES:-480}"
SAMPLES_PER_SEGMENT="${SAMPLES_PER_SEGMENT:-24}"

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_distance_waypoint_acoustic_capture.py" \
  --overwrite \
  --gui \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --fixed-target-position 1.6 0.16 0.05 \
  --distance-waypoints 0.3 0.5 1.0 1.5 2.0 2.5 3.0 \
  --planner-samples "${PLANNER_SAMPLES}" \
  --samples-per-segment "${SAMPLES_PER_SEGMENT}" \
  --settle-steps 40 \
  --planner-settle-steps 5 \
  --substeps-per-sample 2 \
  --min-samples 80 \
  --keep-open-seconds "${KEEP_OPEN_SECONDS}"
