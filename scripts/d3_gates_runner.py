"""D3.0 pre-registered gate runner: g1 (bar detectable) / g2 (bar ranging) /
m3b_target / m3b_sensor (mover-effect A/B), UR10e + REAL Robotiq gripper +
horizontal arm-carried sensor.

Full spec: docs/plan_v2/d3/plan.md "步 1:包 A", regulated by
docs/plan_v2/M3_D3_DESIGN_2026-07-10.md and docs/plan_v2/d3/decisions.md
(D-3 through D-5 in particular). This script produces raw measurements only;
the pre-registered criteria below are ADJUDICATED OFFLINE by the main agent
(plan.md 步 2), never computed or acted upon here.

Skeleton provenance
--------------------
Copied wholesale from scripts/d15_arm_approach_runner.py: boot order
(argparse before SimulationApp -> stage -> UR10e spawn -> sensor -> World/
Robot/IK -> initial pose -> sensor corrective transform -> warmup), the
module-level `_buf` writer pattern, `_extract_frame`, `D15ArmApproachWriter`
(renamed here), `_per_rx_primary`, `_measure_block`/`_measure_point` (settle
-> block A -> block B -> mean + A-vs-B stationarity/drift audit), the table
geometry, the two per-step geometry audits (`_audit_posture`,
`_audit_sensor_pose`), the `_solve_tool0`/`_move_arm` IK-and-kinematic-write
pattern, and the xformOp:translate-only `_move_target`-style prim mover
(rule 3-4 / WPM_EXPERIMENT_RULES.md). Two deliberate changes from that
skeleton (decision D-4, D-5):

  1. Gripper: d15's `_select_bare_arm_variant()` (which selects a "None"
     Gripper variant so D1.5 stays a bare arm) is REPLACED by
     `_select_gripper_variant()`, which selects
     `ur10e_robotiq_common.GRIPPER_VARIANT` ("Robotiq_2f_85") -- the same
     variant-set mechanism `ur10e_robotiq_common.spawn_ur10e_robotiq()`
     itself uses (ur10e_robotiq_common.py:389-392). D1.5 never actually
     tested with a mounted gripper (D-4); this script's whole point is to
     measure the acoustic scene the gripper mesh actually creates.
  2. Target: the 0.10 m cube target is replaced by a 0.06(x) x 0.06(y) x
     0.12(z) m upright "bar" (Cube, anisotropic scale -- same mechanism
     `_build_table` already uses for the table), standing bottom-on-table
     (center z = table_top_z + 0.06, per plan.md's literal formula; see
     BAR_Z_M below for why this differs from the M3_D3_DESIGN draft's
     illustrative "z=0.51").

No S2/D1 distance calibration is loaded at startup (unlike d15): this
script has no closed-loop control decision to feed a calibration into --
g1/g2/m3b_target/m3b_sensor are all open-loop measurement sweeps. The
`true_distance_3d_m` recorded in every row is the deterministic geometric
distance between the (oracle) bar placement and the AUDITED sensor world
pose -- never anything derived from the acoustic signal itself.

Five-iron-law header (docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md §4 / d15's own
header) -- what this script is and is not responsible for
-----------------------------------------------------------------------------
  1. Paired control:
     used by --mode g1 only, exactly as scripts/paired_capture_runner.py
     defines it -- with_target -> noise_ref -> RemovePrim -> without_target
     (same session, same sensor geometry) per distance cell, then rebuilt for
     the next cell. g2/m3b_target/m3b_sensor are single-condition distance
     sweeps (no with/without pairing; they measure peak_sample_idx directly,
     same shape as d15's probe mode).
  2. Information-ablation control:
     not applicable. There is no control loop here -- nothing this script
     measures is ever fed back into a motion decision. Bar/sensor placements
     are oracle-authored scene-build inputs only (acoustic_only exclusivity,
     law 5), recorded for later analysis, never read back mid-session.
  3. Pre-registered criterion:
     written here, verbatim, BEFORE this script is ever run against real
     gate data. Computed ONLY by the main agent's offline analysis
     (plan.md 步 2), never by this script:

       g1_object_detectable : paired_capture-style SNR_peak > 10 for ALL
                               3 distance cells (d in {0.5, 0.8, 1.1} m),
                               bar in the real task geometry (table + arm +
                               REAL Robotiq gripper + horizontal sensor).
       g2_object_ranging     : r(peak_sample_idx, true_distance_3d_m) >= 0.95
                               over stationarity_ok points, bar swept 10
                               points 0.40-1.10 m (equidistant), sensor
                               fixed at the D1.5 corridor start pose.
                               (M3_D3_DESIGN.md's own prose draft says "8
                               點"; plan.md 步1's operational spec says
                               "10 點" -- this script implements plan.md's
                               10, the later/operational document.)
       m3b_mover_effect_null : |slope_target - slope_sensor| <=
                               2 x pooled_SE, comparing OLS
                               (peak_sample_idx ~ true_distance_3d_m) slopes
                               of m3b_target (bar swept, sensor fixed) vs
                               m3b_sensor (bar fixed at x=1.30, arm-carried
                               sensor swept) over the SAME nominal 3D
                               distance set (13 points, 0.40-0.85 m,
                               step 0.0375 m). Pass => no mover effect,
                               D3 may use either series' calibration
                               interchangeably. Fail => attribute to a
                               sensor-motion systematic and have D3 use
                               m3b_sensor's (in-situ) slope instead.
  4. Raw waveform landing:
     every measured condition's mean primary waveform is saved as .npy
     under <mode>/waveforms/, so every derived number (SNR, peak_idx, OLS
     fit) can be recomputed offline from raw data.
  5. acoustic_only exclusivity:
     no oracle quantity computed here (bar position, sensor's nominal
     target x) is ever read back into a control decision, because there is
     no control decision in this script -- g1/g2/m3b_target/m3b_sensor are
     all open-loop sweeps. debug_scaffold is therefore always False in this
     script's meta.json (recorded for the same auditability discipline as
     D-8's oracle-scaffold marking convention, even though it doesn't apply
     here in the oracle-assisted-control sense).

Two per-step geometry audits (verbatim from d15, unchanged rationale --
see scripts/d15_arm_approach_runner.py's own "First-order risk" section):
posture_violation (arm links clipping floor/table) and sensor_pose_violation
(sensor prim's world pose straying from the nominal 0.65 m / +X-forward
mount pose). Neither aborts a run; both are recorded per point/cell and
left for offline exclusion, exactly as d15 does.

CLI
---
    --mode {g1,g2,m3b_target,m3b_sensor}   Required.
    --output-dir PATH                      Required.
    --sensor-offset FLOAT                  default 0.25 m (same as d15;
                                            already chosen to clear a real
                                            gripper's fingertips).
    --smoke                                g1: 1 distance, n_measure=4.
                                            g2/m3b_target/m3b_sensor: 3
                                            points instead of 10/13/13.

Usage
-----
    ./app/python.sh scripts/d3_gates_runner.py \\
        --mode g1 --output-dir runtime/outputs/v2_d3_gates
    ./app/python.sh scripts/d3_gates_runner.py \\
        --mode g2 --output-dir runtime/outputs/v2_d3_gates
    ./app/python.sh scripts/d3_gates_runner.py \\
        --mode m3b_target --output-dir runtime/outputs/v2_d3_gates
    ./app/python.sh scripts/d3_gates_runner.py \\
        --mode m3b_sensor --output-dir runtime/outputs/v2_d3_gates
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ── Argument parsing BEFORE SimulationApp (rule 4-1) ──────────────────────────
parser = argparse.ArgumentParser(
    description="D3.0 pre-registered gates: g1 (bar detectable) / g2 (bar "
                "ranging) / m3b_target / m3b_sensor (mover-effect A/B), "
                "UR10e + real Robotiq gripper + horizontal arm-carried sensor."
)
parser.add_argument("--mode", type=str, required=True,
                     choices=("g1", "g2", "m3b_target", "m3b_sensor"))
parser.add_argument("--output-dir", type=str, required=True,
                     help="Output root; a mode-specific sub-directory is created underneath")
parser.add_argument("--sensor-offset", type=float, default=0.25,
                     help="Acoustic sensor's local +X offset (m) from its mount frame")
parser.add_argument("--smoke", action="store_true",
                     help="g1: 1 distance, n_measure=4. Other modes: 3 points instead of 10/13/13.")
args, _ = parser.parse_known_args()

# ── Physical / scene constants (mirror d15_arm_approach_runner.py) ────────────
N_SETTLE = 40
N_MEASURE = 12
STATIONARITY_DRIFT_MAX = 0.05

ARM_PATH = "/World/ur10e"
SENSOR_LOCAL_NAME = "acoustic_sensor"
BAR_PATH = "/World/bar"
TABLE_PATH = "/World/table"

TOOL_Z_M = 0.65                  # tool0 height; fixed for every step (same as d15)
TABLE_TOP_Z_M = 0.40             # same physical table as d15
TABLE_WIDTH_M = 1.2
TABLE_DEPTH_M = 0.8
TABLE_CENTER_X_M = 1.05
TABLE_CENTER_Y_M = 0.0

# Bar target (decision D-3): 0.06(x) x 0.06(y) x 0.12(z) m, standing bottom-
# on-table. plan.md's literal formula is "中心 z = 桌頂+0.06" -- table_top_z
# (0.40, the table Cube's actual top face) + half the bar's own height
# (0.12/2 = 0.06) = 0.46. (M3_D3_DESIGN.md's prose draft illustrates "z=0.51",
# which is table_top_z + 0.05 (D1.5's *cube-target* resting height, itself
# table_top+0.05 for a 0.10 m cube) + 0.06 -- i.e. it re-used D1.5's target
# reference height instead of the table's own top face. plan.md's literal
# formula is the later, operational spec and is what this script implements;
# noted here for anyone reconciling the two documents.)
BAR_SCALE_M = (0.06, 0.06, 0.12)  # (x, y, z)
BAR_Z_M = TABLE_TOP_Z_M + BAR_SCALE_M[2] / 2.0   # 0.46
HEIGHT_DIFF_M = TOOL_Z_M - BAR_Z_M                # 0.19

SENSOR_X_START_M = 0.60          # D1.5 corridor start pose; g1/g2/m3b_target
                                  # hold the sensor here for the whole session.
BAR_FIXED_X_M3B_SENSOR_M = 1.30  # m3b_sensor: bar fixed here, sensor scans.

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

IK_ORIENTATION_TOLERANCE_RAD_D3 = 0.08   # same as d15 (~4.6 deg)


# ── Pure-stdlib OLS (verbatim from d1/d15) ─────────────────────────────────────
def _ols_pure(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
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


# ── Distance-set helpers (pure stdlib; mode-specific point/cell placements) ───
def _linspace(lo: float, hi: float, n: int) -> list[float]:
    if n <= 1:
        return [lo]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def _g1_distances(smoke: bool) -> list[float]:
    return [0.5] if smoke else [0.5, 0.8, 1.1]


def _g2_distances(smoke: bool) -> list[float]:
    return _linspace(0.40, 1.10, 3 if smoke else 10)


def _m3b_distances(smoke: bool) -> list[float]:
    if smoke:
        return _linspace(0.40, 1.00, 3)
    # 0.40-0.85 m (NOT 0.40-1.00): the sensor-sweep twin (m3b_sensor) must
    # reach every distance in this set, and with the bar at x=1.30 the far
    # distances need sensor_x = 1.30 - sqrt(d^2 - 0.19^2); d=1.00 would need
    # sensor_x ~ 0.32 (tool0_x ~ 0.07, inside the base column, IK-dead --
    # reproduced in the pkg-A smoke). d in [0.40, 0.85] keeps sensor_x in
    # [0.47, 0.95], the corridor D1.5 already validated. Both m3b modes use
    # THIS set so the slope comparison is over identical distances.
    # (Main-agent design decision 2026-07-10, after pkg-A smoke flag.)
    n = 13
    step = (0.85 - 0.40) / (n - 1)  # 0.0375
    return [0.40 + i * step for i in range(n)]


if args.mode == "g1":
    DISTANCES = _g1_distances(args.smoke)
    N_MEASURE_G1 = 4 if args.smoke else N_MEASURE
elif args.mode == "g2":
    DISTANCES = _g2_distances(args.smoke)
    N_MEASURE_G1 = None
elif args.mode == "m3b_target":
    DISTANCES = _m3b_distances(args.smoke)
    N_MEASURE_G1 = None
else:  # m3b_sensor
    DISTANCES = _m3b_distances(args.smoke)
    N_MEASURE_G1 = None


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
    GRIPPER_VARIANT,
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
from geometry_passport_v1 import IK_POSITION_TOLERANCE_M  # noqa: E402

# ── Module-level data buffer (Writer -> main loop communication, rule 4-2) ────
_buf: dict = {"latest": None}


def _extract_frame(gmo) -> dict | None:
    """Verbatim from d15_arm_approach_runner.py._extract_frame."""
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

    return {
        "amp_all": amp_all,
        "num_spsgw": num_spsgw,
        "way_start_rx_ids": way_start_rx_ids,
        "n_elements": n,
    }


class D3GatesWriter(Writer):
    """Parses GMO each frame and stores the full-fidelity frame dict in the
    module-level _buf (rule 4-2). Identical to d15's writer (renamed class only)."""

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
    """Verbatim from d15: way-ordinal grouping."""
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
    """Verbatim from d15: advances n_frames, ACCUMULATES per-RX primary waveforms."""
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
    """Verbatim from d15: settle -> block A -> block B -> point value = (A+B)/2,
    plus the A-vs-B drift audit."""
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

    return {
        "mean_primary": mean_primary,
        "peak_sample_idx": _peak_idx(mean_primary),
        "early_energy": _early_energy(mean_primary),
        "point_drift": point_drift,
        "stationarity_ok": stationarity_ok,
        "n_frames_valid_a": block_a["n_frames_valid"],
        "n_frames_valid_b": block_b["n_frames_valid"],
    }


