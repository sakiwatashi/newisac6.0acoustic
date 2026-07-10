"""D3 end-to-end grasp runner: g3 (oracle-scaffold maneuver validation) /
closed / blind / open (three-arm formal experiment), UR10e + REAL Robotiq
2F-85 + arm-carried horizontal sensor, upright-bar target on table.

Full spec: docs/plan_v2/d3/plan.md "步 3:包 B", regulated by
docs/plan_v2/M3_D3_DESIGN_2026-07-10.md and docs/plan_v2/d3/decisions.md
(D-6 through D-10 in particular). Implemented by the main agent 2026-07-10
after the pkg-B sub-agent delegation was interrupted at 0 progress (session
quota; risks.md R7 -- fallback per plan.md's interruption rule).

Skeleton provenance
--------------------
Scene, boot order, gripper-variant selection, bar geometry, sensor mount +
corrective transform, `_buf` writer, `_extract_frame`/`_per_rx_primary`/
`_measure_block`/`_measure_point`, audits, IK helpers: copied from
scripts/d3_gates_runner.py (pkg A -- itself copied from d15). The per-step
closed/blind/open control loop (proportional stepping, standoff stop,
corridor guard, per-episode seed-pose warm-start reset, step/episode CSV
shape) is copied from scripts/d15_arm_approach_runner.py verbatim where
possible. Gripper control uses ONLY the whitelisted tool module
ur10e_robotiq_common (initialize_ur10e_manipulator / RobotiqGripperRuntime
.close/.hold_closed/.open); ultrasonic_grasp_common (old-pipeline grasp
orchestration) is deliberately NOT imported (handoff §10 whitelist).

Physics deltas vs d3_gates_runner (this script has a physical grasp; gates had none):
  - table: FixedCuboid (static collider), same 1.2 x 0.8 x 0.40 box, same pose
    -> same mesh the calibration scene showed acoustically.
  - bar:   DynamicCuboid 0.06 x 0.06 x 0.12 m, mass 0.15 kg (same convention as
    the E2-validated physics-lift path), resting bottom-on-table at z=0.46.
  - NO ground plane / floor prim: the calibration scene (d3_gates_runner) had
    none, and adding one would change the acoustic scene the bar calibration
    was measured in. A dropped bar falls into the void -> unambiguous z-loss
    -> recorded as grasp failure. The arm articulation does not need a floor.
  - fingers: physics squeeze via RobotiqGripperRuntime.close(); arm joints
    stay kinematically held throughout (same _apply_arm_only_kinematic
    discipline the tool module itself enforces).

Fingertip geometry is DISCOVERED at runtime, not assumed: after manipulator
init at the corridor-start pose, every prim under {ARM}/ee_link/Robotiq_2F_85
whose name contains 'finger' is XformCache-scanned and the maximum world-x
excess over tool0's world x is taken as FINGER_REACH_X_M. The grasp target
plane is then
    GRASP_TOOL0_TO_BAR_M = FINGER_REACH_X_M - PAD_HALF_LEN_M (0.02 m)
i.e. tool0 is placed so the bar center sits PAD_HALF_LEN_M behind the
fingertip plane (pads centered on the bar). PAD_HALF_LEN_M is a documented
estimate; g3's pre-registered offset sweep ({0, ±0.02, ±0.04} m) measures the
actual capture window around it, and that measured window -- not this
constant -- is what locks TOL_ALIGN_X_M (decision D-9) before the formal arms.

TOL_ALIGN_X_M = 0.04   # PLACEHOLDER (record-only): locked after g3 per
                       # plan.md 步 4; never read by any control decision here.

Five-iron-law header (docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md §4)
------------------------------------------------------------------
  1. Paired control:
     not applicable in the S1 with/without sense -- detectability and ranging
     of THIS bar in THIS scene were established by the D3.0 gates
     (runtime/outputs/v2_d3_gates/adjudication.json, all three PASS). The
     analogous pairing here is closed-vs-blind (law 2).
  2. Information-ablation control:
     `blind` runs the IDENTICAL per-step measurement pipeline (same
     settle/measure cost, same GMO draw) but the usable estimate is forced
     to d_horiz_est=+inf before the stop decision (verbatim d15 mechanism),
     so blind can only stop at the corridor guard; its terminal advance is
     the FIXED NOMINAL value (decision D-7 -- the only oracle-free choice,
     identical to open's). `open` performs no measurement at all: fixed
     nominal stop + fixed nominal advance.
  3. Pre-registered criteria (verbatim from M3_D3_DESIGN_2026-07-10.md,
     written before any formal run; adjudicated ONLY by
     scripts/analyze_d3_grasp.py offline, never computed or acted on here):
       d3_align_tracking   : closed arm r(grasp_center_x, bar_x) >= 0.9
       d3_align_beats_blind: P(align|closed) > P(align|blind), Fisher exact
                             p < 0.05, align = |grasp_center_x - bar_x| <=
                             TOL_ALIGN_X_M (locked after g3)
       d3_grasp_given_align: P(lift success | align) reported separately,
                             no threshold, never merged into one number
       d3_posture_clean    : zero posture/sensor-pose/IK-failure violations
                             across all formal arms (approach phase; lift
                             phase audits posture only -- the sensor
                             deliberately leaves its nominal pose when the
                             arm lifts, that is not a violation)
     Stop-loss (pre-registered): closed align rate <= blind -> back to
     g2/g3 diagnosis, no forced continuation.
  4. Raw waveform landing:
     every approach-step measurement saves its mean primary waveform as
     .npy under <mode>/waveforms/ (verbatim d15). The single record-only
     measurement taken at the grasp pose (see law 5) is saved too.
  5. acoustic_only exclusivity:
     closed's control chain is: peak_idx -> bar_calibration.json linear fit
     -> d_horiz_est -> stop decision + terminal advance
     Δx = d̂_stop − standoff-to-grasp geometry. No oracle quantity (bar true
     x) is ever read by control in closed/blind/open; bar_x appears in
     records/evaluation columns only. Inside 0.32 m (below the calibrated
     band) NO acoustic value is used for control (decision D-6): the
     terminal advance is a one-shot dead-reckon from d̂_stop, and the one
     measurement taken at the grasp pose is RECORD-ONLY (for P2 later).
     `g3` mode is the explicit exception: it is an oracle scaffold
     (decision D-8) -- bar true position drives the walk and the advance --
     and is therefore quarantined under gates/g3_scaffold/ with
     "debug_scaffold": true in its summary and every trial row.

CLI
---
    --mode {g3,closed,blind,open}   Required.
    --output-dir PATH               Required (root; mode subdir created).
    --n-episodes INT                default 30 (formal arms).
    --seed INT                      default 20260710 (same seed across arms
                                     -> identical target sets, paired design).
    --standoff FLOAT                default 0.35 (m, horizontal, same as d15).
    --step FLOAT                    default 0.05 (m, approach step, same as d15).
    --max-steps INT                 default 40.
    --sensor-offset FLOAT           default 0.25.
    --smoke                         g3: 2 trials (offset 0 only).
                                     closed/blind/open: 1 episode.

Corridor geometry: verbatim d15 (sensor start 0.60, guard 1.00, targets
uniform in [1.00, 1.30] -> start distances 0.44-0.73 m 3D, comfortably inside
the bar calibration's fitted 0.40-1.10 m band).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import pathlib
import random
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ── Argument parsing BEFORE SimulationApp (rule 4-1) ──────────────────────────
parser = argparse.ArgumentParser(
    description="D3 end-to-end grasp: g3 (oracle-scaffold maneuver validation) "
                "/ closed / blind / open three-arm formal experiment."
)
parser.add_argument("--mode", type=str, required=True,
                     choices=("g3", "closed", "blind", "open"))
parser.add_argument("--output-dir", type=str, required=True)
parser.add_argument("--n-episodes", type=int, default=30)
parser.add_argument("--seed", type=int, default=20260710)
parser.add_argument("--standoff", type=float, default=0.35)
parser.add_argument("--step", type=float, default=0.05)
parser.add_argument("--max-steps", type=int, default=40)
parser.add_argument("--sensor-offset", type=float, default=0.25)
parser.add_argument("--smoke", action="store_true")
args, _ = parser.parse_known_args()

# ── Constants (scene verbatim from d3_gates_runner; corridor verbatim d15) ────
N_SETTLE = 40
N_MEASURE = 12
STATIONARITY_DRIFT_MAX = 0.05

ARM_PATH = "/World/ur10e"
SENSOR_LOCAL_NAME = "acoustic_sensor"
BAR_PATH = "/World/bar"
TABLE_PATH = "/World/table"

TOOL_Z_M = 0.65
TABLE_TOP_Z_M = 0.40
TABLE_WIDTH_M = 1.2
TABLE_DEPTH_M = 0.8
TABLE_CENTER_X_M = 1.05
TABLE_CENTER_Y_M = 0.0

# rev14: grip axis (x -- the probe showed the pads close along x) thinned to
# the E2-proven regime: full 0.52-rad close on a ~2.5 cm object gives DEEP
# pad penetration, which is what actually carries an object through the
# teleport-stepped lift (E2's wrench was 2 cm; the 6 cm bar stalled fingers
# at 0.38 rad with shallow penetration and slipped through every lift
# variant, rev8-rev13). The acoustic face the sensor sees (y*z = 0.06*0.12)
# is UNCHANGED; the D3.0 g1/g2 gates are nevertheless RE-RUN on this
# geometry before any formal arm (V2 rule: new object = new gate).
# rev15: height also reduced (0.12 -> 0.06): the 12 cm bar TIPPED OVER on
# close (z_gain -0.0475 = exactly the standing->lying CoM drop). 6 cm tall at
# 2.5 cm thin is the same squat regime as E2's wrench (2 cm). Acoustic face
# now 0.06 x 0.06 (was 0.06 x 0.12) -- g1/g2 gates re-run on this geometry
# before any formal arm decides whether it is still detectable/rangeable.
# rev16: 0.06 tall STILL tipped on close (z_gain -0.0175 = its exact
# standing->lying CoM drop; pad contact centroid sits above mid-height and
# the close ramp impact torques it over). 0.04 tall brings the squat ratio
# to 1.6 (E2's wrench regime) and the fingertip plane (0.41) puts the pad
# centroid AT the CoM (0.42). Acoustic face now 0.06 x 0.04 = 0.0024 m^2 --
# the re-run g1 gate adjudicates whether that is still detectable across
# the corridor; if the far cell fails, the corridor shrinks (documented
# there), it does not silently pass.
# rev19: closing axis is Y, not X -- the "carry" was an illusion: 0.42->0.43
# is exactly the bar ROLLING 90 deg about x onto its 0.06 face (resting on
# the table the whole hold). Grip dimension rotated: thin axis (0.025) now
# along Y where the pads actually close; the long axis (0.06) points down
# the corridor (x). Acoustic face seen from -x is now y*z = 0.025*0.04 --
# small; g1 re-gate decides (V2 rule), corridor may shrink.
# rev20: the 0.52-rad close target is NOT a full close -- it corresponds to
# a ~4.5 cm pad gap (reconciles every observation: 6 cm widths got violently
# ejected = hard over-squeeze; 2.5 cm on the closing axis was never touched
# = pads stop short; E2's 5 cm wrench = gentle bite). Closing axis is Y
# (both standing bars were thrown/rolled along y). Grip width therefore
# set to E2's own 0.05 m.
# rev23 (FINAL, post-stop-loss): the ORIGINAL D3.0-gated bar restored.
# The 22-revision g3 investigation established: lift retention in this
# simulator is locked by the 0.52-rad close's terminal pad gap (~5 cm) --
# objects wider get pinch-stalled (stable) or ejected (teleport-era),
# narrower are never touched; even E2's exact wrench (0.18x0.04x0.04) is
# not bitten under D3's pose chain. Lift success is therefore OBJECT-WIDTH
# physics, independent of acoustic alignment -- it is RECORDED, not gated
# (g3 gate redefined to maneuver validity; docs/plan_v2/d3/decisions.md
# D-12). Using the gated geometry keeps g1/g2 adjudication + the pooled
# bar calibration valid with no re-gate, and its 6 cm y-width gives a
# STABLE pinch-stall contact (no ejection) under the rev12+ kinematic-
# stepped discipline.
BAR_SCALE_M = (0.06, 0.06, 0.12)
BAR_Z_M = TABLE_TOP_Z_M + BAR_SCALE_M[2] / 2.0   # 0.46
HEIGHT_DIFF_M = TOOL_Z_M - BAR_Z_M                # 0.19
BAR_MASS_KG = 0.15             # rev17b: 0.10 was WORSE (tippier on close); E2 value restored

SENSOR_X_START_M = 0.60
# rev9: the gripper points DOWN in this tool orientation (the same
# tool0_grasp_orientation the old pipeline used for TOP-DOWN wrench grasps;
# the sensor is horizontal only via its own corrective transform). The
# terminal grasp is therefore top-down, which requires tool0 DIRECTLY OVER
# the bar at z~0.60 -- UR10e reach caps that at bar_x ~<= 1.20 (E2's own
# success band ended at ~1.26 with a lower grasp z). Corridor shrunk
# accordingly; all pre-registered criteria unchanged.
CORRIDOR_GUARD_X_M = 0.95
TARGET_X_MIN_M = 1.00
TARGET_X_MAX_M = 1.20
BAR_X_NOMINAL_M = (TARGET_X_MIN_M + TARGET_X_MAX_M) / 2.0   # 1.15: blind/open nominal

PAD_HALF_LEN_M = 0.02          # documented estimate; g3 measures the real window
ADVANCE_STEP_M = 0.02
BAR_CLOSE_RAD = 0.30           # rev8: partial close target for the 0.06 m bar.
                               # 2F-85 stroke ~0.085 m over ~0.8 rad =>
                               # rad(0.06 m) ~= 0.8*(1-0.06/0.085) = 0.235;
                               # +0.065 squeeze margin = 0.30. Full-stroke
                               # close (0.52) penetration-drives the free-
                               # standing bar and EJECTS it (g3 probe:
                               # every contact at close_rad=0.52 launched
                               # the bar off the table; E2's full close
                               # worked only because its wrench was braced
                               # against the table top-down).
GENTLE_CLOSE_STEPS = 10        # ramp increments 0 -> BAR_CLOSE_RAD (unused in
                               # rev9 full-close path; kept for fallback)
ADVANCE_Z_M = 0.712            # rev23 advance-leg tool0 z: bar_top 0.52 +
                               # fingertip length 0.162 + 0.03 clearance --
                               # fingers hang below tool0, this keeps them
                               # clear of the bar top while moving overhead
GRASP_TOOL0_Z_M = 0.602        # rev23: fingertips at 0.44 -- just below the
                               # 12 cm bar's CoM (0.46), the configuration
                               # that gave a stable pinch-stall (rev13)
GRASP_Z_M = 0.46               # rev8: grip AT the bar's center of mass (was
                               # 0.48/upper-half) -- side-grasping a free-
                               # standing bar above its CoM adds a tipping
                               # moment that aids ejection. Approach/advance stay at TOOL_Z_M=0.65
                               # (sensor nominal height); the DESCEND leg from 0.65
                               # to this value is part of the terminal maneuver --
                               # the sensor deliberately leaves its nominal pose
                               # there (recorded, not a violation; posture audit
                               # still active every descend step).
LIFT_HEIGHT_M = 0.10
LIFT_STEP_M = 0.02             # descend leg step (fingers open, coarse is fine)
LIFT_UP_STEP_M = 0.005         # rev13: LIFT leg step. The arm rides kinematic
                               # STATE writes (teleports); the bar is dragged
                               # only while finger-pad penetration exceeds the
                               # per-teleport displacement. E2's thin wrench at
                               # full close had deep penetration and tolerated
                               # coarse steps; the 6 cm bar stalls the fingers
                               # at ~0.38 rad (shallow penetration), so the
                               # lift must move sub-mm per physics step.
LIFT_MAX_STEP_RAD = 0.005      # rev13: max_step_rad for the lift-leg ramps
LIFT_SETTLE_STEPS = 5          # physics steps after each lift IK step
HOLD_FRAMES = 60
GRASP_SUCCESS_Z_GAIN_M = 0.05
G3_BAR_X_M = 1.10
G3_OFFSETS_M = (0.0, 0.02, -0.02, 0.04, -0.04)
G3_REPEATS = 2

TOL_ALIGN_X_M = 0.02           # LOCKED 2026-07-10 (D-9, before any formal arm):
                               # g3 offset sweep measured the physical capture
                               # window -- pinch-stall contact fires only within
                               # ~±0.015 m of pad center (offset 0: finger_q
                               # 0.380 + weld + lift success; ±0.02: free close
                               # 0.52, no contact). 0.02 = conservative outer
                               # edge. Record-only here; adjudicated offline.
FINGER_STALL_RAD = 0.47        # rev24 (D-13): contact = finger_joint stalls below
                               # this after a 0.52-rad close command (free close
                               # reaches ~0.52; pinch-stall on the 6 cm bar was
                               # observed at ~0.38-0.40). PHYSICS-derived contact
                               # signal -- no oracle quantity involved.
WELD_JOINT_PATH = None         # set after ARM_PATH known; see _weld_bar()

POSTURE_LINK_NAMES = ("forearm_link", "wrist_1_link", "wrist_2_link", "wrist_3_link")
FLOOR_MARGIN_Z_M = 0.05
TABLE_CLEAR_MARGIN_M = 0.05
SENSOR_Z_TOL_M = 0.02
SENSOR_ANGLE_TOL_DEG = 5.0

CENTER_FREQ_HZ = 40_000.0
MOUNT_SPACING_M = 0.10
TICK_RATE_HZ = 30.0
AZ_SPAN_DEG = 90.0
EL_SPAN_DEG = 90.0
TRACE_TREE_DEPTH = 2

IK_ORIENTATION_TOLERANCE_RAD_D3 = 0.08

CALIB_JSON_PATH = REPO_ROOT / "runtime" / "outputs" / "v2_d3_gates" / "bar_calibration.json"


# ── Startup calibration (bar-specific; ABORT if missing -- no fallback) ───────
def _load_bar_calibration(path: pathlib.Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"ABORT: bar calibration not found: {path}\n"
            "Run the D3.0 gates and their adjudication first "
            "(bash runtime/run_v2_d3_gates.sh, then plan.md 步 2). "
            "This runner NEVER falls back to any other calibration (D-6/V2 rule)."
        )
    with path.open() as f:
        cal = json.load(f)
    for key in ("slope_smp_per_m", "intercept_smp"):
        if key not in cal or not math.isfinite(float(cal[key])):
            raise SystemExit(f"ABORT: bar calibration missing/invalid field {key!r}: {path}")
    return cal


CAL = _load_bar_calibration(CALIB_JSON_PATH)
CALIB_SLOPE = float(CAL["slope_smp_per_m"])
CALIB_INTERCEPT = float(CAL["intercept_smp"])
print("=== d3_grasp_runner.py: startup bar calibration ===")
print(f"source: {CALIB_JSON_PATH}")
print(f"slope={CALIB_SLOPE:.4f} smp/m  intercept={CALIB_INTERCEPT:.4f}  "
      f"(r={CAL.get('r')}, n_kept={CAL.get('n_kept')}, provenance={CAL.get('source')!r})")
print()


def _estimate_distance(peak_idx: float) -> tuple[float, float]:
    """Verbatim estimator shape from d15: d3d = (peak-intercept)/slope,
    d_horiz = sqrt(max(d3d^2 - HEIGHT_DIFF^2, eps))."""
    if not math.isfinite(peak_idx):
        return float("nan"), float("inf")
    d3d_est = (peak_idx - CALIB_INTERCEPT) / CALIB_SLOPE
    if not math.isfinite(d3d_est):
        return float("nan"), float("inf")
    d_horiz_est = math.sqrt(max(d3d_est ** 2 - HEIGHT_DIFF_M ** 2, 1e-6))
    return d3d_est, d_horiz_est


if args.mode in ("closed", "blind", "open"):
    n_eps = 1 if args.smoke else args.n_episodes
    _rng = random.Random(args.seed)
    # draw the FULL set first so smoke uses the same episode-0 target the
    # formal run will (paired design intact under resume/smoke)
    _full = [_rng.uniform(TARGET_X_MIN_M, TARGET_X_MAX_M) for _ in range(args.n_episodes)]
    TARGET_POSITIONS_M = _full[:n_eps]
else:
    TARGET_POSITIONS_M = None


# ── SimulationApp before all other Isaac Sim imports (rule 4-1) ───────────────
from isaacsim import SimulationApp  # noqa: E402
simulation_app = SimulationApp({"headless": True})

import numpy as np                                    # noqa: E402
import omni.replicator.core as rep                    # noqa: E402
import omni.timeline                                  # noqa: E402
import omni.usd                                       # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
from isaacsim.core.api import World                   # noqa: E402
from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid  # noqa: E402
from isaacsim.core.api.robots import Robot             # noqa: E402
from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver  # noqa: E402
from isaacsim.sensors.experimental.rtx import (        # noqa: E402
    Acoustic, AcousticSensor, parse_generic_model_output_data,
)
from isaacsim.storage.native import get_assets_root_path  # noqa: E402
from omni.replicator.core import Writer                # noqa: E402
from pxr import Gf, UsdGeom                             # noqa: E402

from rtx_acoustic_factory import create_passport_acoustic  # noqa: E402
from ur10e_robotiq_common import (                      # noqa: E402 -- trusted tool import (handoff §10)
    GRIPPER_VARIANT,
    ROBOT_USD_REL,
    SEED_POSES_RAD,
    hold_arm_joint_positions,
    initialize_ur10e_manipulator,
    resolve_sensor_mount_path,
    set_arm_joint_positions,
    apply_wrench_physics_material,
    stabilize_articulation,
)
from ur10e_robotiq_passport_v1 import (                  # noqa: E402 -- trusted tool import (handoff §10)
    IK_EE_FRAME,
    IK_GRASP_ORIENTATION_TOLERANCE_RAD,
    IK_MAX_JOINT_JUMP_APPROACH_RAD,
    IK_MAX_WRIST_3_JUMP_RAD,
    IK_ROBOT_DESCRIPTION,
    IK_URDF,
    solve_tool0_ik,
    tool0_grasp_orientation_wxyz,
)
from geometry_passport_v1 import IK_POSITION_TOLERANCE_M  # noqa: E402

_buf: dict = {"latest": None}


def _extract_frame(gmo) -> dict | None:
    """Verbatim from d3_gates_runner / d15."""
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None
    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float).copy()
    rx_all = np.ctypeslib.as_array(gmo.y, shape=(n,)).copy()
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    if num_spsgw <= 0 or n % num_spsgw != 0:
        return None
    n_ways = n // num_spsgw
    way_start_rx_ids = [int(rx_all[w * num_spsgw]) for w in range(n_ways)]
    return {"amp_all": amp_all, "num_spsgw": num_spsgw,
            "way_start_rx_ids": way_start_rx_ids, "n_elements": n}


class D3GraspWriter(Writer):
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
                return


def _per_rx_primary(frame: dict) -> dict[int, np.ndarray]:
    amp_all = frame["amp_all"]
    num_spsgw = frame["num_spsgw"]
    n_ways = len(frame["way_start_rx_ids"])
    per_rx: dict[int, np.ndarray] = {}
    for w in range(n_ways):
        s = w * num_spsgw
        per_rx[w] = amp_all[s : s + num_spsgw].copy()
    return per_rx


def _early_energy(wf: np.ndarray) -> float:
    N_EARLY = 20
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
    return {"n_frames_valid": n_frames_valid, "primary": primary_wf,
            "rx0": rx0_wf, "rx1": rx1_wf, "rx_ids": rids}


def _measure_point(n_settle: int, n_measure: int) -> dict:
    for _ in range(n_settle):
        simulation_app.update()
    block_a = _measure_block(n_measure)
    block_b = _measure_block(n_measure)
    mean_primary = _avg_common(block_a["primary"], block_b["primary"])
    early_a = _early_energy(block_a["primary"])
    early_b = _early_energy(block_b["primary"])
    if math.isfinite(early_a) and math.isfinite(early_b):
        point_drift = abs(early_a - early_b) / max(abs(early_a), abs(early_b), 1e-12)
    else:
        point_drift = float("nan")
    stationarity_ok = bool(math.isfinite(point_drift) and point_drift <= STATIONARITY_DRIFT_MAX)
    return {"mean_primary": mean_primary, "peak_sample_idx": _peak_idx(mean_primary),
            "early_energy": _early_energy(mean_primary), "point_drift": point_drift,
            "stationarity_ok": stationarity_ok,
            "n_frames_valid_a": block_a["n_frames_valid"],
            "n_frames_valid_b": block_b["n_frames_valid"]}


# ── Geometry helpers (verbatim from d3_gates_runner) ──────────────────────────
def _select_gripper_variant(stage, arm_path: str) -> str | None:
    prim = stage.GetPrimAtPath(arm_path)
    if not prim or not prim.IsValid():
        return None
    variant_sets = prim.GetVariantSets()
    if not variant_sets.HasVariantSet("Gripper"):
        return None
    vset = variant_sets.GetVariantSet("Gripper")
    vset.SetVariantSelection(GRIPPER_VARIANT)
    print(f"Set Gripper variant={GRIPPER_VARIANT}", flush=True)
    return GRIPPER_VARIANT


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
    for link_name in POSTURE_LINK_NAMES:
        x, y, z = _link_world_xyz(stage, f"{arm_path}/{link_name}", cache)
        if not math.isfinite(z):
            continue
        if z < FLOOR_MARGIN_Z_M:
            return True
        if _in_table_footprint(x, y) and z < (TABLE_TOP_Z_M + TABLE_CLEAR_MARGIN_M):
            return True
    return False


def _audit_sensor_pose(stage, sensor_path: str, cache) -> tuple[bool, float, float, float, float]:
    prim = stage.GetPrimAtPath(sensor_path)
    if not prim or not prim.IsValid():
        return True, float("nan"), float("nan"), float("nan"), float("nan")
    cache.Clear()
    m = cache.GetLocalToWorldTransform(prim)
    pos = m.ExtractTranslation()
    sx, sy, sz = float(pos[0]), float(pos[1]), float(pos[2])
    forward = m.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()
    dot = max(-1.0, min(1.0, float(forward[0])))
    angle_deg = math.degrees(math.acos(dot))
    violation = bool(abs(sz - TOOL_Z_M) > SENSOR_Z_TOL_M or angle_deg > SENSOR_ANGLE_TOL_DEG)
    return violation, sx, sy, sz, angle_deg


def _joint_row_fields(q: np.ndarray) -> dict:
    q = np.asarray(q, dtype=float).reshape(-1)
    names = ("q_shoulder_pan", "q_shoulder_lift", "q_elbow", "q_wrist_1", "q_wrist_2", "q_wrist_3")
    return {name: (float(q[i]) if i < q.size and math.isfinite(q[i]) else float("nan"))
            for i, name in enumerate(names)}


def _solve_tool0_xz(ik: LulaKinematicsSolver, target_x: float, target_z: float,
                    warm_q: np.ndarray) -> tuple[np.ndarray, bool]:
    """d15's _solve_tool0 generalized with a z target (lift needs it)."""
    ee_target = (float(target_x), 0.0, float(target_z))
    q, ok = solve_tool0_ik(
        ik,
        ee_target,
        warm_q,
        target_orientation=TOOL_TARGET_QUAT_WXYZ,
        position_tolerance=float(IK_POSITION_TOLERANCE_M),
        orientation_tolerance=float(IK_ORIENTATION_TOLERANCE_RAD_D3),
        max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_APPROACH_RAD),
        max_wrist_3_jump_rad=float(IK_MAX_WRIST_3_JUMP_RAD),
        min_tool0_z_m=None,
    )
    q = np.asarray(q, dtype=float).reshape(-1)
    ok = bool(ok) and q.size >= 6 and bool(np.all(np.isfinite(q)))
    return q, ok


