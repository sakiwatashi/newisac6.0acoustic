"""Extract distance-level RTX features from fixed-TCP sweep timeseries CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE_FIELDNAMES = [
    "source_timeseries",
    "repeat_id",
    "material_condition",
    "target_distance_m",
    "distance_label",
    "sample_count",
    "amplitude_max_mean",
    "amplitude_max_std",
    "amplitude_max_cv",
    "amplitude_mean_mean",
    "amplitude_std_mean",
    "alignment_angle_deg_mean",
    "sensor_tcp_radius_xy_mean",
    "max_ee_motion_m",
]

SIGNAL_WAY_METRICS = [
    ("primary_sgw_peak", "primary_sgw_peak_mean", "primary_sgw_peak_std", "primary_sgw_peak_cv"),
    ("primary_sgw_mean", "primary_sgw_mean_mean", "primary_sgw_mean_std", "primary_sgw_mean_cv"),
    ("primary_sgw_early_energy", "primary_sgw_early_energy_mean", "primary_sgw_early_energy_std", "primary_sgw_early_energy_cv"),
    (
        "primary_sgw_first_time_offset_ns",
        "primary_sgw_first_time_offset_ns_mean",
        "primary_sgw_first_time_offset_ns_std",
        "primary_sgw_first_time_offset_ns_cv",
    ),
    ("ref_sgw_peak", "ref_sgw_peak_mean", "ref_sgw_peak_std", "ref_sgw_peak_cv"),
    ("ref_sgw_early_energy", "ref_sgw_early_energy_mean", "ref_sgw_early_energy_std", "ref_sgw_early_energy_cv"),
    ("all_sgw_peak_mean", "all_sgw_peak_mean_mean", "all_sgw_peak_mean_std", "all_sgw_peak_mean_cv"),
]

SIGNAL_WAY_OUTPUT_FIELDS = [field for _src, mean, std, cv in SIGNAL_WAY_METRICS for field in (mean, std, cv)]
AGGREGATE_COUNT_FIELDS = [
    ("num_signal_ways", "num_signal_ways_mean"),
    ("gmo_valid", "gmo_valid_rate"),
]


def build_fieldnames(sample_rows: list[dict[str, str]]) -> list[str]:
    fieldnames = list(BASE_FIELDNAMES)
    if not sample_rows:
        return fieldnames + SIGNAL_WAY_OUTPUT_FIELDS + [pair[1] for pair in AGGREGATE_COUNT_FIELDS]

    has_signal_way_columns = any("primary_sgw_peak" in row for row in sample_rows)
    if has_signal_way_columns:
        fieldnames.extend(SIGNAL_WAY_OUTPUT_FIELDS)
        fieldnames.extend(pair[1] for pair in AGGREGATE_COUNT_FIELDS)
    return fieldnames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract fixed-TCP RTX distance features.")
    parser.add_argument("--timeseries", nargs="*", default=[], help="One or more timeseries CSV paths.")
    parser.add_argument(
        "--input-root",
        type=Path,
        default=None,
        help="Batch root; discovers **/official_asset_ur10_fixed_tcp_distance_sweep_timeseries.csv",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/phase3_rtx_features/fixed_tcp_rtx_distance_features.csv"),
    )
    return parser.parse_args()


def discover_timeseries(input_root: Path) -> list[Path]:
    return sorted(input_root.glob("**/official_asset_ur10_fixed_tcp_distance_sweep_timeseries.csv"))


def mean_std_cv(values: list[float]) -> tuple[float, float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    cv = float(std / abs(mean)) if mean != 0.0 else float("nan")
    return mean, std, cv


def parse_float(value: object) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def parse_bool_rate(values: list[str]) -> float:
    if not values:
        return float("nan")
    truthy = 0
    counted = 0
    for value in values:
        token = str(value).strip().lower()
        if token in ("", "nan"):
            continue
        counted += 1
        if token in ("1", "true", "yes"):
            truthy += 1
    if counted == 0:
        return float("nan")
    return float(truthy / counted)


def extract_from_timeseries(path: Path) -> list[dict[str, object]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    grouped: dict[tuple[str, str, float], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        repeat_id = row.get("repeat_id", "") or ""
        material_condition = row.get("material_condition", "") or ""
        distance = round(parse_float(row.get("desired_distance_m", row.get("target_distance_m", "nan"))), 6)
        if math.isnan(distance):
            continue
        grouped[(repeat_id, material_condition, distance)].append(row)

    ee_positions = [
        (parse_float(r.get("ee_x_m", "")), parse_float(r.get("ee_y_m", "")), parse_float(r.get("ee_z_m", "")))
        for r in rows
    ]
    max_ee_motion = 0.0
    for i, a in enumerate(ee_positions):
        for b in ee_positions[i + 1 :]:
            if all(math.isfinite(v) for v in (*a, *b)):
                max_ee_motion = max(max_ee_motion, math.dist(a, b))

    features: list[dict[str, object]] = []
    for (repeat_id, material_condition, distance), group_rows in sorted(grouped.items()):
        label = group_rows[0].get("distance_label", f"d_{str(distance).replace('.', 'p')}m")
        amp_max = [parse_float(r.get("amplitude_max", "")) for r in group_rows]
        amp_mean = [parse_float(r.get("amplitude_mean", "")) for r in group_rows]
        amp_std = [parse_float(r.get("amplitude_std", "")) for r in group_rows]
        align = [parse_float(r.get("alignment_angle_deg", "")) for r in group_rows]
        radius = [parse_float(r.get("sensor_tcp_radius_xy_m", "")) for r in group_rows]
        max_mean, max_std, max_cv = mean_std_cv(amp_max)
        feature_row: dict[str, object] = {
            "source_timeseries": str(path),
            "repeat_id": repeat_id,
            "material_condition": material_condition,
            "target_distance_m": distance,
            "distance_label": label,
            "sample_count": len(group_rows),
            "amplitude_max_mean": max_mean,
            "amplitude_max_std": max_std,
            "amplitude_max_cv": max_cv,
            "amplitude_mean_mean": mean_std_cv(amp_mean)[0],
            "amplitude_std_mean": mean_std_cv(amp_std)[0],
            "alignment_angle_deg_mean": mean_std_cv(align)[0],
            "sensor_tcp_radius_xy_mean": mean_std_cv(radius)[0],
            "max_ee_motion_m": max_ee_motion,
        }

        if "primary_sgw_peak" in group_rows[0]:
            for source_field, mean_field, std_field, cv_field in SIGNAL_WAY_METRICS:
                values = [parse_float(r.get(source_field, "")) for r in group_rows]
                mean, std, cv = mean_std_cv(values)
                feature_row[mean_field] = mean
                feature_row[std_field] = std
                feature_row[cv_field] = cv

            for source_field, mean_field in AGGREGATE_COUNT_FIELDS:
                if source_field == "gmo_valid":
                    feature_row[mean_field] = parse_bool_rate([r.get(source_field, "") for r in group_rows])
                else:
                    values = [parse_float(r.get(source_field, "")) for r in group_rows]
                    feature_row[mean_field] = mean_std_cv(values)[0]

        features.append(feature_row)
    return features


def main() -> None:
    args = parse_args()
    paths = [Path(p) for p in args.timeseries]
    if args.input_root is not None:
        paths.extend(discover_timeseries(args.input_root))
    paths = sorted({p.resolve() for p in paths if p.exists()})
    if not paths:
        raise SystemExit("No timeseries CSV files found.")

    all_features: list[dict[str, object]] = []
    sample_rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            if rows and not sample_rows:
                sample_rows = rows
        all_features.extend(extract_from_timeseries(path))

    fieldnames = build_fieldnames(sample_rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_features)

    summary_path = args.output_csv.with_suffix(".summary.json")
    summary_path.write_text(
        json.dumps(
            {
                "timeseries_count": len(paths),
                "feature_row_count": len(all_features),
                "output_csv": str(args.output_csv),
                "signal_way_features_enabled": "primary_sgw_peak" in (sample_rows[0] if sample_rows else {}),
                "fieldnames": fieldnames,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Extracted {len(all_features)} feature rows from {len(paths)} timeseries files")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()