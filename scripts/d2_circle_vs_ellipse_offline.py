#!/usr/bin/env python3
"""Offline D2 geometry: circle (monostatic) vs bistatic ellipse under 0.10 m mounts.

Zero GPU. Uses:
  - runtime/outputs/v2_d2v2_formal/closed/{steps,episodes}.csv  (if present)
  - Synthetic grid over the formal target box × formal vantages

Mount model (matches rtx_acoustic_factory dual-mount):
  m001 at sensor origin s
  m002 at s + (MOUNT_SPACING, 0, 0) in world when sensor faces +X (D2 level)
  Bistatic path L = |p - s| + |p - (s + (0.1,0,0))|
  Ellipse residual uses L; monostatic circle uses R = |p - s|

Empirical range_est in D2 is OLS-mapped peak → treated as monostatic 3D range
in the formal runner. This script answers:
  1) How large is (L/2 - R) in the D2 workspace?
  2) If measurements were perfect L/2 but we still circle-intersect with R_hat=L/2,
     how much localization bias?
  3) On formal closed data, how well does range_est match R vs L/2?

Writes: runtime/outputs/d2_circle_vs_ellipse/metrics.json
        docs-oriented printout
"""
from __future__ import annotations

import csv
import json
import math
import pathlib
import sys

import numpy as np

MOUNT_SPACING_M = 0.10
HEIGHT_DIFF_M = 0.20  # D2 formal: tool/sensor z vs table target (see runner)
# Formal D2 vantages (sensor x,y); z not needed for 2D plane after horiz convert
VANTAGE_YS = (-0.15, -0.075, 0.0, 0.075, 0.15)
SENSOR_X = 0.60
TARGET_Z = 0.45
SENSOR_Z = 0.65  # approx; HEIGHT_DIFF used for horiz

REPO = pathlib.Path(__file__).resolve().parents[1]