# ── SNR metrics (verbatim formula from paired_capture_runner.py) ──────────────
def _truncate_common3(a: np.ndarray, b: np.ndarray, c: np.ndarray):
    lengths = [x.size for x in (a, b, c) if x is not None]
    if not lengths or min(lengths) == 0:
        return (np.array([], dtype=float),) * 3, 0, False
    min_len = min(lengths)
    truncated = len(set(lengths)) > 1
    out = tuple(np.asarray(x[:min_len], dtype=float) for x in (a, b, c))
    return out, min_len, truncated


def _snr_metrics(wf_with: np.ndarray, wf_noise: np.ndarray, wf_without: np.ndarray):
    """snr_peak / snr_energy, verbatim from paired_capture_runner.py's Metrics
    section: noise_floor = |with - noise_ref| (same-scene repeat); signal =
    |with - without| (target-removal difference)."""
    (w, n, o), n_common, truncated = _truncate_common3(wf_with, wf_noise, wf_without)
    if n_common == 0:
        return float("nan"), float("nan"), truncated
    noise_floor_peak = float(np.max(np.abs(w - n)))
    noise_floor_energy = float(np.sum(np.abs(w - n)))
    diff_wo = np.abs(w - o)
    snr_peak = float(np.max(diff_wo)) / max(noise_floor_peak, 1e-12)
    snr_energy = float(np.sum(diff_wo)) / max(noise_floor_energy, 1e-12)
    return snr_peak, snr_energy, truncated


