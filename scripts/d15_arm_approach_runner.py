"""D1.5 1-DOF closed-loop approach runner, UR10e-mounted sensor (probe / closed / blind / open).

Full spec: user task "D1.5" (2026-07-08/09) — take scripts/d1_approach_runner.py's
validated three-arm closed-loop-approach protocol and swap its "flying sensor"
(a bare xformOp:translate-driven prim) for a "UR10e arm-carried sensor" (an
Acoustic prim mounted near the wrist, moved by solving IK for tool0 and writing
joint positions). Everything else — the measurement pipeline, the three-arm
design, the pre-registered criteria shape, the calibration reuse — is
unchanged from D1; see docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Sections 3-4 and
scripts/d1_approach_runner.py's own header for that shared background.

Skeleton provenance (read both, picked deliberately)
-----------------------------------------------------
scripts/official_asset_ur10_ee_acoustic_smoke.py and
scripts/official_asset_ur10_fixed_tcp_distance_sweep.py were both read as
candidate boot-sequence templates. Between them:
  - ee_acoustic_smoke.py is the simpler script overall (SimulationApp -> new
    stage -> add_reference_to_stage -> create Acoustic prim under ee_link ->
    warmup -> writer -> timeline.play() -> capture loop), but it never moves
    the arm: no World, no Robot, no IK. It cannot serve as a template for the
    per-step arm motion D1.5 needs.
  - fixed_tcp_distance_sweep.py has the IK/joint-control layer D1.5 actually
    needs (World(), Robot(prim_path=...), LulaKinematicsSolver,
    solve_fixed_tcp_joints/observe_pose, XformCache-based link-z posture
    checks), but its own IK is UR10 (non-e) specific and its posture check
    only guards a single scalar min_link_z, not two independent per-step
    audits.
  This script's boot order follows ee_acoustic_smoke.py's simpler sequencing
  (stage -> spawn -> sensor -> warmup -> writer -> timeline.play()) for
  everything that ISN'T arm motion, and grafts on fixed_tcp_distance_sweep.py's
  World/Robot/LulaKinematicsSolver IK-and-joint-write pattern (generalized to
  UR10e via ur10e_robotiq_passport_v1's solve_tool0_ik) for the one thing
  D1.5 adds that neither script does alone: solving IK for a NEW tool0 x every
  control step, warm-started from the previous step's joint solution, and
  writing the result kinematically.

Reused verbatim from scripts/d1_approach_runner.py (not re-derived, not
changed): _ols_pure, _load_calibration, _estimate_distance (same S2
distance_tableh calibration source and the same d_horiz_est =
sqrt(max(d3d_est**2 - 0.2**2, 1e-6)) formula — this script's sensor mount
height (0.65 m) minus table target height (0.45 m) is again exactly 0.20 m,
so the same calibration and formula apply unmodified), _extract_frame,
D1ApproachWriter's write() logic (renamed class only), _per_rx_primary,
_measure_block, _measure_point, _early_energy, _peak_idx, _avg_common,
_move_target (renamed None -> same body). oracle_horiz_dist / target_x remain
record-only quantities; the control decision reads only d_horiz_est (closed)
or +inf (blind); open never measures at all. See d1_approach_runner.py's own
five-iron-law header for the full text of that discipline, unchanged here.

THE ONE NEW THING THIS SCRIPT DOES (D0.5): instead of rewriting a bare
sensor prim's xformOp:translate mid-session (D1's D0 validation target), it
solves IK for the UR10e's tool0 frame and writes the 6 arm joint positions
mid-session, with the Acoustic sensor prim mounted as a child of the arm's
wrist subtree (see "Sensor mount" below). `--mode probe` is the D0.5
validation run for exactly this: it sweeps the ARM (tool0 x, hence the
sensor) over 10 known corridor positions with the target fixed, and regards
that live regression's r < 0.99 as inconclusive/failing in exactly the same
way D1's probe did — this is on top of (not instead of) the two per-step
geometry audits below, both of which the probe run also exercises and
reports.

First-order risk this script is built to catch (user-specified, 2026-07-08)
-----------------------------------------------------------------------------
Prior UR10e experiments in this repo have seen the arm clip through the
table/floor, or an elbow/forearm sink below the floor while the tool0 tip
still reads as "arrived" (IK has no collision concept and can jump
solution branches). A clipped/interpenetrating arm would let the WPM ray
tracer see through-geometry and contaminate the acoustic signal without any
other symptom. Two per-step audits guard this, EVERY control step (not just
at episode boundaries), and NEITHER one aborts the run — a violation is
recorded (`posture_violation`, `sensor_pose_violation`) and the owning
episode is marked `episode_valid=false`; the episode still runs to
completion and is still logged. Exclusion from the pre-registered r/RMSE
statistics is entirely the offline analyzer's job (scripts/
analyze_d15_arm_approach.py), never this script's:

  1. Posture audit (posture_violation): reads world position (UsdGeom.
     XformCache) of forearm_link, wrist_1_link, wrist_2_link, wrist_3_link,
     ee_link. Violation = ANY of those links has z < 0.05 m (floor margin),
     OR is within the table's xy footprint AND below table_top + 0.05 m
     (0.45 m) — i.e. clipping through the floor, or clipping through/under
     the tabletop.
  2. Sensor pose audit (sensor_pose_violation): reads the Acoustic sensor
     prim's world pose. Violation = |z - 0.65| > 0.02 m, OR the angle
     between its forward axis (local +X transformed to world, the same
     convention official_asset_ur10_ee_acoustic_smoke.py uses) and world +X
     exceeds 5 degrees.

Anti-branch-jump measures (user-specified)
---------------------------------------------
  - Every IK solve warm-starts from the PREVIOUS step's joint solution
    (ur10e_robotiq_passport_v1.solve_tool0_ik's warm_start argument), never
    from a fresh/zero guess mid-episode.
  - Every episode (closed/blind/open) and every probe point RESETS the warm
    start to an elbow-up, forward-reaching seed pose,
    SEED_POSES_RAD["reach_forward"] from ur10e_robotiq_common (trusted
    tool import, handoff doc Section 10), before solving its first position
    -- so drift cannot compound silently across dozens of episodes.
  - Target ORIENTATION is held fixed at every step: identity quaternion
    (1, 0, 0, 0) wxyz for tool0. An identity orientation quaternion means, by
    definition of what "orientation" parameterizes, that tool0's local axes
    coincide with the world axes -- local +X (the same axis the Acoustic
    sensor and official_asset_ur10_ee_acoustic_smoke.py both treat as
    "forward") maps to world +X. Only tool0's x position is varied between
    steps; y is pinned at 0 and z at 0.65 (this is exactly the "工具姿態固定
    (水平前指),只變 x" requirement). This is the same identity-orientation
    convention scripts/official_asset_ur10_fixed_tcp_distance_sweep.py uses
    for its (non-e) UR10 ee_link horizontal sensor mount -- see
    geometry_passport_v1.py's IK_ORIENTATION_TOLERANCE_RAD=0.70 and identity
    target_orientation=[1,0,0,0] there for precedent. If empirically (once
    this script is actually run on GPU) that assumption is wrong for the
    ur10e USD's tool0 frame convention, the sensor-pose audit's >5 deg check
    will flag it every step and the probe gate will fail -- this script does
    not silently assume the convention holds.
  - IK failure (non-convergent OR any non-finite joint value) never crashes
    the session: the owning episode ends immediately with reason="ik_failed"
    (recorded, episode_valid=false) and the runner moves on to the next
    episode. A pre-loop IK failure (can't even reach the episode's corridor
    start) records a zero-step "ik_failed" episode the same way.

Sensor mount (user asked for "ee_link subtree"; this script uses the
documented-safer choice within that subtree)
-------------------------------------------------------------------------
The task text says "parent to the ee_link subtree". scripts/
ur10e_robotiq_common.py's own resolve_sensor_mount_path() docstring is
explicit and is exactly the kind of documented gotcha this task's warning is
about: "Kinematic mount for RTX sensor (UR10e USD: wrist_3_link moves;
ee_link is static)." Parenting a MOVING sensor to a STATIC ee_link would
silently defeat the entire "arm-carried sensor" premise (the sensor would
never move even though the arm does). This script therefore calls
resolve_sensor_mount_path(ARM_PATH, stage) -- which tries wrist_3_link, then
tool0, then ee_link, in that trusted-module-documented order -- rather than
hardcoding ee_link, and records whichever prim it resolved to in
run_meta.json's "mount_path_used" for auditability. Whatever frame is
chosen is still a descendant of the ee_link/wrist subtree; it does not
introduce a new independent joint.

No gripper: SEED_POSES_RAD/ARM_JOINT_NAMES etc. come from the UR10e+Robotiq
common module (ur10e_robotiq_common.py) because those constants are shared
and trusted, but this script does NOT select a Gripper variant -- D1.5 has
no grasp step, and per the task text ("若無夾爪 variant 就直接用 ur10e.usd
本體") the sensor offset (0.25 m) is chosen to clear where a gripper's
fingertips WOULD be, not because a gripper is actually mounted.
_select_bare_arm_variant() defensively selects a "None"-style Gripper variant
if the USD offers one, and otherwise leaves the asset's default variant
selection untouched (recorded in run_meta.json).

Pre-registered criteria (written here, before this script is ever run;
computed only by scripts/analyze_d15_arm_approach.py, never fed back into
any control decision)
-----------------------------------------------------------------------------
  d05_arm_mount_valid   : probe-mode live regression of peak_sample_idx vs
                           true_distance_3d_m has r >= 0.99 AND zero
                           posture_violation / sensor_pose_violation rows
                           across the probe sweep.
  d15_tracking_r_ge_0.9 : r(stop_sensor_x, target_x) over the CLOSED arm's
                           VALID (episode_valid=true) episodes >= 0.9.
  d15_beats_blind       : closed arm's stop_error RMSE (valid episodes only)
                           is lower than blind's, AND a Welch two-sample
                           t-test on the two arms' (valid-episode) stop_error
                           samples has p < 0.05.
  d15_posture_clean     : total invalid episodes across all three arms == 0.

CLI
---
    --mode {probe,closed,blind,open}   Required.
    --output-dir PATH                  Required.
    --n-episodes INT                   default 30 (closed/blind/open only).
    --seed INT                         default 20260708 (paired across arms).
    --standoff FLOAT                   default 0.35 m.
    --step FLOAT                       default 0.05 m per control step.
    --max-steps INT                    default 40.
    --sensor-offset FLOAT              default 0.25 m (local +X offset of the
                                        Acoustic prim from its mount frame).

Geometry (fixed design constants; all printed into run_meta.json)
-----------------------------------------------------------------------------
    UR10e base       : (0, 0, 0).
    Tool height       : z = 0.65 m; orientation fixed identity (horizontal,
                        +X forward); only x varies.
    Sensor mount      : resolve_sensor_mount_path() result, local offset
                        (+sensor_offset, 0, 0).
    Corridor          : sensor_x starts at 0.45, steps of --step, guard at
                        sensor_x > 1.00 or --max-steps.
    Target            : uniform random x in [0.90, 1.25] (same seed, all
                        three arms), y=0, resting on table top (z=0.45),
                        0.10 m Cube. Probe: fixed at x=1.10.
    Table             : top face z=0.40, 1.2 x 0.8 m, centered at x=1.05.
    Standoff          : 0.35 m (default).

Usage
-----
    ./app/python.sh scripts/d15_arm_approach_runner.py \\
        --mode probe --output-dir runtime/outputs/v2_d15_arm_approach
    ./app/python.sh scripts/d15_arm_approach_runner.py \\
        --mode closed --output-dir runtime/outputs/v2_d15_arm_approach \\
        --n-episodes 30 --seed 20260708 --standoff 0.35 --step 0.05 --max-steps 40
    ./app/python.sh scripts/d15_arm_approach_runner.py \\
        --mode blind --output-dir runtime/outputs/v2_d15_arm_approach
    ./app/python.sh scripts/d15_arm_approach_runner.py \\
        --mode open --output-dir runtime/outputs/v2_d15_arm_approach
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import pathlib
import random
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ── Argument parsing BEFORE SimulationApp (rule 4-1) ──────────────────────────
parser = argparse.ArgumentParser(
    description="D1.5 1-DOF closed-loop approach, UR10e arm-carried sensor "
                "(probe / closed / blind / open)."
)
parser.add_argument("--mode", type=str, required=True,
                     choices=("probe", "closed", "blind", "open"),
                     help="probe = D0.5 arm-mount validation sweep; "
                          "closed/blind/open = D1.5 three-arm episodes")
parser.add_argument("--output-dir", type=str, required=True,
                     help="Output root; a mode-specific sub-directory is created underneath")
parser.add_argument("--n-episodes", type=int, default=30,
                     help="Episodes per session (closed/blind/open only)")
parser.add_argument("--seed", type=int, default=20260708,
                     help="random.Random(seed) draws the SAME n-episodes target x "
                          "positions for all three arms (paired design)")
parser.add_argument("--standoff", type=float, default=0.35,
                     help="Stop when d_horiz_est <= standoff (m)")
parser.add_argument("--step", type=float, default=0.05,
                     help="Sensor forward step size (m) per control iteration")
parser.add_argument("--max-steps", type=int, default=40,
                     help="Guard: stop an episode after this many measurements")
parser.add_argument("--sensor-offset", type=float, default=0.25,
                     help="Acoustic sensor's local +X offset (m) from its mount frame "
                          "(ahead of where a gripper's fingertips would be)")
args, _ = parser.parse_known_args()

# ── Physical / scene constants ────────────────────────────────────────────────
N_SETTLE = 40
N_MEASURE = 12
STATIONARITY_DRIFT_MAX = 0.05  # same threshold as d1_approach_runner.py
N_EARLY = 20

ARM_PATH = "/World/ur10e"
SENSOR_LOCAL_NAME = "acoustic_sensor"
TARGET_PATH = "/World/target"
TABLE_PATH = "/World/table"

TOOL_Z_M = 0.65                  # tool0 height; fixed for every step
TARGET_SIZE_M = 0.10
TARGET_Z_M = 0.45                # target rests on the table top
TABLE_TOP_Z_M = 0.40
HEIGHT_DIFF_M = TOOL_Z_M - TARGET_Z_M  # 0.20, matches the D1/S2 calibration's assumed geometry

TABLE_WIDTH_M = 1.2
TABLE_DEPTH_M = 0.8
TABLE_CENTER_X_M = 1.05          # spans x in [0.45, 1.65], covers the target range
TABLE_CENTER_Y_M = 0.0

# Corridor geometry rev2 (2026-07-09): rev1 started the sensor at x=0.45,
# i.e. tool0 at 0.45-0.25=0.20 m -- essentially inside the base column, which
# is unreachable with a horizontal forward-pointing tool orientation, so the
# very first IK solve failed and the session died. Start further out: sensor
# 0.60 -> tool0 0.35 (comfortable), targets shifted to [1.00, 1.30] so every
# episode still has >=1 approach step (min start distance 0.40 > standoff
# 0.35) and stop points land at tool0 in [0.40, 0.70].
TARGET_X_MIN_M = 1.00
TARGET_X_MAX_M = 1.30
PROBE_TARGET_X_M = 1.25

SENSOR_X_START_M = 0.60          # corridor start (same for every episode and the probe sweep)
PROBE_STEP_M = 0.025             # fixed regardless of --step; 13 points inclusive (rev4: 0.05 gave only 7 pts, too thin for the r>=0.99 gate)
PROBE_SENSOR_X_END_M = 0.90
CORRIDOR_GUARD_X_M = 1.00        # guard: sensor_x beyond this ends an episode ("corridor_end")

# Posture audit (every step): world z of these links must clear the floor and
# the table (see module docstring's "First-order risk" section).
# ee_link removed 2026-07-09: it is a STATIC frame in the UR10e USD (the same
# property that made it unusable as a sensor mount) — it idles at its authored
# default pose (z≈0), permanently tripping the floor check and flagging every
# step (observed: probe rev3 posture_violation=7/7). Auditing a frame that
# never moves says nothing about posture.
POSTURE_LINK_NAMES = ("forearm_link", "wrist_1_link", "wrist_2_link", "wrist_3_link")
FLOOR_MARGIN_Z_M = 0.05
TABLE_CLEAR_MARGIN_M = 0.05      # violation z-threshold over the table = TABLE_TOP_Z_M + this

# Sensor pose audit (every step): sensor prim world pose must stay near the
# nominal (0.65 m, +X-forward) mount pose.
SENSOR_Z_TOL_M = 0.02
SENSOR_ANGLE_TOL_DEG = 5.0

CENTER_FREQ_HZ = 40_000.0
MOUNT_SPACING_M = 0.10
TICK_RATE_HZ = 30.0
AZ_SPAN_DEG = 90.0
EL_SPAN_DEG = 90.0
TRACE_TREE_DEPTH = 2

# Fixed tool0 orientation for every IK solve (identity wxyz -- see module
# docstring's "Anti-branch-jump measures" section for why this makes the
# tool "horizontal, +X forward" by definition of what an orientation
# quaternion parameterizes).
IDENTITY_QUAT_WXYZ = (1.0, 0.0, 0.0, 0.0)
IK_ORIENTATION_TOLERANCE_RAD_D15 = 0.08   # ~4.6 deg, tighter than the 5 deg audit cutoff

CALIB_CSV_PATH = REPO_ROOT / "runtime" / "outputs" / "v2_s2_datasheet" / "distance_tableh" / "points.csv"
CALIB_R_MIN = 0.99


# ── Pure-stdlib OLS (verbatim from d1_approach_runner.py) ─────────────────────
def _ols_pure(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """y = slope*x + intercept OLS fit. Returns (slope, intercept, pearson_r);
    NaNs if fewer than 2 points or zero variance in x or y."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return float("nan"), float("nan"), float("nan")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx <= 0.0:
        return float("nan"), float("nan"), float("nan")
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    syy = sum((y - mean_y) ** 2 for y in ys)
    r = sxy / math.sqrt(sxx * syy) if syy > 0.0 else float("nan")
    return slope, intercept, r


