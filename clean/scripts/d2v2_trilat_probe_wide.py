"""D2v2 g2-wide gate: WIDE-BASELINE multilateration probe (2D-grasp gate 2 of 3).

Fork of scripts/d2v2_trilat_probe.py (measurement pipeline verbatim; only
geometry constants + criteria differ). Motivation: the 2D-grasp error budget
(scripts/d2v2_error_budget.py, runtime/outputs/d2v2_error_budget_v1/) found
NO configuration inside the validated bearing domain (<=33.5 deg) reaching
the +/-1.5 cm capture window; the minimal-extrapolation config is
scan_x=0.50, baseline 0.60 m, 13 vantages -> predicted lateral RMSE 1.26 cm
at max bearing 41.9 deg. This probe's single job: measure detection, ranging
and localization at bearings 34-43 deg, which no experiment has visited.

Geometry revision log (failure -> attribution -> fix, all BEFORE any
acoustic data was taken):
  round 1 (scan_x=0.50): ABORT at initial IK -- tool0 x = 0.50-0.25 = 0.25
    is inside the base-proximal dead zone (original g2's tool0 x=0.35 is
    the validated position). Additionally the budget's scan_x=0.60/B=0.60
    alternative was re-checked against the sensor's rendering cone
    (AZ_SPAN_DEG=90 -> +/-45 deg half-span): its 48 deg max bearing falls
    OUTSIDE the cone. Dual constraint identified: bearing <= ~44.5 deg AND
    tool0 x >= 0.35.
  round 2 (this file): scan_x=0.60 (tool0 x=0.35, validated), 15 vantages
    y in [-0.25,+0.25] (B=0.50). Budget model predicts lateral RMSE
    1.14 cm at max bearing 44.6 deg. Fallback ladders were CONSIDERED AND
    REJECTED before running: inner-13 subset predicts 1.51 cm and
    inner-11 predicts 1.97 cm -- both over the 1.5 cm capture window, so
    there is no viable narrower rung; this probe is a single go/no-go.

Geometry under test:
  scan line x = 0.60, vantages y in [-0.25, +0.25], 15 evenly spaced
  points (baseline 0.50 m); target grid x in {1.00, 1.075, 1.15} (r3
  grasp corridor) x y in {-0.15..0.15} (5 points) minus two opposite
  corners = 13 targets. All vantage-target 3D ranges lie in 0.46-0.84 m,
  inside the bar calibration's fitted band (0.40-1.10 m) -- ranging
  validity is not being extrapolated, only BEARING is.

Five-iron-law header:
  1. Paired control: n/a (no detectability claim -- the bar is the D3.0-gated
     object in its gated scene; this probe measures LOCALIZATION accuracy).
  2. Information-ablation: n/a here (no control loop); lives in the 2D-grasp
     formal three arms if this gate passes.
  3. Pre-registered criteria (written BEFORE first run; adjudicated OFFLINE
     from probe_measurements.csv / probe_solutions.csv by the main agent,
     never computed here). Bearing of a measurement = atan2(|ty-sy|, tx-sx).
       g2w_high_bearing_ranging: over measurements with bearing > 33.5 deg,
           RMSE(range_3d_est - range_3d_true) <= 2x the RMSE of the
           <= 33.5 deg measurements in THIS SAME probe (self-normalized;
           tests the error budget's "residuals do not grow with bearing"
           extrapolation assumption).
       g2w_high_bearing_detect: >= 95% of bearing > 33.5 deg measurements
           yield a finite calibrated range inside a 0.3-1.6 m sanity band.
       g2w_lateral_rmse: RMSE(y_hat - y_true) over the target grid
           <= 0.015 m (the capture window -- the whole point of the route).
       g2w_loc_y_valid: Pearson r(y_hat, y_true) >= 0.9 (continuity with
           the original g2 gate).
     Stop-loss (pre-registered in the error budget; NO fallback ladder --
     narrower subsets were shown infeasible before running, see revision
     log): ANY criterion fails -> the 2D-grasp route is terminated as
     designed-infeasible; the thesis future-work wording stands unchanged.
     No parameter search after the fact. IK failures at extreme vantages
     are recorded as data (ik_ok=False) and count against the config's
     feasibility, not silently skipped.
  4. Raw waveforms land per (target, vantage) as .npy.
  5. acoustic_only: target true (x,y) is scene-build input, recorded for
     evaluation only; the least-squares solver consumes ONLY calibrated
     acoustic ranges + AUDITED sensor poses (the robot's own proprioception,
     not target oracle).

CLI:
    --output-dir PATH   Required.
    --smoke             2 targets x 3 vantages (y = -0.30/0/+0.30).

Usage:
    ./app/python.sh scripts/d2v2_trilat_probe_wide.py --output-dir runtime/outputs/v2_d2v2_probe_wide
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

parser = argparse.ArgumentParser(description="D2v2 g2: motion-synthetic multilateration probe")
parser.add_argument("--output-dir", type=str, required=True)
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
BAR_SCALE_M = (0.06, 0.06, 0.12)     # the D3.0-gated object (calibration valid)
BAR_Z_M = TABLE_TOP_Z_M + BAR_SCALE_M[2] / 2.0   # 0.46
HEIGHT_DIFF_M = TOOL_Z_M - BAR_Z_M                # 0.19

SENSOR_X_VANTAGE_M = 0.60
VANTAGE_Y_M = [round(-0.25 + i * 0.5 / 14, 6) for i in range(15)]
# 13 target grid points: 3x5 grid minus two opposite corners (mirrors the
# original g2 grid; x range = r3 grasp corridor 1.00-1.15)
_GRID = [(x, y) for x in (1.00, 1.075, 1.15) for y in (-0.15, -0.075, 0.0, 0.075, 0.15)]
TARGET_GRID = [p for p in _GRID if p not in ((1.00, -0.15), (1.15, 0.15))]

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

if args.smoke:
    TARGET_GRID = TARGET_GRID[:2]
    VANTAGE_Y_M = [-0.25, 0.0, 0.25]


def _load_calibration(path: pathlib.Path) -> dict:
    if not path.exists():
        raise SystemExit(f"ABORT: bar calibration not found: {path} (run D3.0 gates first)")
    cal = json.load(path.open())
    for k in ("slope_smp_per_m", "intercept_smp"):
        if k not in cal or not math.isfinite(float(cal[k])):
            raise SystemExit(f"ABORT: invalid calibration field {k!r}")
    return cal


CAL = _load_calibration(CALIB_JSON_PATH)
SLOPE, INTERCEPT = float(CAL["slope_smp_per_m"]), float(CAL["intercept_smp"])
print(f"calibration: slope={SLOPE:.3f} intercept={INTERCEPT:.3f} ({CAL.get('source','')[:60]}...)")


def _range_from_peak(peak_idx: float) -> float:
    if not math.isfinite(peak_idx):
        return float("nan")
    return (peak_idx - INTERCEPT) / SLOPE


def _trilat_solve(vantages: list[tuple[float, float]], h_ranges: list[float],
                  x0: float, y0: float) -> tuple[float, float, float, int]:
    """Pure-stdlib Gauss-Newton on sum_k (|p - v_k| - h_k)^2. Returns
    (x_hat, y_hat, rms_residual_m, n_used)."""
    pts = [(v, h) for v, h in zip(vantages, h_ranges) if math.isfinite(h) and h > 0.05]
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


def _extract_frame(gmo) -> dict | None:
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None
    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float).copy()
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    if num_spsgw <= 0 or n % num_spsgw != 0:
        return None
    return {"amp_all": amp_all, "num_spsgw": num_spsgw, "n_ways": n // num_spsgw}


class D2V2ProbeWriter(Writer):
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


def _primary_of(frame: dict) -> np.ndarray:
    k = frame["num_spsgw"]
    ways = [frame["amp_all"][w * k:(w + 1) * k] for w in range(frame["n_ways"])]
    if len(ways) >= 2:
        return ways[0] if float(np.max(ways[0])) >= float(np.max(ways[1])) else ways[1]
    return ways[0]


def _measure_point(n_settle: int, n_measure: int) -> dict:
    for _ in range(n_settle):
        simulation_app.update()

    def _block(nf: int) -> np.ndarray:
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


def _select_gripper_variant(stage, arm_path: str):
    prim = stage.GetPrimAtPath(arm_path)
    if prim and prim.IsValid() and prim.GetVariantSets().HasVariantSet("Gripper"):
        prim.GetVariantSets().GetVariantSet("Gripper").SetVariantSelection(GRIPPER_VARIANT)
        print(f"Set Gripper variant={GRIPPER_VARIANT}", flush=True)
        return GRIPPER_VARIANT
    return None


def _sensor_world(stage, sensor_path: str, cache) -> tuple[float, float, float, float]:
    prim = stage.GetPrimAtPath(sensor_path)
    cache.Clear()
    m = cache.GetLocalToWorldTransform(prim)
    pos = m.ExtractTranslation()
    fwd = m.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()
    ang = math.degrees(math.acos(max(-1.0, min(1.0, float(fwd[0])))))
    return float(pos[0]), float(pos[1]), float(pos[2]), ang


def _solve_tool0_xyz(ik, x: float, y: float, z: float, warm_q):
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


def _move_arm(robot, world, q) -> None:
    hold_arm_joint_positions(robot, q, world, render=False, simulation_app=None, arm_only_kinematic=True)


def _move_bar(stage, x: float, y: float) -> None:
    prim = stage.GetPrimAtPath(BAR_PATH)
    xf = UsdGeom.Xformable(prim)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(x, y, BAR_Z_M))
    else:
        xf.AddTranslateOp().Set(Gf.Vec3d(x, y, BAR_Z_M))


# ── Scene (verbatim d3_gates pattern) ─────────────────────────────────────────
print(f"=== d2v2_trilat_probe_wide.py === smoke={args.smoke} targets={len(TARGET_GRID)} vantages={len(VANTAGE_Y_M)}")
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
     positions=np.array([[TARGET_GRID[0][0], TARGET_GRID[0][1], BAR_Z_M]]))

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
rep.WriterRegistry.register(D2V2ProbeWriter)
sensor.attach_writer("D2V2ProbeWriter")

world = World()
robot = world.scene.add(Robot(prim_path=ARM_PATH, name="ur10e"))
world.reset()

ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
TOOL_TARGET_QUAT_WXYZ = np.asarray(
    tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"]), dtype=float)

timeline = omni.timeline.get_timeline_interface()
timeline.play()

seed_q = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
q0, ok0 = _solve_tool0_xyz(ik, SENSOR_X_VANTAGE_M - args.sensor_offset, 0.0, TOOL_Z_M, seed_q)
if not ok0:
    print("ABORT: initial IK failed", flush=True)
    simulation_app.close()
    sys.exit(2)
_move_arm(robot, world, q0)

cache = UsdGeom.XformCache(0)
# sensor corrective transform (verbatim d3_gates pattern, at the y=0 pose)
_mp = stage.GetPrimAtPath(mount_path)
_minv = cache.GetLocalToWorldTransform(_mp).GetInverse()
_lp = _minv.Transform(Gf.Vec3d(float(SENSOR_X_VANTAGE_M), 0.0, float(TOOL_Z_M)))
_lq = _minv.ExtractRotationQuat().GetNormalized()
_sp = stage.GetPrimAtPath(sensor_path)
_sxf = UsdGeom.Xformable(_sp)
_ops = {op.GetOpName(): op for op in _sxf.GetOrderedXformOps()}
(_ops.get("xformOp:translate") or _sxf.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)).Set(Gf.Vec3d(_lp))
try:
    (_ops.get("xformOp:orient") or _sxf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)).Set(Gf.Quatd(_lq))
except Exception:
    _ops["xformOp:orient"].Set(Gf.Quatf(_lq))
sx0, sy0, sz0, sa0 = _sensor_world(stage, sensor_path, cache)
print(f"sensor corrective transform: world=({sx0:.4f},{sy0:.4f},{sz0:.4f}) angle={sa0:.3f}deg")
if abs(sz0 - TOOL_Z_M) > SENSOR_Z_TOL_M or sa0 > SENSOR_ANGLE_TOL_DEG:
    print("ABORT: sensor pose self-check failed", flush=True)
    simulation_app.close()
    sys.exit(2)

print("warmup...")
for i in range(80):
    simulation_app.update()
    if i >= 20 and _buf["latest"] is not None:
        break

out_dir = pathlib.Path(args.output_dir)
wf_dir = out_dir / "waveforms"
wf_dir.mkdir(parents=True, exist_ok=True)

# ── Main loop: per target grid point, sweep vantages, solve ──────────────────
meas_rows: list[dict] = []
sol_rows: list[dict] = []
for t_idx, (tx, ty) in enumerate(TARGET_GRID):
    _move_bar(stage, tx, ty)
    vantages_actual: list[tuple[float, float]] = []
    h_list: list[float] = []
    warm = q0
    for v_idx, vy in enumerate(VANTAGE_Y_M):
        q, ok = _solve_tool0_xyz(ik, SENSOR_X_VANTAGE_M - args.sensor_offset, vy, TOOL_Z_M, warm)
        if not ok:
            meas_rows.append({"target_index": t_idx, "vantage_index": v_idx, "ik_ok": False})
            print(f"  [t{t_idx} v{v_idx}] IK_FAILED (vy={vy})")
            continue
        _move_arm(robot, world, q)
        warm = q
        svx, svy, svz, sang = _sensor_world(stage, sensor_path, cache)
        res = _measure_point(N_SETTLE, N_MEASURE)
        tag = f"t{t_idx:02d}_v{v_idx}"
        np.save(wf_dir / f"{tag}.npy", res["mean_primary"])
        r3d = _range_from_peak(res["peak_sample_idx"])
        dz = svz - BAR_Z_M
        h = math.sqrt(max(r3d * r3d - dz * dz, 1e-9)) if math.isfinite(r3d) else float("nan")
        vantages_actual.append((svx, svy))
        h_list.append(h)
        meas_rows.append({
            "target_index": t_idx, "vantage_index": v_idx, "ik_ok": True,
            "target_x_true": tx, "target_y_true": ty,
            "sensor_x": svx, "sensor_y": svy, "sensor_z": svz, "sensor_angle_deg": sang,
            "peak_sample_idx": res["peak_sample_idx"], "point_drift": res["point_drift"],
            "stationarity_ok": res["stationarity_ok"],
            "range_3d_est_m": r3d, "range_horiz_est_m": h, "waveform_tag": tag,
        })
    x0 = SENSOR_X_VANTAGE_M + (sum(h_list) / len(h_list) if h_list else 0.5)
    xh, yh, rms, n_used = _trilat_solve(vantages_actual, h_list, x0, 0.0)
    sol_rows.append({"target_index": t_idx, "target_x_true": tx, "target_y_true": ty,
                     "x_hat": xh, "y_hat": yh, "rms_residual_m": rms, "n_vantages_used": n_used,
                     "err_x": xh - tx if math.isfinite(xh) else float("nan"),
                     "err_y": yh - ty if math.isfinite(yh) else float("nan")})
    print(f"[t{t_idx+1:02d}/{len(TARGET_GRID)}] true=({tx:.3f},{ty:+.3f})  "
          f"hat=({xh:.3f},{yh:+.3f})  err=({xh-tx:+.4f},{yh-ty:+.4f})  "
          f"rms={rms:.4f} n={n_used}")

with (out_dir / "probe_measurements.csv").open("w", newline="") as f:
    fields = sorted({k for r in meas_rows for k in r}, key=lambda k: (k != "target_index", k))
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(meas_rows)
with (out_dir / "probe_solutions.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(sol_rows[0].keys()))
    w.writeheader()
    w.writerows(sol_rows)

meta = {"smoke": args.smoke, "target_grid": TARGET_GRID, "vantage_y_m": VANTAGE_Y_M,
        "sensor_x_vantage_m": SENSOR_X_VANTAGE_M, "bar_scale_m": list(BAR_SCALE_M),
        "bar_z_m": BAR_Z_M, "calibration": CAL, "gripper_variant": gripper_variant,
        "criteria_text": {
            "g2w_high_bearing_ranging": "RMSE(range err | bearing>33.5deg) <= 2x RMSE(<=33.5deg), same probe (offline)",
            "g2w_high_bearing_detect": ">=95% of bearing>33.5deg measurements finite in 0.3-1.6 m (offline)",
            "g2w_lateral_rmse": "RMSE(y_hat - y_true) <= 0.015 m over target grid (offline)",
            "g2w_loc_y_valid": "Pearson r(y_hat, y_true) >= 0.9 (offline)"},
        "timestamp": datetime.datetime.now().isoformat(), "script": "d2v2_trilat_probe_wide.py"}
with (out_dir / "meta.json").open("w") as f:
    json.dump(meta, f, indent=1)

timeline.stop()
print(f"-> outputs under {out_dir}")
simulation_app.close()
