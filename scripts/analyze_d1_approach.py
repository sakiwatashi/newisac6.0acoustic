"""Offline analyzer for scripts/d1_approach_runner.py output.

Full spec: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 7, "D1: 1-DOF
closed-loop approach", and the D1 spec draft at the end of
docs/plan_v2/reports/S2_datasheet_report.md.
stdlib + numpy only; matplotlib is optional (figure generation is best-effort
and never crashes the run if matplotlib is unavailable or a plot fails).

Pre-registered criteria (rule 4-3, written BEFORE any of this is run against
real data -- see scripts/d1_approach_runner.py's own header for the same
text):

    d0_sensor_motion_valid : probe-mode regression of peak_sample_idx vs
                             true_distance_3d_m (sensor swept, target fixed,
                             stationarity_ok == True rows only) has r >= 0.99.
    d1_tracking_r_ge_0.9   : r(stop_sensor_x, target_x) over the CLOSED arm's
                             episodes >= 0.9.
    d1_beats_blind         : closed arm's stop_error RMSE
                             (stop_error = |stop_oracle_horiz_dist -
                             standoff|) is lower than blind's, AND a Welch
                             two-sample t-test on the two arms' stop_error
                             samples has p < 0.05 (normal approximation,
                             appropriate for n=30 per arm).

This analyzer NEVER feeds anything back into d1_approach_runner.py -- it is
a pure read-only, offline adjudicator over the raw csv/json files.

Expected directory layout under --scan-dir (as written by
d1_approach_runner.py):

    probe/points.csv                        (D0 sensor-motion validation)
    closed/episodes.csv, closed/steps.csv, closed/meta.json
    blind/episodes.csv,  blind/steps.csv,  blind/meta.json
    open/episodes.csv,   open/steps.csv,   open/meta.json

Usage
-----
    python3 scripts/analyze_d1_approach.py --scan-dir runtime/outputs/v2_d1_approach
    python3 scripts/analyze_d1_approach.py --self-test   # synthetic smoke test, no real data needed
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

D0_R_THRESHOLD = 0.99
D1_TRACKING_R_THRESHOLD = 0.9
D1_BEATS_BLIND_P_THRESHOLD = 0.05
STANDOFF_DEFAULT_M = 0.35
ERROR_OK_THRESHOLD_M = 0.10

ARMS = ("closed", "blind", "open")


# ── Small stdlib/numpy-only statistics helpers (no scipy) ────────────────────
def _pearson_r(x: np.ndarray, y: np.ndarray) -> float | None:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if x.size < 2 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _rmse(residuals: np.ndarray) -> float:
    residuals = np.asarray(residuals, dtype=float)
    residuals = residuals[np.isfinite(residuals)]
    if residuals.size == 0:
        return float("nan")
    return float(math.sqrt(float(np.mean(residuals ** 2))))


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """y = slope*x + intercept OLS fit. Returns (slope, intercept, pearson_r)."""
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
    r = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else float("nan")
    return slope, intercept, r


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _welch_t_test(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Hand-rolled two-sample Welch t-test, two-tailed. Returns (t, p_approx).
    Uses a normal approximation for the p-value (appropriate for n~30 per
    arm, per module docstring) rather than the exact Student-t distribution
    (which would need scipy)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    na, nb = a.size, b.size
    if na < 2 or nb < 2:
        return float("nan"), float("nan")
    ma, mb = float(np.mean(a)), float(np.mean(b))
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    se = math.sqrt(va / na + vb / nb)
    if se == 0.0:
        return float("nan"), float("nan")
    t = (ma - mb) / se
    p = 2.0 * (1.0 - _normal_cdf(abs(t)))
    return t, p


# ── CSV / JSON loading ─────────────────────────────────────────────────────────
def _read_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _read_json(path: pathlib.Path) -> dict | None:
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def _to_float(v, default=float("nan")) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


# ── D0 probe analysis ───────────────────────────────────────────────────────────
def _analyze_probe(scan_dir: pathlib.Path) -> dict:
    rows = _read_csv(scan_dir / "probe" / "points.csv")
    if not rows:
        return {"n_total": 0, "n_kept": 0, "pearson_r": float("nan"),
                "slope_sample_per_m": float("nan"), "intercept_samples": float("nan")}
    kept = [r for r in rows if _to_bool(r.get("stationarity_ok", "True"))]
    x = np.array([_to_float(r.get("true_distance_3d_m")) for r in kept])
    y = np.array([_to_float(r.get("peak_sample_idx")) for r in kept])
    slope, intercept, r = _ols(x, y)
    return {
        "n_total": len(rows),
        "n_kept": len(kept),
        "slope_sample_per_m": slope,
        "intercept_samples": intercept,
        "pearson_r": r,
    }


# ── Per-arm episode analysis ────────────────────────────────────────────────────
def _analyze_arm(scan_dir: pathlib.Path, mode: str) -> dict:
    rows = _read_csv(scan_dir / mode / "episodes.csv")
    meta = _read_json(scan_dir / mode / "meta.json")
    standoff = _to_float((meta or {}).get("standoff_m"), STANDOFF_DEFAULT_M)
    if not math.isfinite(standoff):
        standoff = STANDOFF_DEFAULT_M

    target_x = np.array([_to_float(r.get("target_x")) for r in rows])
    stop_x = np.array([_to_float(r.get("stop_sensor_x")) for r in rows])
    stop_oracle = np.array([_to_float(r.get("stop_oracle_horiz_dist")) for r in rows])
    n_steps = np.array([_to_float(r.get("n_steps")) for r in rows])
    reasons = Counter(r.get("reason", "") for r in rows)

    stop_error = np.abs(stop_oracle - standoff)

    r_stop_target = _pearson_r(stop_x, target_x)
    stop_error_finite = stop_error[np.isfinite(stop_error)]
    p_error_ok = (float(np.mean(stop_error_finite <= ERROR_OK_THRESHOLD_M))
                  if stop_error_finite.size else float("nan"))

    return {
        "mode": mode,
        "n_episodes": len(rows),
        "standoff_m": standoff,
        "stop_sensor_x_mean": float(np.mean(stop_x)) if stop_x.size else float("nan"),
        "stop_sensor_x_std": float(np.std(stop_x, ddof=1)) if stop_x.size > 1 else float("nan"),
        "r_stop_target": r_stop_target,
        "stop_error_mean": float(np.mean(stop_error_finite)) if stop_error_finite.size else float("nan"),
        "stop_error_rmse": _rmse(stop_error),
        "p_error_le_0.10": p_error_ok,
        "n_steps_mean": float(np.mean(n_steps)) if n_steps.size else float("nan"),
        "reason_counts": dict(reasons),
        "_stop_error_array": stop_error,  # internal use (Welch test), stripped before JSON dump
        "_stop_x_array": stop_x,
        "_target_x_array": target_x,
    }


def _strip_internal(arm_stats: dict) -> dict:
    return {k: v for k, v in arm_stats.items() if not k.startswith("_")}


# ── Optional plotting (best-effort, never crashes) ─────────────────────────────
def _plot_closed_stop_vs_target(scan_dir: pathlib.Path, closed_stats: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    try:
        stop_x = closed_stats.get("_stop_x_array")
        target_x = closed_stats.get("_target_x_array")
        if stop_x is None or target_x is None or stop_x.size == 0:
            return
        fig, ax = plt.subplots(figsize=(5.5, 5.5))
        ax.scatter(target_x, stop_x, s=24, label="closed episodes")
        lo = float(min(np.min(target_x), np.min(stop_x)))
        hi = float(max(np.max(target_x), np.max(stop_x)))
        ax.plot([lo, hi], [lo, hi], "k--", linewidth=1, label="y = x")
        ax.set_xlabel("target_x (oracle, m)")
        ax.set_ylabel("stop_sensor_x (m)")
        ax.set_title("D1 closed arm: stop position vs target position")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(scan_dir / "d1_closed_stop_vs_target.png", dpi=120)
        plt.close(fig)
    except Exception:
        return


# ── Main analysis entry point ───────────────────────────────────────────────────
def run_analysis(scan_dir: pathlib.Path) -> dict:
    probe = _analyze_probe(scan_dir)
    arm_stats = {mode: _analyze_arm(scan_dir, mode) for mode in ARMS}

    probe_r = probe["pearson_r"]
    adjudication_d0 = bool(math.isfinite(probe_r) and probe_r >= D0_R_THRESHOLD)

    closed = arm_stats["closed"]
    blind = arm_stats["blind"]
    r_closed = closed["r_stop_target"]
    adjudication_tracking = bool(r_closed is not None and math.isfinite(r_closed)
                                  and r_closed >= D1_TRACKING_R_THRESHOLD)

    t_stat, p_val = _welch_t_test(closed["_stop_error_array"], blind["_stop_error_array"])
    closed_rmse = closed["stop_error_rmse"]
    blind_rmse = blind["stop_error_rmse"]
    rmse_better = (math.isfinite(closed_rmse) and math.isfinite(blind_rmse)
                   and closed_rmse < blind_rmse)
    adjudication_beats_blind = bool(rmse_better and math.isfinite(p_val) and p_val < D1_BEATS_BLIND_P_THRESHOLD)

    print(f"D0 probe: n_kept={probe['n_kept']}/{probe['n_total']}  r={probe_r}  "
          f"slope={probe['slope_sample_per_m']}  intercept={probe['intercept_samples']}")
    print()
    print(f"{'arm':<8} {'n':>4} {'stop_x_mean':>12} {'stop_x_std':>11} {'r(stop,tgt)':>12} "
          f"{'err_mean':>9} {'err_rmse':>9} {'P(err<=.10)':>12} {'n_steps_mean':>13}")
    for mode in ARMS:
        s = arm_stats[mode]
        r_str = f"{s['r_stop_target']:.4f}" if s["r_stop_target"] is not None else "None"
        print(f"{mode:<8} {s['n_episodes']:>4} {s['stop_sensor_x_mean']:>12.4f} "
              f"{s['stop_sensor_x_std']:>11.4f} {r_str:>12} "
              f"{s['stop_error_mean']:>9.4f} {s['stop_error_rmse']:>9.4f} "
              f"{s['p_error_le_0.10']:>12.4f} {s['n_steps_mean']:>13.2f}")
        print(f"         reasons: {s['reason_counts']}")
    print()
    print(f"closed vs blind Welch t-test: t={t_stat}  p_approx={p_val}")
    print()
    print(f"ADJUDICATION d0_sensor_motion_valid: {adjudication_d0}")
    print(f"ADJUDICATION d1_tracking_r_ge_0.9: {adjudication_tracking}")
    print(f"ADJUDICATION d1_beats_blind: {adjudication_beats_blind}")

    _plot_closed_stop_vs_target(scan_dir, closed)

    summary = {
        "scan_dir": str(scan_dir),
        "probe": probe,
        "arms": {mode: _strip_internal(arm_stats[mode]) for mode in ARMS},
        "welch_t_test_closed_vs_blind": {"t": t_stat, "p_approx": p_val},
        "adjudication": {
            "d0_sensor_motion_valid": adjudication_d0,
            "d1_tracking_r_ge_0.9": adjudication_tracking,
            "d1_beats_blind": adjudication_beats_blind,
        },
        "thresholds": {
            "d0_r": D0_R_THRESHOLD,
            "d1_tracking_r": D1_TRACKING_R_THRESHOLD,
            "d1_beats_blind_p": D1_BEATS_BLIND_P_THRESHOLD,
            "error_ok_threshold_m": ERROR_OK_THRESHOLD_M,
        },
    }
    with (scan_dir / "d1_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n-> d1_summary.json saved under {scan_dir}")
    return summary


# ── Synthetic self-test ─────────────────────────────────────────────────────────
def _write_synthetic_probe(scan_dir: pathlib.Path, slope: float = 200.0, intercept: float = 20.0,
                            noise_std: float = 0.3, seed: int = 40) -> None:
    rng = np.random.default_rng(seed)
    d = scan_dir / "probe"
    d.mkdir(parents=True, exist_ok=True)
    sensor_xs = np.arange(0.0, 0.60 + 1e-9, 0.05)
    target_x_fixed = 1.0
    rows = []
    for i, sx in enumerate(sensor_xs):
        true3d = math.sqrt((target_x_fixed - sx) ** 2 + 0.2 ** 2)
        peak_idx = slope * true3d + intercept + rng.normal(0, noise_std)
        rows.append({
            "point_index": i, "sensor_x": float(sx), "true_distance_3d_m": true3d,
            "peak_sample_idx": peak_idx, "point_drift": 0.01, "stationarity_ok": True,
            "waveform_tag": f"point_{i:02d}",
        })
    with (d / "points.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_synthetic_arm(scan_dir: pathlib.Path, mode: str, target_xs: list[float],
                          standoff: float = 0.35, behavior: str = "tracking",
                          seed: int = 0) -> None:
    """behavior='tracking': stop_sensor_x tracks target_x - standoff closely
    (low-error, used for the 'closed' arm). behavior='poor': stop position is
    essentially unrelated to target_x (used for 'blind'/'open')."""
    rng = np.random.default_rng(seed)
    d = scan_dir / mode
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, tx in enumerate(target_xs):
        if behavior == "tracking":
            stop_x = tx - standoff + rng.normal(0, 0.01)
            reason = "standoff_est"
            n_steps = 10
        else:
            stop_x = 1.20 + rng.normal(0, 0.01)  # walks to corridor end regardless of target
            reason = "corridor_end"
            n_steps = 40
        stop_oracle = tx - stop_x
        rows.append({
            "episode": i, "target_x": tx, "stop_sensor_x": stop_x,
            "stop_oracle_horiz_dist": stop_oracle, "n_steps": n_steps, "reason": reason,
        })
    with (d / "episodes.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with (d / "meta.json").open("w") as f:
        json.dump({"mode": mode, "standoff_m": standoff}, f)


def _self_test() -> None:
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="d1_approach_selftest_"))
    print(f"=== analyze_d1_approach.py self-test (synthetic data in {tmp_dir}) ===")
    try:
        rng = np.random.default_rng(99)
        target_xs = [float(rng.uniform(0.45, 1.10)) for _ in range(30)]

        _write_synthetic_probe(tmp_dir)  # high-r, expect d0 True
        _write_synthetic_arm(tmp_dir, "closed", target_xs, behavior="tracking", seed=1)
        _write_synthetic_arm(tmp_dir, "blind", target_xs, behavior="poor", seed=2)
        _write_synthetic_arm(tmp_dir, "open", target_xs, behavior="poor", seed=3)

        summary = run_analysis(tmp_dir)

        assert summary["adjudication"]["d0_sensor_motion_valid"] is True, "expected d0 True"
        assert summary["adjudication"]["d1_tracking_r_ge_0.9"] is True, "expected tracking r>=0.9 True"
        assert summary["adjudication"]["d1_beats_blind"] is True, "expected closed to beat blind"
        assert summary["arms"]["closed"]["stop_error_rmse"] < summary["arms"]["blind"]["stop_error_rmse"]
        print("\nSELF-TEST PASSED")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"(cleaned up {tmp_dir})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline analyzer for D1 approach sessions.")
    parser.add_argument("--scan-dir", type=str, default=None,
                         help="Directory containing probe/closed/blind/open sub-directories")
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