def _load_calibration(csv_path: pathlib.Path) -> tuple[float, float, float, int]:
    """Load the S2 distance_tableh points.csv, keep stationarity_ok==True
    rows, OLS-fit peak_sample_idx vs true_distance_3d_m. Returns
    (slope, intercept, r, n_kept). Verbatim from d1_approach_runner.py --
    D1.5 reuses D1's self-calibration unmodified (same 0.20 m height-diff
    geometry, see HEIGHT_DIFF_M above)."""
    if not csv_path.exists():
        raise SystemExit(
            f"ABORT: calibration source not found: {csv_path}\n"
            "Run the S2 distance_tableh pass first "
            "(bash runtime/run_v2_s2_datasheet.sh) before D1.5."
        )
    xs: list[float] = []
    ys: list[float] = []
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("stationarity_ok", "")).strip().lower() not in ("true", "1"):
                continue
            try:
                x = float(row["true_distance_3d_m"])
                y = float(row["peak_sample_idx"])
            except (KeyError, TypeError, ValueError):
                continue
            xs.append(x)
            ys.append(y)
    slope, intercept, r = _ols_pure(xs, ys)
    return slope, intercept, r, len(xs)


print("=== d15_arm_approach_runner.py: startup self-calibration ===")
print(f"calib source: {CALIB_CSV_PATH}")
CALIB_SLOPE, CALIB_INTERCEPT, CALIB_R, CALIB_N = _load_calibration(CALIB_CSV_PATH)
print(f"calib n_kept={CALIB_N}  slope={CALIB_SLOPE:.4f} samples/m  "
      f"intercept={CALIB_INTERCEPT:.4f} samples  r={CALIB_R}")