# ── Geometry helpers ─────────────────────────────────────────────────────────
def _build_table(stage) -> None:
    Cube(
        TABLE_PATH,
        sizes=[1.0],
        scales=np.array([[TABLE_WIDTH_M, TABLE_DEPTH_M, TABLE_TOP_Z_M]]),
        positions=np.array([[TABLE_CENTER_X_M, TABLE_CENTER_Y_M, TABLE_TOP_Z_M / 2.0]]),
    )


def _build_bar(x: float, y: float, z: float) -> None:
    Cube(
        BAR_PATH,
        sizes=[1.0],
        scales=np.array([[BAR_SCALE_M[0], BAR_SCALE_M[1], BAR_SCALE_M[2]]]),
        positions=np.array([[x, y, z]]),
    )


def _move_bar(stage, x: float, y: float, z: float) -> None:
    """Same xformOp:translate rewrite as d15's _move_target (rule 3-4)."""
    prim = stage.GetPrimAtPath(BAR_PATH)
    xformable = UsdGeom.Xformable(prim)
    ops_by_name = {op.GetOpName(): op for op in xformable.GetOrderedXformOps()}
    key = "xformOp:translate"
    if key in ops_by_name:
        ops_by_name[key].Set(Gf.Vec3d(x, y, z))
    else:
        xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))