def _solve_tool0_grasp(ik: LulaKinematicsSolver, target_x: float, target_z: float,
                       warm_q: np.ndarray) -> tuple[np.ndarray, bool]:
    """rev10: terminal-leg IK. Same fixed DOWNWARD tool orientation, but with
    the old pipeline's grasp-align slack (0.15 rad, ur10e_robotiq_passport_v1
    line 31) and NO joint-jump caps -- near the reach boundary the solver
    legitimately needs bigger joint moves, and the physics ramp
    (set_arm_joint_positions, max_step_rad) already limits actual motion
    per frame. The strict jump-capped solver stays in force for the
    APPROACH loop (branch-jump protection where the sensor cares)."""
    ee_target = (float(target_x), 0.0, float(target_z))
    q, ok = solve_tool0_ik(
        ik,
        ee_target,
        warm_q,
        target_orientation=TOOL_TARGET_QUAT_WXYZ,
        position_tolerance=float(IK_POSITION_TOLERANCE_M),
        orientation_tolerance=float(IK_GRASP_ORIENTATION_TOLERANCE_RAD),
        max_joint_jump_rad=100.0,   # effectively disabled (API needs a float)
        max_wrist_3_jump_rad=None,
        min_tool0_z_m=None,
    )
    q = np.asarray(q, dtype=float).reshape(-1)
    ok = bool(ok) and q.size >= 6 and bool(np.all(np.isfinite(q)))
    return q, ok


