"""Offline analyzer + pre-registered adjudicator for D3 (end-to-end grasp).

Reads runtime/outputs/v2_d3_grasp/{closed,blind,open}/episodes.csv and
gates/g3_scaffold/g3_summary.json, prints the three-arm comparison table and
the four ADJUDICATION lines, writes d3_summary.json + a scatter plot.

Pre-registered criteria (docs/plan_v2/M3_D3_DESIGN_2026-07-10.md, amended by
docs/plan_v2/d3/decisions.md D-12/D-13, both dated BEFORE any formal run):

  d3_align_tracking   : closed arm Pearson r(grasp_center_x_actual, target_x)
                        >= 0.9 over grasp-attempted episodes.
  d3_align_beats_blind: P(aligned|closed) > P(aligned|blind) AND one-sided
                        Fisher exact p < 0.05. aligned = |align_error_x| <=
                        TOL_ALIGN_X_M (0.02, locked from the g3 capture-window
                        sweep per D-9 before the formal arms ran).
  d3_grasp_given_align: P(lift success | aligned) reported separately per arm,
                        NO threshold, never merged into a single success rate.
                        (Lift = weld-on-pinch-stall simulated attach, D-13;
                        the pinch-stall contact signal is physics-derived.)
  d3_posture_clean    : zero posture/sensor-pose violations and zero IK
                        failures across all formal episodes.

This script only ADJUDICATES; it never feeds anything back into control.

Usage:
    python3 scripts/analyze_d3_grasp.py --scan-dir runtime/outputs/v2_d3_grasp
    python3 scripts/analyze_d3_grasp.py --self-test
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import sys

TOL_ALIGN_X_M = 0.02  # locked (D-9); must match the runner's locked value
ARMS = ("closed", "blind", "open")


def _pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def _log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _fisher_exact_one_sided(a: int, b: int, c: int, d: int) -> float:
    """P(X >= a) under hypergeometric for table [[a,b],[c,d]] --
    one-sided 'closed aligns more than blind'. Pure stdlib."""
    row1, col1, n = a + b, a + c, a + b + c + d
    lo = max(0, row1 + col1 - n)
    hi = min(row1, col1)
    denom = _log_comb(n, col1)
    p = 0.0
    for x in range(a, hi + 1):
        p += math.exp(_log_comb(row1, x) + _log_comb(n - row1, col1 - x) - denom)
    return min(1.0, p)


def _mcnemar_exact_p(b: int, c: int) -> float:
    """McNemar exact (binomial) one-sided p for paired binary outcomes:
    b = closed-aligned & blind-missed pairs, c = the reverse. Supplementary
    to the pre-registered Fisher test (adjudication unchanged)."""
    n = b + c
    if n == 0:
        return 1.0
    from math import comb
    return sum(comb(n, k) for k in range(b, n + 1)) / (2 ** n)


def _load_arm(scan: pathlib.Path, arm: str) -> list[dict]:
    path = scan / arm / "episodes.csv"
    if not path.exists():
        raise SystemExit(f"missing {path} -- run the {arm} arm first (bash runtime/run_v2_d3_grasp.sh)")
    rows = []
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def _f(row: dict, key: str) -> float:
    try:
        return float(row.get(key, "nan"))
    except (TypeError, ValueError):
        return float("nan")


def _b(row: dict, key: str) -> bool:
    return str(row.get(key, "")).strip().lower() in ("true", "1")


def analyze(scan_dir: str) -> dict:
    scan = pathlib.Path(scan_dir)
    out: dict = {"tol_align_x_m": TOL_ALIGN_X_M, "arms": {}}

    # g3 gate echo
    g3_path = scan / "gates" / "g3_scaffold" / "g3_summary.json"
    if g3_path.exists():
        g3 = json.load(g3_path.open())
        out["g3"] = {"n_trials": g3.get("n_trials"), "n_lift_success": g3.get("n_success"),
                     "debug_scaffold": g3.get("debug_scaffold")}

    stats: dict[str, dict] = {}
    rows_by_arm: dict[str, list] = {}
    for arm in ARMS:
        rows = _load_arm(scan, arm)
        rows_by_arm[arm] = rows
        n = len(rows)
        attempted = [r for r in rows if math.isfinite(_f(r, "align_error_x"))]
        aligned = [r for r in attempted if abs(_f(r, "align_error_x")) <= TOL_ALIGN_X_M]
        lifted = [r for r in rows if _b(r, "grasp_lift_success")]
        lifted_given_aligned = [r for r in aligned if _b(r, "grasp_lift_success")]
        gx = [_f(r, "grasp_center_x_actual") for r in attempted]
        tx = [_f(r, "target_x") for r in attempted]
        pairs = [(g, t) for g, t in zip(gx, tx) if math.isfinite(g) and math.isfinite(t)]
        r_val = _pearson_r([p[0] for p in pairs], [p[1] for p in pairs])
        errs = [abs(_f(r, "align_error_x")) for r in attempted]
        errs = [e for e in errs if math.isfinite(e)]
        rmse = math.sqrt(sum(e * e for e in errs) / len(errs)) if errs else float("nan")
        invalid = [r for r in rows if not _b(r, "episode_valid")]
        reasons: dict[str, int] = {}
        for r in rows:
            reasons[r.get("reason", "?")] = reasons.get(r.get("reason", "?"), 0) + 1
        stats[arm] = {
            "n": n, "n_attempted": len(attempted), "n_aligned": len(aligned),
            "n_lift": len(lifted), "n_lift_given_aligned": len(lifted_given_aligned),
            "align_rate": len(aligned) / n if n else float("nan"),
            "lift_given_align": (len(lifted_given_aligned) / len(aligned)) if aligned else float("nan"),
            "r_grasp_target": r_val, "align_abs_rmse_m": rmse,
            "n_invalid": len(invalid), "reasons": reasons,
        }
    out["arms"] = stats

    # adjudications
    c, bl = stats["closed"], stats["blind"]
    a, b_ = c["n_aligned"], c["n"] - c["n_aligned"]
    cc, dd = bl["n_aligned"], bl["n"] - bl["n_aligned"]
    fisher_p = _fisher_exact_one_sided(a, b_, cc, dd)
    out["fisher_p_one_sided"] = fisher_p
    # 成對佐證:同 episode 配對之 McNemar exact
    cl_map = {int(r["episode"]): abs(_f(r, "align_error_x")) <= TOL_ALIGN_X_M
              for r in rows_by_arm["closed"] if math.isfinite(_f(r, "align_error_x"))}
    bl_map = {int(r["episode"]): abs(_f(r, "align_error_x")) <= TOL_ALIGN_X_M
              for r in rows_by_arm["blind"] if math.isfinite(_f(r, "align_error_x"))}
    b_pairs = sum(1 for e in cl_map if e in bl_map and cl_map[e] and not bl_map[e])
    c_pairs = sum(1 for e in cl_map if e in bl_map and not cl_map[e] and bl_map[e])
    out["mcnemar_exact_p_one_sided"] = _mcnemar_exact_p(b_pairs, c_pairs)

    adj = {
        "d3_align_tracking": bool(math.isfinite(c["r_grasp_target"]) and c["r_grasp_target"] >= 0.9),
        "d3_align_beats_blind": bool(c["align_rate"] > bl["align_rate"] and fisher_p < 0.05),
        "d3_posture_clean": all(stats[arm]["n_invalid"] == 0 for arm in ARMS),
    }
    out["adjudication"] = adj

    # ── print ──
    print(f"{'arm':<8}{'n':>4}{'r(grasp,tgt)':>14}{'align_rate':>12}{'|err| RMSE':>12}"
          f"{'P(lift|align)':>15}{'invalid':>9}   reasons")
    for arm in ARMS:
        s = stats[arm]
        print(f"{arm:<8}{s['n']:>4}{s['r_grasp_target']:>14.4f}"
              f"{s['align_rate']:>11.1%} {s['align_abs_rmse_m']:>11.4f}"
              f"{s['lift_given_align'] if math.isfinite(s['lift_given_align']) else float('nan'):>14.1%} "
              f"{s['n_invalid']:>8}   {s['reasons']}")
    print()
    print(f"closed vs blind aligned: {a}/{c['n']} vs {cc}/{bl['n']}  "
          f"Fisher exact (one-sided) p={fisher_p:.3e}")
    print(f"INFO McNemar exact(成對佐證,同 seed 配對): p={out['mcnemar_exact_p_one_sided']:.3e}"
          f"(預註冊判準仍為 Fisher,裁定不變)")
    if "g3" in out:
        print(f"g3 (oracle scaffold, quarantined): lift {out['g3']['n_lift_success']}/{out['g3']['n_trials']}")
    print()
    print(f"ADJUDICATION d3_align_tracking: {adj['d3_align_tracking']}")
    print(f"ADJUDICATION d3_align_beats_blind: {adj['d3_align_beats_blind']}")
    print(f"INFO d3_grasp_given_align (report-only, no threshold): "
          f"closed={c['lift_given_align'] if math.isfinite(c['lift_given_align']) else 'n/a'}")
    print(f"ADJUDICATION d3_posture_clean: {adj['d3_posture_clean']}")

    # summary + plot
    with (scan / "d3_summary.json").open("w") as f:
        json.dump(out, f, indent=1)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 5))
        colors = {"closed": "tab:blue", "blind": "tab:red", "open": "tab:gray"}
        for arm in ARMS:
            rows = _load_arm(scan, arm)
            xs = [_f(r, "target_x") for r in rows]
            ys = [_f(r, "grasp_center_x_actual") for r in rows]
            ax.scatter(xs, ys, s=18, alpha=0.7, label=arm, color=colors[arm])
        lo, hi = 0.98, 1.22
        ax.plot([lo, hi], [lo, hi], "k--", lw=0.8, label="ideal")
        ax.set_xlabel("target_x (m, oracle/eval only)")
        ax.set_ylabel("grasp_center_x_actual (m)")
        ax.set_title("D3: grasp placement vs target (three arms)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(scan / "d3_grasp_vs_target.png", dpi=130)
        print(f"\nplot -> {scan / 'd3_grasp_vs_target.png'}")
    except Exception as exc:
        print(f"(plot skipped: {exc})")
    print(f"-> d3_summary.json saved under {scan}")
    return out


def self_test() -> None:
    import random as rnd
    import tempfile
    rng = rnd.Random(7)
    with tempfile.TemporaryDirectory() as td:
        scan = pathlib.Path(td)
        fields = ["episode", "target_x", "stop_sensor_x", "d_horiz_est_stop", "n_steps", "reason",
                  "episode_valid", "bar_x_pred", "grasp_center_x_actual", "align_error_x",
                  "aligned", "bar_z_gain_m", "grasp_lift_success", "advance_ik_ok", "lift_ik_ok",
                  "grasp_pose_peak_idx"]
        for arm in ARMS:
            d = scan / arm
            d.mkdir(parents=True)
            with (d / "episodes.csv").open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                for i in range(30):
                    t = rng.uniform(1.0, 1.2)
                    if arm == "closed":
                        g = t + rng.gauss(0, 0.008)
                    elif arm == "blind":
                        g = 1.10
                    else:
                        g = 1.10
                    err = g - t
                    lift = abs(err) <= 0.015
                    w.writerow({"episode": i, "target_x": t, "stop_sensor_x": 0.8,
                                "d_horiz_est_stop": 0.35, "n_steps": 5, "reason": "standoff_est",
                                "episode_valid": True, "bar_x_pred": g,
                                "grasp_center_x_actual": g, "align_error_x": err,
                                "aligned": abs(err) <= TOL_ALIGN_X_M, "bar_z_gain_m": 0.06 if lift else 0.0,
                                "grasp_lift_success": lift, "advance_ik_ok": True,
                                "lift_ik_ok": True, "grasp_pose_peak_idx": 20})
        out = analyze(str(scan))
        assert out["adjudication"]["d3_align_tracking"], "closed r should pass in self-test"
        assert out["adjudication"]["d3_align_beats_blind"], "closed should beat blind in self-test"
        assert out["adjudication"]["d3_posture_clean"], "self-test episodes are all valid"
        # fisher sanity: identical rates must NOT be significant
        assert _fisher_exact_one_sided(15, 15, 15, 15) > 0.4
        # perfect separation must be significant
        assert _fisher_exact_one_sided(30, 0, 0, 30) < 1e-6
        print("\nSELF-TEST PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-dir", type=str, default=None,
                        help="D3 output root (contains closed/ blind/ open/ gates/)")
    parser.add_argument("--self-test", action="store_true",
                        help="run on synthetic data and assert adjudication logic")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.scan_dir:
        analyze(args.scan_dir)
    else:
        parser.error("need --scan-dir or --self-test")
        sys.exit(2)