def _select_gripper_variant(stage, arm_path: str) -> str | None:
    """D-4: select the REAL Robotiq gripper variant (not d15's bare-arm
    'None' selection) -- same variant-set mechanism
    ur10e_robotiq_common.spawn_ur10e_robotiq() uses (ur10e_robotiq_common.py
    :389-392). Returns the variant selection applied, or None if the USD
    offers no Gripper variant set at all."""
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
    """Verbatim from d15: True if a posture VIOLATION exists on any monitored
    link this step (floor clip or table clip)."""
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
    """Same violation rule as d15's _audit_sensor_pose, extended to return the
    sensor's world y as well (needed for a true 3D distance, not just x/z)."""
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


# ── IK helper (verbatim pattern from d15) ──────────────────────────────────────
def _solve_tool0(ik: LulaKinematicsSolver, target_x: float, warm_q: np.ndarray) -> tuple[np.ndarray, bool]:
    ee_target = (float(target_x), 0.0, float(TOOL_Z_M))
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


def _move_arm(robot, world, q: np.ndarray) -> None:
    hold_arm_joint_positions(robot, q, world, render=False, simulation_app=None, arm_only_kinematic=True)


# ── Scene construction ─────────────────────────────────────────────────────────
print("=== d3_gates_runner.py ===")
print(f"mode={args.mode}  smoke={args.smoke}  n_points/cells={len(DISTANCES)}")
print(f"n_settle={N_SETTLE}  n_measure={N_MEASURE_G1 if N_MEASURE_G1 is not None else N_MEASURE}")
print(f"bar_scale_m={BAR_SCALE_M}  bar_z_m={BAR_Z_M:.4f}  height_diff_m={HEIGHT_DIFF_M:.4f}")
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
rep.WriterRegistry.register(D3GatesWriter)
sensor.attach_writer("D3GatesWriter")