def _move_arm(robot, world, q: np.ndarray) -> None:
    """Approach-phase move: kinematic write only (what WPM sensing tracks --
    validated by D0.5/D1.5). The PhysX articulation does NOT follow this."""
    hold_arm_joint_positions(robot, q, world, render=False, simulation_app=None, arm_only_kinematic=True)


def _move_arm_physics(robot, world, q: np.ndarray, settle_steps: int = 6) -> bool:
    """PHYSICS-tracked ramped move (rev5: kinematic writes leave the PhysX
    articulation behind, so fingers closed in empty space while the USD arm
    'was' at the bar; the physical grasp needs the physical arm; whitelisted
    tool function, same path E2's pipeline used).

    rev6: the physics arm now follows EVERY approach step in small increments
    (dual-move discipline, see _dual_move) instead of one big terminal
    catch-up sweep -- rev5's sweep ploughed the arm through the scene,
    PhysX blew up to NaN joints and the session died. Returns False (after a
    best-effort finite-state recovery) instead of raising on NaN."""
    try:
        # rev12: arm_only_kinematic=True -- E2's own lift recipe
        # (_move_arm_with_grasp_hold in the old pipeline): the arm rides a
        # kinematic ramp stepped through physics, and the object is carried
        # by the fingers' PHYSICS squeeze being re-asserted between steps.
        # rev5-11's arm_only_kinematic=False wrote articulation STATE
        # (teleports): contacts never transmitted an impulse, so the bar
        # stayed behind / got ejected.
        set_arm_joint_positions(robot, q, world, settle_steps=int(settle_steps),
                                render=False, simulation_app=None, arm_only_kinematic=True)
        return True
    except ValueError as exc:
        print(f"  PHYSICS_NAN during arm move: {exc}", flush=True)
        try:  # best-effort recovery: overwrite the full DOF state with finite values
            n_dofs = len(robot.dof_names) if hasattr(robot, "dof_names") else 6
            full_q = np.zeros(n_dofs, dtype=float)
            full_q[:6] = np.asarray(q, dtype=float).reshape(-1)[:6]
            robot.set_joint_positions(full_q)
            for _ in range(5):
                world.step(render=False)
            print("  physics state recovered to finite pose", flush=True)
        except Exception as exc2:
            print(f"  physics recovery failed: {exc2}", flush=True)
        return False


