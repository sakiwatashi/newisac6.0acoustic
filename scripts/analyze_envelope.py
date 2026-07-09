#!/usr/bin/env python3
"""Offline analyzer for the V2 S1 sensing-envelope scan.

Spec source: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md §5.3 (analyzer) and §6
(S1 block definitions + pre-registered adjudication criteria). Reads the
per-cell `cell_result.json` files written by scripts/paired_capture_runner.py
(one per `<scan-dir>/<cell_id>/cell_result.json`), and produces:

    <scan-dir>/cells.csv             one row per cell: all cell input fields
                                      + snr_peak/snr_energy + the three
                                      conditions' peak_idx/early_energy
    <scan-dir>/envelope_summary.json  the same content, structured, plus the
                                      pre-registered adjudication verdicts
    <scan-dir>/heatmap_p<P>_c<C>.png  one distance x size SNR heatmap per
                                      (pitch, clutter) combination present in
                                      the data (best-effort; skipped with a
                                      warning if matplotlib is unavailable)

Pre-registered criteria (§6, fixed *before* looking at data):
    - SNR_peak > snr_threshold (default 10.0)  => cell is "detectable".
    - Block D cells all failing the criterion   => wrist-mounted horizontal
      mount is not viable ("腕載水平構型不可行"); Stage 2 must change mount
      configuration.
    - All 52 cells failing the criterion        => stop-loss point #1: the
      thesis is downgraded to "WPM characterization + negative result" and
      Stage 2 does not proceed.

This script is pure stdlib + numpy for the data path; matplotlib is optional
(heatmaps degrade gracefully to a printed warning, never a crash). Missing or
corrupt cell_result.json files are recorded in a `missing` list rather than
raising.

Usage
-----
    python3 scripts/analyze_envelope.py --scan-dir runtime/outputs/v2_s1_envelope
    python3 scripts/analyze_envelope.py --scan-dir DIR --snr-threshold 10.0 --out DIR/envelope_summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from collections import defaultdict

CSV_FIELDS = [
    "cell_id", "block",
    "target_distance_m", "target_size_m", "sensor_pitch_deg", "clutter",
    "sensor_pos_x_m", "sensor_pos_y_m", "sensor_pos_z_m", "notes",
    "snr_peak", "snr_energy",
    "peak_idx_with", "early_energy_with",
    "peak_idx_without", "early_energy_without",
    "peak_idx_noise", "early_energy_noise",
    "detectable",
]


def block_of(cell_id: str) -> str:
    """Block letter is the cell_id prefix before the first underscore."""
    return cell_id.split("_", 1)[0]


def _get_condition(result: dict, key: str) -> dict:
    return result.get(key, {}) or {}


def load_cell_result(path: pathlib.Path, snr_threshold: float) -> dict:
    """Parse one cell_result.json into a flat row. Raises on bad JSON/schema;
    caller is responsible for catching and routing to `missing`."""
    with path.open() as f:
        result = json.load(f)

    cell_id = result["cell_id"]
    sensor_pos = result.get("sensor_pos_m", [None, None, None])
    sensor_pos = list(sensor_pos) + [None] * (3 - len(sensor_pos))

    with_cond = _get_condition(result, "with_target")
    without_cond = _get_condition(result, "without_target")
    noise_cond = _get_condition(result, "noise_ref")

    snr_peak = result.get("snr_peak")
    try:
        detectable = bool(snr_peak is not None and float(snr_peak) > snr_threshold)
    except (TypeError, ValueError):
        detectable = False

    # Stationarity audit (runner writes stationarity_ok since 2026-07-08).
    # The noise floor max|with - noise_ref| already CONTAINS any drift, so
    # snr_peak is computed against a drift-inflated (conservative) floor:
    # - drift + snr comfortably above threshold  -> "detectable" is safe
    #   (drift only made the SNR estimate smaller); keep verdict, annotate.
    # - drift + snr at/below ~3x threshold       -> cannot distinguish
    #   "undetectable" from "not settled": INVALID, re-run larger --n-settle.
    # (Measured 2026-07-08: some geometries, e.g. d=0.8/z=0.20, oscillate
    # persistently — drift grows with settle=80 — yet snr_peak stays ~244.)
    stationarity_ok = bool(result.get("stationarity_ok", True))
    measurement_invalid = False
    if not stationarity_ok:
        try:
            safe_despite_drift = snr_peak is not None and float(snr_peak) > 3.0 * snr_threshold
        except (TypeError, ValueError):
            safe_despite_drift = False
        if not safe_despite_drift:
            detectable = False
            measurement_invalid = True

    row = {
        "cell_id": cell_id,
        "block": block_of(cell_id),
        "target_distance_m": result.get("target_distance_m"),
        "target_size_m": result.get("target_size_m"),
        "sensor_pitch_deg": result.get("sensor_pitch_deg"),
        "clutter": result.get("clutter"),
        "sensor_pos_x_m": sensor_pos[0],
        "sensor_pos_y_m": sensor_pos[1],
        "sensor_pos_z_m": sensor_pos[2],
        "notes": result.get("notes", ""),
        "snr_peak": snr_peak,
        "snr_energy": result.get("snr_energy"),
        "peak_idx_with": with_cond.get("peak_sample_idx"),
        "early_energy_with": with_cond.get("early_energy"),
        "peak_idx_without": without_cond.get("peak_sample_idx"),
        "early_energy_without": without_cond.get("early_energy"),
        "peak_idx_noise": noise_cond.get("peak_sample_idx"),
        "early_energy_noise": noise_cond.get("early_energy"),
        "energy_drift_rel": result.get("energy_drift_rel"),
        "stationarity_ok": stationarity_ok,
        "measurement_invalid": measurement_invalid,
        "detectable": detectable,
    }
    return row


def collect_rows(scan_dir: pathlib.Path, snr_threshold: float) -> tuple[list[dict], list[dict]]:
    """Walk <scan_dir>/*/cell_result.json. Returns (rows, missing) where
    `missing` entries are {"path": str, "reason": str} for anything that
    could not be parsed (file absent, bad JSON, missing required key)."""
    rows: list[dict] = []
    missing: list[dict] = []

    if not scan_dir.is_dir():
        return rows, missing

    for sub in sorted(scan_dir.iterdir()):
        if not sub.is_dir():
            continue
        result_path = sub / "cell_result.json"
        if not result_path.exists():
            missing.append({"path": str(result_path), "reason": "cell_result.json not found"})
            continue
        try:
            rows.append(load_cell_result(result_path, snr_threshold))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            missing.append({"path": str(result_path), "reason": f"{type(exc).__name__}: {exc}"})

    return rows, missing


def write_csv(rows: list[dict], out_path: pathlib.Path) -> None:
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def fmt_snr(v) -> str:
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "nan"


def print_block_tables(rows: list[dict]) -> None:
    by_block: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_block[row["block"]].append(row)

    for block in sorted(by_block):
        block_rows = sorted(
            by_block[block],
            key=lambda r: (
                r.get("target_distance_m") or 0,
                r.get("target_size_m") or 0,
                r.get("sensor_pitch_deg") or 0,
            ),
        )
        print(f"\n=== Block {block} ({len(block_rows)} cells) ===")
        hdr = f"{'cell_id':<28} {'d(m)':>6} {'z(m)':>6} {'p(deg)':>7} {'clutter':<10} {'snr_peak':>10}  ok"
        print(hdr)
        print("-" * len(hdr))
        for r in block_rows:
            mark = "✓" if r["detectable"] else "✗"
            print(f"{r['cell_id']:<28} {r.get('target_distance_m',''):>6} "
                  f"{r.get('target_size_m',''):>6} {r.get('sensor_pitch_deg',''):>7} "
                  f"{r.get('clutter',''):<10} {fmt_snr(r.get('snr_peak')):>10}  {mark}")


def summarize(rows: list[dict], missing: list[dict], snr_threshold: float) -> dict:
    by_block: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_block[row["block"]].append(row)

    block_summary = {}
    for block, block_rows in by_block.items():
        n_detect = sum(1 for r in block_rows if r["detectable"])
        block_summary[block] = {
            "n_cells": len(block_rows),
            "n_detectable": n_detect,
            "detectable_cell_ids": [r["cell_id"] for r in block_rows if r["detectable"]],
        }

    detectable_all = [r["cell_id"] for r in rows if r["detectable"]]

    block_d_rows = by_block.get("D", [])
    block_d_all_fail = len(block_d_rows) > 0 and all(not r["detectable"] for r in block_d_rows)

    all_cells_fail = len(rows) > 0 and all(not r["detectable"] for r in rows)

    return {
        "snr_threshold": snr_threshold,
        "n_cells_total": len(rows),
        "n_missing": len(missing),
        "missing": missing,
        "block_summary": block_summary,
        "detectable_cell_ids": detectable_all,
        "adjudication": {
            "block_D_all_fail": block_d_all_fail,
            "all_cells_fail": all_cells_fail,
        },
    }


def print_summary(summary: dict) -> None:
    print("\n=== Summary (per block, detectable / total) ===")
    for block in sorted(summary["block_summary"]):
        bs = summary["block_summary"][block]
        print(f"  Block {block}: {bs['n_detectable']}/{bs['n_cells']} detectable")

    print(f"\nGlobally detectable cells ({len(summary['detectable_cell_ids'])}):")
    if summary["detectable_cell_ids"]:
        for cid in summary["detectable_cell_ids"]:
            print(f"  - {cid}")
    else:
        print("  (none)")

    if summary["missing"]:
        print(f"\nMissing/unreadable cells ({len(summary['missing'])}):")
        for m in summary["missing"]:
            print(f"  - {m['path']}: {m['reason']}")

    print("\n=== Pre-registered adjudication (docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md §6) ===")
    print(f"ADJUDICATION block_D_all_fail: {summary['adjudication']['block_D_all_fail']}")
    print(f"ADJUDICATION all_cells_fail: {summary['adjudication']['all_cells_fail']}")


def make_heatmaps(rows: list[dict], scan_dir: pathlib.Path, snr_threshold: float) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("\nWARNING: matplotlib (or numpy) not available; skipping heatmaps.", file=sys.stderr)
        return

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        pitch = r.get("sensor_pitch_deg")
        clutter = r.get("clutter")
        if pitch is None or clutter is None:
            continue
        groups[(pitch, clutter)].append(r)

    if not groups:
        print("\nWARNING: no rows with pitch/clutter available; skipping heatmaps.", file=sys.stderr)
        return

    for (pitch, clutter), grp_rows in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        distances = sorted({r["target_distance_m"] for r in grp_rows if r["target_distance_m"] is not None})
        sizes = sorted({r["target_size_m"] for r in grp_rows if r["target_size_m"] is not None})
        if not distances or not sizes:
            continue

        grid = np.full((len(sizes), len(distances)), np.nan)
        for r in grp_rows:
            d = r["target_distance_m"]
            z = r["target_size_m"]
            snr = r.get("snr_peak")
            if d is None or z is None or snr is None:
                continue
            try:
                snr_f = float(snr)
            except (TypeError, ValueError):
                continue
            i = sizes.index(z)
            j = distances.index(d)
            grid[i, j] = snr_f

        plot_grid = np.where(grid > 0, grid, np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            log_grid = np.log10(plot_grid)

        fig, ax = plt.subplots(figsize=(1.4 * len(distances) + 2, 1.4 * len(sizes) + 2))
        im = ax.imshow(log_grid, cmap="viridis", aspect="auto", origin="lower")

        for i in range(len(sizes)):
            for j in range(len(distances)):
                val = grid[i, j]
                if np.isnan(val):
                    text = "n/a"
                else:
                    text = f"{val:.1f}"
                color = "white" if (not np.isnan(val) and val > snr_threshold) else "black"
                ax.text(j, i, text, ha="center", va="center", color=color, fontsize=9)

        ax.set_xticks(range(len(distances)))
        ax.set_xticklabels([f"{d:g}" for d in distances])
        ax.set_yticks(range(len(sizes)))
        ax.set_yticklabels([f"{z:g}" for z in sizes])
        ax.set_xlabel("target_distance_m")
        ax.set_ylabel("target_size_m")
        clutter_safe = str(clutter).replace("_", "")
        ax.set_title(f"snr_peak (log10) — pitch={pitch} deg, clutter={clutter}")
        fig.colorbar(im, ax=ax, label="log10(snr_peak)")
        fig.tight_layout()

        out_path = scan_dir / f"heatmap_p{int(pitch)}_c{clutter_safe}.png"
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        print(f"wrote {out_path}")


def run(scan_dir: pathlib.Path, snr_threshold: float, out_path: pathlib.Path) -> dict:
    rows, missing = collect_rows(scan_dir, snr_threshold)

    csv_path = scan_dir / "cells.csv"
    scan_dir.mkdir(parents=True, exist_ok=True)
    write_csv(rows, csv_path)
    print(f"wrote {csv_path} ({len(rows)} rows)")

    print_block_tables(rows)
    summary = summarize(rows, missing, snr_threshold)
    print_summary(summary)

    with out_path.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {out_path}")

    make_heatmaps(rows, scan_dir, snr_threshold)

    return summary


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline analyzer for the V2 S1 sensing-envelope scan.")
    parser.add_argument("--scan-dir", type=str, required=True,
                         help="Directory containing one <cell_id>/cell_result.json subdirectory per cell")
    parser.add_argument("--snr-threshold", type=float, default=10.0,
                         help="SNR_peak threshold for 'detectable' (default 10.0, per §6)")
    parser.add_argument("--out", type=str, default=None,
                         help="Output summary JSON path (default <scan-dir>/envelope_summary.json)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    scan_dir = pathlib.Path(args.scan_dir)
    out_path = pathlib.Path(args.out) if args.out else scan_dir / "envelope_summary.json"
    run(scan_dir, args.snr_threshold, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