world = World()
robot = world.scene.add(Robot(prim_path=ARM_PATH, name="ur10e"))
world.reset()

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

# ── Initial bar placement (mode-dependent) ────────────────────────────────────
if args.mode == "m3b_sensor":
    init_bar_x, init_bar_y, init_bar_z = BAR_FIXED_X_M3B_SENSOR_M, 0.0, BAR_Z_M
else:
    _d0 = DISTANCES[0]
    _horiz0 = math.sqrt(max(_d0 ** 2 - HEIGHT_DIFF_M ** 2, 1e-6))
    init_bar_x, init_bar_y, init_bar_z = SENSOR_X_START_M + _horiz0, 0.0, BAR_Z_M

_build_bar(init_bar_x, init_bar_y, init_bar_z)
print(f"bar Cube created at ({init_bar_x:.4f}, {init_bar_y:.4f}, {init_bar_z:.4f}) "
      f"(scale={BAR_SCALE_M})")
_bar_exists = True

# ── Initial arm pose: elbow-up forward-reach seed -> corridor start ──────────
seed_q = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
q_init, ok_init = _solve_tool0(ik, SENSOR_X_START_M - args.sensor_offset, seed_q)
if not ok_init:
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
print("SENSOR_POSE_SELF_CHECK passed: "
      f"|z-{TOOL_Z_M}|={abs(float(_s_pos[2]) - TOOL_Z_M):.4f} <= {SENSOR_Z_TOL_M}, "
      f"angle={_s_angle_deg:.3f} <= {SENSOR_ANGLE_TOL_DEG} deg")

# ── Simulation warmup (rule: >=20 frames until numElements>0, max 60) ────────
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
result_summary: dict = {}

# ═══════════════════════════════════════════════════════════════════════════
# g1: paired capture (with -> noise_ref -> RemovePrim -> without -> rebuild)
# per distance cell; bar in real task geometry, sensor static at corridor start.
# ═══════════════════════════════════════════════════════════════════════════
if args.mode == "g1":
    cells: list[dict] = []
    for i, d3d_nominal in enumerate(DISTANCES):
        horiz = math.sqrt(max(d3d_nominal ** 2 - HEIGHT_DIFF_M ** 2, 1e-6))
        bar_x, bar_y, bar_z = SENSOR_X_START_M + horiz, 0.0, BAR_Z_M

        if _bar_exists:
            _move_bar(stage, bar_x, bar_y, bar_z)
        else:
            _build_bar(bar_x, bar_y, bar_z)
            _bar_exists = True

        posture_violation = _audit_posture(stage, ARM_PATH, cache)
        sensor_violation, sx, sy, sz, sensor_angle_deg = _audit_sensor_pose(stage, sensor_path, cache)
        true3d = math.sqrt((bar_x - sx) ** 2 + (bar_y - sy) ** 2 + (bar_z - sz) ** 2)

        res_with = _measure_point(N_SETTLE, N_MEASURE_G1)
        if not res_with["stationarity_ok"]:
            n_drift_flagged += 1
        wf_tag = f"d{i:02d}"
        np.save(wf_dir / f"{wf_tag}_with.npy", res_with["mean_primary"])

        res_noise = _measure_point(N_SETTLE, N_MEASURE_G1)
        if not res_noise["stationarity_ok"]:
            n_drift_flagged += 1
        np.save(wf_dir / f"{wf_tag}_noise_ref.npy", res_noise["mean_primary"])

        stage.RemovePrim(BAR_PATH)
        _bar_exists = False
        res_without = _measure_point(N_SETTLE, N_MEASURE_G1)
        if not res_without["stationarity_ok"]:
            n_drift_flagged += 1
        np.save(wf_dir / f"{wf_tag}_without.npy", res_without["mean_primary"])

        snr_peak, snr_energy, wf_truncated = _snr_metrics(
            res_with["mean_primary"], res_noise["mean_primary"], res_without["mean_primary"]
        )

        # Rebuild (plan.md step 1.3 "→重建") so the scene ends this cell in a
        # known state and the next cell's move op has a prim to act on.
        _build_bar(bar_x, bar_y, bar_z)
        _bar_exists = True

        cell = {
            "cell_index": i,
            "nominal_distance_3d_m": d3d_nominal,
            "bar_x": bar_x, "bar_y": bar_y, "bar_z": bar_z,
            "sensor_x_actual": sx, "sensor_y_actual": sy, "sensor_z_actual": sz,
            "sensor_angle_deg": sensor_angle_deg,
            "true_distance_3d_m": true3d,
            "posture_violation": posture_violation,
            "sensor_pose_violation": sensor_violation,
            "with_peak_idx": res_with["peak_sample_idx"],
            "noise_peak_idx": res_noise["peak_sample_idx"],
            "without_peak_idx": res_without["peak_sample_idx"],
            "with_stationarity_ok": res_with["stationarity_ok"],
            "noise_stationarity_ok": res_noise["stationarity_ok"],
            "without_stationarity_ok": res_without["stationarity_ok"],
            "snr_peak": snr_peak,
            "snr_energy": snr_energy,
            "waveform_truncated": wf_truncated,
            "waveform_tag": wf_tag,
        }
        cells.append(cell)
        print(f"[g1 {i+1}/{len(DISTANCES)}] d3d_nominal={d3d_nominal:.3f} true3d={true3d:.4f} "
              f"snr_peak={snr_peak:.3f} snr_energy={snr_energy:.3f} "
              f"posture_violation={posture_violation} sensor_pose_violation={sensor_violation}")

    result_summary = {
        "mode": "g1",
        "criterion_text": "g1_object_detectable: SNR_peak > 10 for ALL cells "
                           "(adjudicated offline, plan.md 步 2 -- NOT computed here)",
        "cells": cells,
    }
    with (out_dir / "gates_g1.json").open("w") as f:
        json.dump(result_summary, f, indent=2)
    print()
    all_snr = [c["snr_peak"] for c in cells]
    print(f"G1_RESULT n_cells={len(cells)} snr_peak_values={all_snr}")

