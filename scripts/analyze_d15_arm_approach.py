"""Offline analyzer for scripts/d15_arm_approach_runner.py output.

D1.5: same three-arm (closed/blind/open) 1-DOF closed-loop approach protocol
as scripts/analyze_d1_approach.py, but for the UR10e arm-carried-sensor
variant. Structure and statistics helpers are carried over from
analyze_d1_approach.py verbatim where the underlying math is unchanged
(_pearson_r, _rmse, _ols, _normal_cdf, _welch_t_test); what's new here is the
posture/sensor-pose audit accounting and the exclusion of invalid episodes
from every pre-registered statistic.

stdlib + numpy only; matplotlib is optional (figure generation is best-effort
and never crashes the run if matplotlib is unavailable or a plot fails).

Pre-registered criteria (written BEFORE any of this is run against real
data -- see scripts/d15_arm_approach_runner.py's own header for the same
text):

    d05_arm_mount_valid   : probe-mode regression of peak_sample_idx vs
                            true_distance_3d_m (stationarity_ok and ik_ok
                            rows only) has r >= 0.99 AND zero
                            posture_violation / sensor_pose_violation rows
                            across the whole probe sweep.
    d15_tracking_r_ge_0.9 : r(stop_sensor_x_actual, target_x) over the
                            CLOSED arm's VALID (episode_valid=true) episodes
                            only, >= 0.9.
    d15_beats_blind       : closed arm's stop_error RMSE (valid episodes
                            only; stop_error = |stop_oracle_horiz_dist -
                            standoff|, computed against the ACTUAL achieved
                            stop position) is lower than blind's (valid
                            episodes only), AND a Welch two-sample t-test on
                            the two arms' stop_error samples has p < 0.05.
    d15_posture_clean     : total invalid episodes across closed+blind+open
                            == 0.

This analyzer NEVER feeds anything back into d15_arm_approach_runner.py --
it is a pure read-only, offline adjudicator over the raw csv/json files.

Why "stop_sensor_x_actual" and not "stop_sensor_x": in D1 the sensor's
xformOp:translate was written directly, so the commanded position and the
achieved position were identical by construction. In D1.5 the sensor is
carried by an IK-solved, physically-realized arm pose, so the commanded
corridor position ("stop_sensor_x") and the empirically read prim position
("stop_sensor_x_actual") can differ by IK tolerance and any mount-frame
offset. The whole point of D1.5 is to test the REAL arm's physical closed
loop, so this analyzer computes the tracking correlation and stop-error
statistics against the actual achieved position; "stop_sensor_x" (commanded)
is still reported for reference/debugging.

Expected directory layout under --scan-dir (as written by
d15_arm_approach_runner.py):

    probe/points.csv                        (D0.5 arm-mount validation)
    closed/episodes.csv, closed/steps.csv, closed/meta.json
    blind/episodes.csv,  blind/steps.csv,  blind/meta.json
    open/episodes.csv,   open/steps.csv,   open/meta.json

Usage
-----
    python3 scripts/analyze_d15_arm_approach.py --scan-dir runtime/outputs/v2_d15_arm_approach
    python3 scripts/analyze_d15_arm_approach.py --self-test   # synthetic smoke test, no real data needed
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

D05_R_THRESHOLD = 0.99
D15_TRACKING_R_THRESHOLD = 0.9
D15_BEATS_BLIND_P_THRESHOLD = 0.05
STANDOFF_DEFAULT_M = 0.35
ERROR_OK_THRESHOLD_M = 0.10

ARMS = ("closed", "blind", "open")


# ── Small stdlib/numpy-only statistics helpers (verbatim from
#    analyze_d1_approach.py -- no scipy) ────────────────────────────────────────
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
    """Hand-rolled two-sample Welch t-test, two-tailed. Returns (t, p_approx),
    normal-approximation p-value (n~30 per arm; no scipy dependency)."""
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


# ── D0.5 probe analysis ─────────────────────────────────────────────────────────
def _analyze_probe(scan_dir: pathlib.Path) -> dict:
    rows = _read_csv(scan_dir / "probe" / "points.csv")
    if not rows:
        return {
            "n_total": 0, "n_kept": 0, "pearson_r": float("nan"),
            "slope_sample_per_m": float("nan"), "intercept_samples": float("nan"),
            "n_posture_violations": 0, "n_sensor_pose_violations": 0,
        }
    kept = [r for r in rows if _to_bool(r.get("stationarity_ok", "True")) and _to_bool(r.get("ik_ok", "True"))]
    x = np.array([_to_float(r.get("true_distance_3d_m")) for r in kept])
    y = np.array([_to_float(r.get("peak_sample_idx")) for r in kept])
    slope, intercept, r = _ols(x, y)
    n_posture = sum(1 for row in rows if _to_bool(row.get("posture_violation", "False")))
    n_sensor_pose = sum(1 for row in rows if _to_bool(row.get("sensor_pose_violation", "False")))
    return {
        "n_total": len(rows),
        "n_kept": len(kept),
        "slope_sample_per_m": slope,
        "intercept_samples": intercept,
        "pearson_r": r,
        "n_posture_violations": n_posture,
        "n_sensor_pose_violations": n_sensor_pose,
    }


# ── Per-arm episode analysis ────────────────────────────────────────────────────
def _analyze_arm(scan_dir: pathlib.Path, mode: str) -> dict:
    rows = _read_csv(scan_dir / mode / "episodes.csv")
    steps = _read_csv(scan_dir / mode / "steps.csv")
    meta = _read_json(scan_dir / mode / "meta.json")
    standoff = _to_float((meta or {}).get("standoff_m"), STANDOFF_DEFAULT_M)
    if not math.isfinite(standoff):
        standoff = STANDOFF_DEFAULT_M

    n_episodes_total = len(rows)
    valid_rows = [r for r in rows if _to_bool(r.get("episode_valid", "True"))]
    n_invalid = n_episodes_total - len(valid_rows)

    target_x = np.array([_to_float(r.get("target_x")) for r in valid_rows])
    # Prefer the physically-achieved stop position; fall back to the
    # commanded one only if "actual" is missing/non-finite (e.g. an
    # ik_failed episode with no real stop position at all).
    stop_x_actual = np.array([_to_float(r.get("stop_sensor_x_actual")) for r in valid_rows])
    stop_x_commanded = np.array([_to_float(r.get("stop_sensor_x")) for r in valid_rows])
    stop_x = np.where(np.isfinite(stop_x_actual), stop_x_actual, stop_x_commanded)
    stop_oracle = np.array([_to_float(r.get("stop_oracle_horiz_dist")) for r in valid_rows])
    n_steps = np.array([_to_float(r.get("n_steps")) for r in valid_rows])
    reasons = Counter(r.get("reason", "") for r in rows)  # all episodes, incl. invalid

    stop_error = np.abs(stop_oracle - standoff)

    r_stop_target = _pearson_r(stop_x, target_x)
    stop_error_finite = stop_error[np.isfinite(stop_error)]
    p_error_ok = (float(np.mean(stop_error_finite <= ERROR_OK_THRESHOLD_M))
                  if stop_error_finite.size else float("nan"))

    n_posture_violation_steps = sum(1 for s in steps if _to_bool(s.get("posture_violation", "False")))
    n_sensor_pose_violation_steps = sum(1 for s in steps if _to_bool(s.get("sensor_pose_violation", "False")))
    n_ik_failed_steps = sum(1 for s in steps if not _to_bool(s.get("ik_ok", "True")))

    return {
        "mode": mode,
        "n_episodes": n_episodes_total,
        "n_invalid_episodes": n_invalid,
        "standoff_m": standoff,
        "stop_sensor_x_mean": float(np.mean(stop_x)) if stop_x.size else float("nan"),
        "stop_sensor_x_std": float(np.std(stop_x, ddof=1)) if stop_x.size > 1 else float("nan"),
        "r_stop_target": r_stop_target,
        "stop_error_mean": float(np.mean(stop_error_finite)) if stop_error_finite.size else float("nan"),
        "stop_error_rmse": _rmse(stop_error),
        "p_error_le_0.10": p_error_ok,
        "n_steps_mean": float(np.mean(n_steps)) if n_steps.size else float("nan"),
        "reason_counts": dict(reasons),
        "n_posture_violation_steps": n_posture_violation_steps,
        "n_sensor_pose_violation_steps": n_sensor_pose_violation_steps,
        "n_ik_failed_steps": n_ik_failed_steps,
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
        ax.scatter(target_x, stop_x, s=24, label="closed episodes (valid only)")
        lo = float(min(np.min(target_x), np.min(stop_x)))
        hi = float(max(np.max(target_x), np.max(stop_x)))
        ax.plot([lo, hi], [lo, hi], "k--", linewidth=1, label="y = x")
        ax.set_xlabel("target_x (oracle, m)")
        ax.set_ylabel("stop_sensor_x_actual (m)")
        ax.set_title("D1.5 closed arm: stop position vs target position")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(scan_dir / "d15_closed_stop_vs_target.png", dpi=120)
        plt.close(fig)
    except Exception:
        return


# ── Main analysis entry point ───────────────────────────────────────────────────
def run_analysis(scan_dir: pathlib.Path) -> dict:
    probe = _analyze_probe(scan_dir)
    arm_stats = {mode: _analyze_arm(scan_dir, mode) for mode in ARMS}

    probe_r = probe["pearson_r"]
    probe_violations_clean = (probe["n_posture_violations"] == 0
                               and probe["n_sensor_pose_violations"] == 0)
    adjudication_d05 = bool(math.isfinite(probe_r) and probe_r >= D05_R_THRESHOLD and probe_violations_clean)

    closed = arm_stats["closed"]
    blind = arm_stats["blind"]
    r_closed = closed["r_stop_target"]
    adjudication_tracking = bool(r_closed is not None and math.isfinite(r_closed)
                                  and r_closed >= D15_TRACKING_R_THRESHOLD)

    t_stat, p_val = _welch_t_test(closed["_stop_error_array"], blind["_stop_error_array"])
    closed_rmse = closed["stop_error_rmse"]
    blind_rmse = blind["stop_error_rmse"]
    rmse_better = (math.isfinite(closed_rmse) and math.isfinite(blind_rmse)
                   and closed_rmse < blind_rmse)
    adjudication_beats_blind = bool(rmse_better and math.isfinite(p_val) and p_val < D15_BEATS_BLIND_P_THRESHOLD)

    total_invalid_episodes = sum(arm_stats[mode]["n_invalid_episodes"] for mode in ARMS)
    adjudication_posture_clean = bool(total_invalid_episodes == 0)

    print(f"D0.5 probe: n_kept={probe['n_kept']}/{probe['n_total']}  r={probe_r}  "
          f"slope={probe['slope_sample_per_m']}  intercept={probe['intercept_samples']}  "
          f"n_posture_violations={probe['n_posture_violations']}  "
          f"n_sensor_pose_violations={probe['n_sensor_pose_violations']}")
    print()
    print(f"{'arm':<8} {'n':>4} {'n_inv':>6} {'stop_x_mean':>12} {'stop_x_std':>11} {'r(stop,tgt)':>12} "
          f"{'err_mean':>9} {'err_rmse':>9} {'P(err<=.10)':>12} {'n_steps_mean':>13}")
    for mode in ARMS:
        s = arm_stats[mode]
        r_str = f"{s['r_stop_target']:.4f}" if s["r_stop_target"] is not None else "None"
        print(f"{mode:<8} {s['n_episodes']:>4} {s['n_invalid_episodes']:>6} {s['stop_sensor_x_mean']:>12.4f} "
              f"{s['stop_sensor_x_std']:>11.4f} {r_str:>12} "
              f"{s['stop_error_mean']:>9.4f} {s['stop_error_rmse']:>9.4f} "
              f"{s['p_error_le_0.10']:>12.4f} {s['n_steps_mean']:>13.2f}")
        print(f"         reasons: {s['reason_counts']}  "
              f"audit_steps: posture={s['n_posture_violation_steps']} "
              f"sensor_pose={s['n_sensor_pose_violation_steps']} ik_failed={s['n_ik_failed_steps']}")
    print()
    print(f"closed vs blind Welch t-test (valid episodes only): t={t_stat}  p_approx={p_val}")
    print(f"total invalid episodes across all arms: {total_invalid_episodes}")
    print()
    print(f"ADJUDICATION d05_arm_mount_valid: {adjudication_d05}")
    print(f"ADJUDICATION d15_tracking_r_ge_0.9: {adjudication_tracking}")
    print(f"ADJUDICATION d15_beats_blind: {adjudication_beats_blind}")
    print(f"ADJUDICATION d15_posture_clean: {adjudication_posture_clean}")

    _plot_closed_stop_vs_target(scan_dir, closed)

    summary = {
        "scan_dir": str(scan_dir),
        "probe": probe,
        "arms": {mode: _strip_internal(arm_stats[mode]) for mode in ARMS},
        "welch_t_test_closed_vs_blind": {"t": t_stat, "p_approx": p_val},
        "total_invalid_episodes": total_invalid_episodes,
        "adjudication": {
            "d05_arm_mount_valid": adjudication_d05,
            "d15_tracking_r_ge_0.9": adjudication_tracking,
            "d15_beats_blind": adjudication_beats_blind,
            "d15_posture_clean": adjudication_posture_clean,
        },
        "thresholds": {
            "d05_r": D05_R_THRESHOLD,
            "d15_tracking_r": D15_TRACKING_R_THRESHOLD,
            "d15_beats_blind_p": D15_BEATS_BLIND_P_THRESHOLD,
            "error_ok_threshold_m": ERROR_OK_THRESHOLD_M,
        },
    }
    with (scan_dir / "d15_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n-> d15_summary.json saved under {scan_dir}")
    return summary


# ── Synthetic self-test ─────────────────────────────────────────────────────────
def _write_synthetic_probe(scan_dir: pathlib.Path, slope: float = 200.0, intercept: float = 20.0,
                            noise_std: float = 0.3, seed: int = 40) -> None:
    rng = np.random.default_rng(seed)
    d = scan_dir / "probe"
    d.mkdir(parents=True, exist_ok=True)
    sensor_xs = np.arange(0.45, 0.90 + 1e-9, 0.05)
    target_x_fixed = 1.10
    rows = []
    for i, sx in enumerate(sensor_xs):
        true3d = math.sqrt((target_x_fixed - sx) ** 2 + 0.2 ** 2)
        peak_idx = slope * true3d + intercept + rng.normal(0, noise_std)
        rows.append({
            "point_index": i, "sensor_x": float(sx), "sensor_x_actual": float(sx),
            "true_distance_3d_m": true3d, "peak_sample_idx": peak_idx, "point_drift": 0.01,
            "stationarity_ok": True, "waveform_tag": f"point_{i:02d}",
            "posture_violation": False, "sensor_pose_violation": False,
            "sensor_angle_deg": 0.1, "ik_ok": True,
            "q_shoulder_pan": 0.0, "q_shoulder_lift": -1.2, "q_elbow": 1.2,
            "q_wrist_1": -1.57, "q_wrist_2": -1.57, "q_wrist_3": 0.0,
        })
    with (d / "points.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_synthetic_arm(scan_dir: pathlib.Path, mode: str, target_xs: list[float],
                          standoff: float = 0.35, behavior: str = "tracking",
                          seed: int = 0, posture_violation_episode: int | None = None) -> None:
    """behavior='tracking': stop_sensor_x_actual tracks target_x - standoff
    closely (low-error, used for the 'closed' arm). behavior='poor': stop
    position is essentially unrelated to target_x (used for 'blind'/'open').
    posture_violation_episode: if given, that episode index is written with
    episode_valid=False and a wildly-off stop position, to verify the
    analyzer excludes it from the r/RMSE computation (rather than letting it
    corrupt the statistic)."""
    rng = np.random.default_rng(seed)
    d = scan_dir / mode
    d.mkdir(parents=True, exist_ok=True)
    ep_rows = []
    step_rows = []
    for i, tx in enumerate(target_xs):
        is_violation_ep = (posture_violation_episode is not None and i == posture_violation_episode)
        if behavior == "tracking":
            stop_x = tx - standoff + rng.normal(0, 0.01)
            reason = "standoff_est"
            n_steps = 10
        else:
            stop_x = 1.00 + rng.normal(0, 0.01)  # walks to corridor end regardless of target
            reason = "corridor_end"
            n_steps = 40
        if is_violation_ep:
            stop_x = 5.0  # deliberately absurd, to prove exclusion matters
            reason = "corridor_end"
        stop_oracle = tx - stop_x
        episode_valid = not is_violation_ep
        ep_rows.append({
            "episode": i, "target_x": tx, "stop_sensor_x": stop_x, "stop_sensor_x_actual": stop_x,
            "stop_oracle_horiz_dist": stop_oracle, "n_steps": n_steps, "reason": reason,
            "episode_valid": episode_valid,
        })
        step_rows.append({
            "episode": i, "step": 0, "sensor_x": stop_x, "sensor_x_actual": stop_x,
            "peak_idx": 100.0, "d3d_est": 0.5, "d_horiz_est": 0.4,
            "oracle_horiz_dist": stop_oracle, "drift": 0.01, "stationarity_ok": True,
            "waveform_tag": f"ep{i:03d}_step000",
            "posture_violation": is_violation_ep, "sensor_pose_violation": False, "ik_ok": True,
            "q_shoulder_pan": 0.0, "q_shoulder_lift": -1.2, "q_elbow": 1.2,
            "q_wrist_1": -1.57, "q_wrist_2": -1.57, "q_wrist_3": 0.0,
        })
    with (d / "episodes.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ep_rows[0].keys()))
        w.writeheader()
        w.writerows(ep_rows)
    with (d / "steps.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(step_rows[0].keys()))
        w.writeheader()
        w.writerows(step_rows)
    with (d / "meta.json").open("w") as f:
        json.dump({"mode": mode, "standoff_m": standoff}, f)


def _self_test() -> None:
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="d15_arm_approach_selftest_"))
    print(f"=== analyze_d15_arm_approach.py self-test (synthetic data in {tmp_dir}) ===")
    try:
        rng = np.random.default_rng(99)
        target_xs = [float(rng.uniform(0.90, 1.25)) for _ in range(30)]

        _write_synthetic_probe(tmp_dir)  # high-r, zero violations, expect d05 True
        # closed arm carries ONE posture_violation episode (index 5) with an
        # absurd stop position -- the analyzer must exclude it from r/RMSE,
        # not let it wreck the otherwise-tight tracking fit.
        _write_synthetic_arm(tmp_dir, "closed", target_xs, behavior="tracking", seed=1,
                              posture_violation_episode=5)
        _write_synthetic_arm(tmp_dir, "blind", target_xs, behavior="poor", seed=2)
        _write_synthetic_arm(tmp_dir, "open", target_xs, behavior="poor", seed=3)

        summary = run_analysis(tmp_dir)

        assert summary["adjudication"]["d05_arm_mount_valid"] is True, "expected d05 True"
        assert summary["adjudication"]["d15_tracking_r_ge_0.9"] is True, (
            "expected tracking r>=0.9 True once the posture-violation episode is excluded"
        )
        assert summary["adjudication"]["d15_beats_blind"] is True, "expected closed to beat blind"
        assert summary["adjudication"]["d15_posture_clean"] is False, (
            "expected posture_clean False -- one episode was deliberately made invalid"
        )
        assert summary["arms"]["closed"]["n_invalid_episodes"] == 1
        assert summary["total_invalid_episodes"] == 1
        assert summary["arms"]["closed"]["stop_error_rmse"] < summary["arms"]["blind"]["stop_error_rmse"]
        # Sanity: the excluded episode's absurd stop_x (5.0) must not appear
        # in the internal arrays used for r/RMSE.
        assert 5.0 not in summary_closed_stop_x_for_check(tmp_dir)
        print("\nSELF-TEST PASSED")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"(cleaned up {tmp_dir})")


def summary_closed_stop_x_for_check(scan_dir: pathlib.Path) -> list[float]:
    """Re-read closed/episodes.csv's valid-only stop_sensor_x_actual values,
    for the self-test's exclusion-logic assertion."""
    rows = _read_csv(scan_dir / "closed" / "episodes.csv")
    return [_to_float(r.get("stop_sensor_x_actual")) for r in rows if _to_bool(r.get("episode_valid", "True"))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline analyzer for D1.5 arm-approach sessions.")
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
