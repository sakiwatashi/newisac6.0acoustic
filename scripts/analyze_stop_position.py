#!/usr/bin/env python3
"""Analyze "stop position vs target position" for a closed-loop approach/grasp sweep.

For a sweep output directory this reads:
  - episodes_summary.json      (per-episode wrench target x, approach/terminal reason, success)
  - ultrasonic_closed_loop_grasp_history.csv
        (per-step sensor readings; the row with the largest sensor_x_m for a given
         trial_id is treated as the arm's stop position for that trial)

and reports how the stop position (sensor_x_m at max) correlates with the true
target position (wrench_oracle_position_m[0]), plus distance-to-target summary
statistics at the stop point.

Pure stdlib: argparse, csv, json, math, statistics, pathlib, collections.

Usage:
    python3 analyze_stop_position.py --run-dir <sweep_dir> [--compare <sweep_dir2>] [--out <path>]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def _to_float(value: Any) -> float:
    """Convert to float; returns nan on failure or non-finite result."""
    if value is None:
        return float("nan")
    if isinstance(value, str) and value.strip() == "":
        return float("nan")
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if not math.isfinite(f):
        return float("nan")
    return f


def _is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def load_episodes(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "episodes_summary.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    episodes = data.get("episodes", [])
    if not isinstance(episodes, list):
        return []
    return episodes


def load_stop_rows(run_dir: Path) -> dict[str, dict[str, float]]:
    """Return, per trial_id (as string key), the row (sensor_x_m/oracle_distance_m/
    fused_distance_m) with the maximum sensor_x_m in the history CSV."""
    path = run_dir / "ultrasonic_closed_loop_grasp_history.csv"
    best: dict[str, dict[str, float]] = {}
    if not path.exists():
        return best

    try:
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trial_id = row.get("trial_id")
                if trial_id is None or str(trial_id).strip() == "":
                    continue
                trial_key = str(trial_id).strip()

                sensor_x = _to_float(row.get("sensor_x_m"))
                if not _is_finite(sensor_x):
                    continue

                oracle_dist = _to_float(row.get("oracle_distance_m"))
                fused_dist = _to_float(row.get("fused_distance_m"))

                prev = best.get(trial_key)
                if prev is None or sensor_x > prev["sensor_x_m"]:
                    best[trial_key] = {
                        "sensor_x_m": sensor_x,
                        "oracle_distance_m": oracle_dist,
                        "fused_distance_m": fused_dist,
                    }
    except OSError:
        return best

    return best


def pearson_r(xs: list[float], ys: list[float]) -> tuple[float | None, str | None]:
    """Pearson correlation between paired finite values. Returns (r, note)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if _is_finite(x) and _is_finite(y)]
    if len(pairs) < 2:
        return None, "degenerate: insufficient paired finite samples"

    xv = [p[0] for p in pairs]
    yv = [p[1] for p in pairs]

    var_x = statistics.pvariance(xv)
    var_y = statistics.pvariance(yv)
    if var_x == 0.0 or var_y == 0.0:
        return None, "degenerate: zero variance"

    mean_x = statistics.fmean(xv)
    mean_y = statistics.fmean(yv)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs) / len(pairs)
    denom = math.sqrt(var_x) * math.sqrt(var_y)
    if denom == 0.0:
        return None, "degenerate: zero variance"
    return cov / denom, None


def stdev_safe(values: list[float]) -> float:
    finite = [v for v in values if _is_finite(v)]
    if len(finite) < 2:
        return 0.0
    if len(set(finite)) == 1:
        return 0.0
    return statistics.stdev(finite)


