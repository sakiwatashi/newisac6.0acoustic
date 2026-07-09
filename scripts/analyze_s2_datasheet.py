"""Offline analyzer for scripts/s2_datasheet_runner.py output.

Full spec: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 6, "S2: datasheet".
stdlib + numpy only; matplotlib is optional (figure generation is best-effort
and never crashes the run if matplotlib is unavailable or a plot fails).

Pre-registered criteria (rule 4-3, written BEFORE any of this is run against
real data -- see scripts/s2_datasheet_runner.py's own header for the same
text):

    distance_r_ge_0.95      : Pearson r(peak_idx, true_distance_3d_m), over
                              the combined p1-p3 distance passes (rows with
                              stationarity_ok == False excluded and listed),
                              >= 0.95.
    lateral_monotonic_ge_0.9: |Spearman rho(balance, y_offset_m)| >= 0.9 over
                              the 13-point lateral sweep.
    repeat_cv_lt_5pct       : CV(early_energy) = std/mean over the 10 repeat
                              trials of the same point < 0.05 (5%).

The distance_tableh pass (--target-height table) is analyzed with the same
regression but is INFORMATIONAL ONLY (not part of the pre-registered
adjudication) -- it exists to sanity-check that the distance encoding still
holds when the target sits on the table instead of on the boresight axis.

Expected directory layout under --scan-dir (as written by
s2_datasheet_runner.py):

    distance_p1/points.csv, distance_p2/points.csv, distance_p3/points.csv
    distance_tableh/points.csv       (--target-height table pass; informational)
    lateral/points.csv
    repeat_r01/point.json .. repeat_rNN/point.json   (>= 2 for CV; 10 expected)

Usage
-----
    python3 scripts/analyze_s2_datasheet.py --scan-dir runtime/outputs/v2_s2_datasheet
    python3 scripts/analyze_s2_datasheet.py --self-test   # synthetic smoke test, no real data needed
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import shutil
import tempfile
from collections import Counter

import numpy as np

N_EARLY = 20
V_SOUND = 343.0

DISTANCE_R_THRESHOLD = 0.95
LATERAL_RHO_THRESHOLD = 0.9
REPEAT_CV_THRESHOLD = 0.05


# ── Small stdlib/numpy-only statistics helpers (no scipy) ────────────────────
def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Ordinary least squares y = slope*x + intercept. Returns (slope,
    intercept, pearson_r). NaNs if fewer than 2 finite points or zero
    variance in x."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if x.size < 2:
        return float("nan"), float("nan"), float("nan")
    xm, ym = float(np.mean(x)), float(np.mean(y))
    sxx = float(np.sum((x - xm) ** 2))
    if sxx <= 0.0:
        return float("nan"), float("nan"), float("nan")
    sxy = float(np.sum((x - xm) * (y - ym)))
    slope = sxy / sxx
    intercept = ym - slope * xm
    if np.std(x) > 0 and np.std(y) > 0:
        r = float(np.corrcoef(x, y)[0, 1])
    else:
        r = float("nan")
    return slope, intercept, r


def _rankdata(v: np.ndarray) -> np.ndarray:
    """Average-tie ranks (1-indexed), the same convention scipy.stats.rankdata
    uses with method='average'. Implemented by hand (no scipy dependency)."""
    v = np.asarray(v, dtype=float)
    n = v.size
    order = np.argsort(v, kind="mergesort")
    sorted_v = v[order]
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j < n - 1 and sorted_v[j + 1] == sorted_v[i]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if x.size < 2:
        return float("nan")
    rx = _rankdata(x)
    ry = _rankdata(y)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def _rmse(residuals: np.ndarray) -> float:
    residuals = np.asarray(residuals, dtype=float)
    residuals = residuals[np.isfinite(residuals)]
    if residuals.size == 0:
        return float("nan")
    return float(math.sqrt(float(np.mean(residuals ** 2))))


# ── CSV / JSON loading ─────────────────────────────────────────────────────────
def _read_points_csv(path: pathlib.Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def _to_float(v, default=float("nan")) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


# ── Distance-pass analysis ─────────────────────────────────────────────────────
def _analyze_distance_rows(rows: list[dict], label: str) -> dict:
    excluded_idx = [r.get("point_index") for r in rows if not _to_bool(r.get("stationarity_ok", "True"))]
    kept = [r for r in rows if _to_bool(r.get("stationarity_ok", "True"))]

    peak_idx = np.array([_to_float(r.get("peak_sample_idx")) for r in kept])
    true_dist = np.array([_to_float(r.get("true_distance_3d_m")) for r in kept])

    slope, intercept, r = _ols(true_dist, peak_idx)  # peak_idx vs true_distance_3d_m

    t_cal_s = float("nan")
    if math.isfinite(slope) and slope != 0.0:
        t_cal_s = 2.0 / (slope * V_SOUND)

    predicted_dist = np.full_like(true_dist, float("nan"))
    if math.isfinite(slope) and slope != 0.0 and math.isfinite(intercept):
        predicted_dist = (peak_idx - intercept) / slope
    residuals = true_dist - predicted_dist
    rmse_m = _rmse(residuals)

    return {
        "label": label,
        "n_total": len(rows),
        "n_kept": len(kept),
        "n_excluded_drift": len(excluded_idx),
        "excluded_point_indices": excluded_idx,
        "slope_sample_per_m": slope,
        "intercept_samples": intercept,
        "pearson_r": r,
        "t_cal_s": t_cal_s,
        "t_cal_us": t_cal_s * 1e6 if math.isfinite(t_cal_s) else float("nan"),
        "distance_rmse_m": rmse_m,
    }


def _load_distance_dirs(scan_dir: pathlib.Path) -> tuple[dict[str, list[dict]], list[dict] | None]:
    """Return (main_passes {label: rows}, tableh_rows_or_None)."""
    main_passes: dict[str, list[dict]] = {}
    tableh_rows: list[dict] | None = None
    for d in sorted(scan_dir.glob("distance_*")):
        csv_path = d / "points.csv"
        if not csv_path.exists():
            continue
        rows = _read_points_csv(csv_path)
        if d.name == "distance_tableh":
            tableh_rows = rows
        else:
            main_passes[d.name] = rows
    return main_passes, tableh_rows


def _analyze_distance(scan_dir: pathlib.Path) -> dict:
    main_passes, tableh_rows = _load_distance_dirs(scan_dir)

    per_pass: dict[str, dict] = {}
    combined_rows: list[dict] = []
    for name, rows in sorted(main_passes.items()):
        per_pass[name] = _analyze_distance_rows(rows, name)
        combined_rows.extend(rows)

    combined = _analyze_distance_rows(combined_rows, "combined_p1_p3") if combined_rows else {
        "label": "combined_p1_p3", "n_total": 0, "n_kept": 0, "n_excluded_drift": 0,
        "excluded_point_indices": [], "slope_sample_per_m": float("nan"),
        "intercept_samples": float("nan"), "pearson_r": float("nan"),
        "t_cal_s": float("nan"), "t_cal_us": float("nan"), "distance_rmse_m": float("nan"),
    }

    tableh = _analyze_distance_rows(tableh_rows, "distance_tableh") if tableh_rows else None

    return {
        "combined": combined,
        "per_pass": per_pass,
        "tableh": tableh,
    }


# ── Lateral analysis ────────────────────────────────────────────────────────────
def _analyze_lateral(scan_dir: pathlib.Path) -> dict:
    csv_path = scan_dir / "lateral" / "points.csv"
    if not csv_path.exists():
        return {"n_total": 0, "n_kept": 0, "spearman_rho": float("nan")}
    rows = _read_points_csv(csv_path)
    excluded_idx = [r.get("point_index") for r in rows if not _to_bool(r.get("stationarity_ok", "True"))]
    kept = [r for r in rows if _to_bool(r.get("stationarity_ok", "True"))]

    y = np.array([_to_float(r.get("y_offset_m")) for r in kept])
    balance = np.array([_to_float(r.get("balance")) for r in kept])
    rho = _spearman(balance, y)

    return {
        "n_total": len(rows),
        "n_kept": len(kept),
        "n_excluded_drift": len(excluded_idx),
        "excluded_point_indices": excluded_idx,
        "spearman_rho": rho,
    }


# ── Repeat analysis ─────────────────────────────────────────────────────────────
def _analyze_repeat(scan_dir: pathlib.Path) -> dict:
    repeat_dirs = sorted(scan_dir.glob("repeat_*"))
    peak_idxs: list[float] = []
    early_energies: list[float] = []
    pass_ids: list[str] = []
    for d in repeat_dirs:
        p = d / "point.json"
        if not p.exists():
            continue
        with p.open() as f:
            rec = json.load(f)
        peak_idxs.append(_to_float(rec.get("peak_sample_idx")))
        early_energies.append(_to_float(rec.get("early_energy")))
        pass_ids.append(rec.get("pass_id", d.name))

    peak_arr = np.array(peak_idxs, dtype=float)
    peak_arr = peak_arr[np.isfinite(peak_arr)]
    early_arr = np.array(early_energies, dtype=float)
    early_arr = early_arr[np.isfinite(early_arr)]

    if peak_arr.size:
        rounded = [int(round(v)) for v in peak_arr]
        mode_val, mode_count = Counter(rounded).most_common(1)[0]
        peak_range = float(np.max(peak_arr) - np.min(peak_arr))
    else:
        mode_val, mode_count = None, 0
        peak_range = float("nan")

    if early_arr.size >= 2 and np.mean(early_arr) != 0:
        cv = float(np.std(early_arr, ddof=1) / abs(np.mean(early_arr)))
    else:
        cv = float("nan")

    return {
        "n_trials": len(repeat_dirs),
        "n_valid": int(peak_arr.size),
        "peak_idx_mode": mode_val,
        "peak_idx_mode_count": mode_count,
        "peak_idx_range": peak_range,
        "early_energy_cv": cv,
    }


# ── Optional plotting (best-effort, never crashes) ─────────────────────────────
def _plot_distance(scan_dir: pathlib.Path, main_passes: dict[str, list[dict]], combined: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    try:
        fig, ax = plt.subplots(figsize=(6, 4.5))
        for name, rows in sorted(main_passes.items()):
            x = [_to_float(r.get("true_distance_3d_m")) for r in rows]
            y = [_to_float(r.get("peak_sample_idx")) for r in rows]
            ax.scatter(x, y, label=name, s=18)
        slope = combined.get("slope_sample_per_m", float("nan"))
        intercept = combined.get("intercept_samples", float("nan"))
        if math.isfinite(slope) and math.isfinite(intercept):
            all_x = [_to_float(r.get("true_distance_3d_m")) for rows in main_passes.values() for r in rows]
            all_x = [v for v in all_x if math.isfinite(v)]
            if all_x:
                xs = np.linspace(min(all_x), max(all_x), 50)
                ax.plot(xs, slope * xs + intercept, "k--", label="OLS fit")
        ax.set_xlabel("true_distance_3d_m")
        ax.set_ylabel("peak_sample_idx")
        ax.set_title("S2 distance encoding")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(scan_dir / "distance_fit.png", dpi=120)
        plt.close(fig)
    except Exception:
        return


def _plot_lateral(scan_dir: pathlib.Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    csv_path = scan_dir / "lateral" / "points.csv"
    if not csv_path.exists():
        return
    try:
        rows = _read_points_csv(csv_path)
        y = [_to_float(r.get("y_offset_m")) for r in rows]
        balance = [_to_float(r.get("balance")) for r in rows]
        fig, ax = plt.subplots(figsize=(6, 4.5))
        ax.plot(y, balance, "o-")
        ax.set_xlabel("y_offset_m")
        ax.set_ylabel("balance = (rx0_early - rx1_early) / (rx0_early + rx1_early)")
        ax.set_title("S2 lateral encoding")
        fig.tight_layout()
        fig.savefig(scan_dir / "lateral_curve.png", dpi=120)
        plt.close(fig)
    except Exception:
        return


# ── Main analysis entry point ───────────────────────────────────────────────────
def run_analysis(scan_dir: pathlib.Path) -> dict:
    main_passes, _tableh_rows = _load_distance_dirs(scan_dir)
    distance = _analyze_distance(scan_dir)
    lateral = _analyze_lateral(scan_dir)
    repeat = _analyze_repeat(scan_dir)

    combined_r = distance["combined"]["pearson_r"]
    adjudication_distance = bool(math.isfinite(combined_r) and combined_r >= DISTANCE_R_THRESHOLD)

    lateral_rho = lateral.get("spearman_rho", float("nan"))
    adjudication_lateral = bool(math.isfinite(lateral_rho) and abs(lateral_rho) >= LATERAL_RHO_THRESHOLD)

    repeat_cv = repeat.get("early_energy_cv", float("nan"))
    adjudication_repeat = bool(math.isfinite(repeat_cv) and repeat_cv < REPEAT_CV_THRESHOLD)

    table_height_r = float("nan")
    if distance["tableh"] is not None:
        table_height_r = distance["tableh"]["pearson_r"]

    t_cal_us = distance["combined"]["t_cal_us"]

    print(f"{'pass':<18} {'n_kept':>7} {'r':>8} {'slope(smp/m)':>13} {'rmse_m':>9} {'t_cal_us':>10}")
    for name, stats in sorted(distance["per_pass"].items()):
        print(f"{name:<18} {stats['n_kept']:>7} {stats['pearson_r']:>8.4f} "
              f"{stats['slope_sample_per_m']:>13.3f} {stats['distance_rmse_m']:>9.4f} "
              f"{stats['t_cal_us']:>10.3f}")
    c = distance["combined"]
    print(f"{'combined_p1_p3':<18} {c['n_kept']:>7} {c['pearson_r']:>8.4f} "
          f"{c['slope_sample_per_m']:>13.3f} {c['distance_rmse_m']:>9.4f} {c['t_cal_us']:>10.3f}")
    if distance["tableh"] is not None:
        th = distance["tableh"]
        print(f"{'distance_tableh':<18} {th['n_kept']:>7} {th['pearson_r']:>8.4f} "
              f"{th['slope_sample_per_m']:>13.3f} {th['distance_rmse_m']:>9.4f} {th['t_cal_us']:>10.3f}")
    print()
    print(f"lateral: n_kept={lateral.get('n_kept', 0)}  spearman_rho={lateral_rho:.4f}")
    print(f"repeat : n_trials={repeat.get('n_trials', 0)}  n_valid={repeat.get('n_valid', 0)}  "
          f"peak_idx_mode={repeat.get('peak_idx_mode')}  peak_idx_range={repeat.get('peak_idx_range')}  "
          f"early_energy_cv={repeat_cv:.4f}")
    print()
    print(f"ADJUDICATION distance_r_ge_0.95: {adjudication_distance}")
    print(f"ADJUDICATION lateral_monotonic_ge_0.9: {adjudication_lateral}")
    print(f"ADJUDICATION repeat_cv_lt_5pct: {adjudication_repeat}")
    print(f"INFO table_height_r: {table_height_r}")
    print(f"INFO T_cal_us: {t_cal_us}")

    _plot_distance(scan_dir, main_passes, distance["combined"])
    _plot_lateral(scan_dir)

    summary = {
        "scan_dir": str(scan_dir),
        "distance": distance,
        "lateral": lateral,
        "repeat": repeat,
        "adjudication": {
            "distance_r_ge_0.95": adjudication_distance,
            "lateral_monotonic_ge_0.9": adjudication_lateral,
            "repeat_cv_lt_5pct": adjudication_repeat,
        },
        "info": {
            "table_height_r": table_height_r,
            "t_cal_us": t_cal_us,
        },
        "thresholds": {
            "distance_r": DISTANCE_R_THRESHOLD,
            "lateral_rho": LATERAL_RHO_THRESHOLD,
            "repeat_cv": REPEAT_CV_THRESHOLD,
        },
    }
    with (scan_dir / "datasheet_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n-> datasheet_summary.json saved under {scan_dir}")
    return summary


# ── Synthetic self-test ─────────────────────────────────────────────────────────
def _write_synthetic_distance_pass(dir_path: pathlib.Path, pass_id: str, slope: float,
                                    intercept: float, noise_std: float, n_points: int = 20,
                                    seed: int = 0, flag_last: bool = False) -> None:
    rng = np.random.default_rng(seed)
    dir_path.mkdir(parents=True, exist_ok=True)
    distances = np.linspace(0.15, 1.20, n_points)
    rows = []
    for i, d in enumerate(distances):
        peak_idx = slope * d + intercept + rng.normal(0, noise_std)
        stationarity_ok = True
        if flag_last and i == n_points - 1:
            stationarity_ok = False
        rows.append({
            "point_index": i,
            "nominal_distance_m": d,
            "true_distance_3d_m": d,
            "target_x_m": d, "target_y_m": 0.0, "target_z_m": 0.65,
            "peak_sample_idx": peak_idx,
            "early_energy": 1000.0 / (d + 0.1),
            "rx0_early": 500.0, "rx1_early": 500.0,
            "point_drift": 0.01,
            "stationarity_ok": stationarity_ok,
            "waveform_tag": f"point_{i:02d}",
        })
    with (dir_path / "points.csv").open("w", newline="") as f:
        fieldnames = list(rows[0].keys())
        writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(rows)


def _write_synthetic_lateral(scan_dir: pathlib.Path, n_points: int = 13, seed: int = 1) -> None:
    """Writes into scan_dir/lateral/points.csv (matching s2_datasheet_runner.py's
    layout, where lateral mode has no pass-id sub-directory)."""
    rng = np.random.default_rng(seed)
    dir_path = scan_dir / "lateral"
    dir_path.mkdir(parents=True, exist_ok=True)
    ys = np.linspace(-0.15, 0.15, n_points)
    rows = []
    for i, y in enumerate(ys):
        balance = -y / 0.15 + rng.normal(0, 0.02)  # monotonic decreasing in y
        rows.append({
            "point_index": i,
            "y_offset_m": y,
            "target_x_m": 0.5, "target_y_m": y, "target_z_m": 0.65,
            "rx0_early": 500.0 * (1 + balance),
            "rx1_early": 500.0 * (1 - balance),
            "balance": balance,
            "peak_sample_idx": 100.0,
            "point_drift": 0.01,
            "stationarity_ok": True,
            "waveform_tag": f"point_{i:02d}",
        })
    with (dir_path / "points.csv").open("w", newline="") as f:
        fieldnames = list(rows[0].keys())
        writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(rows)


def _write_synthetic_repeat(scan_dir: pathlib.Path, n_trials: int = 10, seed: int = 2) -> None:
    rng = np.random.default_rng(seed)
    for i in range(n_trials):
        d = scan_dir / f"repeat_r{i+1:02d}"
        d.mkdir(parents=True, exist_ok=True)
        rec = {
            "point_index": 0,
            "nominal_distance_m": 0.5,
            "peak_sample_idx": 132.0 + rng.normal(0, 0.3),
            "early_energy": 900.0 + rng.normal(0, 5.0),  # CV well under 5%
            "rx0_early": 450.0, "rx1_early": 450.0,
            "point_drift": 0.01,
            "stationarity_ok": True,
            "waveform_tag": "point_00",
            "pass_id": f"r{i+1:02d}",
        }
        with (d / "point.json").open("w") as f:
            json.dump(rec, f, indent=2)


def _self_test() -> None:
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="s2_datasheet_selftest_"))
    print(f"=== analyze_s2_datasheet.py self-test (synthetic data in {tmp_dir}) ===")
    try:
        # Known ground truth: peak_idx = 200*d + 20 (slope=200 samples/m),
        # low noise -> expect r very close to 1.0 and distance_r_ge_0.95 True.
        for pid, seed in (("p1", 10), ("p2", 11), ("p3", 12)):
            _write_synthetic_distance_pass(tmp_dir / f"distance_{pid}", pid,
                                            slope=200.0, intercept=20.0, noise_std=0.5, seed=seed)
        _write_synthetic_distance_pass(tmp_dir / "distance_tableh", "tableh",
                                        slope=200.0, intercept=20.0, noise_std=0.5, seed=13)
        _write_synthetic_lateral(tmp_dir)
        _write_synthetic_repeat(tmp_dir)

        summary = run_analysis(tmp_dir)

        assert summary["adjudication"]["distance_r_ge_0.95"] is True, "self-test expected distance r >= 0.95"
        assert summary["adjudication"]["lateral_monotonic_ge_0.9"] is True, "self-test expected |rho| >= 0.9"
        assert summary["adjudication"]["repeat_cv_lt_5pct"] is True, "self-test expected CV < 5%"
        expected_t_cal_us = (2.0 / (200.0 * V_SOUND)) * 1e6
        got_t_cal_us = summary["info"]["t_cal_us"]
        assert abs(got_t_cal_us - expected_t_cal_us) < 0.05 * expected_t_cal_us, (
            f"self-test T_cal_us mismatch: got {got_t_cal_us}, expected ~{expected_t_cal_us}"
        )
        print("\nSELF-TEST PASSED")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"(cleaned up {tmp_dir})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline analyzer for S2 datasheet sweeps.")
    parser.add_argument("--scan-dir", type=str, default=None,
                         help="Directory containing distance_*/lateral/repeat_* sub-directories")
    parser.add_argument("--self-test", action="store_true",
                         help="Run a synthetic-data smoke test instead of analyzing --scan-dir")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return

    if not args.scan_dir:
        raise SystemExit("--scan-dir is required unless --self-test is given")
    scan_dir = pathlib.Path(args.scan_dir)
    if not scan_dir.exists():
        raise SystemExit(f"--scan-dir {scan_dir} does not exist")
    run_analysis(scan_dir)


if __name__ == "__main__":
    main()