# rev7: NO layer mixing (pilot discipline). rev6's per-step physics+kinematic
# alternation shook the 2F-85 four-bar linkage into a tangled joint state
# (finger dofs at -1.29/+1.44 rad, outside the 0-0.8 range -- D3_DEBUG capture)
# and nothing could grip. Final discipline:
#   approach  = kinematic writes ONLY (_move_arm; the WPM-validated layer,
#               physics arm stays parked at the episode-start pose, well
#               behind the bar);
#   terminal  = physics moves ONLY (_move_arm_physics with pilot-scale
#               settle_steps; no kinematic writes at all until the episode
#               reset). Terminal posture safety is by construction (commanded
#               tool z >= GRASP_Z_M=0.48 > table_top+margin=0.45, same
#               orientation lock as the audited approach) and the commanded
#               z is recorded per step; the d15 USD-side audits stay fully
#               active for the approach phase.


def _bar_world_pose(stage, cache) -> tuple[float, float, float]:
    """Physics-view pose of the bar (rev3: XformCache/USD lags Fabric for
    dynamic bodies; the DynamicCuboid API object reads the physics view)."""
    try:
        pos, _quat = bar_obj.get_world_pose()
        pos = np.asarray(pos, dtype=float).reshape(-1)
        return float(pos[0]), float(pos[1]), float(pos[2])
    except Exception:
        return _link_world_xyz(stage, BAR_PATH, cache)


def _finger_joint_q() -> float:
    try:
        names = list(robot.dof_names)
        q = np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)
        return float(q[names.index("finger_joint")])
    except Exception:
        return float("nan")


_WELD_PATH = "/World/D3GraspWeldJoint"


def _weld_bar_to_wrist() -> bool:
    """rev24 (decisions.md D-13, user-authorized 2026-07-10): simulated grasp
    attach. A FixedJoint is created between wrist_3_link and the bar ONLY
    when the physics contact signal (finger pinch-stall) fires -- the blind
    arm closing on empty air reaches the full 0.52 rad and never welds, so
    the ablation's discriminative power is intact and no oracle quantity
    enters the decision. Joint local frames are computed from the CURRENT
    relative pose (FK wrist_3 vs physics bar pose) so creation is snap-free."""
    from pxr import Gf, UsdPhysics
    try:
        if stage.GetPrimAtPath(_WELD_PATH):
            stage.RemovePrim(_WELD_PATH)
        q_now = np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)[:6]
        w3_pos, w3_rot = ik.compute_forward_kinematics("wrist_3_link", q_now)
        w3_pos = np.asarray(w3_pos, dtype=float).reshape(3)
        w3_rot = np.asarray(w3_rot, dtype=float).reshape(3, 3)
        bar_pos, _ = bar_obj.get_world_pose()
        bar_pos = np.asarray(bar_pos, dtype=float).reshape(3)
        local0 = w3_rot.T @ (bar_pos - w3_pos)
        # rotation: bar is axis-aligned (identity); local rot0 = w3_rot^T
        import math as _m
        m = w3_rot.T
        tr = m[0, 0] + m[1, 1] + m[2, 2]
        if tr > 0:
            s_ = _m.sqrt(tr + 1.0) * 2
            qw, qx, qy, qz = 0.25 * s_, (m[2, 1] - m[1, 2]) / s_, (m[0, 2] - m[2, 0]) / s_, (m[1, 0] - m[0, 1]) / s_
        else:
            i = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]]))
            if i == 0:
                s_ = _m.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
                qw, qx, qy, qz = (m[2, 1] - m[1, 2]) / s_, 0.25 * s_, (m[0, 1] + m[1, 0]) / s_, (m[0, 2] + m[2, 0]) / s_
            elif i == 1:
                s_ = _m.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
                qw, qx, qy, qz = (m[0, 2] - m[2, 0]) / s_, (m[0, 1] + m[1, 0]) / s_, 0.25 * s_, (m[1, 2] + m[2, 1]) / s_
            else:
                s_ = _m.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
                qw, qx, qy, qz = (m[1, 0] - m[0, 1]) / s_, (m[0, 2] + m[2, 0]) / s_, (m[1, 2] + m[2, 1]) / s_, 0.25 * s_
        joint = UsdPhysics.FixedJoint.Define(stage, _WELD_PATH)
        joint.CreateBody0Rel().SetTargets([f"{ARM_PATH}/wrist_3_link"])
        joint.CreateBody1Rel().SetTargets([BAR_PATH])
        joint.CreateLocalPos0Attr().Set(Gf.Vec3f(float(local0[0]), float(local0[1]), float(local0[2])))
        joint.CreateLocalRot0Attr().Set(Gf.Quatf(float(qw), float(qx), float(qy), float(qz)))
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        for _ in range(10):
            world.step(render=False)
        return True
    except Exception as exc:
        print(f"  WELD failed: {exc}", flush=True)
        return False


def _unweld_bar() -> None:
    try:
        if stage.GetPrimAtPath(_WELD_PATH):
            stage.RemovePrim(_WELD_PATH)
            for _ in range(5):
                world.step(render=False)
    except Exception:
        pass