# ═══════════════════════════════════════════════════════════════════════════
# g2 / m3b_target: bar swept over DISTANCES, sensor static at corridor start.
# Single-condition measurement per point (peak_sample_idx + drift audit),
# same shape as d15's probe mode.
# ═══════════════════════════════════════════════════════════════════════════
elif args.mode in ("g2", "m3b_target"):
    rows: list[dict] = []
    for i, d3d_nominal in enumerate(DISTANCES):
        horiz = math.sqrt(max(d3d_nominal ** 2 - HEIGHT_DIFF_M ** 2, 1e-6))
        bar_x, bar_y, bar_z = SENSOR_X_START_M + horiz, 0.0, BAR_Z_M
        _move_bar(stage, bar_x, bar_y, bar_z)

        posture_violation = _audit_posture(stage, ARM_PATH, cache)
        sensor_violation, sx, sy, sz, sensor_angle_deg = _audit_sensor_pose(stage, sensor_path, cache)
        true3d = math.sqrt((bar_x - sx) ** 2 + (bar_y - sy) ** 2 + (bar_z - sz) ** 2)

        res = _measure_point(N_SETTLE, N_MEASURE)
        if not res["stationarity_ok"]:
            n_drift_flagged += 1
        wf_tag = f"point_{i:02d}"
        np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])

        rows.append({
            "point_index": i,
            "nominal_distance_3d_m": d3d_nominal,
            "bar_x": bar_x, "bar_y": bar_y, "bar_z": bar_z,
            "sensor_x_actual": sx, "sensor_y_actual": sy, "sensor_z_actual": sz,
            "sensor_angle_deg": sensor_angle_deg,
            "true_distance_3d_m": true3d,
            "peak_sample_idx": res["peak_sample_idx"],
            "point_drift": res["point_drift"],
            "stationarity_ok": res["stationarity_ok"],
            "posture_violation": posture_violation,
            "sensor_pose_violation": sensor_violation,
            "waveform_tag": wf_tag,
        })
        print(f"[{args.mode} {i+1}/{len(DISTANCES)}] true3d={true3d:.4f} "
              f"peak_idx={res['peak_sample_idx']:.1f} drift={res['point_drift']:.4f} "
              f"ok={res['stationarity_ok']} posture_violation={posture_violation} "
              f"sensor_pose_violation={sensor_violation}")

    csv_name = "g2_points.csv" if args.mode == "g2" else "m3b_target_points.csv"
    csv_path = out_dir / csv_name
    fieldnames = ["point_index", "nominal_distance_3d_m", "bar_x", "bar_y", "bar_z",
                  "sensor_x_actual", "sensor_y_actual", "sensor_z_actual", "sensor_angle_deg",
                  "true_distance_3d_m", "peak_sample_idx", "point_drift", "stationarity_ok",
                  "posture_violation", "sensor_pose_violation", "waveform_tag"]
    with csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(rows)

    kept_x = [r["true_distance_3d_m"] for r in rows if r["stationarity_ok"]]
    kept_y = [r["peak_sample_idx"] for r in rows if r["stationarity_ok"]]
    slope, intercept, r_val = _ols_pure(kept_x, kept_y)
    print()
    label = "G2_RESULT" if args.mode == "g2" else "M3B_TARGET_RESULT"
    print(f"{label} r={r_val} slope={slope} intercept={intercept} n_kept={len(kept_x)}/{len(DISTANCES)}")
    result_summary = {"mode": args.mode, "csv": csv_name, "n_points": len(DISTANCES),
                       "n_kept": len(kept_x), "r": r_val, "slope": slope, "intercept": intercept}

