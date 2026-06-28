#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
DISTANCES="${DISTANCES:-0.5 1.0 1.5 2.0 2.5 3.0}"
REPEATS="${REPEATS:-3}"
FRAMES="${FRAMES:-80}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-20}"
MAX_RUNTIME_SECONDS="${MAX_RUNTIME_SECONDS:-300}"
END_EFFECTOR_FRAME="${END_EFFECTOR_FRAME:-ee_link}"

OUTPUT_ROOT="${OUTPUT_ROOT:-${HOST_ROOT}/runtime/outputs/ur10_official_asset_ee_sweep_${RUN_ID}}"
SCENE_ROOT="${SCENE_ROOT:-${HOST_ROOT}/runtime/scenes/ur10_official_asset_ee_sweep_${RUN_ID}}"

mkdir -p "${OUTPUT_ROOT}" "${SCENE_ROOT}"

echo "Official asset UR10 EE distance sweep"
echo "  output root: ${OUTPUT_ROOT}"
echo "  scene root:  ${SCENE_ROOT}"
echo "  distances:   ${DISTANCES}"
echo "  repeats:     ${REPEATS}"
echo "  frames:      ${FRAMES}"
echo "  ee frame:    ${END_EFFECTOR_FRAME}"

for distance in ${DISTANCES}; do
  distance_label="${distance//./p}m"
  for repeat in $(seq 1 "${REPEATS}"); do
    case_id="distance_${distance_label}_repeat_$(printf '%03d' "${repeat}")"
    case_output_dir="${OUTPUT_ROOT}/${case_id}"
    case_output_stage="${SCENE_ROOT}/${case_id}.usda"
    echo
    echo "Running ${case_id}"
    "${SCRIPT_DIR}/run_host_python.sh" \
      "${SCRIPT_DIR}/official_asset_ur10_ee_acoustic_smoke.py" \
      --overwrite \
      --gui \
      --end-effector-frame "${END_EFFECTOR_FRAME}" \
      --target-distance "${distance}" \
      --output-dir "${case_output_dir}" \
      --output-stage "${case_output_stage}" \
      --frames "${FRAMES}" \
      --progress-interval "${PROGRESS_INTERVAL}" \
      --max-runtime-seconds "${MAX_RUNTIME_SECONDS}"
  done
done

python3 - "${OUTPUT_ROOT}" > "${OUTPUT_ROOT}/summary.csv" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for summary_path in sorted(root.glob("distance_*_repeat_*/official_asset_ur10_ee_acoustic_smoke_summary.json")):
    data = json.loads(summary_path.read_text())
    first = data.get("first_gmo_data") or {}
    rows.append({
        "case_id": summary_path.parent.name,
        "pass": data.get("pass"),
        "target_distance_m": data.get("target_distance_m"),
        "sensor_path": data.get("sensor_path"),
        "sensor_prim_type": data.get("sensor_prim_type"),
        "sensor_parent_ok": data.get("sensor_parent_ok"),
        "alignment_angle_deg": data.get("alignment_angle_deg"),
        "alignment_dot": data.get("alignment_dot"),
        "writer_calls": data.get("writer_calls"),
        "num_elements": first.get("num_elements"),
        "amplitude_min": first.get("amplitude_min"),
        "amplitude_max": first.get("amplitude_max"),
        "amplitude_mean": first.get("amplitude_mean"),
        "amplitude_std": first.get("amplitude_std"),
        "summary_path": str(summary_path),
        "output_stage": data.get("output_stage"),
    })

fieldnames = [
    "case_id",
    "pass",
    "target_distance_m",
    "sensor_path",
    "sensor_prim_type",
    "sensor_parent_ok",
    "alignment_angle_deg",
    "alignment_dot",
    "writer_calls",
    "num_elements",
    "amplitude_min",
    "amplitude_max",
    "amplitude_mean",
    "amplitude_std",
    "summary_path",
    "output_stage",
]
writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
writer.writeheader()
writer.writerows(rows)
PY

python3 - "${OUTPUT_ROOT}/summary.csv" <<'PY'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
rows = list(csv.DictReader(path.open()))
passes = sum(row["pass"] == "True" for row in rows)
print()
print(f"Wrote {path}")
print(f"PASS {passes}/{len(rows)}")
for row in rows:
    print(
        f"{row['case_id']}: pass={row['pass']} "
        f"distance={row['target_distance_m']} "
        f"num_elements={row['num_elements']} "
        f"amp_max={row['amplitude_max']} "
        f"angle_deg={row['alignment_angle_deg']}"
    )
PY
