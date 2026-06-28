#!/usr/bin/env bash
# Phase 3: run fixed-TCP smoke for material conditions A/B/C and compare RTX distance trends.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYROOM_PYTHON="${PYROOM_PYTHON:-/home/lab109/song/venvs/isaac_acoustic_pyroom/bin/python}"
SENSITIVITY_ROOT="${SENSITIVITY_ROOT:-${ISAACSIM_ROOT}/runtime/outputs/phase3_material_sensitivity_sgw}"

mkdir -p "${SENSITIVITY_ROOT}"

for CONDITION in A B C; do
  echo "=== Material condition ${CONDITION} ==="
  OUTPUT_DIR="${SENSITIVITY_ROOT}/rtx_smoke_cond_${CONDITION}"
  OUTPUT_STAGE="${ISAACSIM_ROOT}/runtime/scenes/phase3_material_sensitivity_cond_${CONDITION}.usda"
  MATERIAL_CONDITION="${CONDITION}" OUTPUT_DIR="${OUTPUT_DIR}" OUTPUT_STAGE="${OUTPUT_STAGE}" \
    "${SCRIPT_DIR}/run_host_official_asset_ur10_fixed_tcp_distance_sweep_smoke.sh"

  FEATURES_CSV="${SENSITIVITY_ROOT}/rtx_features_cond_${CONDITION}.csv"
  python3 "${SCRIPT_DIR}/extract_fixed_tcp_rtx_features.py" \
    --timeseries "${OUTPUT_DIR}/official_asset_ur10_fixed_tcp_distance_sweep_timeseries.csv" \
    --output-csv "${FEATURES_CSV}"

  PRA_ROOT="${SENSITIVITY_ROOT}/pra_cond_${CONDITION}"
  MATERIAL_CONDITION="${CONDITION}" OUTPUT_ROOT="${PRA_ROOT}" \
    "${SCRIPT_DIR}/run_pyroom_experiment_4_passport_v1.sh"

  COMP_ROOT="${SENSITIVITY_ROOT}/comparison_cond_${CONDITION}"
  "${PYROOM_PYTHON}" "${SCRIPT_DIR}/analyze_fixed_tcp_rtx_pra.py" \
    --rtx-features "${FEATURES_CSV}" \
    --pra-features "${PRA_ROOT}/pra_reference_features.csv" \
    --output-root "${COMP_ROOT}" \
    --material-condition "${CONDITION}"
done

python3 - <<'PY' "${SENSITIVITY_ROOT}"
import csv
import sys
from pathlib import Path

root = Path(sys.argv[1])
TRACKED_RTX_FEATURES = (
    "amplitude_max_mean",
    "primary_sgw_peak_mean",
    "primary_sgw_early_energy_mean",
    "ref_sgw_early_energy_mean",
    "all_sgw_peak_mean_mean",
)

summary_rows = []
for cond in ("A", "B", "C"):
    comp = root / f"comparison_cond_{cond}" / "fixed_tcp_rtx_pra_correlations.csv"
    if not comp.exists():
        continue
    with comp.open() as f:
        for row in csv.DictReader(f):
            if row.get("comparison") != "distance_vs_rtx":
                continue
            if row.get("y_feature") not in TRACKED_RTX_FEATURES:
                continue
            summary_rows.append(
                {
                    "material_condition": cond,
                    "comparison": row["comparison"],
                    "y_feature": row["y_feature"],
                    "rho": row["rho"],
                    "p_value": row.get("p_value", ""),
                    "trend_label": row["trend_label"],
                }
            )

summary_path = root / "material_sensitivity_summary.csv"
if summary_rows:
    with summary_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Wrote {summary_path}")

cross_rows = []
for cond in ("A", "B", "C"):
    features_csv = root / f"rtx_features_cond_{cond}.csv"
    if not features_csv.exists():
        continue
    with features_csv.open() as f:
        for row in csv.DictReader(f):
            distance = float(row["target_distance_m"])
            if distance not in (0.5, 3.0):
                continue
            cross_rows.append(
                {
                    "material_condition": cond,
                    "target_distance_m": distance,
                    "amplitude_max_mean": row.get("amplitude_max_mean", ""),
                    "primary_sgw_peak_mean": row.get("primary_sgw_peak_mean", ""),
                    "primary_sgw_early_energy_mean": row.get("primary_sgw_early_energy_mean", ""),
                    "ref_sgw_early_energy_mean": row.get("ref_sgw_early_energy_mean", ""),
                    "all_sgw_peak_mean_mean": row.get("all_sgw_peak_mean_mean", ""),
                }
            )

cross_path = root / "material_cross_condition_features.csv"
if cross_rows:
    with cross_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(cross_rows[0].keys()))
        writer.writeheader()
        writer.writerows(cross_rows)
    print(f"Wrote {cross_path}")
PY

echo "Material sensitivity complete: ${SENSITIVITY_ROOT}"