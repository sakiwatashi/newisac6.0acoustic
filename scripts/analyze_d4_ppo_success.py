#!/usr/bin/env python3
"""Recompute Track B PPO success: d_hat-based vs oracle true_range (log only).

Usage:
  python3 scripts/analyze_d4_ppo_success.py runtime/outputs/v2_d4_ppo_grasp_dhatfix/run.log
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STANDOFF_M = 0.35
TOL_M = 0.05
NEAR_M = STANDOFF_M + TOL_M


def parse_log(path: Path) -> list[dict]:
    text = path.read_text(errors="replace")
    rows: list[dict] = []
    for m in re.finditer(
        r"Learning iteration\s+(\d+)/\d+(.*?)(?=Learning iteration|\Z|Training time)",
        text,
        re.S,
    ):
        it = int(m.group(1))
        b = m.group(2)

        def g(k: str):
            mm = re.search(rf"{re.escape(k)}:\s*([-\d.]+)", b)
            return float(mm.group(1)) if mm else None

        rows.append(
            {
                "it": it,
                "reward": g("Mean reward"),
                "d_hat": g("Metrics/d_hat_xy"),
                "true": g("Metrics/true_range_m"),
                "err": g("Metrics/d_hat_abs_err"),
                "grip": g("Metrics/gripper_open"),
                "succ_dhat_log": g("Metrics/success_near_and_closed"),
                "succ_true_log": g("Metrics/success_true_near_and_closed"),
                "peak": g("Metrics/peak_sample_idx"),
            }
        )
    return rows


def near(x: float | None, thr: float = NEAR_M) -> bool:
    return x is not None and x <= thr + 1e-9


def closed(g: float | None) -> bool:
    return g is not None and g < 0.5


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_log", type=Path, help="path to train run.log")
    ap.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="optional summary json path (default: sibling success_true_vs_dhat.json)",
    )
    args = ap.parse_args()
    path = args.run_log
    if not path.exists():
        print(f"missing log: {path}", file=sys.stderr)
        return 1

    rows = parse_log(path)
    n = len(rows)
    if n == 0:
        print("no learning iterations parsed", file=sys.stderr)
        return 1

    succ_dhat_log = [r for r in rows if r["succ_dhat_log"] is not None and r["succ_dhat_log"] > 0.5]
    succ_dhat = [r for r in rows if near(r["d_hat"]) and closed(r["grip"])]
    succ_true = [r for r in rows if near(r["true"]) and closed(r["grip"])]
    fp = [r for r in rows if near(r["d_hat"]) and closed(r["grip"]) and not near(r["true"])]
    fn = [r for r in rows if near(r["true"]) and closed(r["grip"]) and not (near(r["d_hat"]) and closed(r["grip"]))]
    dhat_near = [r for r in rows if near(r["d_hat"])]
    true_near = [r for r in rows if near(r["true"])]
    n_closed = sum(1 for r in rows if closed(r["grip"]))
    prec = (
        len([r for r in succ_dhat if near(r["true"])]) / len(succ_dhat) if succ_dhat else None
    )

    print(f"parsed {n} iters from {path}")
    print(f"near threshold = standoff+tol = {NEAR_M:.2f} m")
    print()
    print("=== Last-step snapshot rates ===")
    print(f"success_dhat (log)     : {len(succ_dhat_log)}/{n} = {100 * len(succ_dhat_log) / n:.1f}%")
    print(f"success_dhat (recomp)  : {len(succ_dhat)}/{n} = {100 * len(succ_dhat) / n:.1f}%")
    print(f"success_TRUE (oracle)  : {len(succ_true)}/{n} = {100 * len(succ_true) / n:.1f}%  << claim-relevant")
    print(f"false positive         : {len(fp)}/{n} = {100 * len(fp) / n:.1f}%")
    print(f"false negative         : {len(fn)}/{n}")
    print(f"d_hat near (any grip)  : {len(dhat_near)}/{n}")
    print(f"true near (any grip)   : {len(true_near)}/{n}")
    print(f"gripper closed         : {n_closed}/{n}")
    if prec is not None:
        print(f"precision(d_hat succ)  : {100 * prec:.1f}%")

    if fp:
        print("\n=== FP examples (d_hat success, true far) ===")
        for r in fp[:8]:
            print(
                f"  it={r['it']:3d} d_hat={r['d_hat']:.3f} true={r['true']:.3f} "
                f"err={r['err']} grip={r['grip']}"
            )
    if succ_true:
        print("\n=== TRUE success examples ===")
        for r in succ_true[:10]:
            print(
                f"  it={r['it']:3d} d_hat={r['d_hat']:.3f} true={r['true']:.3f} "
                f"err={r['err']} grip={r['grip']}"
            )

    out = {
        "source_log": str(path),
        "definition": {
            "near_m": NEAR_M,
            "standoff_m": STANDOFF_M,
            "tol_m": TOL_M,
            "closed": "gripper_open < 0.5",
            "note": "Per learning-iteration last-step snapshot, not episode success rate.",
        },
        "n_iters": n,
        "success_dhat_log": len(succ_dhat_log),
        "success_dhat_recomp": len(succ_dhat),
        "success_true_oracle": len(succ_true),
        "false_positive_dhat": len(fp),
        "false_negative": len(fn),
        "rate_success_dhat": len(succ_dhat) / n,
        "rate_success_true": len(succ_true) / n,
        "rate_fp_among_iters": len(fp) / n,
        "precision_dhat_success": prec,
        "n_dhat_near": len(dhat_near),
        "n_true_near": len(true_near),
        "n_gripper_closed": n_closed,
    }
    out_path = args.out_json or (path.parent / "success_true_vs_dhat.json")
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