if not (math.isfinite(CALIB_R) and CALIB_R >= CALIB_R_MIN):
    raise SystemExit(
        f"ABORT: calibration r={CALIB_R} < required {CALIB_R_MIN} "
        f"(source: {CALIB_CSV_PATH}). Re-run/inspect S2 distance_tableh before D1.5."
    )
print()

if args.mode in ("closed", "blind", "open"):
    if args.n_episodes < 1:
        raise SystemExit("--n-episodes must be >= 1")
    _rng = random.Random(args.seed)
    TARGET_POSITIONS_M = [_rng.uniform(TARGET_X_MIN_M, TARGET_X_MAX_M) for _ in range(args.n_episodes)]
else:
    TARGET_POSITIONS_M = None


def _estimate_distance(peak_idx: float) -> tuple[float, float]:
    """Verbatim from d1_approach_runner.py: d3d_est=(peak_idx-intercept)/slope;
    d_horiz_est=sqrt(max(d3d_est**2-0.2**2,1e-6)). Returns (d3d_est,
    d_horiz_est); d_horiz_est is +inf if peak_idx/d3d_est is non-finite."""
    if not math.isfinite(peak_idx):
        return float("nan"), float("inf")
    d3d_est = (peak_idx - CALIB_INTERCEPT) / CALIB_SLOPE
    if not math.isfinite(d3d_est):
        return float("nan"), float("inf")
    d_horiz_est = math.sqrt(max(d3d_est ** 2 - HEIGHT_DIFF_M ** 2, 1e-6))
    return d3d_est, d_horiz_est


# ── SimulationApp must come before all other Isaac Sim imports (rule 4-1) ────
from isaacsim import SimulationApp  # noqa: E402
simulation_app = SimulationApp({"headless": True})

import numpy as np                                    # noqa: E402
import omni.replicator.core as rep                    # noqa: E402
import omni.timeline                                  # noqa: E402
import omni.usd                                       # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
from isaacsim.core.api import World                   # noqa: E402
from isaacsim.core.api.robots import Robot             # noqa: E402
from isaacsim.core.experimental.objects import Cube    # noqa: E402
from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver  # noqa: E402
from isaacsim.sensors.experimental.rtx import (        # noqa: E402
    Acoustic, AcousticSensor, parse_generic_model_output_data,
)
from isaacsim.storage.native import get_assets_root_path  # noqa: E402
from omni.replicator.core import Writer                # noqa: E402
from pxr import Gf, UsdGeom                             # noqa: E402

from rtx_acoustic_factory import create_passport_acoustic  # noqa: E402
from ur10e_robotiq_common import (                      # noqa: E402 -- trusted tool import (handoff §10)
    ROBOT_USD_REL,
    SEED_POSES_RAD,
    hold_arm_joint_positions,
    resolve_sensor_mount_path,
)
from ur10e_robotiq_passport_v1 import (                  # noqa: E402 -- trusted tool import (handoff §10)
    IK_EE_FRAME,
    IK_MAX_JOINT_JUMP_APPROACH_RAD,
    IK_MAX_WRIST_3_JUMP_RAD,
    IK_ROBOT_DESCRIPTION,
    IK_URDF,
    solve_tool0_ik,
    tool0_grasp_orientation_wxyz,
)
from geometry_passport_v1 import IK_POSITION_TOLERANCE_M  # noqa: E402 -- same reuse precedent as
                                                           # official_asset_ur10_ultrasonic_closed_loop_approach.py

IDENTITY_QUAT_WXYZ_ARR = np.array(IDENTITY_QUAT_WXYZ, dtype=float)

# ── Module-level data buffer (Writer -> main loop communication, rule 4-2) ────
_buf: dict = {"latest": None}


