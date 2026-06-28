#!/usr/bin/env bash
# Phase 3: extract fixed-TCP RTX features and compare trend-level features with PyRoom.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYROOM_PYTHON="${PYROOM_PYTHON:-/home/lab109/song/venvs/isaac_acoustic_pyroom/bin/python}"

RTX_TIMESERIES="${RTX_TIMESERIES:-${ISAACSIM_ROOT}/runtime/outputs/ur10_official_asset_fixed_tcp_distance_sweep_smoke/official_asset_ur10_fixed_tcp_distance_sweep_timeseries.csv}"
RTX_BATCH_ROOT="${RTX_BATCH_ROOT:-}"
MATERIAL_CONDITION="${MATERIAL_CONDITION:-B}"
PRA_OUTPUT_ROOT="${PRA_OUTPUT_ROOT:-${ISAACSIM_ROOT}/runtime/outputs/experiment_4_pra_reference_passport_v1_cond_${MATERIAL_CONDITION}}"
RTX_FEATURES_CSV="${RTX_FEATURES_CSV:-${ISAACSIM_ROOT}/runtime/outputs/phase3_rtx_features/fixed_tcp_rtx_distance_features_cond_${MATERIAL_CONDITION}.csv}"
COMPARISON_ROOT="${COMPARISON_ROOT:-${ISAACSIM_ROOT}/runtime/outputs/phase3_rtx_pra_comparison_cond_${MATERIAL_CONDITION}}"

echo "Phase 3 RTX x PRA comparison"
echo "  material_condition=${MATERIAL_CONDITION}"

MATERIAL_CONDITION="${MATERIAL_CONDITION}" OUTPUT_ROOT="${PRA_OUTPUT_ROOT}" \
  "${SCRIPT_DIR}/run_pyroom_experiment_4_passport_v1.sh"

EXTRACT_ARGS=(--output-csv "${RTX_FEATURES_CSV}")
if [[ -n "${RTX_BATCH_ROOT}" ]]; then
  EXTRACT_ARGS+=(--input-root "${RTX_BATCH_ROOT}")
else
  EXTRACT_ARGS+=(--timeseries "${RTX_TIMESERIES}")
fi
python3 "${SCRIPT_DIR}/extract_fixed_tcp_rtx_features.py" "${EXTRACT_ARGS[@]}"

"${PYROOM_PYTHON}" "${SCRIPT_DIR}/analyze_fixed_tcp_rtx_pra.py" \
  --rtx-features "${RTX_FEATURES_CSV}" \
  --pra-features "${PRA_OUTPUT_ROOT}/pra_reference_features.csv" \
  --output-root "${COMPARISON_ROOT}" \
  --material-condition "${MATERIAL_CONDITION}"

echo "Phase 3 complete: ${COMPARISON_ROOT}"