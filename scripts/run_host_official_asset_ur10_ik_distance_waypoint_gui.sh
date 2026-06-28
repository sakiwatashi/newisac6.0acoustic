#!/usr/bin/env bash
# DIAGNOSTIC ONLY — deprecated thesis motion path (moving arm to change distance).
# Formal experiment: run_host_official_asset_ur10_fixed_tcp_distance_sweep_gui.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_ik_distance_waypoint_acoustic_gui}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_ik_distance_waypoint_acoustic_gui.usda}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-600}"
SAMPLES_PER_SEGMENT="${SAMPLES_PER_SEGMENT:-12}"
PRE_RUN_HOLD_SECONDS="${PRE_RUN_HOLD_SECONDS:-8}"
STEP_DELAY_SECONDS="${STEP_DELAY_SECONDS:-0.08}"
IK_DENSE_STEP_M="${IK_DENSE_STEP_M:-0.20}"
IK_MIN_LINK_Z="${IK_MIN_LINK_Z:-0.0}"
IK_SWEEP_Z="${IK_SWEEP_Z:-0.65}"
TARGET_Z="${TARGET_Z:-0.65}"

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_ik_distance_waypoint_acoustic_capture.py" \
  --overwrite \
  --gui \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --fixed-target-position 1.6 0.16 "${TARGET_Z}" \
  --distance-waypoints 0.3 0.5 1.0 1.5 2.0 2.5 \
  --samples-per-segment "${SAMPLES_PER_SEGMENT}" \
  --pre-run-hold-seconds "${PRE_RUN_HOLD_SECONDS}" \
  --step-delay-seconds "${STEP_DELAY_SECONDS}" \
  --ik-orientation-mode world_x \
  --ik-sweep-z "${IK_SWEEP_Z}" \
  --ik-dense-step-m "${IK_DENSE_STEP_M}" \
  --ik-min-link-z "${IK_MIN_LINK_Z}" \
  --ik-orientation-tolerance 0.70 \
  --settle-steps 40 \
  --planner-settle-steps 5 \
  --substeps-per-sample 2 \
  --min-samples 80 \
  --keep-open-seconds "${KEEP_OPEN_SECONDS}"