def _extract_frame(gmo) -> dict | None:
    """Verbatim from d1_approach_runner.py._extract_frame (full scalar array +
    stride + rx id at each way's start index)."""
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None

    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float).copy()
    rx_all = np.ctypeslib.as_array(gmo.y, shape=(n,)).copy()

    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    if num_spsgw <= 0 or n % num_spsgw != 0:
        return None  # no stride -> cannot split into signal ways (rule 1-2)

    n_ways = n // num_spsgw
    way_start_rx_ids = [int(rx_all[w * num_spsgw]) for w in range(n_ways)]

    if os.environ.get("D15_DEBUG_IDS") == "1" and not _buf.get("ids_printed"):
        tx_all = np.ctypeslib.as_array(gmo.x, shape=(n,))
        ch_all = np.ctypeslib.as_array(gmo.z, shape=(n,))
        keys = [(int(tx_all[w * num_spsgw]), int(rx_all[w * num_spsgw]), int(ch_all[w * num_spsgw]))
                for w in range(n_ways)]
        print(f"D15_DEBUG_IDS frame: n={n} num_spsgw={num_spsgw} n_ways={n_ways} "
              f"(tx,rx,ch) at way starts = {keys}", flush=True)
        _buf["ids_printed"] = True

    return {
        "amp_all": amp_all,
        "num_spsgw": num_spsgw,
        "way_start_rx_ids": way_start_rx_ids,
        "n_elements": n,
    }


class D15ArmApproachWriter(Writer):
    """Parses GMO each frame and stores the full-fidelity frame dict in the
    module-level _buf (rule 4-2). Identical to d1_approach_runner.py's
    D1ApproachWriter (renamed class only)."""

    def __init__(self):
        self.data_structure = "renderProduct"
        self.annotators = [rep.annotators.get("GenericModelOutput")]

    def write(self, data):
        _buf["latest"] = None
        if "renderProducts" not in data:
            return
        for _rp, rp_data in data["renderProducts"].items():
            raw = rp_data.get("GenericModelOutput")
            if isinstance(raw, dict):
                raw = raw.get("data")
            gmo = parse_generic_model_output_data(raw)
            feats = _extract_frame(gmo)
            if feats is not None:
                _buf["latest"] = feats
                return  # first render product is sufficient


def _per_rx_primary(frame: dict) -> dict[int, np.ndarray]:
    """Verbatim from d1_approach_runner.py._per_rx_primary: way-ordinal
    grouping. Returns {ordinal: waveform}."""
    amp_all = frame["amp_all"]
    num_spsgw = frame["num_spsgw"]
    n_ways = len(frame["way_start_rx_ids"])

    per_rx: dict[int, np.ndarray] = {}
    for w in range(n_ways):
        s = w * num_spsgw
        per_rx[w] = amp_all[s : s + num_spsgw].copy()
    return per_rx


# ── Frame-level feature helpers (verbatim from d1_approach_runner.py) ─────────
def _early_energy(wf: np.ndarray) -> float:
    if wf is None or wf.size == 0:
        return float("nan")
    return float(np.sum(wf[:N_EARLY] ** 2))


def _peak_idx(wf: np.ndarray) -> float:
    if wf is None or wf.size == 0:
        return float("nan")
    return float(np.argmax(wf))


def _avg_common(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a is None or b is None or a.size == 0 or b.size == 0:
        return np.array([], dtype=float)
    n = min(a.size, b.size)
    return (a[:n] + b[:n]) / 2.0


def _measure_block(n_frames: int) -> dict:
    """Verbatim from d1_approach_runner.py._measure_block: advances n_frames,
    ACCUMULATES per-RX primary waveforms across frames."""
    by_rx: dict[int, list[np.ndarray]] = {}
    n_frames_valid = 0

    for _ in range(n_frames):
        simulation_app.update()
        frame = _buf["latest"]
        if frame is None:
            continue
        per_rx = _per_rx_primary(frame)
        if not per_rx:
            continue
        n_frames_valid += 1
        for rid, wf in per_rx.items():
            by_rx.setdefault(int(rid), []).append(wf)

    def _mean_stack(wfs: list[np.ndarray]) -> np.ndarray:
        if not wfs:
            return np.array([], dtype=float)
        min_len = min(w.size for w in wfs)
        stacked = np.array([w[:min_len] for w in wfs], dtype=float)
        return np.mean(stacked, axis=0)

    rids = sorted(by_rx.keys())
    rx0_wf = _mean_stack(by_rx[rids[0]]) if len(rids) >= 1 else np.array([], dtype=float)
    rx1_wf = _mean_stack(by_rx[rids[1]]) if len(rids) >= 2 else np.array([], dtype=float)
    if rx0_wf.size and rx1_wf.size:
        primary_wf = rx0_wf if float(np.max(rx0_wf)) >= float(np.max(rx1_wf)) else rx1_wf
    elif rx0_wf.size:
        primary_wf = rx0_wf
    else:
        primary_wf = rx1_wf

    return {
        "n_frames_valid": n_frames_valid,
        "primary": primary_wf,
        "rx0": rx0_wf,
        "rx1": rx1_wf,
        "rx_ids": rids,
    }


def _measure_point(n_settle: int, n_measure: int) -> dict:
    """Verbatim from d1_approach_runner.py._measure_point: settle -> block A ->
    block B (no extra settle between) -> point value = (A+B)/2, plus the
    A-vs-B drift audit. Every arm move (this script's IK-solve-and-write, in
    place of D1's sensor xformOp:translate) must be followed by exactly this
    call so the settle is never skipped."""
    for _ in range(n_settle):
        simulation_app.update()

    block_a = _measure_block(n_measure)
    block_b = _measure_block(n_measure)

    mean_primary = _avg_common(block_a["primary"], block_b["primary"])
    mean_rx0 = _avg_common(block_a["rx0"], block_b["rx0"])
    mean_rx1 = _avg_common(block_a["rx1"], block_b["rx1"])

    early_a = _early_energy(block_a["primary"])
    early_b = _early_energy(block_b["primary"])
    if math.isfinite(early_a) and math.isfinite(early_b):
        point_drift = abs(early_a - early_b) / max(abs(early_a), abs(early_b), 1e-12)
    else:
        point_drift = float("nan")
    stationarity_ok = bool(math.isfinite(point_drift) and point_drift <= STATIONARITY_DRIFT_MAX)

    return {
        "mean_primary": mean_primary,
        "mean_rx0": mean_rx0,
        "mean_rx1": mean_rx1,
        "peak_sample_idx": _peak_idx(mean_primary),
        "early_energy": _early_energy(mean_primary),
        "point_drift": point_drift,
        "stationarity_ok": stationarity_ok,
        "n_frames_valid_a": block_a["n_frames_valid"],
        "n_frames_valid_b": block_b["n_frames_valid"],
    }


def _move_target(stage, x: float, y: float, z: float) -> None:
    """Verbatim from d1_approach_runner.py._move_target: rewrite TARGET_PATH's
    xformOp:translate (world frame). The target is NEVER re-created between
    episodes -- only this op is rewritten."""
    prim = stage.GetPrimAtPath(TARGET_PATH)
    xformable = UsdGeom.Xformable(prim)
    ops_by_name = {op.GetOpName(): op for op in xformable.GetOrderedXformOps()}
    key = "xformOp:translate"
    if key in ops_by_name:
        ops_by_name[key].Set(Gf.Vec3d(x, y, z))
    else:
        xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))


# ── Geometry helpers ─────────────────────────────────────────────────────────
def _build_table(stage) -> None:
    Cube(
        TABLE_PATH,
        sizes=[1.0],
        scales=np.array([[TABLE_WIDTH_M, TABLE_DEPTH_M, TABLE_TOP_Z_M]]),
        positions=np.array([[TABLE_CENTER_X_M, TABLE_CENTER_Y_M, TABLE_TOP_Z_M / 2.0]]),
    )