# ═══════════════════════════════════════════════════════════════════════════
# m3b_sensor: bar fixed at x=BAR_FIXED_X_M3B_SENSOR_M; arm-carried sensor
# scans to reproduce the SAME nominal 3D distance set as m3b_target. Per-point
# IK solve (like d15's probe mode); IK failure never crashes the session
# (recorded ik_ok=False, point skipped, same non-crash convention as d15).
# ═══════════════════════════════════════════════════════════════════════════
else:  # m3b_sensor
    rows = []
    warm_q = q_init
    for i, d3d_nominal in enumerate(DISTANCES):
        horiz = math.sqrt(max(d3d_nominal ** 2 - HEIGHT_DIFF_M ** 2, 1e-6))
        target_sensor_x = BAR_FIXED_X_M3B_SENSOR_M - horiz
        tool0_x = target_sensor_x - args.sensor_offset
        q, ok = _solve_tool0(ik, tool0_x, warm_q)
        if ok:
            _move_arm(robot, world, q)
            warm_q = q

        posture_violation = _audit_posture(stage, ARM_PATH, cache)
        sensor_violation, sx, sy, sz, sensor_angle_deg = _audit_sensor_pose(stage, sensor_path, cache)
        true3d = math.sqrt(
            (BAR_FIXED_X_M3B_SENSOR_M - sx) ** 2 + (0.0 - sy) ** 2 + (BAR_Z_M - sz) ** 2
        )

        row = {
            "point_index": i,
            "nominal_distance_3d_m": d3d_nominal,
            "target_sensor_x": target_sensor_x,
            "sensor_x_actual": sx, "sensor_y_actual": sy, "sensor_z_actual": sz,
            "sensor_angle_deg": sensor_angle_deg,
            "true_distance_3d_m": true3d if ok else float("nan"),
            "peak_sample_idx": float("nan"), "point_drift": float("nan"),
            "stationarity_ok": False, "waveform_tag": "",
            "posture_violation": posture_violation, "sensor_pose_violation": sensor_violation,
            "ik_ok": ok,
        }
        row.update(_joint_row_fields(q if ok else warm_q))

        if not ok:
            rows.append(row)
            print(f"[m3b_sensor {i+1}/{len(DISTANCES)}] target_sensor_x={target_sensor_x:.4f} "
                  f"IK_FAILED -- point skipped "
                  f"(posture_violation={posture_violation} sensor_pose_violation={sensor_violation})")
            continue

        res = _measure_point(N_SETTLE, N_MEASURE)
        if not res["stationarity_ok"]:
            n_drift_flagged += 1
        wf_tag = f"point_{i:02d}"
        np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])
        row.update({
            "peak_sample_idx": res["peak_sample_idx"],
            "point_drift": res["point_drift"],
            "stationarity_ok": res["stationarity_ok"],
            "waveform_tag": wf_tag,
        })
        rows.append(row)
        print(f"[m3b_sensor {i+1}/{len(DISTANCES)}] target_sensor_x={target_sensor_x:.4f} "
              f"(actual={sx:.4f}) true3d={true3d:.4f} peak_idx={res['peak_sample_idx']:.1f} "
              f"drift={res['point_drift']:.4f} ok={res['stationarity_ok']} "
              f"posture_violation={posture_violation} sensor_pose_violation={sensor_violation}")

    csv_path = out_dir / "m3b_sensor_points.csv"
    fieldnames = ["point_index", "nominal_distance_3d_m", "target_sensor_x",
                  "sensor_x_actual", "sensor_y_actual", "sensor_z_actual", "sensor_angle_deg",
                  "true_distance_3d_m", "peak_sample_idx", "point_drift", "stationarity_ok",
                  "posture_violation", "sensor_pose_violation", "ik_ok", "waveform_tag",
                  "q_shoulder_pan", "q_shoulder_lift", "q_elbow", "q_wrist_1", "q_wrist_2", "q_wrist_3"]
    with csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(rows)

    kept_x = [r["true_distance_3d_m"] for r in rows if r["stationarity_ok"] and r["ik_ok"]]
    kept_y = [r["peak_sample_idx"] for r in rows if r["stationarity_ok"] and r["ik_ok"]]
    slope, intercept, r_val = _ols_pure(kept_x, kept_y)
    n_ik_failed = sum(1 for r in rows if not r["ik_ok"])
    print()
    print(f"M3B_SENSOR_RESULT r={r_val} slope={slope} intercept={intercept} "
          f"n_kept={len(kept_x)}/{len(DISTANCES)} n_ik_failed={n_ik_failed}")
    result_summary = {"mode": "m3b_sensor", "csv": "m3b_sensor_points.csv", "n_points": len(DISTANCES),
                       "n_kept": len(kept_x), "n_ik_failed": n_ik_failed,
                       "r": r_val, "slope": slope, "intercept": intercept}

