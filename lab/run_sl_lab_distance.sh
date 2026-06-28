#!/usr/bin/env bash
# Supervised learning: RTX early_energy -> distance (Lab §4.6).
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB_CSV="${LAB_CSV:-${HOST_ROOT}/runtime/outputs/lab_dynamic_smoke_v1/lab_dynamic_obs_timeseries.csv}"
SIM_ROOT="${SIM_ROOT:-${HOST_ROOT}/runtime/outputs/fixed_tcp_repeatability_v1}"
OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/lab_sl_distance_v1}"
FEATURE_PRESET="${FEATURE_PRESET:-early_energy_only}"

python3 "${HOST_ROOT}/lab/train_sl_distance_regressor.py" \
  --lab-csv "${LAB_CSV}" \
  --sim-root "${SIM_ROOT}" \
  --output-dir "${OUTPUT_DIR}" \
  --feature-preset "${FEATURE_PRESET}" \
  --overwrite

echo "Done. Summary: ${OUTPUT_DIR}/sl_distance_summary.json"