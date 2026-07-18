"""Offline adjudicator for D4 Track A (acoustic + continuous-physics grasp SM).

Pre-registered (docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md §2.2; d4/decisions):

  A1 d4_align_beats_blind : closed align_rate > blind AND Fisher one-sided p<0.05
  A2 d4_align_tracking    : closed r(grasp_x, target_x) >= 0.9
  A3 d4_lift_given_align  : REPORT-ONLY primary; optional gate closed P(lift|align)>=0.70
                            if --require-lift-gate (default: report only until g0 locks)
  A4 d4_posture_clean     : zero invalid episodes across arms

Also reports weld_used rate so friction vs weld is never conflated.

Usage:
  python3 scripts/analyze_d4_sm_grasp.py --scan-dir runtime/outputs/v2_d4_sm_grasp
  python3 scripts/analyze_d4_sm_grasp.py --self-test
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import sys
import tempfile

# allow `python3 scripts/analyze_d4_sm_grasp.py` without package install
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from d4_grasp_common import (  # noqa: E402
    TOL_ALIGN_X_M,
    fisher_exact_one_sided,
    pearson_r,
)

ARMS = ("closed", "blind", "open")
LIFT_GATE = 0.70


def _f(row: dict, key: str) -> float:
    try:
        return float(row.get(key, "nan"))
    except (TypeError, ValueError):
        return float("nan")


def _b(row: dict, key: str) -> bool:
    return str(row.get(key, "")).strip().lower() in ("true", "1", "yes")


def _load_arm(scan: pathlib.Path, arm: str) -> list[dict]:
    path = scan / arm / "episodes.csv"
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def analyze_arm(rows: list[dict], tol: float = TOL_ALIGN_X_M) -> dict:
    n = len(rows)
    attempted = [r for r in rows if math.isfinite(_f(r, "align_error_x"))]
    aligned = [r for r in attempted if abs(_f(r, "align_error_x")) <= tol]
    lifted = [r for r in rows if _b(r, "grasp_lift_success")]
    lift_given = [r for r in aligned if _b(r, "grasp_lift_success")]
    weld_n = sum(1 for r in rows if _b(r, "weld_applied"))
    invalid = sum(1 for r in rows if not _b(r, "episode_valid"))
    pairs = []
    for r in attempted:
        g, t = _f(r, "grasp_center_x_actual"), _f(r, "target_x")
        if math.isfinite(g) and math.isfinite(t):
            pairs.append((g, t))
    r_val = pearson_r([p[0] for p in pairs], [p[1] for p in pairs]) if pairs else float("nan")
    return {
        "n": n,
        "n_aligned": len(aligned),
        "align_rate": len(aligned) / n if n else float("nan"),
        "n_lift": len(lifted),
        "lift_given_align": (len(lift_given) / len(aligned)) if aligned else float("nan"),
        "r_grasp_target": r_val,
        "n_weld_applied": weld_n,
        "weld_rate": weld_n / n if n else float("nan"),
        "n_invalid": invalid,
    }


def run_analysis(scan_dir: pathlib.Path, *, require_lift_gate: bool = False) -> dict:
    stats = {arm: analyze_arm(_load_arm(scan_dir, arm)) for arm in ARMS}
    c, bl = stats["closed"], stats["blind"]
    a, b_ = c["n_aligned"], c["n"] - c["n_aligned"]
    cc, dd = bl["n_aligned"], bl["n"] - bl["n_aligned"]
    # guard empty arms
    if c["n"] == 0 or bl["n"] == 0:
        fisher_p = float("nan")
    else:
        fisher_p = fisher_exact_one_sided(a, b_, cc, dd)

    adj = {
        "d4_align_tracking": bool(
            math.isfinite(c["r_grasp_target"]) and c["r_grasp_target"] >= 0.9
        ),
        "d4_align_beats_blind": bool(
            c["n"] > 0
            and bl["n"] > 0
            and c["align_rate"] > bl["align_rate"]
            and math.isfinite(fisher_p)
            and fisher_p < 0.05
        ),
        "d4_posture_clean": all(stats[a]["n_invalid"] == 0 for a in ARMS if stats[a]["n"] > 0),
    }
    if require_lift_gate:
        adj["d4_lift_given_align_gate"] = bool(
            math.isfinite(c["lift_given_align"]) and c["lift_given_align"] >= LIFT_GATE
        )
    else:
        adj["d4_lift_given_align_gate"] = None  # report-only phase

    out = {
        "scan_dir": str(scan_dir),
        "tol_align_x_m": TOL_ALIGN_X_M,
        "require_lift_gate": require_lift_gate,
        "arms": stats,
        "fisher_p_one_sided": fisher_p,
        "adjudication": adj,
        "note": "P(lift|align) is never merged into a single success rate (D4-3).",
    }

    print(f"{'arm':<8}{'n':>4}{'r':>8}{'align':>10}{'P(lift|al)':>12}{'weld%':>8}{'inv':>5}")
    for arm in ARMS:
        s = stats[arm]
        if s["n"] == 0:
            print(f"{arm:<8}   0   (missing episodes.csv)")
            continue
        print(
            f"{arm:<8}{s['n']:>4}{s['r_grasp_target']:>8.4f}"
            f"{s['align_rate']:>9.1%}{s['lift_given_align'] if math.isfinite(s['lift_given_align']) else float('nan'):>12.1%}"
            f"{s['weld_rate']:>7.1%}{s['n_invalid']:>5}"
        )
    print(f"\nFisher one-sided p={fisher_p}")
    for k, v in adj.items():
        print(f"ADJUDICATION {k}: {v}")

    out_path = scan_dir / "d4_sm_summary.json"
    scan_dir.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(out, f, indent=2)
    print(f"-> {out_path}")
    return out


def _write_synthetic(scan: pathlib.Path) -> None:
    """closed strong align+lift; blind weak; open medium; all valid; no weld."""
    for arm, n_al, n_lift_al, err_aligned, err_miss in (
        # err_miss must be > TOL_ALIGN_X_M (0.02) so align_rate reflects n_al
        ("closed", 24, 20, 0.005, 0.05),
        ("blind", 10, 3, 0.01, 0.08),
        ("open", 9, 7, 0.01, 0.06),
    ):
        d = scan / arm
        d.mkdir(parents=True, exist_ok=True)
        rows = []
        for i in range(30):
            tgt = 1.05 + 0.01 * i  # wider span → stable Pearson
            aligned = i < n_al
            grasp = tgt + (err_aligned if aligned else err_miss)
            lift = aligned and (i < n_lift_al)
            rows.append(
                {
                    "episode": i,
                    "target_x": tgt,
                    "grasp_center_x_actual": grasp,
                    "align_error_x": grasp - tgt,
                    "aligned": str(aligned),
                    "grasp_lift_success": str(lift),
                    "weld_applied": "False",
                    "episode_valid": "True",
                    "bar_z_gain_m": 0.06 if lift else 0.0,
                    "sm_final_state": "DONE" if lift else "FAILED",
                }
            )
        with (d / "episodes.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def self_test() -> None:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="d4_sm_selftest_"))
    try:
        _write_synthetic(tmp)
        out = run_analysis(tmp, require_lift_gate=True)
        assert out["adjudication"]["d4_align_beats_blind"] is True
        assert out["adjudication"]["d4_align_tracking"] is True
        assert out["adjudication"]["d4_posture_clean"] is True
        assert out["adjudication"]["d4_lift_given_align_gate"] is True
        assert out["arms"]["closed"]["n_weld_applied"] == 0
        print("SELF-TEST PASSED")
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan-dir", type=str, default=None)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument(
        "--require-lift-gate",
        action="store_true",
        help="Enable A3 gate P(lift|align)>=0.70 (after g0 locks policy)",
    )
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.scan_dir:
        raise SystemExit("--scan-dir required unless --self-test")
    run_analysis(pathlib.Path(args.scan_dir), require_lift_gate=args.require_lift_gate)


if __name__ == "__main__":
    main()
