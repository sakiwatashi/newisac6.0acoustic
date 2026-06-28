#!/usr/bin/env bash
# Formal repeatability batch: 6 distances x N repeats (fresh process per run).
# All outputs under isaacsim6.0/runtime/outputs/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BATCH_ID="${BATCH_ID:-fixed_tcp_repeatability_v1}"
MATERIAL_CONDITION="${MATERIAL_CONDITION:-B}"
DISTANCES="${DISTANCES:-0.5 1.0 1.5 2.0 2.5 3.0}"
REPEAT_START="${REPEAT_START:-1}"
REPEAT_COUNT="${REPEAT_COUNT:-5}"
SAMPLES_PER_DISTANCE="${SAMPLES_PER_DISTANCE:-4}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ISAACSIM_ROOT}/runtime/outputs/${BATCH_ID}}"
SCENE_ROOT="${SCENE_ROOT:-${ISAACSIM_ROOT}/runtime/scenes/${BATCH_ID}}"

mkdir -p "${OUTPUT_ROOT}" "${SCENE_ROOT}"

echo "Batch: ${BATCH_ID}"
echo "Material condition: ${MATERIAL_CONDITION}"
echo "Distances: ${DISTANCES}"
echo "Repeats: ${REPEAT_START}..$((REPEAT_START + REPEAT_COUNT - 1))"
echo "Output root: ${OUTPUT_ROOT}"

pass_count=0
fail_count=0
total_count=0

for repeat_idx in $(seq "${REPEAT_START}" $((REPEAT_START + REPEAT_COUNT - 1))); do
  repeat_id="$(printf 'repeat_%03d' "${repeat_idx}")"
  for distance in ${DISTANCES}; do
    total_count=$((total_count + 1))
    distance_tag="${distance//./p}"
    run_dir="${OUTPUT_ROOT}/${repeat_id}/distance_${distance_tag}m"
    stage_path="${SCENE_ROOT}/${repeat_id}_distance_${distance_tag}m.usda"
    mkdir -p "${run_dir}"
    echo "--- run=${total_count} repeat=${repeat_id} distance=${distance}m ---"
    if "${SCRIPT_DIR}/run_host_python.sh" \
      "${SCRIPT_DIR}/official_asset_ur10_fixed_tcp_distance_sweep.py" \
      --overwrite \
      --output-dir "${run_dir}" \
      --output-stage "${stage_path}" \
      --single-distance "${distance}" \
      --repeat-id "${repeat_id}" \
      --material-condition "${MATERIAL_CONDITION}" \
      --samples-per-distance "${SAMPLES_PER_DISTANCE}" \
      --settle-steps 24 \
      --target-settle-steps 12 \
      --substeps-per-sample 1 \
      --min-samples 2 \
      --max-ee-motion-m 0.02 \
      --keep-open-seconds 0; then
      pass_count=$((pass_count + 1))
      echo "PASS repeat=${repeat_id} distance=${distance}m"
    else
      fail_count=$((fail_count + 1))
      echo "FAIL repeat=${repeat_id} distance=${distance}m"
    fi
  done
done

summary_file="${OUTPUT_ROOT}/batch_summary.txt"
{
  echo "batch_id=${BATCH_ID}"
  echo "material_condition=${MATERIAL_CONDITION}"
  echo "total_runs=${total_count}"
  echo "pass=${pass_count}"
  echo "fail=${fail_count}"
  echo "output_root=${OUTPUT_ROOT}"
} > "${summary_file}"

echo "Batch complete: pass=${pass_count} fail=${fail_count} total=${total_count}"
echo "Wrote ${summary_file}"

if [[ "${fail_count}" -gt 0 ]]; then
  exit 1
fi