#!/usr/bin/env python3
"""Build a Physical-AI acoustic closed-loop dataset from Phase C grasp histories.

This is an offline analysis tool: it does not launch Isaac Sim and does not touch
PhysX. It converts history CSV files into sense-act rows suitable for a small
state estimator / decision policy study.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

FEATURE_COLUMNS = [
    "early_energy",
    "primary_sgw_early_energy",
    "ref_early_energy",
    "tof_ns",
    "ref_tof_ns",
    "peak_amplitude",
    "amplitude_mean",
    "amplitude_std",
    "all_sgw_peak_std",
    "rx_energy_balance",
    "rx_tof_delta_ns",
    "waveform_early_fraction",
    "estimated_distance_energy_m",
    "estimated_distance_tof_m",
    "fused_distance_m",
    "alignment_score",
    "sensor_x_m",
    "sensor_y_m",
    "num_signal_ways",
]

OUTPUT_COLUMNS = [
    "source_dir",
    "mode",
    "claim_mode",
    "trial_id",
    "episode_id",
    "step_index",
    "phase",
    "controller_state",
    "motion_tier",
    "supervisor_action",
    *FEATURE_COLUMNS,
    "oracle_distance_m",
    "gmo_valid",
    "near_label",
    "stop_region_label",
    "terminal_step_label",
    "raw_episode_success",
    "geometry_consistent_success",
    "episode_success",
    "approach_reason",
    "terminal_reason",
    "approach_end_oracle_distance_m",
    "final_oracle_distance_m",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Physical-AI acoustic dataset from grasp batch outputs.")
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("runtime/outputs/scaffold_grasp_v6"),
        help="Batch output root containing *_trial_* subdirectories.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runtime/outputs/physical_ai_acoustic_v1"),
        help="Directory for dataset CSV and report JSON.",
    )
    parser.add_argument("--near-threshold-m", type=float, default=0.35)
    parser.add_argument("--stop-threshold-m", type=float, default=0.45)
    return parser.parse_args()


def f(value: Any, default: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def b(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def discover_trial_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [p for p in root.iterdir() if p.is_dir() and (p / "ultrasonic_closed_loop_grasp_history.csv").is_file()],
        key=lambda p: p.name,
    )


def trial_mode(path: Path, summary: dict[str, Any]) -> str:
    if summary.get("mode"):
        return str(summary["mode"])
    if path.name.startswith("open_loop"):
        return "open_loop_baseline"
    if path.name.startswith("closed_loop"):
        return "closed_loop"
    return "unknown"


def build_rows(trial_dir: Path, near_threshold_m: float, stop_threshold_m: float) -> list[dict[str, Any]]:
    summary = load_json(trial_dir / "ultrasonic_closed_loop_grasp_summary.json")
    mode = trial_mode(trial_dir, summary)
    claim_mode = str(summary.get("claim_mode", ""))
    raw_success = bool(summary.get("success", False))
    approach_reason = str(summary.get("approach_reason", ""))
    terminal_reason = str(summary.get("terminal_reason", ""))
    approach_end_oracle = f(summary.get("approach_end_oracle_distance_m"))
    final_oracle = f(summary.get("final_oracle_distance_m"))
    eval_oracle = approach_end_oracle if math.isfinite(approach_end_oracle) else final_oracle
    geometry_consistent_success = raw_success and math.isfinite(eval_oracle) and eval_oracle <= stop_threshold_m

    with (trial_dir / "ultrasonic_closed_loop_grasp_history.csv").open(encoding="utf-8", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))

    approach_indices = [i for i, row in enumerate(raw_rows) if row.get("phase") == "approach"]
    last_approach_index = approach_indices[-1] if approach_indices else -1

    out: list[dict[str, Any]] = []
    step = 0
    for i, row in enumerate(raw_rows):
        if row.get("phase") != "approach":
            continue
        step += 1
        oracle = f(row.get("oracle_distance_m"))
        record: dict[str, Any] = {
            "source_dir": str(trial_dir),
            "mode": mode,
            "claim_mode": claim_mode,
            "trial_id": row.get("trial_id") or summary.get("trial_id"),
            "episode_id": row.get("episode_id") or 1,
            "step_index": step,
            "phase": row.get("phase", ""),
            "controller_state": row.get("controller_state", ""),
            "motion_tier": row.get("motion_tier", ""),
            "supervisor_action": row.get("supervisor_action", ""),
            "oracle_distance_m": oracle,
            "gmo_valid": b(row.get("gmo_valid")),
            "near_label": math.isfinite(oracle) and oracle <= near_threshold_m,
            "stop_region_label": math.isfinite(oracle) and oracle <= stop_threshold_m,
            "terminal_step_label": i == last_approach_index,
            "raw_episode_success": raw_success,
            "geometry_consistent_success": geometry_consistent_success,
            "episode_success": geometry_consistent_success,
            "approach_reason": approach_reason,
            "terminal_reason": terminal_reason,
            "approach_end_oracle_distance_m": approach_end_oracle,
            "final_oracle_distance_m": final_oracle,
        }
        for col in FEATURE_COLUMNS:
            record[col] = f(row.get(col))
        out.append(record)
    return out


def finite_pairs(rows: list[dict[str, Any]], feature: str, label: str) -> list[tuple[float, bool]]:
    pairs = []
    for row in rows:
        value = f(row.get(feature))
        if math.isfinite(value):
            pairs.append((value, bool(row.get(label))))
    return pairs


def evaluate_threshold(values: list[tuple[float, bool]], threshold: float, *, leq_positive: bool) -> dict[str, float]:
    tp = fp = tn = fn = 0
    for value, actual in values:
        pred = value <= threshold if leq_positive else value >= threshold
        if pred and actual:
            tp += 1
        elif pred and not actual:
            fp += 1
        elif not pred and actual:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    acc = (tp + tn) / max(1, tp + fp + tn + fn)
    return {"threshold": threshold, "precision": precision, "recall": recall, "f1": f1, "accuracy": acc, "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def best_threshold(rows: list[dict[str, Any]], feature: str, label: str) -> dict[str, Any] | None:
    pairs = finite_pairs(rows, feature, label)
    if len(pairs) < 3 or len({actual for _, actual in pairs}) < 2:
        return None
    candidates = sorted({value for value, _ in pairs})
    directions = []
    for leq in (True, False):
        scored = [evaluate_threshold(pairs, t, leq_positive=leq) for t in candidates]
        best = max(scored, key=lambda r: (r["f1"], r["accuracy"]))
        best["direction"] = "<=" if leq else ">="
        directions.append(best)
    out = max(directions, key=lambda r: (r["f1"], r["accuracy"]))
    out["feature"] = feature
    out["label"] = label
    out["n"] = len(pairs)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def main() -> None:
    args = parse_args()
    trial_dirs = discover_trial_dirs(args.input_root)
    all_rows: list[dict[str, Any]] = []
    for trial_dir in trial_dirs:
        all_rows.extend(build_rows(trial_dir, args.near_threshold_m, args.stop_threshold_m))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset_csv = args.output_dir / "physical_ai_acoustic_steps.csv"
    write_csv(dataset_csv, all_rows, OUTPUT_COLUMNS)

    threshold_rows = []
    for feature in FEATURE_COLUMNS:
        for label in ("near_label", "stop_region_label", "terminal_step_label"):
            result = best_threshold(all_rows, feature, label)
            if result is not None:
                threshold_rows.append(result)
    threshold_rows.sort(key=lambda r: (r["label"], -r["f1"], -r["accuracy"], r["feature"]))
    threshold_csv = args.output_dir / "physical_ai_threshold_baselines.csv"
    write_csv(
        threshold_csv,
        threshold_rows,
        ["label", "feature", "direction", "threshold", "f1", "accuracy", "precision", "recall", "tp", "fp", "tn", "fn", "n"],
    )

    by_mode = defaultdict(list)
    for row in all_rows:
        by_mode[str(row.get("mode"))].append(row)

    terminal_counts = Counter((row.get("mode"), row.get("terminal_reason")) for row in all_rows if row.get("terminal_step_label"))
    trial_records = []
    anomaly_rows = []
    for trial_dir in trial_dirs:
        summary = load_json(trial_dir / "ultrasonic_closed_loop_grasp_summary.json")
        mode = trial_mode(trial_dir, summary)
        raw_success = bool(summary.get("success"))
        approach_end_oracle = f(summary.get("approach_end_oracle_distance_m"))
        final_oracle = f(summary.get("final_oracle_distance_m"))
        eval_oracle = approach_end_oracle if math.isfinite(approach_end_oracle) else final_oracle
        geometry_consistent_success = raw_success and math.isfinite(eval_oracle) and eval_oracle <= args.stop_threshold_m
        trial_records.append(
            {
                "source_dir": str(trial_dir),
                "mode": mode,
                "trial_id": summary.get("trial_id"),
                "terminal_reason": summary.get("terminal_reason"),
                "raw_success": raw_success,
                "geometry_consistent_success": geometry_consistent_success,
                "approach_end_oracle_distance_m": approach_end_oracle,
                "final_oracle_distance_m": final_oracle,
                "eval_oracle_distance_m": eval_oracle,
            }
        )
        if raw_success and (not math.isfinite(eval_oracle) or eval_oracle > args.stop_threshold_m):
            anomaly_rows.append(
                {
                    "source_dir": str(trial_dir),
                    "mode": mode,
                    "trial_id": summary.get("trial_id"),
                    "terminal_reason": summary.get("terminal_reason"),
                    "approach_end_oracle_distance_m": approach_end_oracle,
                    "final_oracle_distance_m": final_oracle,
                    "eval_oracle_distance_m": eval_oracle,
                    "note": "raw_success_true_but_approach_end_geometry_not_within_stop_threshold",
                }
            )
    anomalies_json = args.output_dir / "physical_ai_anomalies.json"
    anomalies_json.write_text(json.dumps(anomaly_rows, indent=2), encoding="utf-8")

    trial_records_json = args.output_dir / "physical_ai_trial_success_audit.json"
    trial_records_json.write_text(json.dumps(trial_records, indent=2), encoding="utf-8")

    trial_counts_by_mode: dict[str, Counter] = defaultdict(Counter)
    for record in trial_records:
        mode = str(record["mode"])
        trial_counts_by_mode[mode]["trials"] += 1
        if record["raw_success"]:
            trial_counts_by_mode[mode]["raw_success"] += 1
        if record["geometry_consistent_success"]:
            trial_counts_by_mode[mode]["geometry_consistent_success"] += 1

    report = {
        "input_root": str(args.input_root),
        "output_dir": str(args.output_dir),
        "trial_dir_count": len(trial_dirs),
        "step_row_count": len(all_rows),
        "near_threshold_m": args.near_threshold_m,
        "stop_threshold_m": args.stop_threshold_m,
        "rows_by_mode": {mode: len(rows) for mode, rows in by_mode.items()},
        "terminal_counts": {f"{mode}:{reason}": count for (mode, reason), count in terminal_counts.items()},
        "trial_success_counts_by_mode": {mode: dict(counts) for mode, counts in trial_counts_by_mode.items()},
        "top_threshold_baselines": threshold_rows[:10],
        "anomaly_count": len(anomaly_rows),
        "outputs": {
            "dataset_csv": str(dataset_csv),
            "threshold_csv": str(threshold_csv),
            "anomalies_json": str(anomalies_json),
            "trial_success_audit_json": str(trial_records_json),
        },
        "claim_boundary": (
            "Rows are offline Physical-AI state/action data from Isaac Sim histories. "
            "Oracle distance is retained only for labels/evaluation, not as a deployable observation. "
            "For contact-only proxy runs, geometry-consistent success is audited using approach_end_oracle_distance_m "
            "because final_oracle_distance_m can reflect post-contact/post-motion state rather than the approach endpoint."
        ),
    }
    report_json = args.output_dir / "physical_ai_acoustic_report.json"
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote {dataset_csv}")
    print(f"Wrote {threshold_csv}")
    print(f"Wrote {anomalies_json}")
    print(f"Wrote {report_json}")
    print(f"steps={len(all_rows)} trials={len(trial_dirs)} anomalies={len(anomaly_rows)}")
    if threshold_rows:
        top = threshold_rows[0]
        print(
            "top baseline: "
            f"label={top['label']} feature={top['feature']} {top['direction']} {top['threshold']:.6g} "
            f"f1={top['f1']:.3f} acc={top['accuracy']:.3f}"
        )


if __name__ == "__main__":
    main()