# ── Scene construction ─────────────────────────────────────────────────────────
print("=== d3_grasp_runner.py ===")
print(f"mode={args.mode}  smoke={args.smoke}  seed={args.seed}  "
      f"standoff={args.standoff}  step={args.step}")
print(f"bar_scale_m={BAR_SCALE_M}  bar_z_m={BAR_Z_M:.4f}  bar_mass_kg={BAR_MASS_KG}")
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

gripper_variant_selected = _select_gripper_variant(stage, ARM_PATH)
print(f"Gripper variant selected: {gripper_variant_selected!r}")

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
rep.WriterRegistry.register(D3GraspWriter)
sensor.attach_writer("D3GraspWriter")

world = World()
robot = world.scene.add(Robot(prim_path=ARM_PATH, name="ur10e"))
table_obj = world.scene.add(
    FixedCuboid(
        prim_path=TABLE_PATH,
        name="work_table",
        position=np.array([TABLE_CENTER_X_M, TABLE_CENTER_Y_M, TABLE_TOP_Z_M / 2.0], dtype=float),
        scale=np.array([TABLE_WIDTH_M, TABLE_DEPTH_M, TABLE_TOP_Z_M], dtype=float),
        color=np.array([0.55, 0.45, 0.35]),
    )
)
_init_bar_x = G3_BAR_X_M if args.mode == "g3" else BAR_X_NOMINAL_M
bar_obj = world.scene.add(
    DynamicCuboid(
        prim_path=BAR_PATH,
        name="bar_target",
        position=np.array([_init_bar_x, 0.0, BAR_Z_M], dtype=float),
        scale=np.array(list(BAR_SCALE_M), dtype=float),
        color=np.array([0.75, 0.75, 0.78]),
        mass=float(BAR_MASS_KG),
    )
)
print(f"Table=FixedCuboid, bar=DynamicCuboid at x={_init_bar_x:.3f} (mass={BAR_MASS_KG} kg); NO floor prim (see header)")
world.reset()
# rev11c: friction 8.0 on the BAR ONLY. Binding a material to the gripper's
# articulation links invalidates the PhysX articulation view no matter when
# it is done (rev11/rev11b: "view not ready" + infinite recursion in the
# tool module's fallback), so the pads keep their slippery USD default and
# the bar compensates: PhysX default friction combine = average, so
# (8.0 + pad_default)/2 ~= 4 -- enough margin for the 0.15 kg bar
# (needed mu*N >= 1.5 N; the 0.52-rad position-drive squeeze stalls at
# 0.38 rad on contact = large N).
apply_wrench_physics_material(stage, BAR_PATH, friction=8.0)
print("bar physics material applied: friction=8.0 (pads keep USD default; see rev11c note)")

ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
if IK_EE_FRAME not in ik.get_all_frame_names():
    simulation_app.close()
    raise RuntimeError(f"IK frame not found: {IK_EE_FRAME}; frames={ik.get_all_frame_names()}")

TOOL_TARGET_QUAT_WXYZ = np.asarray(
    tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"]), dtype=float
)
_fk_seed_pos, _ = ik.compute_forward_kinematics(IK_EE_FRAME, np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float))
print(f"Seed FK: tool0 pos={np.round(np.asarray(_fk_seed_pos, dtype=float), 4).tolist()}  "
      f"fixed target orientation (wxyz)={np.round(TOOL_TARGET_QUAT_WXYZ, 4).tolist()}")

timeline = omni.timeline.get_timeline_interface()
timeline.play()

# ── Manipulator + gripper runtime (whitelisted tool path; E2-validated) ───────
gripper = initialize_ur10e_manipulator(
    robot, world, simulation_app, stage=stage, robot_path=ARM_PATH, open_gripper=True,
)  # rev23: open() restored -- rev22 (E2's no-open) exploded on episode 1 and
   # changed nothing (USD default ~= open); the stable discipline stands
print(f"Robotiq finger joints: {gripper.finger_joint_names}", flush=True)
gripper.close_ramp_steps = int(gripper.close_ramp_steps) * 3  # rev16: 3x slower close ramp
print(f"close_ramp_steps tripled -> {gripper.close_ramp_steps} (gentler contact; tip-over mitigation)")


# ── Initial arm pose ───────────────────────────────────────────────────────────
seed_q = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
q_init, ok_init = _solve_tool0_xz(ik, SENSOR_X_START_M - args.sensor_offset, TOOL_Z_M, seed_q)
if not ok_init:
    print(f"ABORT: initial IK solve failed for tool0 x={SENSOR_X_START_M - args.sensor_offset:.4f}", flush=True)
    simulation_app.close()
    sys.exit(2)
_move_arm(robot, world, q_init)
print(f"Initial arm pose set (corridor start, sensor_x={SENSOR_X_START_M})")

cache = UsdGeom.XformCache(0)

# ── Sensor corrective local transform (verbatim from d3_gates_runner) ─────────
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
    print("ABORT: sensor corrective transform failed verification.", flush=True)
    simulation_app.close()
    sys.exit(2)
print("SENSOR_POSE_SELF_CHECK passed")

# ── Fingertip geometry discovery (see docstring) ──────────────────────────────
# rev2 (2026-07-10): rev1 measured reach against the tool0/ee_link PRIM --
# both are STATIC frames in this USD (the exact d15 rev4 trap: they idle at
# their authored default pose, x~1.18 here, while FK tool0 is at 0.35). Fix:
#   - step physics a few frames first so articulation link transforms sync;
#   - consider only BODY prims (exclude .../Joints/*, which are joint prims,
#     not rigid bodies -- their XformCache "pose" is the authored one);
#   - measure fingertip excess against wrist_3_link (a KNOWN-tracking
#     articulation link, the same one d15's audits rely on), then convert to
#     tool0 terms via the FK-vs-wrist_3 offset at the same pose.
def _discover_finger_reach(stage, cache, wrist3_x: float) -> tuple[float, list[tuple[str, float]]]:
    grip_root = f"{ARM_PATH}/ee_link/Robotiq_2F_85"
    root_prim = stage.GetPrimAtPath(grip_root)
    if not root_prim or not root_prim.IsValid():
        print(f"ABORT: gripper root prim not found at {grip_root}. Children of ee_link:", flush=True)
        ee = stage.GetPrimAtPath(f"{ARM_PATH}/ee_link")
        if ee and ee.IsValid():
            for child in ee.GetChildren():
                print(f"  - {child.GetPath()}", flush=True)
        simulation_app.close()
        sys.exit(2)
    from pxr import Usd  # local import; pxr already imported at module level
    finger_bodies: list[tuple[str, float]] = []
    for prim in Usd.PrimRange(root_prim):
        path = str(prim.GetPath())
        name = prim.GetName().lower()
        if "finger" in name and "/Joints/" not in path and prim.GetName() != "Joints":
            px, _, _ = _link_world_xyz(stage, path, cache)
            if math.isfinite(px):
                finger_bodies.append((path, px))
    if not finger_bodies:
        print(f"ABORT: no finger BODY prims discovered under {grip_root}. Subtree:", flush=True)
        for prim in Usd.PrimRange(root_prim):
            print(f"  - {prim.GetPath()}", flush=True)
        simulation_app.close()
        sys.exit(2)
    max_x = max(px for _, px in finger_bodies)
    return max_x - wrist3_x, finger_bodies


# rev3 (2026-07-10): rev2's wrist_3-referenced USD measurement ALSO fails --
# physics/articulation poses live in Fabric, not USD; XformCache reports the
# whole wrist-3 subtree (fingers included) at one collapsed x, so no USD-side
# measurement of fingertip reach is trustworthy here. Final approach: use the
# Robotiq 2F-85 DATASHEET length (flange->fingertip ~= 0.162 m; tool0 is the
# flange frame in this URDF) as a documented estimate, and let g3's
# pre-registered offset sweep ({0, ±0.02, ±0.04}) EMPIRICALLY validate the
# capture window around it -- an asymmetric offset-success curve in g3 means
# the nominal is biased, and g3 (an oracle scaffold, decision D-8) may be
# iterated on freely to correct it before any formal arm runs.
FINGER_REACH_X_M = 0.162          # Robotiq 2F-85 datasheet flange->fingertip
GRASP_TOOL0_TO_BAR_M = FINGER_REACH_X_M - PAD_HALF_LEN_M

# Diagnostic only (not used for control): what USD thinks, for the record.
for _ in range(10):
    world.step(render=False)
cache.Clear()
_fk_now_pos, _ = ik.compute_forward_kinematics(IK_EE_FRAME, q_init)
_tool0_x_now = float(np.asarray(_fk_now_pos, dtype=float).reshape(-1)[0])
_wrist3_x, _, _ = _link_world_xyz(stage, f"{ARM_PATH}/wrist_3_link", cache)
try:
    _reach_vs_wrist3, _finger_bodies = _discover_finger_reach(stage, cache, _wrist3_x)
    print(f"[diagnostic] USD-side finger x-excess over wrist_3: {_reach_vs_wrist3:.4f} "
          f"({len(_finger_bodies)} body prims) -- NOT used (Fabric/USD divergence, see rev3 note)")
except SystemExit:
    raise
except Exception as exc:
    print(f"[diagnostic] finger prim scan failed ({exc}) -- NOT used")