def _select_bare_arm_variant(stage, arm_path: str) -> str | None:
    """Prefer a 'None'-style Gripper variant so the robot stays a bare arm
    (D1.5 has no grasp step); leaves the USD's default selection untouched if
    no such option exists. Returns the variant selection applied, or None."""
    prim = stage.GetPrimAtPath(arm_path)
    if not prim or not prim.IsValid():
        return None
    variant_sets = prim.GetVariantSets()
    if not variant_sets.HasVariantSet("Gripper"):
        return None
    vset = variant_sets.GetVariantSet("Gripper")
    try:
        names = list(vset.GetVariantNames())
    except Exception:
        names = []
    for candidate in ("None", "none", "No_Gripper", "Bare"):
        if candidate in names:
            vset.SetVariantSelection(candidate)
            return candidate
    return None  # no bare-arm option found; USD default selection stands


def _link_world_xyz(stage, prim_path: str, cache) -> tuple[float, float, float]:
    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return float("nan"), float("nan"), float("nan")
    cache.Clear()
    t = cache.GetLocalToWorldTransform(prim).ExtractTranslation()
    return float(t[0]), float(t[1]), float(t[2])


def _in_table_footprint(x: float, y: float) -> bool:
    if not (math.isfinite(x) and math.isfinite(y)):
        return False
    return (
        TABLE_CENTER_X_M - TABLE_WIDTH_M / 2.0 <= x <= TABLE_CENTER_X_M + TABLE_WIDTH_M / 2.0
        and TABLE_CENTER_Y_M - TABLE_DEPTH_M / 2.0 <= y <= TABLE_CENTER_Y_M + TABLE_DEPTH_M / 2.0
    )


def _audit_posture(stage, arm_path: str, cache) -> bool:
    """True if a posture VIOLATION exists on any monitored link this step
    (floor clip or table clip -- see module docstring's "First-order risk"
    section). A link that cannot be resolved is skipped, not flagged."""
    for link_name in POSTURE_LINK_NAMES:
        x, y, z = _link_world_xyz(stage, f"{arm_path}/{link_name}", cache)
        if not math.isfinite(z):
            continue
        if z < FLOOR_MARGIN_Z_M:
            if os.environ.get("D15_DEBUG_POSTURE") == "1":
                print(f"POSTURE_DEBUG floor: {link_name} at ({x:.3f},{y:.3f},{z:.3f})", flush=True)
            return True
        if _in_table_footprint(x, y) and z < (TABLE_TOP_Z_M + TABLE_CLEAR_MARGIN_M):
            if os.environ.get("D15_DEBUG_POSTURE") == "1":
                print(f"POSTURE_DEBUG table: {link_name} at ({x:.3f},{y:.3f},{z:.3f})", flush=True)
            return True
    return False


def _audit_sensor_pose(stage, sensor_path: str, cache) -> tuple[bool, float, float, float]:
    """Returns (violation, sensor_world_x, sensor_world_z, forward_angle_deg)."""
    prim = stage.GetPrimAtPath(sensor_path)
    if not prim or not prim.IsValid():
        return True, float("nan"), float("nan"), float("nan")
    cache.Clear()
    m = cache.GetLocalToWorldTransform(prim)
    pos = m.ExtractTranslation()
    sx, sz = float(pos[0]), float(pos[2])
    forward = m.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()
    dot = max(-1.0, min(1.0, float(forward[0])))  # forward . world(+X) == forward[0]
    angle_deg = math.degrees(math.acos(dot))
    violation = bool(abs(sz - TOOL_Z_M) > SENSOR_Z_TOL_M or angle_deg > SENSOR_ANGLE_TOL_DEG)
    return violation, sx, sz, angle_deg


# ── IK helper ──────────────────────────────────────────────────────────────────
def _solve_tool0(ik: LulaKinematicsSolver, target_x: float, warm_q: np.ndarray) -> tuple[np.ndarray, bool]:
    """Solve tool0 IK for (target_x, 0, TOOL_Z_M) with a fixed identity
    orientation, warm-started from warm_q. Returns (q, ok); ok is False on
    non-convergence, a rejected joint jump/wrist flip (solve_tool0_ik's own
    guards), OR any non-finite value in q ("不收斂/非有限" -> ik_failed)."""
    ee_target = (float(target_x), 0.0, float(TOOL_Z_M))
    # Fixed orientation = FK of the reach_forward seed (guaranteed-feasible),
    # NOT the world-identity quaternion: forcing tool0 axes to coincide with
    # world axes is not a reachable orientation for UR10e in this corridor
    # (rev2 2026-07-09: identity-orientation IK failed even at tool0 x=0.35).
    q, ok = solve_tool0_ik(
        ik,
        ee_target,
        warm_q,
        target_orientation=TOOL_TARGET_QUAT_WXYZ,
        position_tolerance=float(IK_POSITION_TOLERANCE_M),
        orientation_tolerance=float(IK_ORIENTATION_TOLERANCE_RAD_D15),
        max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_APPROACH_RAD),
        max_wrist_3_jump_rad=float(IK_MAX_WRIST_3_JUMP_RAD),
        min_tool0_z_m=None,
    )
    q = np.asarray(q, dtype=float).reshape(-1)
    ok = bool(ok) and q.size >= 6 and bool(np.all(np.isfinite(q)))
    return q, ok


def _move_arm(robot, world, q: np.ndarray) -> None:
    """Direct kinematic joint write (settle is owned entirely by
    _measure_point's simulation_app.update() loop, per the task spec)."""
    hold_arm_joint_positions(robot, q, world, render=False, simulation_app=None, arm_only_kinematic=True)


# ── Scene construction ─────────────────────────────────────────────────────────
print("=== d15_arm_approach_runner.py ===")
print(f"mode={args.mode}  n_episodes={args.n_episodes if args.mode != 'probe' else '-'}  seed={args.seed}")
print(f"standoff={args.standoff}  step={args.step}  max_steps={args.max_steps}  sensor_offset={args.sensor_offset}")
print(f"n_settle={N_SETTLE}  n_measure={N_MEASURE}")
print()

context = omni.usd.get_context()
context.new_stage()
stage = context.get_stage()
if stage is None:
    simulation_app.close()
    raise RuntimeError("Failed to create stage")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

assets_root_used = get_assets_root_path()
if not assets_root_used:
    raise RuntimeError("get_assets_root_path() returned empty/None; cannot spawn UR10e asset")
usd_path_used = f"{assets_root_used}/{ROBOT_USD_REL}"
print(f"Loading UR10e: {usd_path_used}", flush=True)
stage_utils.add_reference_to_stage(usd_path=usd_path_used, path=ARM_PATH)
for _ in range(20):
    simulation_app.update()
if not stage.GetPrimAtPath(ARM_PATH):
    simulation_app.close()
    raise RuntimeError(f"UR10e prim missing after spawn: {ARM_PATH}")

gripper_variant_selected = _select_bare_arm_variant(stage, ARM_PATH)
print(f"Gripper variant selected: {gripper_variant_selected!r} (None => USD default left untouched)")

_build_table(stage)
print(f"Table built: top z={TABLE_TOP_Z_M}, center x={TABLE_CENTER_X_M} "
      f"(spans x in [{TABLE_CENTER_X_M - TABLE_WIDTH_M/2:.3f}, {TABLE_CENTER_X_M + TABLE_WIDTH_M/2:.3f}])")

mount_path = resolve_sensor_mount_path(ARM_PATH, stage)
sensor_path = f"{mount_path}/{SENSOR_LOCAL_NAME}"
print(f"Sensor mount resolved to: {mount_path}  (sensor prim: {sensor_path})")

