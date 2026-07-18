#!/usr/bin/env python3
"""Offline merge: D4 ④ B handoff rates + Track A formal lift column.

  python3 scripts/analyze_d4_sm_policy_hookup.py \\
    --hookup runtime/outputs/v2_d4_sm_policy_hookup/sm_policy_hookup_summary.json \\
    --a-dir runtime/outputs/v2_d4_sm_grasp_n30
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]


def _load_json(path: pathlib.Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _closed_arm_rates(a_dir: pathlib.Path) -> dict:
    """From A formal closed/episodes.csv if present."""
    ep = a_dir / "closed" / "episodes.csv"
    if not ep.is_file():
        # some layouts nest under mode subdirs differently
        cand = list(a_dir.glob("**/closed/**/episodes.csv")) + list(a_dir.glob("closed/episodes.csv"))
        ep = cand[0] if cand else ep
    if not ep.is_file():
        return {"available": False, "path": str(ep)}

    rows = list(csv.DictReader(ep.open()))
    n = len(rows)
    if n == 0:
        return {"available": True, "n": 0, "path": str(ep)}

    def _b(key: str) -> list[bool]:
        out = []
        for r in rows:
            v = r.get(key, "")
            if isinstance(v, str):
                out.append(v.strip().lower() in ("1", "true", "yes"))
            else:
                out.append(bool(v))
        return out

    # flexible column names from d3 export
    def _col(*names: str) -> list[bool]:
        for name in names:
            if rows and name in rows[0]:
                return _b(name)
        return []

    align = _col("align_success", "aligned", "align_ok")
    lift = _col("grasp_lift_success", "lift_success")
    weld = _col("weld_applied")
    contact = _col("contact_detected")

    def rate(flags: list[bool]) -> float:
        return sum(flags) / len(flags) if flags else float("nan")

    n_align = sum(align) if align else 0
    lift_given_align = float("nan")
    if align and lift and n_align > 0:
        lift_given_align = sum(
            1 for a, L in zip(align, lift) if a and L
        ) / n_align

    return {
        "available": True,
        "path": str(ep),
        "n": n,
        "rate_align": rate(align) if align else float("nan"),
        "rate_lift": rate(lift) if lift else float("nan"),
        "rate_weld": rate(weld) if weld else float("nan"),
        "rate_contact": rate(contact) if contact else float("nan"),
        "rate_lift_given_align": lift_given_align,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--hookup",
        type=pathlib.Path,
        default=REPO / "runtime/outputs/v2_d4_sm_policy_hookup/sm_policy_hookup_summary.json",
    )
    ap.add_argument(
        "--a-dir",
        type=pathlib.Path,
        default=REPO / "runtime/outputs/v2_d4_sm_grasp_n30",
    )
    ap.add_argument("--output", type=pathlib.Path, default=None)
    args = ap.parse_args()

    hook = pathlib.Path(args.hookup)
    if not hook.is_file():
        # try relative to REPO
        alt = REPO / hook
        hook = alt if alt.is_file() else hook
    if not hook.is_file():
        print(f"missing hookup summary: {args.hookup}", file=sys.stderr)
        return 2

    b = _load_json(hook)
    a_dir = pathlib.Path(args.a_dir)
    if not a_dir.is_absolute():
        a_dir = REPO / a_dir
    a = _closed_arm_rates(a_dir)

    # Also try adjudication if present
    adj_path = a_dir / "adjudication.json"
    adj = _load_json(adj_path) if adj_path.is_file() else None

    report = {
        "track": "D4_4_sm_policy_hookup_combined",
        "b_policy_hookup": {
            "path": str(hook),
            "checkpoint": b.get("checkpoint"),
            "n_episodes": b.get("n_episodes"),
            "rate_final_true_near": b.get("rate_final_true_near"),
            "rate_final_true_success": b.get("rate_final_true_success"),
            "rate_lift_handoff_ready": b.get("rate_lift_handoff_ready"),
            "mean_handoff_step": b.get("mean_handoff_step"),
            "claim_boundary": b.get("claim_boundary"),
        },
        "a_sm_lift": a,
        "a_adjudication": adj,
        "pipeline": {
            "phase_B": "REST → ACOUSTIC_APPROACH → ALIGN → CLOSE (policy, acoustic obs)",
            "handoff": "LIFT_HANDOFF when oracle true near + closed",
            "phase_A": "DESCEND → CLOSE contact → weld-on-stall → LIFT → HOLD (Track A SM)",
        },
        "combined_claim": (
            "Dual-track integration: B provides approach+close timing under acoustic "
            "policy obs; A provides physical lift under weld-on-stall. "
            "Do NOT multiply rates into a single 'e2e pure acoustic lift' number without "
            "same-scene sequential run. Handoff readiness ≠ lift success."
        ),
        "status": "PASS" if float(b.get("rate_lift_handoff_ready") or 0) > 0 else "REVIEW",
    }

    out = args.output
    if out is None:
        out = hook.parent / "sm_policy_hookup_combined.json"
    out = out if out.is_absolute() else (REPO / out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")

    print("=== D4 ④ combined (B handoff + A lift ref) ===")
    print(f"  B handoff ready: {100 * float(b.get('rate_lift_handoff_ready') or 0):.1f}%")
    print(f"  B true success:  {100 * float(b.get('rate_final_true_success') or 0):.1f}%")
    if a.get("available"):
        la = a.get("rate_lift_given_align")
        print(f"  A n={a.get('n')} align={a.get('rate_align')} "
              f"lift|align={la if la == la else 'n/a'}")
    else:
        print("  A formal CSV: not found")
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
