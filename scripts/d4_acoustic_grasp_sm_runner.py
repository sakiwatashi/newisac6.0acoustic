#!/usr/bin/env python3
"""D4 Track A entry: acoustic approach + grasp SM (thin orchestrator).

Does NOT re-implement the full Isaac scene. It launches
`scripts/d3_grasp_runner.py` with D4 defaults into a **new** output directory:

  - default: --weld-on-stall  (D4-7: g0 proved friction-only lift fails)
  - friction probe: pass --no-weld-on-stall (g0 already did; negative result)
  - default: --lift-up-step 0.002 (finer continuous lift)
  - corridor / seed / standoff same as D3 r3 unless overridden

Pre-registered adjudication is offline only:
  python3 scripts/analyze_d4_sm_grasp.py --scan-dir <out>

Spec: docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md
Iron laws: same as D3 (oracle never in control for closed/blind/open).

Usage
-----
  # single arm smoke (1 episode)
  ./app/python.sh scripts/d4_acoustic_grasp_sm_runner.py \\
      --mode closed --output-dir runtime/outputs/v2_d4_sm_grasp --smoke

  # formal arm (30 ep) — weld attach (D4-7 main path)
  ./app/python.sh scripts/d4_acoustic_grasp_sm_runner.py \\
      --mode closed --output-dir runtime/outputs/v2_d4_sm_grasp

  # g0 friction probe (negative result already recorded 2026-07-16)
  ./app/python.sh scripts/d4_acoustic_grasp_sm_runner.py \\
      --mode g3 --output-dir runtime/outputs/v2_d4_g0_executor --no-weld-on-stall --smoke
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
D3_SCRIPT = REPO / "scripts" / "d3_grasp_runner.py"
DEFAULT_LIFT_STEP = 0.002  # D4 continuous-lift default (d4_grasp_common.LIFT_UP_STEP_M)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", required=True, choices=("g3", "closed", "blind", "open"))
    ap.add_argument("--output-dir", required=True, type=str)
    ap.add_argument("--n-episodes", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260716)
    ap.add_argument("--standoff", type=float, default=0.35)
    ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--sensor-offset", type=float, default=0.25)
    ap.add_argument("--target-x-min", type=float, default=1.00)
    ap.add_argument("--target-x-max", type=float, default=1.15)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument(
        "--weld-on-stall",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="D4-7 default True (g0: friction-only lift failed). "
             "Pass --no-weld-on-stall only for friction probe / negative-result columns.",
    )
    ap.add_argument("--lift-up-step", type=float, default=DEFAULT_LIFT_STEP)
    ap.add_argument(
        "--python",
        type=str,
        default=str(REPO / "app" / "python.sh"),
        help="Isaac python launcher (default app/python.sh)",
    )
    args = ap.parse_args()

    out = pathlib.Path(args.output_dir)
    if out.resolve() == (REPO / "runtime" / "outputs" / "v2_d3_grasp_r3").resolve():
        print("ABORT: refuse to write into canonical D3 r3 directory", file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "track": "D4_A_state_machine",
        "delegate": "scripts/d3_grasp_runner.py",
        "mode": args.mode,
        "weld_on_stall": bool(args.weld_on_stall),
        "lift_up_step_m": float(args.lift_up_step),
        "seed": args.seed,
        "smoke": bool(args.smoke),
        "note": "Adjudicate with analyze_d4_sm_grasp.py; never merge lift into single success rate.",
    }
    with (out / "d4_run_meta.json").open("w") as f:
        json.dump(meta, f, indent=2)

    cmd = [
        args.python,
        str(D3_SCRIPT),
        "--mode", args.mode,
        "--output-dir", str(out),
        "--n-episodes", str(args.n_episodes),
        "--seed", str(args.seed),
        "--standoff", str(args.standoff),
        "--step", str(args.step),
        "--max-steps", str(args.max_steps),
        "--sensor-offset", str(args.sensor_offset),
        "--target-x-min", str(args.target_x_min),
        "--target-x-max", str(args.target_x_max),
        "--lift-up-step", str(args.lift_up_step),
    ]
    if args.weld_on_stall:
        cmd.append("--weld-on-stall")
    else:
        cmd.append("--no-weld-on-stall")
    if args.smoke:
        cmd.append("--smoke")

    print("=== d4_acoustic_grasp_sm_runner ===", flush=True)
    print("meta:", json.dumps(meta), flush=True)
    print("exec:", " ".join(cmd), flush=True)
    # app/python.sh is a shell script — run via bash if needed
    if args.python.endswith(".sh"):
        rc = subprocess.call(["bash", *cmd])
    else:
        rc = subprocess.call(cmd)
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