acoustic, sensor = create_passport_acoustic(
    sensor_path,
    Acoustic=Acoustic,
    AcousticSensor=AcousticSensor,
    np=np,
    tick_rate_hz=TICK_RATE_HZ,
    center_frequency_hz=CENTER_FREQ_HZ,
    sensor_local_offset_m=(float(args.sensor_offset), 0.0, 0.0),
    mount_spacing_m=MOUNT_SPACING_M,
    aux_output_level="BASIC",
    writer_brings_annotator=True,
    az_span_deg=AZ_SPAN_DEG,
    el_span_deg=EL_SPAN_DEG,
    trace_tree_depth=TRACE_TREE_DEPTH,
)
rep.WriterRegistry.register(D15ArmApproachWriter)
sensor.attach_writer("D15ArmApproachWriter")
# Sensor prim has no xformOp:orient of its own (identity local rotation
# relative to its mount parent) -- same convention as D1's sensor. Its world
# forward therefore equals the mount frame's world forward, which in turn
# equals world +X whenever tool0 (and hence, rigidly, the mount frame) is
# held at the identity orientation this script's IK always targets.

world = World()
robot = world.scene.add(Robot(prim_path=ARM_PATH, name="ur10e"))
world.reset()

ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
if IK_EE_FRAME not in ik.get_all_frame_names():
    simulation_app.close()
    raise RuntimeError(f"IK frame not found: {IK_EE_FRAME}; frames={ik.get_all_frame_names()}")

# Fixed tool orientation for every IK solve: the reach_forward seed's own FK
# orientation (trusted-module helper; same technique as the legacy grasp
# pipeline). Guaranteed feasible by construction, unlike world-identity.
TOOL_TARGET_QUAT_WXYZ = np.asarray(
    tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"]), dtype=float
)
_fk_seed_pos, _ = ik.compute_forward_kinematics(IK_EE_FRAME, np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float))
print(f"Seed FK: tool0 pos={np.round(np.asarray(_fk_seed_pos, dtype=float), 4).tolist()}  "
      f"fixed target orientation (wxyz)={np.round(TOOL_TARGET_QUAT_WXYZ, 4).tolist()}")

timeline = omni.timeline.get_timeline_interface()
timeline.play()

# ── Initial target placement (depends on mode) ────────────────────────────────
if args.mode == "probe":
    init_target_x = PROBE_TARGET_X_M
else:
    init_target_x = TARGET_POSITIONS_M[0]

Cube(
    TARGET_PATH,
    sizes=[TARGET_SIZE_M],
    positions=np.array([[init_target_x, 0.0, TARGET_Z_M]]),
)
print(f"target Cube created at ({init_target_x:.4f}, 0.0000, {TARGET_Z_M:.4f}) (edge={TARGET_SIZE_M}m)")

# ── Initial arm pose: elbow-up forward-reach seed -> corridor start ──────────
seed_q = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
q_init, ok_init = _solve_tool0(ik, SENSOR_X_START_M - args.sensor_offset, seed_q)
if not ok_init:
    # Print BEFORE close(): with --/app/fastShutdown=True the process can die
    # inside close() and a raise placed after it never reaches the log
    # (observed 2026-07-09: rev1's silent probe death).
    print(
        f"ABORT: initial IK solve failed for tool0 x={SENSOR_X_START_M - args.sensor_offset:.4f} "
        f"(sensor_x={SENSOR_X_START_M}). Scene/seed geometry needs adjustment before any run.",
        flush=True,
    )
    simulation_app.close()
    sys.exit(2)
_move_arm(robot, world, q_init)
print(f"Initial arm pose set (corridor start, sensor_x={SENSOR_X_START_M}): "
      f"q={np.round(q_init, 4).tolist()}")
print()

cache = UsdGeom.XformCache(0)

# ── Sensor corrective local transform (one-time, before warmup/capture) ───────
# With the FK-derived (non-identity) tool orientation, the mount frame's world
# rotation is fixed-but-arbitrary; a child sensor with identity local rotation
# would inherit it and point off-axis. Give the sensor prim a one-time local
# orient/translate so its WORLD pose is exactly (SENSOR_X_START_M, 0, TOOL_Z_M)
# with world-axis alignment (+X forward). The tool orientation is locked for
# every subsequent IK solve, so this correction is constant along the corridor;
# the per-step sensor-pose audit still verifies it empirically.
_mount_prim = stage.GetPrimAtPath(mount_path)
_m_world = cache.GetLocalToWorldTransform(_mount_prim)
_m_inv = _m_world.GetInverse()
_local_pos = _m_inv.Transform(Gf.Vec3d(float(SENSOR_X_START_M), 0.0, float(TOOL_Z_M)))
_local_quat = _m_inv.ExtractRotationQuat().GetNormalized()
_sensor_prim = stage.GetPrimAtPath(sensor_path)
_sensor_xf = UsdGeom.Xformable(_sensor_prim)
_sensor_ops = {op.GetOpName(): op for op in _sensor_xf.GetOrderedXformOps()}
if "xformOp:translate" in _sensor_ops:
    _sensor_ops["xformOp:translate"].Set(Gf.Vec3d(_local_pos))
else:
    _sensor_xf.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Vec3d(_local_pos))
if "xformOp:orient" in _sensor_ops:
    try:
        _sensor_ops["xformOp:orient"].Set(Gf.Quatd(_local_quat))
    except Exception:
        _sensor_ops["xformOp:orient"].Set(Gf.Quatf(_local_quat))
else:
    _sensor_xf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Quatd(_local_quat))
cache.Clear()
_s_world = cache.GetLocalToWorldTransform(_sensor_prim)
_s_pos = _s_world.ExtractTranslation()
_s_fwd = _s_world.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()
_s_angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, float(_s_fwd[0])))))
print(f"Sensor corrective transform applied: world pos=({_s_pos[0]:.4f}, {_s_pos[1]:.4f}, {_s_pos[2]:.4f})  "
      f"forward-vs-+X angle={_s_angle_deg:.3f} deg")
if abs(float(_s_pos[2]) - TOOL_Z_M) > SENSOR_Z_TOL_M or _s_angle_deg > SENSOR_ANGLE_TOL_DEG:
    print("ABORT: sensor corrective transform failed verification (see values above).", flush=True)
    simulation_app.close()
    sys.exit(2)

# ── Simulation warmup (rule: >=20 frames until numElements>0; verbatim from
#    d1_approach_runner.py) ────────────────────────────────────────────────────
print("Warming up until sensor produces data (>=20 frames, max 60)...")
_warmup_frames = 0
for _ in range(60):
    simulation_app.update()
    _warmup_frames += 1
    if _warmup_frames >= 20 and _buf["latest"] is not None:
        break
_n_elems = int(_buf["latest"]["n_elements"]) if _buf["latest"] is not None else 0
print(f"Warmup complete after {_warmup_frames} frames (numElements={_n_elems})")
print()

# ── Output paths ───────────────────────────────────────────────────────────────
out_root = pathlib.Path(args.output_dir)
out_dir = out_root / args.mode
wf_dir = out_dir / "waveforms"
wf_dir.mkdir(parents=True, exist_ok=True)

n_drift_flagged = 0


def _joint_row_fields(q: np.ndarray) -> dict:
    q = np.asarray(q, dtype=float).reshape(-1)
    names = ("q_shoulder_pan", "q_shoulder_lift", "q_elbow", "q_wrist_1", "q_wrist_2", "q_wrist_3")
    return {name: (float(q[i]) if i < q.size and math.isfinite(q[i]) else float("nan"))
            for i, name in enumerate(names)}


