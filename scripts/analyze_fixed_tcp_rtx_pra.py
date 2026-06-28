"""Cross-model trend analysis for fixed-TCP RTX features vs PyRoom reference."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

DEFAULT_RTX_FEATURES = (
    "/home/lab109/song/isaacsim6.0/runtime/outputs/phase3_rtx_features/fixed_tcp_rtx_distance_features.csv"
)
DEFAULT_PRA_FEATURES = (
    "/home/lab109/song/isaacsim6.0/runtime/outputs/experiment_4_pra_reference_passport_v1/pra_reference_features.csv"
)
DEFAULT_OUTPUT_ROOT = Path("/home/lab109/song/isaacsim6.0/runtime/outputs/phase3_rtx_pra_comparison")

RTX_METRICS = [
    ("amplitude_max_mean", "RTX GMO amplitude max distance trend"),
    ("amplitude_mean_mean", "RTX GMO amplitude mean distance trend"),
    ("primary_sgw_peak_mean", "RTX primary signal-way peak distance trend"),
    ("primary_sgw_early_energy_mean", "RTX primary signal-way early energy distance trend"),
    ("ref_sgw_peak_mean", "RTX reference signal-way peak distance trend"),
    ("all_sgw_peak_mean_mean", "RTX mean-of-peaks across signal ways distance trend"),
]
PRA_METRICS = [
    ("rir_peak_abs_value", "PRA RIR abs peak distance trend"),
    ("early_energy_50ms", "PRA early energy 50 ms distance trend"),
    ("direct_delay_ms", "PRA direct delay ms distance trend"),
    ("rt60_measured", "PRA RT60 distance trend"),
]
CROSS_PAIRS = [
    ("amplitude_max_mean", "rir_peak_abs_value"),
    ("amplitude_max_mean", "early_energy_50ms"),
    ("amplitude_mean_mean", "direct_delay_ms"),
    ("primary_sgw_peak_mean", "rir_peak_abs_value"),
    ("primary_sgw_early_energy_mean", "early_energy_50ms"),
    ("ref_sgw_peak_mean", "direct_delay_ms"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze fixed-TCP RTX x PRA trends.")
    parser.add_argument("--rtx-features", type=Path, default=Path(DEFAULT_RTX_FEATURES))
    parser.add_argument("--pra-features", type=Path, default=Path(DEFAULT_PRA_FEATURES))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--material-condition", default="B")
    parser.add_argument("--absorption-label", default="")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value: object) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def spearman(x: list[float], y: list[float]) -> tuple[float, float]:
    if len(x) != len(y) or len(x) < 2:
        return float("nan"), float("nan")
    try:
        from scipy.stats import spearmanr

        result = spearmanr(x, y)
        return float(result.correlation), float(result.pvalue)
    except Exception:
        return float("nan"), float("nan")


def monotonic_label(rho: float) -> str:
    if math.isnan(rho) or abs(rho) < 0.7:
        return "no_clear_monotonic_relation"
    return "monotonic_positive" if rho > 0 else "monotonic_negative"


def cross_model_label(rtx_rho: float, pra_rho: float) -> str:
    if any(math.isnan(v) or abs(v) < 0.7 for v in (rtx_rho, pra_rho)):
        return "no_clear_monotonic_relation"
    return "trend_agreement" if rtx_rho * pra_rho > 0 else "trend_disagreement"


def aggregate_rtx(rows: list[dict[str, str]], material_condition: str) -> dict[float, dict[str, object]]:
    grouped: dict[float, list[dict[str, str]]] = {}
    for row in rows:
        if material_condition and row.get("material_condition", "") != material_condition:
            continue
        distance = round(parse_float(row.get("target_distance_m", "")), 6)
        grouped.setdefault(distance, []).append(row)

    aggregated: dict[float, dict[str, object]] = {}
    for distance, group_rows in sorted(grouped.items()):
        amp_max = [parse_float(r.get("amplitude_max_mean", "")) for r in group_rows]
        amp_mean = [parse_float(r.get("amplitude_mean_mean", "")) for r in group_rows]
        aggregated[distance] = {
            "target_distance_m": distance,
            "rtx_repeat_count": len(group_rows),
            "amplitude_max_mean": float(np.mean(amp_max)),
            "amplitude_mean_mean": float(np.mean(amp_mean)),
            "amplitude_max_std_across_repeats": float(np.std(amp_max, ddof=1)) if len(amp_max) > 1 else 0.0,
        }
        optional_metrics = [
            "primary_sgw_peak_mean",
            "primary_sgw_early_energy_mean",
            "ref_sgw_peak_mean",
            "all_sgw_peak_mean_mean",
        ]
        for metric in optional_metrics:
            values = [parse_float(r.get(metric, "")) for r in group_rows]
            finite = [v for v in values if math.isfinite(v)]
            if finite:
                aggregated[distance][metric] = float(np.mean(finite))
    return aggregated


def load_pra(rows: list[dict[str, str]], absorption_label: str) -> dict[float, dict[str, str]]:
    by_distance: dict[float, dict[str, str]] = {}
    for row in rows:
        if absorption_label and row.get("absorption_label", "") != absorption_label:
            continue
        by_distance[round(parse_float(row["target_distance_m"]), 6)] = row
    return by_distance


def build_comparison_rows(
    rtx: dict[float, dict[str, object]],
    pra: dict[float, dict[str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for distance, rtx_row in sorted(rtx.items()):
        if distance not in pra:
            continue
        pra_row = pra[distance]
        row = dict(rtx_row)
        row.update(
            {
                "pra_geometry_policy": pra_row.get("geometry_policy", ""),
                "pra_absorption_label": pra_row.get("absorption_label", ""),
                "pra_absorption_value": parse_float(pra_row.get("absorption_value", "")),
                "pra_rir_peak_abs_value": parse_float(pra_row.get("rir_peak_abs_value", "")),
                "pra_direct_delay_ms": parse_float(pra_row.get("direct_delay_ms", "")),
                "pra_rt60_measured": parse_float(pra_row.get("rt60_measured", "")),
                "pra_early_energy_50ms": parse_float(pra_row.get("early_energy_50ms", "")),
            }
        )
        rows.append(row)
    return rows


def make_correlations(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []
    distances = [float(r["target_distance_m"]) for r in sorted(rows, key=lambda r: float(r["target_distance_m"]))]
    out: list[dict[str, object]] = []

    rtx_rhos: dict[str, float] = {}
    for metric, interpretation in RTX_METRICS:
        selected = sorted(rows, key=lambda r: float(r["target_distance_m"]))
        if not all(metric in r and math.isfinite(float(r[metric])) for r in selected):
            continue
        y = [float(r[metric]) for r in selected]
        rho, p_value = spearman(distances, y)
        rtx_rhos[metric] = rho
        out.append(
            {
                "comparison": "distance_vs_rtx",
                "x_feature": "target_distance_m",
                "y_feature": metric,
                "rho": rho,
                "p_value": p_value,
                "n": len(distances),
                "trend_label": monotonic_label(rho),
                "interpretation": interpretation,
            }
        )

    pra_rhos: dict[str, float] = {}
    for metric, interpretation in PRA_METRICS:
        pra_field = f"pra_{metric}"
        y = [float(r[pra_field]) for r in sorted(rows, key=lambda r: float(r["target_distance_m"]))]
        rho, p_value = spearman(distances, y)
        pra_rhos[metric] = rho
        out.append(
            {
                "comparison": "distance_vs_pra",
                "x_feature": "target_distance_m",
                "y_feature": pra_field,
                "rho": rho,
                "p_value": p_value,
                "n": len(distances),
                "trend_label": monotonic_label(rho),
                "interpretation": interpretation,
            }
        )

    for rtx_metric, pra_metric in CROSS_PAIRS:
        selected = sorted(rows, key=lambda r: float(r["target_distance_m"]))
        if not all(
            rtx_metric in r
            and math.isfinite(float(r[rtx_metric]))
            and math.isfinite(float(r[f"pra_{pra_metric}"]))
            for r in selected
        ):
            continue
        x = [float(r[rtx_metric]) for r in selected]
        y = [float(r[f"pra_{pra_metric}"]) for r in selected]
        rho, p_value = spearman(x, y)
        out.append(
            {
                "comparison": "rtx_vs_pra",
                "x_feature": rtx_metric,
                "y_feature": pra_metric,
                "rho": rho,
                "p_value": p_value,
                "n": len(x),
                "trend_label": cross_model_label(rtx_rhos.get(rtx_metric, float("nan")), pra_rhos.get(pra_metric, float("nan"))),
                "interpretation": "Cross-model trend characterization; not waveform validation.",
            }
        )
    return out


def make_plots(output_root: Path, rows: list[dict[str, object]]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    output_root.mkdir(parents=True, exist_ok=True)
    figure_paths: list[str] = []
    selected = sorted(rows, key=lambda r: float(r["target_distance_m"]))
    x = [float(r["target_distance_m"]) for r in selected]

    plt.figure()
    plt.plot(x, [float(r["amplitude_max_mean"]) for r in selected], marker="o", label="RTX amplitude_max_mean")
    plt.xlabel("Target distance (m)")
    plt.ylabel("RTX GMO amplitude max")
    plt.title("Fixed-TCP RTX distance trend")
    plt.grid(True, alpha=0.3)
    plt.legend()
    path = output_root / "rtx_amplitude_max_vs_distance.png"
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()
    figure_paths.append(str(path))

    plt.figure()
    plt.plot(x, [float(r["pra_early_energy_50ms"]) for r in selected], marker="s", label="PRA early_energy_50ms")
    plt.plot(x, [float(r["pra_rir_peak_abs_value"]) for r in selected], marker="^", label="PRA rir_peak_abs_value")
    plt.xlabel("Target distance (m)")
    plt.ylabel("PRA feature value")
    plt.title("PyRoom reference distance trends")
    plt.grid(True, alpha=0.3)
    plt.legend()
    path = output_root / "pra_features_vs_distance.png"
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()
    figure_paths.append(str(path))

    if selected and "primary_sgw_peak_mean" in selected[0]:
        plt.figure()
        plt.plot(
            x,
            [float(r["primary_sgw_peak_mean"]) for r in selected],
            marker="o",
            label="RTX primary_sgw_peak_mean",
        )
        if "ref_sgw_peak_mean" in selected[0]:
            plt.plot(
                x,
                [float(r["ref_sgw_peak_mean"]) for r in selected],
                marker="x",
                label="RTX ref_sgw_peak_mean",
            )
        plt.xlabel("Target distance (m)")
        plt.ylabel("RTX signal-way peak amplitude")
        plt.title("Fixed-TCP RTX signal-way distance trend")
        plt.grid(True, alpha=0.3)
        plt.legend()
        path = output_root / "rtx_signal_way_peak_vs_distance.png"
        plt.savefig(path, dpi=160, bbox_inches="tight")
        plt.close()
        figure_paths.append(str(path))

    return figure_paths


def main() -> None:
    args = parse_args()
    rtx_rows = read_csv(args.rtx_features)
    pra_rows = read_csv(args.pra_features)

    absorption_label = args.absorption_label
    if not absorption_label:
        label_map = {"A": "low_absorption", "B": "medium_absorption", "C": "high_absorption"}
        absorption_label = label_map.get(str(args.material_condition).upper(), "medium_absorption")

    rtx = aggregate_rtx(rtx_rows, str(args.material_condition))
    pra = load_pra(pra_rows, absorption_label)
    comparison_rows = build_comparison_rows(rtx, pra)
    correlation_rows = make_correlations(comparison_rows)
    figure_paths = make_plots(args.output_root, comparison_rows)

    comparison_csv = args.output_root / "fixed_tcp_rtx_pra_comparison.csv"
    correlation_csv = args.output_root / "fixed_tcp_rtx_pra_correlations.csv"
    comparison_fields = [
        "target_distance_m",
        "rtx_repeat_count",
        "amplitude_max_mean",
        "amplitude_mean_mean",
        "amplitude_max_std_across_repeats",
        "primary_sgw_peak_mean",
        "primary_sgw_early_energy_mean",
        "ref_sgw_peak_mean",
        "all_sgw_peak_mean_mean",
        "pra_geometry_policy",
        "pra_absorption_label",
        "pra_absorption_value",
        "pra_rir_peak_abs_value",
        "pra_direct_delay_ms",
        "pra_rt60_measured",
        "pra_early_energy_50ms",
    ]
    if comparison_rows:
        comparison_fields = [field for field in comparison_fields if field in comparison_rows[0]]
    write_csv(comparison_csv, comparison_fields, comparison_rows)
    write_csv(
        correlation_csv,
        ["comparison", "x_feature", "y_feature", "rho", "p_value", "n", "trend_label", "interpretation"],
        correlation_rows,
    )

    report_path = args.output_root / "PHASE3_RTX_PRA_REPORT.json"
    report_path.write_text(
        json.dumps(
            {
                "material_condition": args.material_condition,
                "absorption_label": absorption_label,
                "rtx_features": str(args.rtx_features),
                "pra_features": str(args.pra_features),
                "comparison_rows": len(comparison_rows),
                "figure_paths": figure_paths,
                "claim_boundary": "Trend-level cross-model characterization only; not RTX validation against PRA.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Comparison rows: {len(comparison_rows)}")
    print(f"Wrote {comparison_csv}")
    print(f"Wrote {correlation_csv}")
    print(f"Wrote {report_path}")
    for path in figure_paths:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()