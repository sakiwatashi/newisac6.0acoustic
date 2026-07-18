#!/usr/bin/env python3
"""D4 g0 executor smoke: oracle-scaffold grasp sequence (debug_scaffold).

Runs d3 g3 mode into runtime/outputs/v2_d4_g0_executor with:
  - default --no-weld-on-stall (test friction lift after oracle alignment)
  - finer --lift-up-step 0.002

g0 MAY use oracle for motion (decision D4-2). Formal A/B must not.

Usage:
  ./app/python.sh scripts/d4_g0_executor_smoke.py
  ./app/python.sh scripts/d4_g0_executor_smoke.py --weld-on-stall   # control column
  ./app/python.sh scripts/d4_g0_executor_smoke.py --smoke
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "runtime" / "outputs" / "v2_d4_g0_executor"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", type=str, default=str(DEFAULT_OUT))
    ap.add_argument("--smoke", action="store_true", help="g3 offset-0 only (fast)")
    ap.add_argument(
        "--weld-on-stall",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Default False: probe friction. True: D3-like weld control column.",
    )
    ap.add_argument("--lift-up-step", type=float, default=0.002)
    ap.add_argument("--python", type=str, default=str(REPO / "app" / "python.sh"))
    args = ap.parse_args()

    out = pathlib.Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    banner = {
        "gate": "D4_g0_executor",
        "debug_scaffold": True,
        "oracle_motion": True,
        "weld_on_stall": bool(args.weld_on_stall),
        "lift_up_step_m": float(args.lift_up_step),
        "purpose": "Isolate whether continuous-physics lift can hold without weld when pre-aligned.",
    }
    with (out / "g0_banner.json").open("w") as f:
        json.dump(banner, f, indent=2)
    print(json.dumps(banner, indent=2), flush=True)

    cmd = [
        str(REPO / "scripts" / "d4_acoustic_grasp_sm_runner.py"),
        "--mode", "g3",
        "--output-dir", str(out),
        "--lift-up-step", str(args.lift_up_step),
        "--python", args.python,
    ]
    if args.weld_on_stall:
        cmd.append("--weld-on-stall")
    else:
        cmd.append("--no-weld-on-stall")
    if args.smoke:
        cmd.append("--smoke")

    # d4 runner already shells python.sh
    return int(subprocess.call([sys.executable, *cmd]))


if __name__ == "__main__":
    raise SystemExit(main())