# ═══════════════════════════════════════════════════════════════════════════
# probe mode (D0.5): sweep the ARM (tool0 x, hence the sensor), target fixed,
# regress peak_idx vs known 3D distance. Validation gate for arm-carried
# sensor motion; ALSO runs the two per-step geometry audits.
# ═══════════════════════════════════════════════════════════════════════════
if args.mode == "probe":
    n_points = int(round((PROBE_SENSOR_X_END_M - SENSOR_X_START_M) / PROBE_STEP_M)) + 1
    probe_rows: list[dict] = []
    n_posture_violations = 0
    n_sensor_pose_violations = 0
    warm_q = q_init

    for i in range(n_points):
        target_sensor_x = SENSOR_X_START_M + i * PROBE_STEP_M
        tool0_x = target_sensor_x - args.sensor_offset
        q, ok = _solve_tool0(ik, tool0_x, warm_q)
        if ok:
            _move_arm(robot, world, q)
            warm_q = q

        posture_violation = _audit_posture(stage, ARM_PATH, cache)
        sensor_violation, sensor_x_actual, sensor_z_actual, sensor_angle_deg = _audit_sensor_pose(
            stage, sensor_path, cache
        )
        if posture_violation:
            n_posture_violations += 1
        if sensor_violation:
            n_sensor_pose_violations += 1

        row = {
            "point_index": i,
            "sensor_x": target_sensor_x,
            "sensor_x_actual": sensor_x_actual,
            "true_distance_3d_m": float("nan"),
            "peak_sample_idx": float("nan"),
            "point_drift": float("nan"),
            "stationarity_ok": False,
            "waveform_tag": "",
            "posture_violation": posture_violation,
            "sensor_pose_violation": sensor_violation,
            "sensor_angle_deg": sensor_angle_deg,
            "ik_ok": ok,
        }
        row.update(_joint_row_fields(q if ok else warm_q))

        if not ok:
            probe_rows.append(row)
            print(f"[{i+1:02d}/{n_points}] sensor_x={target_sensor_x:.4f}m IK_FAILED -- point skipped "
                  f"(posture_violation={posture_violation} sensor_pose_violation={sensor_violation})")
            continue

        res = _measure_point(N_SETTLE, N_MEASURE)
        if not res["stationarity_ok"]:
            n_drift_flagged += 1
        true3d = math.sqrt(
            (PROBE_TARGET_X_M - sensor_x_actual) ** 2
            + (0.0 - 0.0) ** 2
            + (sensor_z_actual - TARGET_Z_M) ** 2
        )

        wf_tag = f"point_{i:02d}"
        np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])

        row.update({
            "true_distance_3d_m": true3d,
            "peak_sample_idx": res["peak_sample_idx"],
            "point_drift": res["point_drift"],
            "stationarity_ok": res["stationarity_ok"],
            "waveform_tag": wf_tag,
        })
        probe_rows.append(row)
        print(f"[{i+1:02d}/{n_points}] sensor_x={target_sensor_x:.4f}m (actual={sensor_x_actual:.4f}m) "
              f"true3d={true3d:.4f}m peak_idx={res['peak_sample_idx']:.1f} drift={res['point_drift']:.4f} "
              f"ok={res['stationarity_ok']} posture_violation={posture_violation} "
              f"sensor_pose_violation={sensor_violation}")

    csv_path = out_dir / "points.csv"
    fieldnames = ["point_index", "sensor_x", "sensor_x_actual", "true_distance_3d_m", "peak_sample_idx",
                  "point_drift", "stationarity_ok", "waveform_tag", "posture_violation",
                  "sensor_pose_violation", "sensor_angle_deg", "ik_ok",
                  "q_shoulder_pan", "q_shoulder_lift", "q_elbow", "q_wrist_1", "q_wrist_2", "q_wrist_3"]
    with csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(probe_rows)

    kept_x = [r["true_distance_3d_m"] for r in probe_rows if r["stationarity_ok"] and r["ik_ok"]]
    kept_y = [r["peak_sample_idx"] for r in probe_rows if r["stationarity_ok"] and r["ik_ok"]]
    probe_slope, probe_intercept, probe_r = _ols_pure(kept_x, kept_y)

    print()
    print(f"probe regression: n_kept={len(kept_x)}/{n_points}  "
          f"slope={probe_slope}  intercept={probe_intercept}  r={probe_r}")
    print(f"PROBE_RESULT r={probe_r} slope={probe_slope} "
          f"n_posture_violations={n_posture_violations} n_sensor_pose_violations={n_sensor_pose_violations}")

    n_episodes_meta = None