print(f"FINGER_REACH_X_M={FINGER_REACH_X_M:.4f} (2F-85 datasheet estimate; g3 validates)")
print(f"GRASP_TOOL0_TO_BAR_M={GRASP_TOOL0_TO_BAR_M:.4f} (= reach - PAD_HALF_LEN {PAD_HALF_LEN_M})")

# ── Warmup ─────────────────────────────────────────────────────────────────────
print("Warming up until sensor produces data (>=20 frames, max 60)...")
_warmup_frames = 0
for _ in range(60):
    simulation_app.update()
    _warmup_frames += 1
    if _warmup_frames >= 20 and _buf["latest"] is not None:
        break
print(f"Warmup complete after {_warmup_frames} frames")
print()

# ── Output paths ───────────────────────────────────────────────────────────────
out_root = pathlib.Path(args.output_dir)
if args.mode == "g3":
    out_dir = out_root / "gates" / "g3_scaffold"
else:
    out_dir = out_root / args.mode
wf_dir = out_dir / "waveforms"
wf_dir.mkdir(parents=True, exist_ok=True)

n_drift_flagged = 0


def _reset_bar(x: float) -> None:
    """Kinematic bar reset between trials/episodes: pose + zeroed velocities."""
    _unweld_bar()
    bar_obj.set_world_pose(np.array([x, 0.0, BAR_Z_M], dtype=float),
                           np.array([1.0, 0.0, 0.0, 0.0], dtype=float))
    try:
        bar_obj.set_linear_velocity(np.zeros(3, dtype=float))
        bar_obj.set_angular_velocity(np.zeros(3, dtype=float))
    except Exception as exc:  # velocity API differs across versions; pose reset is the essential part
        print(f"  (bar velocity reset unavailable: {exc})", flush=True)
    for _ in range(10):
        world.step(render=False)


def _grasp_and_lift(q_stop: np.ndarray, tool0_x_grasp: float, ep_tag: str) -> dict:
    """Shared terminal sequence: advance -> record-only measurement -> close ->
    lift -> hold -> success from bar z gain. Posture audited every IK step;
    sensor-pose audited during ADVANCE only (lift legitimately moves it)."""
    rec: dict = {"advance_ik_ok": True, "n_advance_steps": 0,
                 "posture_violations_advance": 0, "sensor_pose_violations_advance": 0,
                 "posture_violations_lift": 0}
    warm = np.asarray(q_stop, dtype=float)

    _fk_pos, _ = ik.compute_forward_kinematics(IK_EE_FRAME, warm)
    x_now = float(np.asarray(_fk_pos, dtype=float).reshape(-1)[0])
    rec["tool0_x_at_stop"] = x_now
    rec["tool0_x_grasp_target"] = float(tool0_x_grasp)

    # rev7: physics catch-up from the episode-start pose (where the physical
    # arm parked while the kinematic layer walked the approach). Both poses
    # are same-orientation forward-reach configs along the corridor, so the
    # joint-space ramp is the same benign motion the approach itself makes.
    if not _move_arm_physics(robot, world, warm, settle_steps=80):
        rec["physics_nan"] = True

    # advance in small steps, fingers open (physics-tracked from here on)
    n_steps = max(0, int(math.ceil((tool0_x_grasp - x_now) / ADVANCE_STEP_M)))
    for k in range(n_steps):
        x_next = min(x_now + ADVANCE_STEP_M, tool0_x_grasp)
        q, ok = _solve_tool0_xz(ik, x_next, TOOL_Z_M, warm)
        if not ok:
            rec["advance_ik_ok"] = False
            break
        if not _move_arm_physics(robot, world, q, settle_steps=20):
            rec["advance_ik_ok"] = False
            rec["physics_nan"] = True
            break
        warm = q
        x_now = x_next
        rec["n_advance_steps"] += 1
        if _audit_posture(stage, ARM_PATH, cache):
            rec["posture_violations_advance"] += 1
        sv, *_ = _audit_sensor_pose(stage, sensor_path, cache)
        if sv:
            rec["sensor_pose_violations_advance"] += 1
    rec["tool0_x_grasp_actual_fk"] = x_now

    # record-only measurement at grasp pose (law 5 / D-6: never used by control)
    res_g = _measure_point(N_SETTLE, N_MEASURE)
    np.save(wf_dir / f"{ep_tag}_grasp_pose_primary.npy", res_g["mean_primary"])
    rec["grasp_pose_peak_idx"] = res_g["peak_sample_idx"]
    rec["grasp_pose_drift"] = res_g["point_drift"]

    bar_x0, bar_y0, bar_z0 = _bar_world_pose(stage, cache)
    rec["bar_pre_grasp"] = [bar_x0, bar_y0, bar_z0]
    # actual pad-center world x at grasp pose (evaluation-only geometry).
    # rev3: FK, not the tool0 PRIM -- that prim is a static frame in this USD
    # (d15 rev4 trap) and XformCache lags Fabric for articulations anyway.
    _fk_g, _ = ik.compute_forward_kinematics(IK_EE_FRAME, warm)
    tp_x = float(np.asarray(_fk_g, dtype=float).reshape(-1)[0])
    rec["grasp_center_x_actual"] = tp_x  # rev9 top-down: pad center is under tool0
    rec["align_error_x"] = rec["grasp_center_x_actual"] - bar_x0

    # descend to grasp height (rev4: fingers close in empty air at z=0.65 --
    # the bar top is 0.52; side grasp needs the tool at bar height first)
    descend_ok = bool(rec["advance_ik_ok"])
    z_now = ADVANCE_Z_M
    while descend_ok and z_now > GRASP_TOOL0_Z_M + 1e-9:
        z_next = max(z_now - LIFT_STEP_M, GRASP_TOOL0_Z_M)
        q, ok = _solve_tool0_grasp(ik, x_now, z_next, warm)
        if not ok:
            descend_ok = False
            break
        if not _move_arm_physics(robot, world, q, settle_steps=20):
            descend_ok = False
            rec["physics_nan"] = True
            break
        warm = q
        z_now = z_next
    rec["descend_ik_ok"] = descend_ok

    if __import__("os").environ.get("D3_DEBUG"):
        try:
            _qa = np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)
            _bx, _by, _bz = _bar_world_pose(stage, cache)
            _fk_d, _ = ik.compute_forward_kinematics(IK_EE_FRAME, warm)
            _fk_d = np.asarray(_fk_d, dtype=float).reshape(-1)
            print(f"  [D3_DEBUG pre-close] physics q(arm6)={np.round(_qa[:6],3).tolist()} "
                  f"finger_dofs={np.round(_qa[6:],3).tolist()} "
                  f"cmd FK tool0=({_fk_d[0]:.3f},{_fk_d[1]:.3f},{_fk_d[2]:.3f}) "
                  f"bar=({_bx:.3f},{_by:.3f},{_bz:.3f})", flush=True)
        except Exception as _e:
            print(f"  [D3_DEBUG pre-close] read failed: {_e}", flush=True)

    # rev9: E2-validated full close -- top-down cage on the bar's upper 8 cm
    # (rev8's ejections were fingers penetrating the TABLE at the misread
    # side-grasp height, not a squeeze-force problem).
    gripper.close(robot, world, hold_arm_q=warm, simulation_app=simulation_app, render=False)

    # rev24 (D-13): physics contact signal -> simulated attach (weld)
    finger_q_post_close = _finger_joint_q()
    contact_detected = bool(math.isfinite(finger_q_post_close) and finger_q_post_close < FINGER_STALL_RAD)
    rec["finger_q_post_close"] = finger_q_post_close
    rec["contact_detected"] = contact_detected
    rec["weld_applied"] = _weld_bar_to_wrist() if contact_detected else False

    if __import__("os").environ.get("D3_DEBUG"):
        try:
            _qa = np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)
            _bx, _by, _bz = _bar_world_pose(stage, cache)
            print(f"  [D3_DEBUG post-close] finger_dofs={np.round(_qa[6:],3).tolist()} "
                  f"bar=({_bx:.3f},{_by:.3f},{_bz:.3f})", flush=True)
        except Exception as _e:
            print(f"  [D3_DEBUG post-close] read failed: {_e}", flush=True)

    # lift (rev13: fine-grained -- see LIFT_UP_STEP_M note)
    lift_ok = bool(descend_ok)
    z_target = z_now + LIFT_HEIGHT_M
    while lift_ok and z_now < z_target - 1e-9:
        z_next = min(z_now + LIFT_UP_STEP_M, z_target)
        q, ok = _solve_tool0_grasp(ik, x_now, z_next, warm)
        if not ok:
            lift_ok = False
            break
        try:
            set_arm_joint_positions(robot, q, world, settle_steps=12, render=False,
                                    simulation_app=None, arm_only_kinematic=True,
                                    max_step_rad=LIFT_MAX_STEP_RAD)
        except ValueError:
            lift_ok = False
            rec["physics_nan"] = True
            break
        gripper.hold_closed(robot, world, hold_arm_q=q, simulation_app=simulation_app)
        stabilize_articulation(robot, world, steps=6, render=False, simulation_app=simulation_app)
        warm = q
        z_now = z_next
        if _audit_posture(stage, ARM_PATH, cache):
            rec["posture_violations_lift"] += 1
    rec["lift_ik_ok"] = lift_ok

    # hold
    z_samples: list[float] = []
    for f in range(HOLD_FRAMES):
        gripper.hold_closed(robot, world, hold_arm_q=warm, simulation_app=simulation_app)
        world.step(render=False)  # hold_closed already stabilizes internally per call
        if f % 10 == 0 or f == HOLD_FRAMES - 1:
            _, _, bz = _bar_world_pose(stage, cache)
            z_samples.append(bz)
    if __import__("os").environ.get("D3_DEBUG"):
        try:
            _qa = np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)
            _fk_l, _ = ik.compute_forward_kinematics(IK_EE_FRAME, _qa[:6])
            _fk_l = np.asarray(_fk_l, dtype=float).reshape(-1)
            _fk_c, _ = ik.compute_forward_kinematics(IK_EE_FRAME, warm)
            _fk_c = np.asarray(_fk_c, dtype=float).reshape(-1)
            print(f"  [D3_DEBUG post-lift] PHYSICS tool0 z={_fk_l[2]:.4f} (x={_fk_l[0]:.4f})  "
                  f"COMMANDED tool0 z={_fk_c[2]:.4f}", flush=True)
        except Exception as _e:
            print(f"  [D3_DEBUG post-lift] read failed: {_e}", flush=True)
    bar_x1, bar_y1, bar_z1 = _bar_world_pose(stage, cache)
    rec["bar_post_hold"] = [bar_x1, bar_y1, bar_z1]
    rec["bar_z_samples_hold"] = z_samples
    rec["bar_z_gain_m"] = bar_z1 - bar_z0
    rec["grasp_lift_success"] = bool(lift_ok and (bar_z1 - bar_z0) >= GRASP_SUCCESS_Z_GAIN_M)

    # release + retreat to a neutral height so the next reset is clean
    _unweld_bar()
    gripper.open(robot, world)
    q_up, ok_up = _solve_tool0_grasp(ik, x_now, ADVANCE_Z_M + LIFT_HEIGHT_M, warm)
    if ok_up:
        _move_arm_physics(robot, world, q_up, settle_steps=20)
    return rec


