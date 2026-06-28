#!/usr/bin/env bash
# PyRoom Experiment 4 batch aligned to Geometry Passport v1.0 (no repo edit required).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SONG_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYROOM_PYTHON="${PYROOM_PYTHON:-${SONG_ROOT}/venvs/isaac_acoustic_pyroom/bin/python}"
RESEARCH_ROOT="${RESEARCH_ROOT:-${SONG_ROOT}/isaac_acoustic_research}"
AI_PYROOMACOUSTICS_ROOT="${AI_PYROOMACOUSTICS_ROOT:-/home/lab109/下載/ai-pyroomacoustics-main}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${SCRIPT_DIR}/../runtime/outputs/experiment_4_pra_reference_passport_v1}"
MATERIAL_CONDITION="${MATERIAL_CONDITION:-B}"

case "${MATERIAL_CONDITION}" in
  A) ABSORPTION_VALUE=0.10; ABSORPTION_LABEL=low_absorption ;;
  B) ABSORPTION_VALUE=0.35; ABSORPTION_LABEL=medium_absorption ;;
  C) ABSORPTION_VALUE=0.70; ABSORPTION_LABEL=high_absorption ;;
  *) echo "Unknown MATERIAL_CONDITION=${MATERIAL_CONDITION} (expected A, B, or C)" >&2; exit 1 ;;
esac

exec "${PYROOM_PYTHON}" "${RESEARCH_ROOT}/scripts/experiment_4_pra_reference.py" \
  --output-root "${OUTPUT_ROOT}" \
  --external-root "${AI_PYROOMACOUSTICS_ROOT}" \
  --geometry-policy "formal_ur10_fixed_tcp_reference_cond_${MATERIAL_CONDITION}" \
  --room-dim 4.5 3.0 2.8 \
  --mic-position 0.8 0.16 0.65 \
  --distances 0.5 1.0 1.5 2.0 2.5 3.0 \
  --absorption-label "${ABSORPTION_LABEL}" \
  --absorption-value "${ABSORPTION_VALUE}"