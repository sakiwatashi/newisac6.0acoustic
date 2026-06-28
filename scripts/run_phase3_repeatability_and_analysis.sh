#!/usr/bin/env bash
# Phase 3: full repeatability batch (6x5) then RTX x PRA analysis on batch outputs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BATCH_ID="${BATCH_ID:-fixed_tcp_repeatability_v1}"
MATERIAL_CONDITION="${MATERIAL_CONDITION:-B}"
REPEAT_COUNT="${REPEAT_COUNT:-5}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ISAACSIM_ROOT}/runtime/outputs/${BATCH_ID}}"
RTX_FEATURES_CSV="${RTX_FEATURES_CSV:-${ISAACSIM_ROOT}/runtime/outputs/phase3_rtx_features/${BATCH_ID}_distance_features.csv}"
COMPARISON_ROOT="${COMPARISON_ROOT:-${ISAACSIM_ROOT}/runtime/outputs/phase3_rtx_pra_comparison_${BATCH_ID}}"

echo "Phase 3 repeatability + analysis"
echo "  batch_id=${BATCH_ID}"
echo "  repeat_count=${REPEAT_COUNT}"

BATCH_ID="${BATCH_ID}" MATERIAL_CONDITION="${MATERIAL_CONDITION}" REPEAT_COUNT="${REPEAT_COUNT}" OUTPUT_ROOT="${OUTPUT_ROOT}" \
  "${SCRIPT_DIR}/run_host_fixed_tcp_repeatability_batch.sh"

python3 "${SCRIPT_DIR}/extract_fixed_tcp_rtx_features.py" \
  --input-root "${OUTPUT_ROOT}" \
  --output-csv "${RTX_FEATURES_CSV}"

RTX_BATCH_ROOT="${OUTPUT_ROOT}" RTX_FEATURES_CSV="${RTX_FEATURES_CSV}" COMPARISON_ROOT="${COMPARISON_ROOT}" \
  MATERIAL_CONDITION="${MATERIAL_CONDITION}" \
  "${SCRIPT_DIR}/run_phase3_rtx_pra_comparison.sh"

echo "Phase 3 repeatability analysis complete"
echo "  features: ${RTX_FEATURES_CSV}"
echo "  comparison: ${COMPARISON_ROOT}"