#!/usr/bin/env bash
# Formal thesis GUI entry: Geometry Passport v1.0 fixed-TCP + moving-target sweep.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_fixed_tcp_distance_sweep_gui}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10_official_asset_fixed_tcp_distance_sweep_gui.usda}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-600}"
SAMPLES_PER_DISTANCE="${SAMPLES_PER_DISTANCE:-8}"
PRE_RUN_HOLD_SECONDS="${PRE_RUN_HOLD_SECONDS:-8}"
STEP_DELAY_SECONDS="${STEP_DELAY_SECONDS:-0.12}"
REPEAT_ID="${REPEAT_ID:-}"
MATERIAL_CONDITION="${MATERIAL_CONDITION:-B}"
TARGET_SCALE_X="${TARGET_SCALE_X:-0.08}"
TARGET_SCALE_Y="${TARGET_SCALE_Y:-0.08}"
TARGET_SCALE_Z="${TARGET_SCALE_Z:-0.02}"

ARGS=(
  --overwrite
  --gui
  --output-dir "${OUTPUT_DIR}"
  --output-stage "${OUTPUT_STAGE}"
  --distance-waypoints 0.5 1.0 1.5 2.0 2.5 3.0
  --samples-per-distance "${SAMPLES_PER_DISTANCE}"
  --pre-run-hold-seconds "${PRE_RUN_HOLD_SECONDS}"
  --step-delay-seconds "${STEP_DELAY_SECONDS}"
  --settle-steps 40
  --target-settle-steps 24
  --substeps-per-sample 2
  --min-samples 24
  --max-ee-motion-m 0.02
  --material-condition "${MATERIAL_CONDITION}"
  --target-scale "${TARGET_SCALE_X}" "${TARGET_SCALE_Y}" "${TARGET_SCALE_Z}"
  --keep-open-seconds "${KEEP_OPEN_SECONDS}"
)

if [[ -n "${REPEAT_ID}" ]]; then
  ARGS+=(--repeat-id "${REPEAT_ID}")
fi

"${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_fixed_tcp_distance_sweep.py" \
  "${ARGS[@]}"