def _ols(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size < 2:
        return float("nan"), float("nan"), float("nan")
    xm, ym = x.mean(), y.mean()
    sxx = float(np.sum((x - xm) ** 2))
    if sxx <= 0:
        return float("nan"), float("nan"), float("nan")
    slope = float(np.sum((x - xm) * (y - ym)) / sxx)
    intercept = float(ym - slope * xm)
    r = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else float("nan")
    return slope, intercept, r


def _horiz(r3d: float, hdiff: float = HEIGHT_DIFF_M) -> float:
    if not math.isfinite(r3d):
        return float("nan")
    return math.sqrt(max(r3d * r3d - hdiff * hdiff, 1e-12))


def _mono_R(s, p) -> float:
    return float(np.linalg.norm(np.asarray(p) - np.asarray(s)))


def _bistatic_L(s, p, spacing: float = MOUNT_SPACING_M) -> float:
    s = np.asarray(s, float)
    p = np.asarray(p, float)
    s_rx = s + np.array([spacing, 0.0, 0.0])
    return float(np.linalg.norm(p - s) + np.linalg.norm(p - s_rx))


def trilat_circle(vantages_xy, h_ranges, x0, y0):
    """Same Gauss-Newton as d2v2_formal_runner._trilat_solve (2D)."""
    pts = [(v, h) for v, h in zip(vantages_xy, h_ranges) if math.isfinite(h) and 0.05 < h < 5.0]
    if len(pts) < 3:
        return float("nan"), float("nan"), float("nan")
    x, y = x0, y0
    for _ in range(25):
        JtJ = [[0.0, 0.0], [0.0, 0.0]]
        Jtr = [0.0, 0.0]
        for (vx, vy), h in pts:
            dx, dy = x - vx, y - vy
            d = math.sqrt(dx * dx + dy * dy)
            if d < 1e-9:
                continue
            r = d - h
            gx, gy = dx / d, dy / d
            JtJ[0][0] += gx * gx
            JtJ[0][1] += gx * gy
            JtJ[1][0] += gy * gx
            JtJ[1][1] += gy * gy
            Jtr[0] += gx * r
            Jtr[1] += gy * r
        det = JtJ[0][0] * JtJ[1][1] - JtJ[0][1] * JtJ[1][0]
        if abs(det) < 1e-12:
            break
        sx = (JtJ[1][1] * Jtr[0] - JtJ[0][1] * Jtr[1]) / det
        sy = (JtJ[0][0] * Jtr[1] - JtJ[1][0] * Jtr[0]) / det
        x -= sx
        y -= sy
        if abs(sx) + abs(sy) < 1e-7:
            break
    rms = math.sqrt(
        sum((math.sqrt((x - vx) ** 2 + (y - vy) ** 2) - h) ** 2 for (vx, vy), h in pts) / len(pts)
    )
    return x, y, rms


def trilat_ellipse(vantages_xy, L_paths, x0, y0, spacing: float = MOUNT_SPACING_M):
    """Gauss-Newton on sum_i ( |p-TX_i| + |p-RX_i| - L_i )^2 in 2D plane.
    TX_i = (vx,vy), RX_i = (vx+spacing, vy) — forward-axis dual mount.
    """
    pts = [(v, L) for v, L in zip(vantages_xy, L_paths) if math.isfinite(L) and L > 0.1]
    if len(pts) < 3:
        return float("nan"), float("nan"), float("nan")
    x, y = x0, y0
    for _ in range(30):
        JtJ = [[0.0, 0.0], [0.0, 0.0]]
        Jtr = [0.0, 0.0]
        for (vx, vy), L in pts:
            # TX
            dtx = math.sqrt((x - vx) ** 2 + (y - vy) ** 2)
            # RX
            rx, ry = vx + spacing, vy
            drx = math.sqrt((x - rx) ** 2 + (y - ry) ** 2)
            if dtx < 1e-9 or drx < 1e-9:
                continue
            pred = dtx + drx
            res = pred - L
            gx = (x - vx) / dtx + (x - rx) / drx
            gy = (y - vy) / dtx + (y - ry) / drx
            JtJ[0][0] += gx * gx
            JtJ[0][1] += gx * gy
            JtJ[1][0] += gy * gx
            JtJ[1][1] += gy * gy
            Jtr[0] += gx * res
            Jtr[1] += gy * res
        det = JtJ[0][0] * JtJ[1][1] - JtJ[0][1] * JtJ[1][0]
        if abs(det) < 1e-12:
            break
        sx = (JtJ[1][1] * Jtr[0] - JtJ[0][1] * Jtr[1]) / det
        sy = (JtJ[0][0] * Jtr[1] - JtJ[1][0] * Jtr[0]) / det
        x -= sx
        y -= sy
        if abs(sx) + abs(sy) < 1e-7:
            break
    rms = 0.0
    for (vx, vy), L in pts:
        dtx = math.sqrt((x - vx) ** 2 + (y - vy) ** 2)
        drx = math.sqrt((x - vx - spacing) ** 2 + (y - vy) ** 2)
        rms += (dtx + drx - L) ** 2
    rms = math.sqrt(rms / len(pts))
    return x, y, rms


def synthetic_grid():
    """Targets like formal: x in [1.0,1.2], y in [-0.15,0.15]."""
    xs = np.linspace(1.00, 1.20, 5)
    ys = np.linspace(-0.15, 0.15, 7)
    vants = [(SENSOR_X, y) for y in VANTAGE_YS]
    rows = []
    deltas = []
    for tx in xs:
        for ty in ys:
            p = np.array([tx, ty, TARGET_Z])
            h_mono, h_halfL = [], []
            L_list = []
            for sx, sy in vants:
                s = np.array([sx, sy, SENSOR_Z])
                R = _mono_R(s, p)
                L = _bistatic_L(s, p)
                deltas.append(L / 2.0 - R)
                h_mono.append(_horiz(R))
                h_halfL.append(_horiz(L / 2.0))
                L_list.append(L)
            # seed
            x0, y0 = 1.10, 0.0
            xm, ym, rms_m = trilat_circle(vants, h_mono, x0, y0)
            # misspecified: use L/2 as if monostatic circle radius
            xh, yh, rms_h = trilat_circle(vants, h_halfL, x0, y0)
            # correct ellipse with true L
            xe, ye, rms_e = trilat_ellipse(vants, L_list, x0, y0)
            rows.append(
                dict(
                    tx=tx,
                    ty=ty,
                    err_mono_circle=math.hypot(xm - tx, ym - ty),
                    err_halfL_as_circle=math.hypot(xh - tx, yh - ty),
                    err_ellipse=math.hypot(xe - tx, ye - ty),
                    xm=xm,
                    ym=ym,
                    xh=xh,
                    yh=yh,
                    xe=xe,
                    ye=ye,
                )
            )
    d = np.asarray(deltas)
    return rows, dict(
        n_delta=int(d.size),
        delta_L2_minus_R_mean_m=float(d.mean()),
        delta_L2_minus_R_std_m=float(d.std()),
        delta_L2_minus_R_min_m=float(d.min()),
        delta_L2_minus_R_max_m=float(d.max()),
        delta_abs_max_m=float(np.max(np.abs(d))),
        rmse_loc_mono_circle_m=float(np.sqrt(np.mean([r["err_mono_circle"] ** 2 for r in rows]))),
        rmse_loc_halfL_as_circle_m=float(
            np.sqrt(np.mean([r["err_halfL_as_circle"] ** 2 for r in rows]))
        ),
        rmse_loc_ellipse_m=float(np.sqrt(np.mean([r["err_ellipse"] ** 2 for r in rows]))),
        mean_err_halfL_as_circle_m=float(np.mean([r["err_halfL_as_circle"] for r in rows])),
        mean_err_ellipse_m=float(np.mean([r["err_ellipse"] for r in rows])),
    )


def formal_closed_analysis(formal_dir: pathlib.Path):
    steps_p = formal_dir / "closed" / "steps.csv"
    eps_p = formal_dir / "closed" / "episodes.csv"
    if not steps_p.exists():
        return None
    steps = list(csv.DictReader(steps_p.open()))
    eps = {int(r["episode"]): r for r in csv.DictReader(eps_p.open())}
    # group vantage rows
    by_ep: dict[int, list] = {}
    for r in steps:
        if r.get("phase") != "vantage":
            continue
        ep = int(r["episode"])
        by_ep.setdefault(ep, []).append(r)

    R_list, L2_list, est_list = [], [], []
    loc_rows = []
    for ep, rows in sorted(by_ep.items()):
        e = eps.get(ep)
        if not e:
            continue
        tx, ty = float(e["target_x"]), float(e["target_y"])
        p = np.array([tx, ty, TARGET_Z])
        vants, h_est, h_R, h_L2, Ls = [], [], [], [], []
        for r in sorted(rows, key=lambda z: int(z["step"])):
            sx, sy = float(r["sensor_x"]), float(r["sensor_y"])
            s = np.array([sx, sy, SENSOR_Z])
            R = _mono_R(s, p)
            L = _bistatic_L(s, p)
            est = float(r["range_est"])
            R_list.append(R)
            L2_list.append(L / 2.0)
            est_list.append(est)
            vants.append((sx, sy))
            h_est.append(_horiz(est))
            h_R.append(_horiz(R))
            h_L2.append(_horiz(L / 2.0))
            Ls.append(L)
        x0, y0 = 1.10, 0.0
        xe_est, ye_est, _ = trilat_circle(vants, h_est, x0, y0)
        xe_R, ye_R, _ = trilat_circle(vants, h_R, x0, y0)
        xe_h, ye_h, _ = trilat_circle(vants, h_L2, x0, y0)
        xe_e, ye_e, _ = trilat_ellipse(vants, Ls, x0, y0)
        x_hat_run, y_hat_run = float(e["x_hat"]), float(e["y_hat"])
        loc_rows.append(
            dict(
                ep=ep,
                err_run=math.hypot(x_hat_run - tx, y_hat_run - ty),
                err_re_est=math.hypot(xe_est - tx, ye_est - ty),
                err_oracle_mono=math.hypot(xe_R - tx, ye_R - ty),
                err_oracle_halfL_circle=math.hypot(xe_h - tx, ye_h - ty),
                err_oracle_ellipse=math.hypot(xe_e - tx, ye_e - ty),
            )
        )

    est = np.asarray(est_list)
    R = np.asarray(R_list)
    L2 = np.asarray(L2_list)
    # residual stats
    def res_stats(pred, name):
        e = est - pred
        return dict(
            name=name,
            n=int(e.size),
            bias_m=float(np.mean(e)),
            rmse_m=float(np.sqrt(np.mean(e**2))),
            pearson_r_est_vs_pred=float(np.corrcoef(est, pred)[0, 1]),
        )

    return dict(
        n_vantage_meas=int(est.size),
        n_episodes=len(loc_rows),
        range_vs_mono_R=res_stats(R, "range_est - R_mono"),
        range_vs_L_over_2=res_stats(L2, "range_est - L/2"),
        # which model closer?
        mean_abs_err_vs_R=float(np.mean(np.abs(est - R))),
        mean_abs_err_vs_L2=float(np.mean(np.abs(est - L2))),
        prefers_mono_R=bool(np.mean(np.abs(est - R)) <= np.mean(np.abs(est - L2))),
        loc_rmse_run_m=float(np.sqrt(np.mean([r["err_run"] ** 2 for r in loc_rows]))),
        loc_rmse_re_est_m=float(np.sqrt(np.mean([r["err_re_est"] ** 2 for r in loc_rows]))),
        loc_rmse_oracle_mono_circle_m=float(
            np.sqrt(np.mean([r["err_oracle_mono"] ** 2 for r in loc_rows]))
        ),
        loc_rmse_oracle_halfL_circle_m=float(
            np.sqrt(np.mean([r["err_oracle_halfL_circle"] ** 2 for r in loc_rows]))
        ),
        loc_rmse_oracle_ellipse_m=float(
            np.sqrt(np.mean([r["err_oracle_ellipse"] ** 2 for r in loc_rows]))
        ),
    )


def main() -> int:
    out = REPO / "runtime" / "outputs" / "d2_circle_vs_ellipse"
    out.mkdir(parents=True, exist_ok=True)

    syn_rows, syn_sum = synthetic_grid()
    formal = formal_closed_analysis(REPO / "runtime" / "outputs" / "v2_d2v2_formal")

    # Adjudication (matched observation model, not raw ToF physics alone)
    # ------------------------------------------------------------------
    # Dual-mount geometry has L = |p-TX|+|p-RX| with L/2 − R ≈ −spacing/2 on-axis
    # (~5 cm). That is large vs cm ranging — BUT V2 does not feed L/2 into D2.
    # OLS maps peak → true monostatic-like distance from sensor origin. Therefore:
    #   PASS circle if formal range_est matches R far better than L/2, and
    #   oracle monostatic circle localizes the formal targets, and
    #   feeding L/2 into circle (mismatched) is worse than matched mono circle.
    delta_max = syn_sum["delta_abs_max_m"]
    misspec_rmse = syn_sum["rmse_loc_halfL_as_circle_m"]
    ell_rmse = syn_sum["rmse_loc_ellipse_m"]
    mono_rmse = syn_sum["rmse_loc_mono_circle_m"]

    adj = {
        "geometric_L2_minus_R_abs_max_m": delta_max,
        "geometric_L2_minus_R_abs_max_cm": delta_max * 100,
        "note_geometric_bias": (
            "On-axis dual-mount along +X: L/2−R ≈ −spacing/2 = −5 cm. "
            "This is geometric, not a bug; relevant only if raw ToF used without OLS."
        ),
        "synthetic_mono_circle_rmse_m": mono_rmse,
        "synthetic_halfL_as_circle_rmse_m": misspec_rmse,
        "synthetic_ellipse_with_true_L_rmse_m": ell_rmse,
        "gate_matched_mono_circle_near_zero": bool(mono_rmse < 1e-6),
        "gate_mismatched_halfL_circle_worse": bool(misspec_rmse > mono_rmse + 0.01),
        "formal": formal,
        "circle_matched_to_OLS_observation": None,
        "recommendation": "",
    }

    formal_ok = True
    if formal:
        prefers = bool(formal["mean_abs_err_vs_R"] < formal["mean_abs_err_vs_L2"] - 0.01)
        rmse_ok = bool(formal["range_vs_mono_R"]["rmse_m"] < 0.03)
        formal_ok = prefers and rmse_ok
        adj["formal_range_prefers_mono_R"] = prefers
        adj["formal_range_vs_R_rmse_m"] = formal["range_vs_mono_R"]["rmse_m"]
        adj["formal_range_vs_L2_rmse_m"] = formal["range_vs_L_over_2"]["rmse_m"]
        adj["formal_loc_rmse_run_m"] = formal["loc_rmse_run_m"]

    adequate = (
        adj["gate_matched_mono_circle_near_zero"]
        and adj["gate_mismatched_halfL_circle_worse"]
        and (formal is None or formal_ok)
    )
    adj["circle_matched_to_OLS_observation"] = bool(adequate)
    adj["circle_approx_adequate_for_D2_workspace"] = bool(adequate)
    if adequate:
        adj["recommendation"] = (
            "KEEP circle multilateration as D2 canon. OLS range tracks monostatic R "
            f"(formal RMSE {formal['range_vs_mono_R']['rmse_m']*100:.2f} cm vs L/2 "
            f"{formal['range_vs_L_over_2']['rmse_m']*100:.2f} cm). "
            "Document geometric |L/2−R|~spacing/2 as physics footnote; do not switch "
            "to ellipse unless peak is re-interpreted as raw bistatic ToF without OLS."
        )
    else:
        adj["recommendation"] = (
            "Revisit observation model: if range_est tracks L/2, switch to ellipse; "
            "if not, re-check mount-axis assumption."
        )
    payload = {
        "mount_spacing_m": MOUNT_SPACING_M,
        "mount_axis": "sensor forward +X (m002 = m001 + (0.10,0,0))",
        "synthetic": syn_sum,
        "formal_closed": formal,
        "adjudication": adj,
        "note": "OLS maps peak→empirical monostatic-like range; ellipse uses geometric L.",
    }
    (out / "metrics.json").write_text(json.dumps(payload, indent=2))
    # brief csv of synthetic corners
    with (out / "synthetic_grid_errors.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(syn_rows[0].keys()))
        w.writeheader()
        w.writerows(syn_rows)

    print("=== D2 circle vs ellipse (offline) ===")
    print(json.dumps(syn_sum, indent=2))
    if formal:
        print("formal:", json.dumps(formal, indent=2))
    print("ADJUDICATION:", json.dumps(adj, indent=2))
    print("wrote", out / "metrics.json")
    return 0 if adequate else 1


if __name__ == "__main__":
    raise SystemExit(main())