def summarize(run_dir: Path) -> dict[str, Any]:
    episodes = load_episodes(run_dir)
    stop_rows = load_stop_rows(run_dir)

    per_trial: list[dict[str, Any]] = []
    wrench_xs: list[float] = []
    stop_xs: list[float] = []
    oracle_dists: list[float] = []

    approach_counter: Counter = Counter()
    terminal_counter: Counter = Counter()
    success_count = 0

    for ep in episodes:
        trial_id = ep.get("trial_id")
        trial_key = str(trial_id) if trial_id is not None else ""

        wrench_pos = ep.get("wrench_oracle_position_m")
        if isinstance(wrench_pos, list) and len(wrench_pos) > 0:
            wrench_x = _to_float(wrench_pos[0])
        else:
            wrench_x = float("nan")

        approach_reason = ep.get("approach_reason", "unknown")
        terminal_reason = ep.get("terminal_reason", "unknown")
        success = bool(ep.get("success", False))

        approach_counter[approach_reason if approach_reason is not None else "unknown"] += 1
        terminal_counter[terminal_reason if terminal_reason is not None else "unknown"] += 1
        if success:
            success_count += 1

        row = stop_rows.get(trial_key)
        if row is not None:
            stop_x = row["sensor_x_m"]
            oracle_dist = row["oracle_distance_m"]
            fused_dist = row["fused_distance_m"]
        else:
            stop_x = float("nan")
            oracle_dist = float("nan")
            fused_dist = float("nan")

        per_trial.append(
            {
                "trial_id": trial_id,
                "wrench_x_m": wrench_x,
                "stop_x_m": stop_x,
                "oracle_distance_at_stop_m": oracle_dist,
                "fused_distance_at_stop_m": fused_dist,
                "approach_reason": approach_reason,
                "terminal_reason": terminal_reason,
                "success": success,
            }
        )

        wrench_xs.append(wrench_x)
        stop_xs.append(stop_x)
        oracle_dists.append(oracle_dist)

    n_episodes = len(episodes)

    finite_stop_xs = [v for v in stop_xs if _is_finite(v)]
    stop_x_summary = {
        "min": min(finite_stop_xs) if finite_stop_xs else None,
        "max": max(finite_stop_xs) if finite_stop_xs else None,
        "mean": statistics.fmean(finite_stop_xs) if finite_stop_xs else None,
        "stdev": stdev_safe(stop_xs),
    }

    r, r_note = pearson_r(wrench_xs, stop_xs)

    finite_oracle = [v for v in oracle_dists if _is_finite(v)]
    oracle_summary = {
        "min": min(finite_oracle) if finite_oracle else None,
        "max": max(finite_oracle) if finite_oracle else None,
        "mean": statistics.fmean(finite_oracle) if finite_oracle else None,
    }

    n_oracle_valid = len(finite_oracle)
    n_le_045 = sum(1 for v in finite_oracle if v <= 0.45)
    n_le_035 = sum(1 for v in finite_oracle if v <= 0.35)

    rate_le_045 = (n_le_045 / n_oracle_valid) if n_oracle_valid > 0 else None
    rate_le_035 = (n_le_035 / n_oracle_valid) if n_oracle_valid > 0 else None

    summary: dict[str, Any] = {
        "run_dir": str(run_dir),
        "n_episodes": n_episodes,
        "stop_x_m": stop_x_summary,
        "pearson_r_wrench_x_vs_stop_x": r,
        "pearson_r_note": r_note,
        "oracle_distance_at_stop_m": oracle_summary,
        "rate_oracle_le_0.45": {
            "count": n_le_045,
            "total": n_oracle_valid,
            "rate": rate_le_045,
        },
        "rate_oracle_le_0.35": {
            "count": n_le_035,
            "total": n_oracle_valid,
            "rate": rate_le_035,
        },
        "approach_reason_counts": dict(approach_counter),
        "terminal_reason_counts": dict(terminal_counter),
        "success_count": success_count,
        "per_trial": per_trial,
    }
    return summary


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "nan"
        return f"{value:.{digits}f}"
    return str(value)