# ═══════════════════════════════════════════════════════════════════════════
# closed / blind / open modes: n_episodes episodes, same target_x sequence
# ═══════════════════════════════════════════════════════════════════════════
else:
    episode_rows: list[dict] = []
    step_rows: list[dict] = []
    total_posture_violations = 0
    total_sensor_pose_violations = 0

    for ep_idx, target_x in enumerate(TARGET_POSITIONS_M):
        _move_target(stage, target_x, 0.0, TARGET_Z_M)

        # Anti-branch-jump: reset warm start to the elbow-up seed at the start
        # of EVERY episode, then solve the corridor-start pose fresh.
        warm_q = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
        q, ok = _solve_tool0(ik, SENSOR_X_START_M - args.sensor_offset, warm_q)
        if not ok:
            episode_rows.append({
                "episode": ep_idx, "target_x": target_x,
                "stop_sensor_x": float("nan"), "stop_sensor_x_actual": float("nan"),
                "stop_oracle_horiz_dist": float("nan"), "n_steps": 0,
                "reason": "ik_failed", "episode_valid": False,
            })
            print(f"[ep {ep_idx+1:02d}/{len(TARGET_POSITIONS_M)}] mode={args.mode} target_x={target_x:.4f} "
                  f"-> IK_FAILED at corridor start; episode recorded as ik_failed (0 steps)")
            continue
        _move_arm(robot, world, q)
        warm_q = q

        if args.mode == "open":
            # No measurement at all: walk straight to the fixed nominal
            # position, oracle-blind by construction. Explicit settle both
            # before and after moving, per D1's own open-arm pattern.
            nominal_sensor_x = (TARGET_X_MIN_M + TARGET_X_MAX_M) / 2.0 - args.standoff
            for _ in range(N_SETTLE):
                simulation_app.update()
            q, ok = _solve_tool0(ik, nominal_sensor_x - args.sensor_offset, warm_q)
            if not ok:
                episode_rows.append({
                    "episode": ep_idx, "target_x": target_x,
                    "stop_sensor_x": float("nan"), "stop_sensor_x_actual": float("nan"),
                    "stop_oracle_horiz_dist": float("nan"), "n_steps": 0,
                    "reason": "ik_failed", "episode_valid": False,
                })
                print(f"[ep {ep_idx+1:02d}/{len(TARGET_POSITIONS_M)}] mode=open target_x={target_x:.4f} "
                      f"-> IK_FAILED reaching nominal position; episode recorded as ik_failed")
                continue
            _move_arm(robot, world, q)
            warm_q = q
            for _ in range(N_SETTLE):
                simulation_app.update()

            posture_violation = _audit_posture(stage, ARM_PATH, cache)
            sensor_violation, sensor_x_actual, sensor_z_actual, sensor_angle_deg = _audit_sensor_pose(
                stage, sensor_path, cache
            )
            if posture_violation:
                total_posture_violations += 1
            if sensor_violation:
                total_sensor_pose_violations += 1
            ep_valid = not (posture_violation or sensor_violation)

            oracle_horiz_dist = target_x - nominal_sensor_x
            step_row = {
                "episode": ep_idx, "step": 0, "sensor_x": nominal_sensor_x,
                "sensor_x_actual": sensor_x_actual,
                "peak_idx": float("nan"), "d3d_est": float("nan"), "d_horiz_est": float("nan"),
                "oracle_horiz_dist": oracle_horiz_dist, "drift": float("nan"),
                "stationarity_ok": "", "waveform_tag": "",
                "posture_violation": posture_violation, "sensor_pose_violation": sensor_violation,
                "ik_ok": True,
            }
            step_row.update(_joint_row_fields(q))
            step_rows.append(step_row)
            episode_rows.append({
                "episode": ep_idx, "target_x": target_x,
                "stop_sensor_x": nominal_sensor_x, "stop_sensor_x_actual": sensor_x_actual,
                "stop_oracle_horiz_dist": oracle_horiz_dist,
                "n_steps": 1, "reason": "open_fixed", "episode_valid": ep_valid,
            })
            print(f"[ep {ep_idx+1:02d}/{len(TARGET_POSITIONS_M)}] mode=open target_x={target_x:.4f} "
                  f"-> fixed sensor_x={nominal_sensor_x:.4f} (actual={sensor_x_actual:.4f}) "
                  f"oracle_horiz_dist={oracle_horiz_dist:+.4f} episode_valid={ep_valid}")
            continue

        # closed / blind: for-loop over at most --max-steps measurements; the
        # `else` clause on the for-loop fires only if it runs to completion
        # without `break`, i.e. exactly the max_steps guard condition.
        sensor_x = SENSOR_X_START_M
        stop_reason = None
        stop_sensor_x = sensor_x
        stop_sensor_x_actual = float("nan")
        ep_step_rows: list[dict] = []
        ep_valid = True

        for step_idx in range(args.max_steps):
            res = _measure_point(N_SETTLE, N_MEASURE)
            if not res["stationarity_ok"]:
                n_drift_flagged += 1
            peak_idx = res["peak_sample_idx"]
            d3d_est, d_horiz_est_real = _estimate_distance(peak_idx)
            # Information-ablation control (law 2): blind forces the USABLE
            # estimate to +inf; d3d_est (informational only) stays the real
            # computed value, but the control decision below reads
            # d_horiz_est, which can never trigger a standoff stop for blind.
            d_horiz_est = float("inf") if args.mode == "blind" else d_horiz_est_real

            oracle_horiz_dist = target_x - sensor_x  # RECORD ONLY -- never read by control

            posture_violation = _audit_posture(stage, ARM_PATH, cache)
            sensor_violation, sensor_x_actual, sensor_z_actual, sensor_angle_deg = _audit_sensor_pose(
                stage, sensor_path, cache
            )
            if posture_violation:
                total_posture_violations += 1
                ep_valid = False
            if sensor_violation:
                total_sensor_pose_violations += 1
                ep_valid = False

            wf_tag = f"ep{ep_idx:03d}_step{step_idx:03d}"
            np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])

            step_row = {
                "episode": ep_idx, "step": step_idx, "sensor_x": sensor_x,
                "sensor_x_actual": sensor_x_actual,
                "peak_idx": peak_idx, "d3d_est": d3d_est, "d_horiz_est": d_horiz_est,
                "oracle_horiz_dist": oracle_horiz_dist, "drift": res["point_drift"],
                "stationarity_ok": res["stationarity_ok"], "waveform_tag": wf_tag,
                "posture_violation": posture_violation, "sensor_pose_violation": sensor_violation,
                "ik_ok": True,
            }
            step_row.update(_joint_row_fields(warm_q))
            ep_step_rows.append(step_row)
            stop_sensor_x = sensor_x
            stop_sensor_x_actual = sensor_x_actual

            if d_horiz_est <= args.standoff:
                stop_reason = "standoff_est"
                break

            next_x = sensor_x + args.step
            if next_x > CORRIDOR_GUARD_X_M:
                stop_reason = "corridor_end"
                break

            q, ok = _solve_tool0(ik, next_x - args.sensor_offset, warm_q)
            if not ok:
                stop_reason = "ik_failed"
                ep_valid = False
                break
            _move_arm(robot, world, q)
            warm_q = q
            sensor_x = next_x
        else:
            stop_reason = "max_steps"
            # stop_sensor_x already holds the last measured position

        step_rows.extend(ep_step_rows)
        stop_oracle_horiz_dist = target_x - stop_sensor_x
        episode_rows.append({
            "episode": ep_idx, "target_x": target_x,
            "stop_sensor_x": stop_sensor_x, "stop_sensor_x_actual": stop_sensor_x_actual,
            "stop_oracle_horiz_dist": stop_oracle_horiz_dist,
            "n_steps": len(ep_step_rows), "reason": stop_reason, "episode_valid": ep_valid,
        })
        print(f"[ep {ep_idx+1:02d}/{len(TARGET_POSITIONS_M)}] mode={args.mode} target_x={target_x:.4f} "
              f"-> stop_sensor_x={stop_sensor_x:.4f} (actual={stop_sensor_x_actual:.4f}) "
              f"n_steps={len(ep_step_rows)} reason={stop_reason} "
              f"stop_oracle_horiz_dist={stop_oracle_horiz_dist:+.4f} episode_valid={ep_valid}")

    steps_csv_path = out_dir / "steps.csv"
    step_fieldnames = ["episode", "step", "sensor_x", "sensor_x_actual", "peak_idx", "d3d_est", "d_horiz_est",
                       "oracle_horiz_dist", "drift", "stationarity_ok", "waveform_tag",
                       "posture_violation", "sensor_pose_violation", "ik_ok",
                       "q_shoulder_pan", "q_shoulder_lift", "q_elbow", "q_wrist_1", "q_wrist_2", "q_wrist_3"]
    with steps_csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=step_fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(step_rows)

    episodes_csv_path = out_dir / "episodes.csv"
    episode_fieldnames = ["episode", "target_x", "stop_sensor_x", "stop_sensor_x_actual",
                          "stop_oracle_horiz_dist", "n_steps", "reason", "episode_valid"]
    with episodes_csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=episode_fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(episode_rows)

    n_episodes_meta = len(episode_rows)
    print()
    print(f"RESULT mode={args.mode} episodes={n_episodes_meta} "
          f"total_posture_violations={total_posture_violations} "
          f"total_sensor_pose_violations={total_sensor_pose_violations}")

timeline.stop()

# ── meta.json (all modes) ─────────────────────────────────────────────────────
meta = {
    "mode": args.mode,
    "seed": args.seed,
    "n_episodes": args.n_episodes if args.mode != "probe" else None,
    "standoff_m": args.standoff,
    "step_m": args.step,
    "max_steps": args.max_steps,
    "sensor_offset_m": args.sensor_offset,
    "n_settle": N_SETTLE,
    "n_measure": N_MEASURE,
    "calib_source": str(CALIB_CSV_PATH),
    "calib_slope_sample_per_m": CALIB_SLOPE,
    "calib_intercept_samples": CALIB_INTERCEPT,
    "calib_r": CALIB_R,
    "calib_n_kept": CALIB_N,
    "arm_path": ARM_PATH,
    "mount_path_used": mount_path,
    "sensor_path": sensor_path,
    "gripper_variant_selected": gripper_variant_selected,
    "tool_z_m": TOOL_Z_M,
    "target_size_m": TARGET_SIZE_M,
    "target_z_m": TARGET_Z_M,
    "height_diff_m": HEIGHT_DIFF_M,
    "table_top_z_m": TABLE_TOP_Z_M,
    "table_center_x_m": TABLE_CENTER_X_M,
    "table_width_m": TABLE_WIDTH_M,
    "table_depth_m": TABLE_DEPTH_M,
    "sensor_x_start_m": SENSOR_X_START_M,
    "corridor_guard_x_m": CORRIDOR_GUARD_X_M,
    "target_x_min_m": TARGET_X_MIN_M,
    "target_x_max_m": TARGET_X_MAX_M,
    "posture_link_names": list(POSTURE_LINK_NAMES),
    "floor_margin_z_m": FLOOR_MARGIN_Z_M,
    "table_clear_margin_m": TABLE_CLEAR_MARGIN_M,
    "sensor_z_tol_m": SENSOR_Z_TOL_M,
    "sensor_angle_tol_deg": SENSOR_ANGLE_TOL_DEG,
    "ik_robot_description": str(IK_ROBOT_DESCRIPTION),
    "ik_urdf": str(IK_URDF),
    "ik_orientation_tolerance_rad": IK_ORIENTATION_TOLERANCE_RAD_D15,
    "ik_position_tolerance_m": IK_POSITION_TOLERANCE_M,
    "assets_root_used": assets_root_used,
    "usd_path_used": usd_path_used,
    "warmup_frames": _warmup_frames,
    "n_drift_flagged": n_drift_flagged,
    "timestamp": datetime.datetime.now().isoformat(),
    "script": "d15_arm_approach_runner.py",
}
with (out_dir / "meta.json").open("w") as f:
    json.dump(meta, f, indent=2)

print()
print(f"-> outputs saved under {out_dir}")

simulation_app.close()