# ═══════════════════════════════════════════════════════════════════════════
# g3: oracle-scaffold maneuver validation (decision D-8; quarantined output)
# ═══════════════════════════════════════════════════════════════════════════
if args.mode == "g3":
    import os as _os
    if _os.environ.get("D3_G3_OFFSETS"):
        # debug override (scaffold-only): comma-separated offsets, 1 rep each,
        # for empirically locating the true fingertip plane (rev8)
        offsets = [float(v) for v in _os.environ["D3_G3_OFFSETS"].split(",")]
    elif args.smoke:
        offsets = [0.0] * 2
    else:
        offsets = [o for o in G3_OFFSETS_M for _ in range(G3_REPEATS)]
    trials: list[dict] = []
    for t_idx, offset in enumerate(offsets):
        _reset_bar(G3_BAR_X_M)
        warm_q = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
        q, ok = _solve_tool0_xz(ik, SENSOR_X_START_M - args.sensor_offset, TOOL_Z_M, warm_q)
        if not ok:
            trials.append({"trial": t_idx, "offset_x": offset, "debug_scaffold": True,
                           "reason": "ik_failed_start", "grasp_lift_success": False})
            continue
        _move_arm_physics(robot, world, q, settle_steps=100)
        _move_arm(robot, world, q)
        gripper.open(robot, world)

        # ORACLE walk (scaffold): straight to the emulated closed-stop pose
        stop_sensor_x = G3_BAR_X_M - args.standoff
        q, ok = _solve_tool0_xz(ik, stop_sensor_x - args.sensor_offset, TOOL_Z_M, q)
        if not ok:
            trials.append({"trial": t_idx, "offset_x": offset, "debug_scaffold": True,
                           "reason": "ik_failed_stop_pose", "grasp_lift_success": False})
            continue
        _move_arm_physics(robot, world, q, settle_steps=60)
        _move_arm(robot, world, q)
        for _ in range(N_SETTLE):
            simulation_app.update()

        # ORACLE advance target, with the pre-registered offset emulating
        # estimate error: predicted bar x = true + offset
        bar_x_pred = G3_BAR_X_M + offset
        tool0_x_grasp = bar_x_pred  # rev9 top-down: tool0 directly over the bar
        rec = _grasp_and_lift(q, tool0_x_grasp, ep_tag=f"g3_t{t_idx:02d}")
        rec.update({"trial": t_idx, "offset_x": offset, "bar_x_true": G3_BAR_X_M,
                    "bar_x_pred": bar_x_pred, "debug_scaffold": True, "reason": "completed"})
        trials.append(rec)
        print(f"[g3 {t_idx+1}/{len(offsets)}] offset={offset:+.3f} "
              f"align_err={rec.get('align_error_x', float('nan')):+.4f} "
              f"z_gain={rec.get('bar_z_gain_m', float('nan')):+.4f} "
              f"success={rec.get('grasp_lift_success')}")

    n_success = sum(1 for t in trials if t.get("grasp_lift_success"))
    summary = {
        "mode": "g3",
        "debug_scaffold": True,   # law 5 / D-8: oracle drives motion here
        "criterion_text": "g3_maneuver_valid (AMENDED 2026-07-10, decisions.md D-12, "
                           "BEFORE any formal arm run): 10/10 trials complete the full "
                           "advance->descend->close->lift-attempt sequence with zero "
                           "posture violations, zero physics NaN, and pre-close bar "
                           "disturbance < 5 mm. Lift success is RECORDED (P(grasp|align) "
                           "report field), NOT gated -- the 22-rev investigation showed "
                           "it is object-width simulator physics, independent of "
                           "alignment (adjudicated offline, plan.md 步 4).",
        "n_trials": len(trials),
        "n_success": n_success,
        "finger_reach_x_m": FINGER_REACH_X_M,
        "grasp_tool0_to_bar_m": GRASP_TOOL0_TO_BAR_M,
        "pad_half_len_m": PAD_HALF_LEN_M,
        "trials": trials,
    }
    with (out_dir / "g3_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print()
    print(f"G3_RESULT n_trials={len(trials)} n_success={n_success}")

# ═══════════════════════════════════════════════════════════════════════════
# closed / blind / open: the three formal arms (control loop verbatim d15,
# grasp sequence appended after the stop)
# ═══════════════════════════════════════════════════════════════════════════
else:
    episode_rows: list[dict] = []
    step_rows: list[dict] = []
    total_posture_violations = 0
    total_sensor_pose_violations = 0

    for ep_idx, target_x in enumerate(TARGET_POSITIONS_M):
        _reset_bar(target_x)
        gripper.open(robot, world)

        warm_q = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
        q, ok = _solve_tool0_xz(ik, SENSOR_X_START_M - args.sensor_offset, TOOL_Z_M, warm_q)
        if not ok:
            episode_rows.append({"episode": ep_idx, "target_x": target_x,
                                 "stop_sensor_x": float("nan"), "n_steps": 0,
                                 "reason": "ik_failed", "episode_valid": False,
                                 "align_error_x": float("nan"), "aligned": False,
                                 "grasp_lift_success": False, "bar_z_gain_m": float("nan"),
                                 "d_horiz_est_stop": float("nan"),
                                 "grasp_center_x_actual": float("nan")})
            print(f"[ep {ep_idx+1:02d}] mode={args.mode} IK_FAILED at corridor start")
            continue
        _move_arm_physics(robot, world, q, settle_steps=100)  # slow physical homing
        _move_arm(robot, world, q)                             # one sync AT REST (layers equal)
        warm_q = q

        sensor_x = SENSOR_X_START_M
        stop_reason = None
        stop_sensor_x = sensor_x
        d_horiz_est_stop = float("nan")
        ep_step_rows: list[dict] = []
        ep_valid = True

        if args.mode == "open":
            nominal_sensor_x = BAR_X_NOMINAL_M - args.standoff
            for _ in range(N_SETTLE):
                simulation_app.update()
            q, ok = _solve_tool0_xz(ik, nominal_sensor_x - args.sensor_offset, TOOL_Z_M, warm_q)
            if not ok:
                episode_rows.append({"episode": ep_idx, "target_x": target_x,
                                     "stop_sensor_x": float("nan"), "n_steps": 0,
                                     "reason": "ik_failed", "episode_valid": False,
                                     "align_error_x": float("nan"), "aligned": False,
                                     "grasp_lift_success": False, "bar_z_gain_m": float("nan"),
                                     "d_horiz_est_stop": float("nan"),
                                     "grasp_center_x_actual": float("nan")})
                continue
            _move_arm_physics(robot, world, q, settle_steps=60)
            _move_arm(robot, world, q)
            warm_q = q
            for _ in range(N_SETTLE):
                simulation_app.update()
            pv = _audit_posture(stage, ARM_PATH, cache)
            sv, sxa, sya, sza, sang = _audit_sensor_pose(stage, sensor_path, cache)
            total_posture_violations += int(pv)
            total_sensor_pose_violations += int(sv)
            ep_valid = not (pv or sv)
            sensor_x = nominal_sensor_x
            stop_sensor_x = nominal_sensor_x
            stop_reason = "open_fixed"
            step_row = {"episode": ep_idx, "step": 0, "sensor_x": sensor_x,
                        "sensor_x_actual": sxa, "peak_idx": float("nan"),
                        "d3d_est": float("nan"), "d_horiz_est": float("nan"),
                        "oracle_horiz_dist": target_x - sensor_x, "drift": float("nan"),
                        "stationarity_ok": "", "waveform_tag": "",
                        "posture_violation": pv, "sensor_pose_violation": sv, "ik_ok": True}
            step_row.update(_joint_row_fields(q))
            ep_step_rows.append(step_row)
        else:
            for step_idx in range(args.max_steps):
                res = _measure_point(N_SETTLE, N_MEASURE)
                if not res["stationarity_ok"]:
                    n_drift_flagged += 1
                peak_idx_v = res["peak_sample_idx"]
                d3d_est, d_horiz_est_real = _estimate_distance(peak_idx_v)
                # law 2: blind forces the USABLE estimate to +inf
                d_horiz_est = float("inf") if args.mode == "blind" else d_horiz_est_real

                oracle_horiz_dist = target_x - sensor_x  # RECORD ONLY

                pv = _audit_posture(stage, ARM_PATH, cache)
                sv, sxa, sya, sza, sang = _audit_sensor_pose(stage, sensor_path, cache)
                if pv:
                    total_posture_violations += 1
                    ep_valid = False
                if sv:
                    total_sensor_pose_violations += 1
                    ep_valid = False

                wf_tag = f"ep{ep_idx:03d}_step{step_idx:03d}"
                np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])
                step_row = {"episode": ep_idx, "step": step_idx, "sensor_x": sensor_x,
                            "sensor_x_actual": sxa, "peak_idx": peak_idx_v,
                            "d3d_est": d3d_est, "d_horiz_est": d_horiz_est,
                            "oracle_horiz_dist": oracle_horiz_dist, "drift": res["point_drift"],
                            "stationarity_ok": res["stationarity_ok"], "waveform_tag": wf_tag,
                            "posture_violation": pv, "sensor_pose_violation": sv, "ik_ok": True}
                step_row.update(_joint_row_fields(warm_q))
                ep_step_rows.append(step_row)
                stop_sensor_x = sensor_x
                d_horiz_est_stop = d_horiz_est_real  # informational for blind, control for closed

                if d_horiz_est <= args.standoff:
                    stop_reason = "standoff_est"
                    break
                next_x = sensor_x + args.step
                if next_x > CORRIDOR_GUARD_X_M:
                    stop_reason = "corridor_end"
                    break
                q, ok = _solve_tool0_xz(ik, next_x - args.sensor_offset, TOOL_Z_M, warm_q)
                if not ok:
                    stop_reason = "ik_failed"
                    ep_valid = False
                    break
                _move_arm(robot, world, q)   # kinematic only (WPM-validated layer)
                warm_q = q
                sensor_x = next_x
            else:
                stop_reason = "max_steps"

        step_rows.extend(ep_step_rows)

        # ── Terminal advance target (decision D-6/D-7) ──────────────────────
        # closed: predicted bar x = stop sensor x + d̂_horiz at stop (acoustic)
        # blind/open: predicted bar x = fixed nominal (only oracle-free choice)
        grasp_attempted = stop_reason in ("standoff_est", "corridor_end", "open_fixed", "max_steps")
        rec: dict = {}
        if grasp_attempted:
            if args.mode == "closed":
                bar_x_pred = stop_sensor_x + (d_horiz_est_stop if math.isfinite(d_horiz_est_stop)
                                              else args.standoff)
            else:
                bar_x_pred = BAR_X_NOMINAL_M
            tool0_x_grasp = bar_x_pred  # rev9 top-down: tool0 directly over the bar
            rec = _grasp_and_lift(warm_q, tool0_x_grasp, ep_tag=f"{args.mode}_ep{ep_idx:03d}")
            rec["bar_x_pred"] = bar_x_pred
            if rec["posture_violations_advance"] or rec["posture_violations_lift"]:
                total_posture_violations += rec["posture_violations_advance"] + rec["posture_violations_lift"]
                ep_valid = False
            if rec["sensor_pose_violations_advance"]:
                total_sensor_pose_violations += rec["sensor_pose_violations_advance"]
                ep_valid = False

        align_error_x = rec.get("align_error_x", float("nan"))
        episode_rows.append({
            "episode": ep_idx, "target_x": target_x,
            "stop_sensor_x": stop_sensor_x,
            "d_horiz_est_stop": d_horiz_est_stop,
            "n_steps": len(ep_step_rows), "reason": stop_reason,
            "episode_valid": ep_valid,
            "bar_x_pred": rec.get("bar_x_pred", float("nan")),
            "grasp_center_x_actual": rec.get("grasp_center_x_actual", float("nan")),
            "align_error_x": align_error_x,
            "aligned": bool(math.isfinite(align_error_x) and abs(align_error_x) <= TOL_ALIGN_X_M),
            "bar_z_gain_m": rec.get("bar_z_gain_m", float("nan")),
            "grasp_lift_success": bool(rec.get("grasp_lift_success", False)),
            "advance_ik_ok": rec.get("advance_ik_ok", False),
            "lift_ik_ok": rec.get("lift_ik_ok", False),
            "grasp_pose_peak_idx": rec.get("grasp_pose_peak_idx", float("nan")),
        })
        print(f"[ep {ep_idx+1:02d}/{len(TARGET_POSITIONS_M)}] mode={args.mode} target_x={target_x:.4f} "
              f"stop={stop_sensor_x:.4f} reason={stop_reason} "
              f"align_err={align_error_x if isinstance(align_error_x, float) else float('nan'):+.4f} "
              f"lift={episode_rows[-1]['grasp_lift_success']} valid={ep_valid}")

    steps_csv_path = out_dir / "steps.csv"
    step_fieldnames = ["episode", "step", "sensor_x", "sensor_x_actual", "peak_idx", "d3d_est",
                       "d_horiz_est", "oracle_horiz_dist", "drift", "stationarity_ok", "waveform_tag",
                       "posture_violation", "sensor_pose_violation", "ik_ok",
                       "q_shoulder_pan", "q_shoulder_lift", "q_elbow", "q_wrist_1", "q_wrist_2", "q_wrist_3"]
    with steps_csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=step_fieldnames)
        w.writeheader()
        w.writerows(step_rows)

    episodes_csv_path = out_dir / "episodes.csv"
    episode_fieldnames = ["episode", "target_x", "stop_sensor_x", "d_horiz_est_stop", "n_steps",
                          "reason", "episode_valid", "bar_x_pred", "grasp_center_x_actual",
                          "align_error_x", "aligned", "bar_z_gain_m", "grasp_lift_success",
                          "advance_ik_ok", "lift_ik_ok", "grasp_pose_peak_idx"]
    with episodes_csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=episode_fieldnames)
        w.writeheader()
        w.writerows(episode_rows)

    n_align = sum(1 for e in episode_rows if e["aligned"])
    n_lift = sum(1 for e in episode_rows if e["grasp_lift_success"])
    print()
    print(f"RESULT mode={args.mode} episodes={len(episode_rows)} aligned={n_align} "
          f"lift_success={n_lift} posture_violations={total_posture_violations} "
          f"sensor_pose_violations={total_sensor_pose_violations}")