def print_report(summary: dict[str, Any]) -> None:
    print(f"=== stop position analysis: {summary['run_dir']} ===")
    print(f"n_episodes = {summary['n_episodes']}")
    print()
    print(f"{'trial_id':>8} {'wrench_x':>10} {'stop_x':>10} {'oracle_dist':>12} {'fused':>10}  approach_reason")
    for t in summary["per_trial"]:
        print(
            f"{str(t['trial_id']):>8} "
            f"{_fmt(t['wrench_x_m']):>10} "
            f"{_fmt(t['stop_x_m']):>10} "
            f"{_fmt(t['oracle_distance_at_stop_m']):>12} "
            f"{_fmt(t['fused_distance_at_stop_m']):>10}  "
            f"{t['approach_reason']}"
        )

    print()
    print("--- summary ---")
    sx = summary["stop_x_m"]
    print(
        f"stop_x_m: min={_fmt(sx['min'])} max={_fmt(sx['max'])} "
        f"mean={_fmt(sx['mean'])} stdev={_fmt(sx['stdev'])}"
    )
    r = summary["pearson_r_wrench_x_vs_stop_x"]
    r_note = summary["pearson_r_note"]
    if r is None:
        print(f"pearson_r(wrench_x, stop_x) = None ({r_note})")
    else:
        print(f"pearson_r(wrench_x, stop_x) = {_fmt(r, 4)}")

    od = summary["oracle_distance_at_stop_m"]
    print(
        f"oracle_distance_at_stop_m: min={_fmt(od['min'])} max={_fmt(od['max'])} mean={_fmt(od['mean'])}"
    )

    le45 = summary["rate_oracle_le_0.45"]
    le35 = summary["rate_oracle_le_0.35"]
    print(
        f"rate_oracle_le_0.45: {le45['count']}/{le45['total']} = "
        f"{_fmt(le45['rate'], 3) if le45['rate'] is not None else 'None'}"
    )
    print(
        f"rate_oracle_le_0.35: {le35['count']}/{le35['total']} = "
        f"{_fmt(le35['rate'], 3) if le35['rate'] is not None else 'None'}"
    )

    print(f"approach_reason counts: {dict(summary['approach_reason_counts'])}")
    print(f"terminal_reason counts: {dict(summary['terminal_reason_counts'])}")
    print(f"success_count: {summary['success_count']}/{summary['n_episodes']}")
    print()


def print_compare(summary_a: dict[str, Any], summary_b: dict[str, Any]) -> None:
    print("=== compare ===")
    print(f"A: {summary_a['run_dir']}")
    print(f"B: {summary_b['run_dir']}")
    print()

    def line(label: str, a: str, b: str) -> None:
        print(f"{label:<28} A={a:<24} B={b}")

    sa, sb = summary_a["stop_x_m"], summary_b["stop_x_m"]
    line(
        "stop_x mean +/- std",
        f"{_fmt(sa['mean'])} +/- {_fmt(sa['stdev'])}",
        f"{_fmt(sb['mean'])} +/- {_fmt(sb['stdev'])}",
    )

    ra, rb = summary_a["pearson_r_wrench_x_vs_stop_x"], summary_b["pearson_r_wrench_x_vs_stop_x"]
    ra_str = _fmt(ra, 4) if ra is not None else f"None ({summary_a['pearson_r_note']})"
    rb_str = _fmt(rb, 4) if rb is not None else f"None ({summary_b['pearson_r_note']})"
    line("pearson_r(wrench_x, stop_x)", ra_str, rb_str)

    le45a, le45b = summary_a["rate_oracle_le_0.45"], summary_b["rate_oracle_le_0.45"]
    line(
        "rate_oracle_le_0.45",
        f"{le45a['count']}/{le45a['total']}",
        f"{le45b['count']}/{le45b['total']}",
    )

    le35a, le35b = summary_a["rate_oracle_le_0.35"], summary_b["rate_oracle_le_0.35"]
    line(
        "rate_oracle_le_0.35",
        f"{le35a['count']}/{le35a['total']}",
        f"{le35b['count']}/{le35b['total']}",
    )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze stop position vs target position for a closed-loop sweep."
    )
    parser.add_argument("--run-dir", required=True, type=Path, help="Sweep output directory")
    parser.add_argument(
        "--compare", type=Path, default=None, help="Second sweep output directory for comparison"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="JSON output path (default: <run-dir>/stop_position_analysis.json)"
    )
    args = parser.parse_args()

    run_dir: Path = args.run_dir
    out_path: Path = args.out if args.out is not None else (run_dir / "stop_position_analysis.json")

    summary = summarize(run_dir)
    print_report(summary)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"(wrote {out_path})")

    if args.compare is not None:
        compare_dir: Path = args.compare
        compare_out = compare_dir / "stop_position_analysis.json"
        compare_summary = summarize(compare_dir)
        print()
        print_report(compare_summary)
        compare_out.write_text(json.dumps(compare_summary, indent=2))
        print(f"(wrote {compare_out})")
        print()
        print_compare(summary, compare_summary)


if __name__ == "__main__":
    main()
