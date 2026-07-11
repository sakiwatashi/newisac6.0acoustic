"""Offline adjudicator for the D2 formal three-arm experiment (2-D
multilateration closed-loop approach).

Pre-registered criteria (docs/plan_v2/D2V2_DESIGN_2026-07-10.md §3, written
before the formal run; this script is their only computation site):

  d2_loc_y_tracking    : closed r(y_hat, y_true) >= 0.9
  d2_loc_x_tracking    : closed r(x_hat, x_true) >= 0.95
  d2_stop2d_beats_blind: closed stop_err_2d RMSE < blind's AND Welch t p<0.05
  d2_posture_clean     : zero posture/sensor-pose/IK violations, all arms

Usage:
    python3 scripts/analyze_d2v2.py --scan-dir runtime/outputs/v2_d2v2_formal
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib

ARMS = ("closed", "blind", "open")


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def _welch(a, b):
    na, nb = len(a), len(b)
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    t = (ma - mb) / math.sqrt(va / na + vb / nb)
    df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    # normal approximation for p (df ~ 30+): one-sided
    z = abs(t)
    p = 0.5 * math.erfc(z / math.sqrt(2))
    return t, df, p


def _paired_permutation_p(diffs, n_perm=100000, seed=20260712):
    """Paired sign-flip permutation test (one-sided, mean(closed-blind)<0).
    Supplementary robustness check -- the PRE-REGISTERED test remains Welch
    (adjudication unchanged); this addresses the paired design (same seeds/
    targets across arms) with an exact-in-spirit, distribution-free method."""
    import random as _rnd
    rng = _rnd.Random(seed)
    obs = sum(diffs) / len(diffs)
    hits = 0
    for _ in range(n_perm):
        v = sum(d if rng.random() < 0.5 else -d for d in diffs) / len(diffs)
        if v <= obs:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def _f(r, k):
    try:
        return float(r.get(k, "nan"))
    except (TypeError, ValueError):
        return float("nan")


def main(scan_dir: str) -> None:
    scan = pathlib.Path(scan_dir)
    stats = {}
    for arm in ARMS:
        path = scan / arm / "episodes.csv"
        rows = list(csv.DictReader(path.open()))
        errs = [_f(r, "stop_err_2d") for r in rows if math.isfinite(_f(r, "stop_err_2d"))]
        rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
        invalid = sum(1 for r in rows if str(r.get("episode_valid", "")).lower() != "true")
        reasons = {}
        for r in rows:
            reasons[r.get("reason", "?")] = reasons.get(r.get("reason", "?"), 0) + 1
        stats[arm] = {"n": len(rows), "errs": errs, "rmse": rmse,
                      "invalid": invalid, "reasons": reasons, "rows": rows}

    c = stats["closed"]["rows"]
    loc = [(_f(r, "x_hat"), _f(r, "y_hat"), _f(r, "target_x"), _f(r, "target_y"))
           for r in c if math.isfinite(_f(r, "x_hat"))]
    r_x = _pearson([p[0] for p in loc], [p[2] for p in loc])
    r_y = _pearson([p[1] for p in loc], [p[3] for p in loc])
    ex = [p[0] - p[2] for p in loc]
    ey = [p[1] - p[3] for p in loc]
    rmse_x = math.sqrt(sum(e * e for e in ex) / len(ex))
    rmse_y = math.sqrt(sum(e * e for e in ey) / len(ey))

    t, df, p = _welch(stats["closed"]["errs"], stats["blind"]["errs"])
    diffs = [a - b for a, b in zip(stats["closed"]["errs"], stats["blind"]["errs"])]
    p_perm = _paired_permutation_p(diffs)

    adj = {
        "d2_loc_y_tracking": bool(math.isfinite(r_y) and r_y >= 0.9),
        "d2_loc_x_tracking": bool(math.isfinite(r_x) and r_x >= 0.95),
        "d2_stop2d_beats_blind": bool(stats["closed"]["rmse"] < stats["blind"]["rmse"] and p < 0.05),
        "d2_posture_clean": all(stats[a]["invalid"] == 0 for a in ARMS),
    }

    print(f"{'arm':<8}{'n':>4}{'stop_err_2d RMSE':>18}{'invalid':>9}   reasons")
    for arm in ARMS:
        s = stats[arm]
        print(f"{arm:<8}{s['n']:>4}{s['rmse']:>17.4f}m{s['invalid']:>9}   {s['reasons']}")
    print()
    print(f"closed localization: r(x_hat,x)={r_x:.4f} (RMSE {rmse_x*100:.2f} cm)  "
          f"r(y_hat,y)={r_y:.4f} (RMSE {rmse_y*100:.2f} cm)  n={len(loc)}")
    p_disp = f"{p:.3e}" if p > 1e-6 else "<1e-6(常態近似,勿引用其精確值)"
    print(f"closed vs blind stop_err_2d: Welch t={t:.2f} df={df:.1f} p(one-sided)={p_disp}")
    print(f"INFO 成對置換檢定(佐證,同 seed 配對設計): p={p_perm:.2e}"
          f"(預註冊判準仍為 Welch,裁定不變)")
    print()
    for k, v in adj.items():
        print(f"ADJUDICATION {k}: {v}")

    out = {"arms": {a: {k: v for k, v in stats[a].items() if k not in ("rows", "errs")} for a in ARMS},
           "r_x": r_x, "r_y": r_y, "rmse_x_m": rmse_x, "rmse_y_m": rmse_y,
           "welch_t": t, "welch_p_one_sided": p,
           "paired_permutation_p_one_sided": p_perm, "adjudication": adj}
    with (scan / "d2_summary.json").open("w") as f:
        json.dump(out, f, indent=1)
    print(f"-> {scan/'d2_summary.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-dir", required=True)
    a = ap.parse_args()
    main(a.scan_dir)