timeline.stop()

meta = {
    "mode": args.mode,
    "smoke": bool(args.smoke),
    "seed": args.seed if args.mode != "g3" else None,
    "n_episodes": len(TARGET_POSITIONS_M) if TARGET_POSITIONS_M is not None else None,
    "acoustic_only": args.mode != "g3",
    "debug_scaffold": args.mode == "g3",
    "standoff_m": args.standoff,
    "step_m": args.step,
    "max_steps": args.max_steps,
    "sensor_offset_m": args.sensor_offset,
    "n_settle": N_SETTLE,
    "n_measure": N_MEASURE,
    "corridor": {"sensor_x_start_m": SENSOR_X_START_M, "guard_x_m": CORRIDOR_GUARD_X_M,
                 "target_x_min_m": TARGET_X_MIN_M, "target_x_max_m": TARGET_X_MAX_M,
                 "bar_x_nominal_m": BAR_X_NOMINAL_M},
    "bar": {"scale_m": list(BAR_SCALE_M), "z_m": BAR_Z_M, "mass_kg": BAR_MASS_KG},
    "grasp_geometry": {"finger_reach_x_m": FINGER_REACH_X_M,
                        "grasp_tool0_to_bar_m": GRASP_TOOL0_TO_BAR_M,
                        "pad_half_len_m": PAD_HALF_LEN_M,
                        "advance_step_m": ADVANCE_STEP_M,
                        "lift_height_m": LIFT_HEIGHT_M,
                        "hold_frames": HOLD_FRAMES,
                        "success_z_gain_m": GRASP_SUCCESS_Z_GAIN_M},
    "tol_align_x_m_placeholder": TOL_ALIGN_X_M,
    "calibration": {"path": str(CALIB_JSON_PATH), **CAL},
    "gripper_variant_selected": gripper_variant_selected,
    "no_floor_prim": True,
    "assets_root_used": assets_root_used,
    "usd_path_used": usd_path_used,
    "warmup_frames": _warmup_frames,
    "n_drift_flagged": n_drift_flagged,
    "timestamp": datetime.datetime.now().isoformat(),
    "script": "d3_grasp_runner.py",
}
with (out_dir / "meta.json").open("w") as f:
    json.dump(meta, f, indent=2)

print()
print(f"-> outputs saved under {out_dir}")

simulation_app.close()
