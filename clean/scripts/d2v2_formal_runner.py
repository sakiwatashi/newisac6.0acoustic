"""D2 formal three-arm experiment: 2-D localization + 2-DOF closed-loop approach
via motion-synthesized multilateration.

Full spec: docs/plan_v2/D2V2_DESIGN_2026-07-10.md §3. Gate provenance: the g2
trilateration probe PASSED both pre-registered criteria
(runtime/outputs/v2_d2v2_probe/adjudication.json: r_x=0.9878, r_y=0.9600), and
the native lateral paths are quadruply falsified (energy/timing/id/rxGroup) --
this experiment tests whether the ALGORITHMIC lateral recovery drives a
closed-loop 2-DOF approach whose causality survives information ablation.

Skeleton: scripts/d2v2_trilat_probe.py (scene, measurement, IK-with-y,
least-squares solver) + scripts/d15_arm_approach_runner.py (episode loop,
three-arm mechanics, guards, audit bookkeeping). Approach phase is kinematic-
writes only (the WPM-validated layer); there is NO grasp phase and therefore
no physics-articulation interaction in this runner.

Per-episode flow (closed arm):
  1. draw target (x,y) from the seeded uniform grid; place the bar there.
  2. vantage sweep: move the sensor to 5 lateral vantage points
     (x=0.60, y in {-0.15,-0.075,0,+0.075,+0.15}), measure range at each.
  3. localize: Gauss-Newton least-squares circle intersection -> (x_hat, y_hat).
  4. approach: step 0.05 m along the straight line from (0.60, 0) toward
     (x_hat, y_hat); at every step re-measure 1-D range and stop when the
     horizontal range estimate <= standoff 0.35 m. Guards: max 40 steps,
     corridor end at sensor x > 0.95.
Blind arm: identical pipeline (vantage sweep runs, measurement cost kept) but
every usable range is forced to +inf BEFORE localization and stop decisions:
localization has no solution (recorded as NaN), bearing falls back to straight
ahead (y=0), and only the corridor guard can end the episode.
Open arm: no measurement at all; walk straight to the fixed nominal stop
(1.10 - 0.35 = 0.75, y=0).

Pre-registered criteria (adjudicated OFFLINE by scripts/analyze_d2v2.py):
  d2_loc_y_tracking    : closed r(y_hat, y_true) >= 0.9
  d2_loc_x_tracking    : closed r(x_hat, x_true) >= 0.95
  d2_stop2d_beats_blind: closed |dist2D(stop, target) - standoff| RMSE <
                         blind's, Welch t-test p < 0.05
  d2_posture_clean     : zero posture/sensor-pose/IK violations, all arms
Iron laws: target true (x,y) is recorded for evaluation only; control consumes
ONLY calibrated acoustic ranges + the robot's own commanded/audited poses.

CLI:
    --arm {closed,blind,open}  Required.
    --output-dir PATH          Required.
    --n-episodes INT           default 30.
    --seed INT                 default 20260711 (same across arms = paired).
    --standoff FLOAT           default 0.35.
    --step FLOAT               default 0.05.
    --max-steps INT            default 40.
    --smoke                    1 episode.
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

parser = argparse.ArgumentParser(description="D2 formal: 2-D multilateration three-arm experiment")
parser.add_argument("--arm", type=str, required=True, choices=("closed", "blind", "open"))
parser.add_argument("--output-dir", type=str, required=True)
parser.add_argument("--n-episodes", type=int, default=30)
parser.add_argument("--seed", type=int, default=20260711)
parser.add_argument("--standoff", type=float, default=0.35)
parser.add_argument("--step", type=float, default=0.05)
parser.add_argument("--max-steps", type=int, default=40)
parser.add_argument("--sensor-offset", type=float, default=0.25)
parser.add_argument("--smoke", action="store_true")
args, _ = parser.parse_known_args()

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
BAR_SCALE_M = (0.06, 0.06, 0.12)
BAR_Z_M = TABLE_TOP_Z_M + BAR_SCALE_M[2] / 2.0
HEIGHT_DIFF_M = TOOL_Z_M - BAR_Z_M   # 0.19

SENSOR_X_START_M = 0.60
VANTAGE_Y_M = [-0.15, -0.075, 0.0, 0.075, 0.15]
CORRIDOR_GUARD_X_M = 0.95
TARGET_X_MIN_M, TARGET_X_MAX_M = 1.00, 1.20
TARGET_Y_MIN_M, TARGET_Y_MAX_M = -0.15, 0.15
NOMINAL_STOP = (1.10 - 0.35, 0.0)   # open arm: mid-range nominal minus standoff

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
IK_ORIENTATION_TOLERANCE_RAD = 0.08

CALIB_JSON_PATH = REPO_ROOT / "runtime" / "outputs" / "v2_d3_gates" / "bar_calibration.json"

N_EPISODES = 1 if args.smoke else args.n_episodes
_rng = random.Random(args.seed)
_full = [(_rng.uniform(TARGET_X_MIN_M, TARGET_X_MAX_M),
          _rng.uniform(TARGET_Y_MIN_M, TARGET_Y_MAX_M)) for _ in range(args.n_episodes)]
TARGETS = _full[:N_EPISODES]


def _load_calibration(path: pathlib.Path) -> dict:
    if not path.exists():
        raise SystemExit(f"ABORT: bar calibration not found: {path}")
    cal = json.load(path.open())
    for k in ("slope_smp_per_m", "intercept_smp"):
        if k not in cal or not math.isfinite(float(cal[k])):
            raise SystemExit(f"ABORT: invalid calibration field {k!r}")
    return cal


CAL = _load_calibration(CALIB_JSON_PATH)
SLOPE, INTERCEPT = float(CAL["slope_smp_per_m"]), float(CAL["intercept_smp"])
print(f"calibration: slope={SLOPE:.3f} intercept={INTERCEPT:.3f}")


def _range_from_peak(peak_idx: float) -> float:
    if not math.isfinite(peak_idx):
        return float("nan")
    return (peak_idx - INTERCEPT) / SLOPE


def _horiz_of(r3d: float) -> float:
    if not math.isfinite(r3d):
        return float("inf")
    return math.sqrt(max(r3d * r3d - HEIGHT_DIFF_M * HEIGHT_DIFF_M, 1e-6))


def _trilat_solve(vantages, h_ranges, x0, y0):
    pts = [(v, h) for v, h in zip(vantages, h_ranges) if math.isfinite(h) and 0.05 < h < 5.0]
    if len(pts) < 3:
        return float("nan"), float("nan"), float("nan"), len(pts)
    x, y = x0, y0
    for _ in range(25):
        JtJ = [[0.0, 0.0], [0.0, 0.0]]
        Jtr = [0.0, 0.0]
        for (vx, vy), h in pts:
            dx, dy = x - vx, y - vy
            d = math.sqrt(dx * dx + dy * dy)
            if d < 1e-9:
                continue
            r = d - h
            gx, gy = dx / d, dy / d
            JtJ[0][0] += gx * gx; JtJ[0][1] += gx * gy
            JtJ[1][0] += gy * gx; JtJ[1][1] += gy * gy
            Jtr[0] += gx * r; Jtr[1] += gy * r
        det = JtJ[0][0] * JtJ[1][1] - JtJ[0][1] * JtJ[1][0]
        if abs(det) < 1e-12:
            break
        sx = (JtJ[1][1] * Jtr[0] - JtJ[0][1] * Jtr[1]) / det
        sy = (JtJ[0][0] * Jtr[1] - JtJ[1][0] * Jtr[0]) / det
        x -= sx; y -= sy
        if abs(sx) + abs(sy) < 1e-7:
            break
    rms = math.sqrt(sum((math.sqrt((x - vx) ** 2 + (y - vy) ** 2) - h) ** 2 for (vx, vy), h in pts) / len(pts))
    return x, y, rms, len(pts)


# ── SimulationApp (rule 4-1) ─────────────────────────────────────────────────
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
from ur10e_robotiq_common import (                      # noqa: E402
    GRIPPER_VARIANT,
    ROBOT_USD_REL,
    SEED_POSES_RAD,
    hold_arm_joint_positions,
    resolve_sensor_mount_path,
)
from ur10e_robotiq_passport_v1 import (                  # noqa: E402
    IK_EE_FRAME,
    IK_MAX_JOINT_JUMP_APPROACH_RAD,
    IK_MAX_WRIST_3_JUMP_RAD,
    IK_ROBOT_DESCRIPTION,
    IK_URDF,
    solve_tool0_ik,
    tool0_grasp_orientation_wxyz,
)
from geometry_passport_v1 import IK_POSITION_TOLERANCE_M  # noqa: E402

_buf: dict = {"latest": None}


def _extract_frame(gmo):
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None
    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float).copy()
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    if num_spsgw <= 0 or n % num_spsgw != 0:
        return None
    return {"amp_all": amp_all, "num_spsgw": num_spsgw, "n_ways": n // num_spsgw}


class D2FormalWriter(Writer):
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


def _primary_of(frame):
    k = frame["num_spsgw"]
    ways = [frame["amp_all"][w * k:(w + 1) * k] for w in range(frame["n_ways"])]
    if len(ways) >= 2:
        return ways[0] if float(np.max(ways[0])) >= float(np.max(ways[1])) else ways[1]
    return ways[0]


def _measure_point(n_settle: int, n_measure: int) -> dict:
    for _ in range(n_settle):
        simulation_app.update()

    def _block(nf):
        acc = []
        for _ in range(nf):
            simulation_app.update()
            fr = _buf["latest"]
            if fr is None:
                continue
            acc.append(_primary_of(fr))
        if not acc:
            return np.array([], dtype=float)
        m = min(a.size for a in acc)
        return np.mean(np.array([a[:m] for a in acc]), axis=0)

    a = _block(n_measure)
    b = _block(n_measure)
    n = min(a.size, b.size)
    mean = (a[:n] + b[:n]) / 2.0 if n else np.array([], dtype=float)
    ea = float(np.sum(a[:20] ** 2)) if a.size else float("nan")
    eb = float(np.sum(b[:20] ** 2)) if b.size else float("nan")
    drift = abs(ea - eb) / max(abs(ea), abs(eb), 1e-12) if math.isfinite(ea) and math.isfinite(eb) else float("nan")
    return {"mean_primary": mean,
            "peak_sample_idx": float(np.argmax(mean)) if mean.size else float("nan"),
            "point_drift": drift,
            "stationarity_ok": bool(math.isfinite(drift) and drift <= STATIONARITY_DRIFT_MAX)}


def _select_gripper_variant(stage, arm_path):
    prim = stage.GetPrimAtPath(arm_path)
    if prim and prim.IsValid() and prim.GetVariantSets().HasVariantSet("Gripper"):
        prim.GetVariantSets().GetVariantSet("Gripper").SetVariantSelection(GRIPPER_VARIANT)
        return GRIPPER_VARIANT
    return None


def _link_world_xyz(stage, prim_path, cache):
    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return float("nan"), float("nan"), float("nan")
    cache.Clear()
    t = cache.GetLocalToWorldTransform(prim).ExtractTranslation()
    return float(t[0]), float(t[1]), float(t[2])


def _in_table_footprint(x, y):
    if not (math.isfinite(x) and math.isfinite(y)):
        return False
    return (TABLE_CENTER_X_M - TABLE_WIDTH_M / 2 <= x <= TABLE_CENTER_X_M + TABLE_WIDTH_M / 2
            and TABLE_CENTER_Y_M - TABLE_DEPTH_M / 2 <= y <= TABLE_CENTER_Y_M + TABLE_DEPTH_M / 2)


def _audit_posture(stage, arm_path, cache):
    for link_name in POSTURE_LINK_NAMES:
        x, y, z = _link_world_xyz(stage, f"{arm_path}/{link_name}", cache)
        if not math.isfinite(z):
            continue
        if z < FLOOR_MARGIN_Z_M:
            return True
        if _in_table_footprint(x, y) and z < (TABLE_TOP_Z_M + TABLE_CLEAR_MARGIN_M):
            return True
    return False


def _audit_sensor_pose(stage, sensor_path, cache):
    prim = stage.GetPrimAtPath(sensor_path)
    if not prim or not prim.IsValid():
        return True, float("nan"), float("nan"), float("nan"), float("nan")
    cache.Clear()
    m = cache.GetLocalToWorldTransform(prim)
    pos = m.ExtractTranslation()
    sx, sy, sz = float(pos[0]), float(pos[1]), float(pos[2])
    fwd = m.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()
    ang = math.degrees(math.acos(max(-1.0, min(1.0, float(fwd[0])))))
    violation = bool(abs(sz - TOOL_Z_M) > SENSOR_Z_TOL_M or ang > SENSOR_ANGLE_TOL_DEG)
    return violation, sx, sy, sz, ang


def _solve_tool0_xyz(ik, x, y, z, warm_q):
    q, ok = solve_tool0_ik(
        ik, (float(x), float(y), float(z)), warm_q,
        target_orientation=TOOL_TARGET_QUAT_WXYZ,
        position_tolerance=float(IK_POSITION_TOLERANCE_M),
        orientation_tolerance=float(IK_ORIENTATION_TOLERANCE_RAD),
        max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_APPROACH_RAD),
        max_wrist_3_jump_rad=float(IK_MAX_WRIST_3_JUMP_RAD),
        min_tool0_z_m=None,
    )
    q = np.asarray(q, dtype=float).reshape(-1)
    return q, bool(ok) and q.size >= 6 and bool(np.all(np.isfinite(q)))


def _move_arm(robot, world, q):
    hold_arm_joint_positions(robot, q, world, render=False, simulation_app=None, arm_only_kinematic=True)


def _move_bar(stage, x, y):
    prim = stage.GetPrimAtPath(BAR_PATH)
    xf = UsdGeom.Xformable(prim)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(x, y, BAR_Z_M))
    else:
        xf.AddTranslateOp().Set(Gf.Vec3d(x, y, BAR_Z_M))


# ── Scene ─────────────────────────────────────────────────────────────────────
print(f"=== d2v2_formal_runner.py === arm={args.arm} smoke={args.smoke} n={N_EPISODES} seed={args.seed}")
context = omni.usd.get_context()
context.new_stage()
stage = context.get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

assets_root = get_assets_root_path()
stage_utils.add_reference_to_stage(usd_path=f"{assets_root}/{ROBOT_USD_REL}", path=ARM_PATH)
for _ in range(20):
    simulation_app.update()
gripper_variant = _select_gripper_variant(stage, ARM_PATH)

Cube(TABLE_PATH, sizes=[1.0],
     scales=np.array([[TABLE_WIDTH_M, TABLE_DEPTH_M, TABLE_TOP_Z_M]]),
     positions=np.array([[TABLE_CENTER_X_M, TABLE_CENTER_Y_M, TABLE_TOP_Z_M / 2.0]]))
Cube(BAR_PATH, sizes=[1.0],
     scales=np.array([[BAR_SCALE_M[0], BAR_SCALE_M[1], BAR_SCALE_M[2]]]),
     positions=np.array([[TARGETS[0][0], TARGETS[0][1], BAR_Z_M]]))

mount_path = resolve_sensor_mount_path(ARM_PATH, stage)
sensor_path = f"{mount_path}/{SENSOR_LOCAL_NAME}"
acoustic, sensor = create_passport_acoustic(
    sensor_path, Acoustic=Acoustic, AcousticSensor=AcousticSensor, np=np,
    tick_rate_hz=TICK_RATE_HZ, center_frequency_hz=CENTER_FREQ_HZ,
    sensor_local_offset_m=(float(args.sensor_offset), 0.0, 0.0),
    mount_spacing_m=MOUNT_SPACING_M, aux_output_level="BASIC",
    writer_brings_annotator=True, az_span_deg=AZ_SPAN_DEG,
    el_span_deg=EL_SPAN_DEG, trace_tree_depth=TRACE_TREE_DEPTH,
)
rep.WriterRegistry.register(D2FormalWriter)
sensor.attach_writer("D2FormalWriter")

world = World()
robot = world.scene.add(Robot(prim_path=ARM_PATH, name="ur10e"))
world.reset()

ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
TOOL_TARGET_QUAT_WXYZ = np.asarray(
    tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"]), dtype=float)

timeline = omni.timeline.get_timeline_interface()
timeline.play()

seed_q = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
q0, ok0 = _solve_tool0_xyz(ik, SENSOR_X_START_M - args.sensor_offset, 0.0, TOOL_Z_M, seed_q)
if not ok0:
    print("ABORT: initial IK failed", flush=True)
    simulation_app.close()
    sys.exit(2)
_move_arm(robot, world, q0)

cache = UsdGeom.XformCache(0)
_mp = stage.GetPrimAtPath(mount_path)
_minv = cache.GetLocalToWorldTransform(_mp).GetInverse()
_lp = _minv.Transform(Gf.Vec3d(float(SENSOR_X_START_M), 0.0, float(TOOL_Z_M)))
_lq = _minv.ExtractRotationQuat().GetNormalized()
_sp = stage.GetPrimAtPath(sensor_path)
_sxf = UsdGeom.Xformable(_sp)
_ops = {op.GetOpName(): op for op in _sxf.GetOrderedXformOps()}
(_ops.get("xformOp:translate") or _sxf.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)).Set(Gf.Vec3d(_lp))
try:
    (_ops.get("xformOp:orient") or _sxf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)).Set(Gf.Quatd(_lq))
except Exception:
    _ops["xformOp:orient"].Set(Gf.Quatf(_lq))
sv0, sx0, sy0, sz0, sa0 = _audit_sensor_pose(stage, sensor_path, cache)
print(f"sensor pose: ({sx0:.4f},{sy0:.4f},{sz0:.4f}) angle={sa0:.3f} violation={sv0}")
if sv0:
    print("ABORT: sensor pose self-check failed", flush=True)
    simulation_app.close()
    sys.exit(2)

print("warmup...")
for i in range(80):
    simulation_app.update()
    if i >= 20 and _buf["latest"] is not None:
        break

out_dir = pathlib.Path(args.output_dir) / args.arm
wf_dir = out_dir / "waveforms"
wf_dir.mkdir(parents=True, exist_ok=True)

# ── Episode loop ──────────────────────────────────────────────────────────────
episode_rows: list[dict] = []
step_rows: list[dict] = []
total_pv = total_sv = 0

for ep_idx, (tx, ty) in enumerate(TARGETS):
    _move_bar(stage, tx, ty)
    warm = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
    q, ok = _solve_tool0_xyz(ik, SENSOR_X_START_M - args.sensor_offset, 0.0, TOOL_Z_M, warm)
    if not ok:
        episode_rows.append({"episode": ep_idx, "target_x": tx, "target_y": ty,
                             "x_hat": float("nan"), "y_hat": float("nan"),
                             "stop_x": float("nan"), "stop_y": float("nan"),
                             "stop_err_2d": float("nan"), "n_steps": 0,
                             "reason": "ik_failed", "episode_valid": False,
                             "n_vantages_used": 0})
        continue
    _move_arm(robot, world, q)
    warm = q
    ep_valid = True

    # vantage sweep (closed & blind both pay the cost; open skips)
    x_hat = y_hat = float("nan")
    n_used = 0
    if args.arm in ("closed", "blind"):
        vantages, h_list = [], []
        for v_idx, vy in enumerate(VANTAGE_Y_M):
            q, ok = _solve_tool0_xyz(ik, SENSOR_X_START_M - args.sensor_offset, vy, TOOL_Z_M, warm)
            if not ok:
                continue
            _move_arm(robot, world, q)
            warm = q
            pv = _audit_posture(stage, ARM_PATH, cache)
            sv, svx, svy, svz, sang = _audit_sensor_pose(stage, sensor_path, cache)
            total_pv += int(pv); total_sv += int(sv)
            if pv or sv:
                ep_valid = False
            res = _measure_point(N_SETTLE, N_MEASURE)
            tag = f"ep{ep_idx:03d}_v{v_idx}"
            np.save(wf_dir / f"{tag}.npy", res["mean_primary"])
            r3d = _range_from_peak(res["peak_sample_idx"])
            if args.arm == "blind":
                r3d = float("inf")   # information ablation, BEFORE localization
            h = _horiz_of(r3d) if math.isfinite(r3d) else float("inf")
            vantages.append((svx, svy))
            h_list.append(h)
            step_rows.append({"episode": ep_idx, "phase": "vantage", "step": v_idx,
                              "sensor_x": svx, "sensor_y": svy,
                              "peak_idx": res["peak_sample_idx"], "range_est": r3d,
                              "drift": res["point_drift"], "stationarity_ok": res["stationarity_ok"],
                              "posture_violation": pv, "sensor_pose_violation": sv,
                              "waveform_tag": tag})
        finite_h = [h for h in h_list if math.isfinite(h)]
        if len(finite_h) >= 3:
            x0g = SENSOR_X_START_M + sum(finite_h) / len(finite_h)
            x_hat, y_hat, _rms, n_used = _trilat_solve(vantages, h_list, x0g, 0.0)

    # approach bearing
    if args.arm == "closed" and math.isfinite(x_hat) and math.isfinite(y_hat):
        ux, uy = x_hat - SENSOR_X_START_M, y_hat - 0.0
        norm = math.sqrt(ux * ux + uy * uy)
        ux, uy = (ux / norm, uy / norm) if norm > 1e-9 else (1.0, 0.0)
    else:
        ux, uy = 1.0, 0.0   # blind (no solution) and closed-fallback: straight ahead

    # return to corridor start
    q, ok = _solve_tool0_xyz(ik, SENSOR_X_START_M - args.sensor_offset, 0.0, TOOL_Z_M, warm)
    if ok:
        _move_arm(robot, world, q)
        warm = q

    sx_cur, sy_cur = SENSOR_X_START_M, 0.0
    stop_reason = None
    n_steps = 0

    if args.arm == "open":
        q, ok = _solve_tool0_xyz(ik, NOMINAL_STOP[0] - args.sensor_offset, NOMINAL_STOP[1], TOOL_Z_M, warm)
        if ok:
            _move_arm(robot, world, q)
            warm = q
            sx_cur, sy_cur = NOMINAL_STOP
            for _ in range(N_SETTLE):
                simulation_app.update()
            pv = _audit_posture(stage, ARM_PATH, cache)
            sv, *_r = _audit_sensor_pose(stage, sensor_path, cache)
            total_pv += int(pv); total_sv += int(sv)
            if pv or sv:
                ep_valid = False
            stop_reason = "open_fixed"
            n_steps = 1
        else:
            stop_reason = "ik_failed"
            ep_valid = False
    else:
        for step_idx in range(args.max_steps):
            res = _measure_point(N_SETTLE, N_MEASURE)
            r3d = _range_from_peak(res["peak_sample_idx"])
            d_horiz_real = _horiz_of(r3d)
            d_horiz = float("inf") if args.arm == "blind" else d_horiz_real
            pv = _audit_posture(stage, ARM_PATH, cache)
            sv, svx, svy, svz, sang = _audit_sensor_pose(stage, sensor_path, cache)
            total_pv += int(pv); total_sv += int(sv)
            if pv or sv:
                ep_valid = False
            tag = f"ep{ep_idx:03d}_s{step_idx:03d}"
            np.save(wf_dir / f"{tag}.npy", res["mean_primary"])
            step_rows.append({"episode": ep_idx, "phase": "approach", "step": step_idx,
                              "sensor_x": sx_cur, "sensor_y": sy_cur,
                              "peak_idx": res["peak_sample_idx"], "range_est": d_horiz_real,
                              "drift": res["point_drift"], "stationarity_ok": res["stationarity_ok"],
                              "posture_violation": pv, "sensor_pose_violation": sv,
                              "waveform_tag": tag})
            n_steps = step_idx + 1
            if d_horiz <= args.standoff:
                stop_reason = "standoff_est"
                break
            nx, ny = sx_cur + args.step * ux, sy_cur + args.step * uy
            if nx > CORRIDOR_GUARD_X_M:
                stop_reason = "corridor_end"
                break
            q, ok = _solve_tool0_xyz(ik, nx - args.sensor_offset, ny, TOOL_Z_M, warm)
            if not ok:
                stop_reason = "ik_failed"
                ep_valid = False
                break
            _move_arm(robot, world, q)
            warm = q
            sx_cur, sy_cur = nx, ny
        else:
            stop_reason = "max_steps"

    d2d = math.sqrt((sx_cur - tx) ** 2 + (sy_cur - ty) ** 2)
    stop_err = abs(d2d - args.standoff)
    episode_rows.append({"episode": ep_idx, "target_x": tx, "target_y": ty,
                         "x_hat": x_hat, "y_hat": y_hat, "n_vantages_used": n_used,
                         "stop_x": sx_cur, "stop_y": sy_cur,
                         "stop_dist_2d": d2d, "stop_err_2d": stop_err,
                         "n_steps": n_steps, "reason": stop_reason,
                         "episode_valid": ep_valid})
    print(f"[ep {ep_idx+1:02d}/{N_EPISODES}] arm={args.arm} tgt=({tx:.3f},{ty:+.3f}) "
          f"hat=({x_hat:.3f},{y_hat:+.3f}) stop=({sx_cur:.3f},{sy_cur:+.3f}) "
          f"err2d={stop_err:.4f} steps={n_steps} reason={stop_reason} valid={ep_valid}")

with (out_dir / "episodes.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(episode_rows[0].keys()))
    w.writeheader()
    w.writerows(episode_rows)
with (out_dir / "steps.csv").open("w", newline="") as f:
    fields = sorted({k for r in step_rows for k in r}, key=lambda k: (k != "episode", k))
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(step_rows)

meta = {"arm": args.arm, "smoke": args.smoke, "seed": args.seed, "n_episodes": N_EPISODES,
        "standoff_m": args.standoff, "step_m": args.step, "max_steps": args.max_steps,
        "vantage_y_m": VANTAGE_Y_M, "sensor_x_start_m": SENSOR_X_START_M,
        "corridor_guard_x_m": CORRIDOR_GUARD_X_M, "nominal_stop": NOMINAL_STOP,
        "target_range": [TARGET_X_MIN_M, TARGET_X_MAX_M, TARGET_Y_MIN_M, TARGET_Y_MAX_M],
        "bar_scale_m": list(BAR_SCALE_M), "calibration": CAL,
        "gripper_variant": gripper_variant,
        "total_posture_violations": total_pv, "total_sensor_pose_violations": total_sv,
        "criteria_text": {
            "d2_loc_y_tracking": "closed r(y_hat,y_true)>=0.9 (offline)",
            "d2_loc_x_tracking": "closed r(x_hat,x_true)>=0.95 (offline)",
            "d2_stop2d_beats_blind": "closed stop_err_2d RMSE < blind, Welch p<0.05 (offline)",
            "d2_posture_clean": "zero violations all arms (offline)"},
        "timestamp": datetime.datetime.now().isoformat(), "script": "d2v2_formal_runner.py"}
with (out_dir / "meta.json").open("w") as f:
    json.dump(meta, f, indent=1)

print(f"RESULT arm={args.arm} episodes={len(episode_rows)} pv={total_pv} sv={total_sv}")
timeline.stop()
print(f"-> {out_dir}")
simulation_app.close()
