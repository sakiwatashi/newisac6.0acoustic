#!/usr/bin/env python3
"""GUI twin of ``d4_acoustic_grasp_sm_runner.py`` — originals untouched.

Same D4 Track-A experiment (delegates to d3_grasp_runner with weld-on-stall
defaults), but launches the grasp runner through ``gui_formal_exec.py`` so a
viewport opens. Writes to a separate output dir by convention
(``runtime/outputs/v2_d4_sm_grasp_gui``).

Usage::

    python3 scripts/d4_acoustic_grasp_sm_runner_gui.py \\
        --mode closed --output-dir runtime/outputs/v2_d4_sm_grasp_gui --smoke
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
GUI_EXEC = REPO / "scripts" / "gui_formal_exec.py"
D3_SCRIPT = REPO / "scripts" / "d3_grasp_runner.py"
DEFAULT_LIFT_STEP = 0.002


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
        help="D4-7 default True. Pass --no-weld-on-stall for friction probe only.",
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
    forbidden = {
        (REPO / "runtime" / "outputs" / "v2_d3_grasp_r3").resolve(),
        (REPO / "runtime" / "outputs" / "v2_d4_sm_grasp_n30").resolve(),
    }
    if out.resolve() in forbidden:
        print("ABORT: refuse to write into canonical formal directories", file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "track": "D4_A_state_machine_GUI",
        "delegate": "scripts/gui_formal_exec.py -> scripts/d3_grasp_runner.py",
        "mode": args.mode,
        "weld_on_stall": bool(args.weld_on_stall),
        "lift_up_step_m": float(args.lift_up_step),
        "seed": args.seed,
        "smoke": bool(args.smoke),
        "note": "GUI twin; adjudicate with analyze_d4_sm_grasp.py. Headless original unchanged.",
    }
    with (out / "d4_run_meta.json").open("w") as f:
        json.dump(meta, f, indent=2)

    cmd = [
        args.python,
        str(GUI_EXEC),
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

    print("=== d4_acoustic_grasp_sm_runner_gui ===", flush=True)
    print("meta:", json.dumps(meta), flush=True)
    print("exec:", " ".join(cmd), flush=True)
    if args.python.endswith(".sh"):
        rc = subprocess.call(["bash", *cmd])
    else:
        rc = subprocess.call(cmd)
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