timeline.stop()

# ── meta.json (all modes) ─────────────────────────────────────────────────────
meta = {
    "mode": args.mode,
    "smoke": bool(args.smoke),
    "acoustic_only": True,          # law 5: no oracle quantity fed into any control decision
    "debug_scaffold": False,        # no oracle-assisted control exists in this script (see law 5 note)
    "distances_nominal_3d_m": DISTANCES,
    "n_settle": N_SETTLE,
    "n_measure": N_MEASURE_G1 if N_MEASURE_G1 is not None else N_MEASURE,
    "sensor_offset_m": args.sensor_offset,
    "arm_path": ARM_PATH,
    "mount_path_used": mount_path,
    "sensor_path": sensor_path,
    "gripper_variant_selected": gripper_variant_selected,
    "tool_z_m": TOOL_Z_M,
    "bar_scale_m": list(BAR_SCALE_M),
    "bar_z_m": BAR_Z_M,
    "height_diff_m": HEIGHT_DIFF_M,
    "table_top_z_m": TABLE_TOP_Z_M,
    "table_center_x_m": TABLE_CENTER_X_M,
    "table_width_m": TABLE_WIDTH_M,
    "table_depth_m": TABLE_DEPTH_M,
    "sensor_x_start_m": SENSOR_X_START_M,
    "bar_fixed_x_m3b_sensor_m": BAR_FIXED_X_M3B_SENSOR_M if args.mode == "m3b_sensor" else None,
    "posture_link_names": list(POSTURE_LINK_NAMES),
    "floor_margin_z_m": FLOOR_MARGIN_Z_M,
    "table_clear_margin_m": TABLE_CLEAR_MARGIN_M,
    "sensor_z_tol_m": SENSOR_Z_TOL_M,
    "sensor_angle_tol_deg": SENSOR_ANGLE_TOL_DEG,
    "ik_robot_description": str(IK_ROBOT_DESCRIPTION),
    "ik_urdf": str(IK_URDF),
    "ik_orientation_tolerance_rad": IK_ORIENTATION_TOLERANCE_RAD_D3,
    "ik_position_tolerance_m": IK_POSITION_TOLERANCE_M,
    "assets_root_used": assets_root_used,
    "usd_path_used": usd_path_used,
    "warmup_frames": _warmup_frames,
    "n_drift_flagged": n_drift_flagged,
    "criteria_text": {
        "g1_object_detectable": "paired_capture-style SNR_peak > 10 for ALL 3 distance "
                                 "cells (d={0.5,0.8,1.1} m), bar in real task geometry "
                                 "(table + arm + REAL Robotiq gripper + horizontal sensor). "
                                 "Adjudicated offline (plan.md 步 2).",
        "g2_object_ranging": "r(peak_sample_idx, true_distance_3d_m) >= 0.95 over "
                              "stationarity_ok points, bar swept 10 points 0.40-1.10 m "
                              "(equidistant), sensor fixed at D1.5 corridor start pose. "
                              "Adjudicated offline (plan.md 步 2).",
        "m3b_mover_effect_null": "|slope_target - slope_sensor| <= 2 x pooled_SE "
                                  "(m3b_target: bar swept, sensor fixed; m3b_sensor: bar "
                                  "fixed x=1.30, arm-carried sensor swept; same nominal "
                                  "13-point 0.40-0.85 m 3D distance set). "
                                  "Adjudicated offline (plan.md 步 2).",
    },
    "timestamp": datetime.datetime.now().isoformat(),
    "script": "d3_gates_runner.py",
}
with (out_dir / "meta.json").open("w") as f:
    json.dump(meta, f, indent=2)

print()
print(f"-> outputs saved under {out_dir}")

simulation_app.close()
