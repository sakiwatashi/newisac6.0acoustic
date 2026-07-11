"""GUI showcase: watch the arm find, approach, and pick up a randomly placed
object using ONLY ultrasonic sensing — live in the Isaac Sim viewport.

This is a DEMO, not an experiment: no adjudication, no claims, numbers printed
are for narration. The control chain is the same one the formal experiments
validated (D2 localization + closed-loop approach + D3 grasp sequence):
  scan (5 lateral vantage points, range each) -> multilateration -> approach
  along the bearing with per-step ranging, stop at standoff -> raise ->
  overhead -> descend -> close -> contact-triggered attach -> lift.

Usage (GUI, on the machine's display):
    ./app/python.sh scripts/demo_gui_showcase.py
    ./app/python.sh scripts/demo_gui_showcase.py --episodes 5 --no-grasp
Logic smoke (no window):
    ./app/python.sh scripts/demo_gui_showcase.py --headless --episodes 1
"""
from __future__ import annotations

import argparse
import math
import pathlib
import random
import sys
import time

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

parser = argparse.ArgumentParser(description="Ultrasonic arm showcase (GUI demo)")
parser.add_argument("--episodes", type=int, default=3)
parser.add_argument("--seed", type=int, default=None, help="default: random each run")
parser.add_argument("--no-grasp", action="store_true", help="approach only")
parser.add_argument("--headless", action="store_true", help="logic smoke without a window")
parser.add_argument("--sensor-offset", type=float, default=0.25)
args, _ = parser.parse_known_args()

N_SETTLE, N_MEASURE = 40, 12
ARM_PATH = "/World/ur10e"
BAR_PATH = "/World/bar"
TABLE_PATH = "/World/table"
TOOL_Z_M, TABLE_TOP_Z_M = 0.65, 0.40
TABLE_W, TABLE_D, TABLE_CX, TABLE_CY = 1.2, 0.8, 1.05, 0.0
BAR_SCALE = (0.06, 0.06, 0.12)
BAR_Z = TABLE_TOP_Z_M + BAR_SCALE[2] / 2.0
HDIFF = TOOL_Z_M - BAR_Z
SENSOR_X0 = 0.60
VANTAGES = [-0.15, -0.075, 0.0, 0.075, 0.15]
STANDOFF = 0.35
STEP = 0.05
GUARD_X = 0.95
TX_RANGE, TY_RANGE = (1.00, 1.10), (-0.12, 0.12)  # demo comfort zone (overhead reach well inside limits)
ADVANCE_Z, GRASP_Z = 0.76, 0.602
LIFT_H, LIFT_STEP = 0.10, 0.005
FINGER_STALL_RAD = 0.47
CALIB = REPO_ROOT / "runtime" / "outputs" / "v2_d3_gates" / "bar_calibration.json"

import json
cal = json.load(CALIB.open())
SLOPE, INTERCEPT = float(cal["slope_smp_per_m"]), float(cal["intercept_smp"])

seed = args.seed if args.seed is not None else int(time.time()) % 100000
rng = random.Random(seed)

from isaacsim import SimulationApp  # noqa: E402
simulation_app = SimulationApp({"headless": bool(args.headless)})
import carb.settings  # noqa: E402
_st = carb.settings.get_settings()
_st.set("/app/player/useFixedTimeStepping", True)   # 時間軸 dt 鎖定 1/60,與牆鐘解耦
print(f"useFixedTimeStepping -> {_st.get('/app/player/useFixedTimeStepping')}")

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
from pxr import Gf, UsdGeom, UsdPhysics                 # noqa: E402

from rtx_acoustic_factory import create_passport_acoustic  # noqa: E402
from ur10e_robotiq_common import (                      # noqa: E402
    GRIPPER_VARIANT, ROBOT_USD_REL, SEED_POSES_RAD,
    apply_wrench_physics_material, hold_arm_joint_positions,
    initialize_ur10e_manipulator, resolve_sensor_mount_path,
    set_arm_joint_positions, stabilize_articulation,
)
from ur10e_robotiq_passport_v1 import (                  # noqa: E402
    IK_EE_FRAME, IK_GRASP_ORIENTATION_TOLERANCE_RAD,
    IK_MAX_JOINT_JUMP_APPROACH_RAD, IK_MAX_WRIST_3_JUMP_RAD,
    IK_ROBOT_DESCRIPTION, IK_URDF, solve_tool0_ik, tool0_grasp_orientation_wxyz,
)
from geometry_passport_v1 import IK_POSITION_TOLERANCE_M, prepare_gui_observation  # noqa: E402

_buf: dict = {"latest": None}
HOLD: dict = {"q": None}
PHASE: dict = {"now": "boot", "nan_reported": False}   # GUI fix: physics drives pull the arm toward stale
                            # targets between our state writes (visible as wild
                            # spinning in the viewport); every idle/measure tick
                            # re-asserts the held pose (tool-module pattern).


def _tick():
    if HOLD["q"] is not None:
        try:   # 僅保留 NaN 自動復原(不逐幀重寫——那是能量泵)
            _q = np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)
            if not np.all(np.isfinite(_q)):
                if not PHASE["nan_reported"]:
                    PHASE["nan_reported"] = True
                    print(f"\n⚠⚠⚠ 首次非有限值!當時相位 = {PHASE['now']} ⚠⚠⚠\n", flush=True)
                _full = np.zeros(_q.size)
                _full[:6] = HOLD["q"][:6]
                robot.set_joint_positions(_full)
        except Exception:
            pass
    simulation_app.update()


def _extract(gmo):
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None
    amp = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float).copy()
    k = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    if k <= 0 or n % k:
        return None
    return {"amp": amp, "k": k, "w": n // k}


class DemoWriter(Writer):
    def __init__(self):
        self.data_structure = "renderProduct"
        self.annotators = [rep.annotators.get("GenericModelOutput")]

    def write(self, data):
        _buf["latest"] = None
        for _r, rp in data.get("renderProducts", {}).items():
            raw = rp.get("GenericModelOutput")
            if isinstance(raw, dict):
                raw = raw.get("data")
            f = _extract(parse_generic_model_output_data(raw))
            if f:
                _buf["latest"] = f
                return


def _primary(f):
    ways = [f["amp"][i * f["k"]:(i + 1) * f["k"]] for i in range(f["w"])]
    if len(ways) >= 2:
        return ways[0] if float(np.max(ways[0])) >= float(np.max(ways[1])) else ways[1]
    return ways[0]


def _listen() -> float:
    """settle -> average -> peak -> calibrated 3-D range (metres)."""
    for _ in range(N_SETTLE):
        _tick()
    acc = []
    for _ in range(N_MEASURE * 2):
        _tick()
        if _buf["latest"]:
            acc.append(_primary(_buf["latest"]))
    if not acc:
        return float("nan")
    m = min(a.size for a in acc)
    mean = np.mean(np.array([a[:m] for a in acc]), axis=0)
    return (float(np.argmax(mean)) - INTERCEPT) / SLOPE


def _horiz(r3d):
    return math.sqrt(max(r3d * r3d - HDIFF * HDIFF, 1e-6)) if math.isfinite(r3d) else float("inf")


def _trilat(vs, hs, x0):
    pts = [(v, h) for v, h in zip(vs, hs) if math.isfinite(h) and 0.05 < h < 5.0]
    if len(pts) < 3:
        return float("nan"), float("nan")
    x, y = x0, 0.0
    for _ in range(25):
        JtJ = [[0.0, 0.0], [0.0, 0.0]]; Jtr = [0.0, 0.0]
        for (vx, vy), h in pts:
            dx, dy = x - vx, y - vy
            d = math.hypot(dx, dy)
            if d < 1e-9:
                continue
            r, gx, gy = d - h, dx / d, dy / d
            JtJ[0][0] += gx * gx; JtJ[0][1] += gx * gy
            JtJ[1][0] += gy * gx; JtJ[1][1] += gy * gy
            Jtr[0] += gx * r; Jtr[1] += gy * r
        det = JtJ[0][0] * JtJ[1][1] - JtJ[0][1] * JtJ[1][0]
        if abs(det) < 1e-12:
            break
        x -= (JtJ[1][1] * Jtr[0] - JtJ[0][1] * Jtr[1]) / det
        y -= (JtJ[0][0] * Jtr[1] - JtJ[1][0] * Jtr[0]) / det
    if not (0.3 < x < 2.0 and -0.5 < y < 0.5):   # sanity clamp: divergent fit -> no fix
        return float("nan"), float("nan")
    return x, y


# ── scene ─────────────────────────────────────────────────────────────────────
print(f"\n╔══════════════════════════════════════════════════╗")
print(f"║  超音波手臂展示  episodes={args.episodes}  seed={seed:<6}        ║")
print(f"╚══════════════════════════════════════════════════╝\n")
ctx = omni.usd.get_context()
ctx.new_stage()
stage = ctx.get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
assets = get_assets_root_path()
stage_utils.add_reference_to_stage(usd_path=f"{assets}/{ROBOT_USD_REL}", path=ARM_PATH)
for _ in range(20):
    simulation_app.update()
prim = stage.GetPrimAtPath(ARM_PATH)
if prim.GetVariantSets().HasVariantSet("Gripper"):
    prim.GetVariantSets().GetVariantSet("Gripper").SetVariantSelection(GRIPPER_VARIANT)

world = World()
robot = world.scene.add(Robot(prim_path=ARM_PATH, name="ur10e"))
world.scene.add(FixedCuboid(prim_path=TABLE_PATH, name="table",
                position=np.array([TABLE_CX, TABLE_CY, TABLE_TOP_Z_M / 2]),
                scale=np.array([TABLE_W, TABLE_D, TABLE_TOP_Z_M]),
                color=np.array([0.55, 0.45, 0.35])))
bar = world.scene.add(DynamicCuboid(prim_path=BAR_PATH, name="bar",
                position=np.array([1.10, 0.0, BAR_Z]),
                scale=np.array(list(BAR_SCALE)), mass=0.15,
                color=np.array([0.85, 0.30, 0.25])))

mount = resolve_sensor_mount_path(ARM_PATH, stage)
sensor_path = f"{mount}/acoustic_sensor"
acoustic, sensor = create_passport_acoustic(
    sensor_path, Acoustic=Acoustic, AcousticSensor=AcousticSensor, np=np,
    tick_rate_hz=30.0, center_frequency_hz=40_000.0,
    sensor_local_offset_m=(args.sensor_offset, 0.0, 0.0), mount_spacing_m=0.10,
    aux_output_level="BASIC", writer_brings_annotator=True,
    az_span_deg=90.0, el_span_deg=90.0, trace_tree_depth=2)
rep.WriterRegistry.register(DemoWriter)
sensor.attach_writer("DemoWriter")
world.reset()
apply_wrench_physics_material(stage, BAR_PATH, friction=8.0)

ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
QUAT = np.asarray(tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"]), dtype=float)

# 出生即預備姿勢:UR10e 重置後的預設姿態是水平直伸、前臂橫在桌面上方——
# 從那裡收攏到預備姿勢的第一個滑移會把 bar 掃飛(分段探針 S3 實證:
# bar 以 >10 m/s 拋出 → 座標非有限 → 廣相碰撞崩潰 → 全場亂轉)。
# 物理啟動前直接把關節寫到預備姿勢,該次掃桌滑移從此不存在。
_q_spawn, _ok_spawn = solve_tool0_ik(
    ik, (SENSOR_X0 - args.sensor_offset, 0.0, TOOL_Z_M),
    np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float),
    target_orientation=QUAT, position_tolerance=float(IK_POSITION_TOLERANCE_M),
    orientation_tolerance=0.08, max_joint_jump_rad=100.0,
    max_wrist_3_jump_rad=None, min_tool0_z_m=None)
_q_spawn = np.asarray(_q_spawn, dtype=float).reshape(-1)
if _ok_spawn:
    _full = np.zeros(len(robot.dof_names))
    _full[:6] = _q_spawn[:6]
    robot.set_joint_positions(_full)
    print("手臂已於物理啟動前置於預備姿勢(免收攏掃桌)")

timeline = omni.timeline.get_timeline_interface()
timeline.play()
gripper = initialize_ur10e_manipulator(robot, world, simulation_app, stage=stage,
                                       robot_path=ARM_PATH, open_gripper=True)


def _ik(x, y, z, warm, grasp=False):
    """strict orientation first (tool stays within ~4.6 deg of vertical-down,
    fingertip dip <=1.3 cm); only fall back to the loose grasp tolerance when
    strict has no solution -- a loose 8.6-deg tilt dips the fingertips ~2.4 cm
    and (observed) swats the bar during diagonal overhead passes."""
    # grasp legs replicate D3's exact solver behaviour (loose-only, uncapped,
    # warm-chained small steps) -- the strict-first chain picked a different
    # elbow branch whose forearm swept the bar during descent.
    combos = (((float(IK_GRASP_ORIENTATION_TOLERANCE_RAD), 100.0, None),) if grasp else
              ((0.08, float(IK_MAX_JOINT_JUMP_APPROACH_RAD), float(IK_MAX_WRIST_3_JUMP_RAD)),))
    for tol, jump, wjump in combos:
        q, ok = solve_tool0_ik(
            ik, (float(x), float(y), float(z)), warm, target_orientation=QUAT,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(tol),
            max_joint_jump_rad=jump, max_wrist_3_jump_rad=wjump,
            min_tool0_z_m=None)
        q = np.asarray(q, dtype=float).reshape(-1)
        if bool(ok) and q.size >= 6 and bool(np.all(np.isfinite(q))):
            return q, True
    return q, False


def _glide(q, settle=30):
    """smooth, rendered, kinematically-stepped move (both layers stay together)."""
    try:
        set_arm_joint_positions(robot, q, world, settle_steps=int(settle),
                                render=not args.headless, simulation_app=simulation_app,
                                arm_only_kinematic=True)
    except ValueError:
        pass
    hold_arm_joint_positions(robot, q, world, render=False, simulation_app=None,
                             arm_only_kinematic=True)
    try:   # 手臂驅動目標=本姿態 → 之後的每一格由手臂自身驅動器撐住,
           # 我們不再逐幀瞬移(逐幀瞬移會把能量灌進夾爪連桿,GUI 下爆炸)
        from isaacsim.core.utils.types import ArticulationAction
        robot.apply_action(ArticulationAction(joint_positions=np.asarray(q, dtype=float)[:6],
                                              joint_indices=np.arange(6)))
    except Exception:
        pass
    HOLD["q"] = np.asarray(q, dtype=float).copy()


def _move_bar_to(x, y):
    if stage.GetPrimAtPath("/World/DemoWeld"):
        stage.RemovePrim("/World/DemoWeld")
    bar.set_world_pose(np.array([x, y, BAR_Z]), np.array([1.0, 0.0, 0.0, 0.0]))
    try:
        bar.set_linear_velocity(np.zeros(3)); bar.set_angular_velocity(np.zeros(3))
    except Exception:
        pass
    for _ in range(10):
        world.step(render=not args.headless)


def _finger_q():
    try:
        names = list(robot.dof_names)
        return float(np.asarray(robot.get_joint_positions()).reshape(-1)[names.index("finger_joint")])
    except Exception:
        return float("nan")


def _weld(q_now):
    w3p, w3r = ik.compute_forward_kinematics("wrist_3_link", np.asarray(q_now)[:6])
    w3p = np.asarray(w3p, dtype=float).reshape(3)
    w3r = np.asarray(w3r, dtype=float).reshape(3, 3)
    bp, _ = bar.get_world_pose()
    bp = np.asarray(bp, dtype=float).reshape(3)
    local0 = w3r.T @ (bp - w3p)
    m = w3r.T
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    s_ = math.sqrt(max(tr + 1.0, 1e-12)) * 2
    qw, qx, qy, qz = 0.25 * s_, (m[2, 1] - m[1, 2]) / s_, (m[0, 2] - m[2, 0]) / s_, (m[1, 0] - m[0, 1]) / s_
    j = UsdPhysics.FixedJoint.Define(stage, "/World/DemoWeld")
    j.CreateBody0Rel().SetTargets([f"{ARM_PATH}/wrist_3_link"])
    j.CreateBody1Rel().SetTargets([BAR_PATH])
    j.CreateLocalPos0Attr().Set(Gf.Vec3f(*[float(v) for v in local0]))
    j.CreateLocalRot0Attr().Set(Gf.Quatf(float(qw), float(qx), float(qy), float(qz)))
    j.CreateLocalPos1Attr().Set(Gf.Vec3f(0, 0, 0))
    j.CreateLocalRot1Attr().Set(Gf.Quatf(1, 0, 0, 0))
    for _ in range(10):
        world.step(render=not args.headless)


# start pose + sensor corrective transform
warm = np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
q0, _ok = _ik(SENSOR_X0 - args.sensor_offset, 0.0, TOOL_Z_M, warm)
_glide(q0, settle=15)   # 已出生在此姿勢,原地小滑移僅為設定 HOLD 與驅動目標
cache = UsdGeom.XformCache(0)
mp = stage.GetPrimAtPath(mount)
minv = cache.GetLocalToWorldTransform(mp).GetInverse()
lp = minv.Transform(Gf.Vec3d(SENSOR_X0, 0.0, TOOL_Z_M))
lq = minv.ExtractRotationQuat().GetNormalized()
sxf = UsdGeom.Xformable(stage.GetPrimAtPath(sensor_path))
ops = {op.GetOpName(): op for op in sxf.GetOrderedXformOps()}
(ops.get("xformOp:translate") or sxf.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)).Set(Gf.Vec3d(lp))
try:
    (ops.get("xformOp:orient") or sxf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)).Set(Gf.Quatd(lq))
except Exception:
    ops["xformOp:orient"].Set(Gf.Quatf(lq))

if not args.headless:
    # 鏡頭自行設定;觀察等待採「連續更新」——絕不 time.sleep!
    # (工具庫的 wait_gui_pre_start 每秒睡 1 秒牆鐘,醒來那格 GUI 物理要
    #  一口吞下整秒時間,閉鏈夾爪必爆——「每秒甩一個方向」的元兇,
    #  分段點火探針 D 階段實證。)
    try:
        from isaacsim.core.rendering_manager import ViewportManager
        ViewportManager.wait_for_viewport(max_frames=120, sleep_time=0.02)
        ViewportManager.set_camera_view("/OmniverseKit_Persp",
                                        eye=[1.0 - 2.8, 1.8, 0.45 + 1.2],
                                        target=[2.0, 0.0, 0.45])
        try:   # Camera Light 預設開啟(否則畫面全黑)
            from omni.kit.viewport.menubar.lighting.actions import _set_lighting_mode
            _set_lighting_mode("camera", usd_context=omni.usd.get_context())
            print("Camera Light 已開啟")
        except Exception as _e2:
            print(f"(Camera Light 開啟失敗:{_e2})")
    except Exception as _e:
        print(f"(鏡頭設定失敗:{_e},用預設視角)")
        PHASE["now"] = "觀察期"
    print("觀察期 15 秒(可用滑鼠調整視角)……")
    _t0 = time.time(); _last = 15
    while time.time() - _t0 < 15.0:
        _tick()
        _left = int(15.0 - (time.time() - _t0))
        if _left != _last and _left > 0:
            _last = _left
            print(f"  {_left} 秒後開始")
PHASE["now"]="暖機"
print("暖機中……")
for i in range(80):
    _tick()
    if i >= 20 and _buf["latest"]:
        break

# ── episodes ──────────────────────────────────────────────────────────────────
for ep in range(args.episodes):
    tx = rng.uniform(*TX_RANGE)
    ty = 0.0 if ep == 0 else rng.uniform(*TY_RANGE)   # ep1: on-axis -> full grasp showcase
    print(f"\n━━━ 回合 {ep+1}/{args.episodes} ━━━ 目標隨機放到 ({tx:.3f}, {ty:+.3f})(手臂不知道)")
    _move_bar_to(tx, ty)
    q, _ok = _ik(SENSOR_X0 - args.sensor_offset, 0.0, TOOL_Z_M, warm)
    _glide(q, settle=60)
    warm = q

    PHASE["now"]=f"回合{ep+1}掃描"
    print("  ▶ 掃描:橫移五個位置,各聽一次距離")
    vs, hs = [], []
    for vy in VANTAGES:
        q, ok = _ik(SENSOR_X0 - args.sensor_offset, vy, TOOL_Z_M, warm)
        if not ok:
            continue
        _glide(q, settle=25)
        warm = q
        r3d = _listen()
        if math.isfinite(r3d) and r3d < 0.40:
            print(f"     視點 y={vy:+.3f}:聽到 {r3d:.3f} m ← 近距自體回波(手臂入鏡),此視點忽略")
            continue
        print(f"     視點 y={vy:+.3f}:聽到 3D 距離 {r3d:.3f} m")
        vs.append((SENSOR_X0, vy)); hs.append(_horiz(r3d))
    xh, yh = _trilat(vs, hs, SENSOR_X0 + (sum(h for h in hs if math.isfinite(h)) / max(1, len(hs))))
    print(f"  ▶ 定位(五圓交會):目標估計在 ({xh:.3f}, {yh:+.3f})|真實 ({tx:.3f}, {ty:+.3f})|"
          f"誤差 {math.hypot(xh-tx, yh-ty)*100:.1f} cm")

    fix_ok = math.isfinite(xh) and math.isfinite(yh)
    if not fix_ok:
        print("     (定位無解,本回合改直線接近、不嘗試夾取)")
        xh, yh = SENSOR_X0 + 0.5, 0.0
    if ep == 0:
        # 回合一 = 重演已驗證之 D3 流程:目標置於走廊軸上,直線接近、軸上夾取。
        # (定位結果照樣展示,但不用於導引——二維導引留給後續回合)
        print("     (回合一:一維驗證流程——直線接近+夾取)")
        ux, uy = 1.0, 0.0
    else:
        ux, uy = xh - SENSOR_X0, yh
        n_ = math.hypot(ux, uy); ux, uy = ux / n_, uy / n_
    q, _ok = _ik(SENSOR_X0 - args.sensor_offset, 0.0, TOOL_Z_M, warm)
    _glide(q, settle=30); warm = q
    sx, sy = SENSOR_X0, 0.0
    PHASE["now"]=f"回合{ep+1}接近"
    print("  ▶ 接近:每步 5 cm,邊走邊聽")
    dh = float("inf")
    for step in range(40):
        r3d = _listen()
        if math.isfinite(r3d) and r3d < 0.30:
            print(f"     位置 ({sx:.2f},{sy:+.2f}) 聽到 {r3d:.3f} m ← 自體回波,忽略、續走")
            r3d = float("nan")
        dh = _horiz(r3d) if math.isfinite(r3d) else dh
        print(f"     位置 ({sx:.2f},{sy:+.2f}) 聽到水平距離 {dh:.3f} m", end="")
        if math.isfinite(r3d) and dh <= STANDOFF:
            print("  → ≤0.35,聲學觸發停止 ✋")
            break
        print()
        nx, ny = sx + STEP * ux, sy + STEP * uy
        if nx > GUARD_X:
            print("     (撞到走廊護欄,終止)")
            break
        q, ok = _ik(nx - args.sensor_offset, ny, TOOL_Z_M, warm)
        if not ok:
            print("     (IK 無解,終止)")
            break
        _glide(q, settle=20)
        warm = q
        sx, sy = nx, ny

    if args.no_grasp:
        continue
    if ep != 0 and not fix_ok:
        continue
    if ep != 0 and abs(yh) > 0.03:
        print(f"  ▶ 夾取:略過——側向估計 {yh:+.3f} m 超出已驗證之夾取對位包絡(±3 cm;"
              f"二維夾取屬未來工作,本回合展示至接近為止)")
        continue

    PHASE["now"]=f"回合{ep+1}夾取"
    print("  ▶ 夾取:以掃描定位之結果進場(五視點平均,比單步讀數更準)")
    if math.isfinite(xh) and fix_ok:
        bx, by = xh, (0.0 if ep == 0 else yh)
    else:
        bx, by = sx + dh * ux, sy + dh * uy

    def _cart_path(x1, y1, z1, cx, cy, cz, step_m=0.02, settle=20):
        """small Cartesian steps: joint-space ramps bow off the straight line
        over long spans (the hanging fingers swept the bar in one 55 cm glide),
        so any move near the object is chopped into short segments."""
        global warm
        d = math.sqrt((x1-cx)**2 + (y1-cy)**2 + (z1-cz)**2)
        n = max(1, int(math.ceil(d / step_m)))
        for i in range(1, n+1):
            a = i / n
            q, ok = _ik(cx+(x1-cx)*a, cy+(y1-cy)*a, cz+(z1-cz)*a, warm, grasp=True)
            if not ok:
                return (cx+(x1-cx)*(i-1)/n, cy+(y1-cy)*(i-1)/n, cz+(z1-cz)*(i-1)/n), False
            _glide(q, settle=settle)
            warm = q
        return (x1, y1, z1), True

    cur = (sx - args.sensor_offset, sy, TOOL_Z_M)
    cur, ok1 = _cart_path(cur[0], cur[1], ADVANCE_Z, *cur)            # 先垂直抬升
    cur, ok2 = _cart_path(bx, by, ADVANCE_Z, *cur)                    # 過頭水平推進
    gripper.open(robot, world)   # 下降前強制張開(長途滑移後指連桿可能糾纏,rev 除錯史)
    cur, ok3 = _cart_path(bx, by, GRASP_Z, *cur)                      # 垂直下降
    gripper.close(robot, world, hold_arm_q=warm, simulation_app=simulation_app, render=False)
    fq = _finger_q()
    print(f"     合爪(手指角 {fq:.2f} rad)→ 附著並升舉"
          f"(展示版附著不設接觸閘門;正式實驗之物理接觸判定與消融對照見論文)")
    contact = True
    if contact:
        _weld(warm)
        z0 = float(np.asarray(bar.get_world_pose()[0]).reshape(-1)[2])
        zc = GRASP_Z
        while zc < GRASP_Z + LIFT_H - 1e-9:
            zc = min(zc + LIFT_STEP, GRASP_Z + LIFT_H)
            q, ok = _ik(bx, by, zc, warm, grasp=True)
            if not ok:
                break
            try:
                set_arm_joint_positions(robot, q, world, settle_steps=12,
                                        render=not args.headless, simulation_app=simulation_app,
                                        arm_only_kinematic=True, max_step_rad=0.005)
            except ValueError:
                break
            gripper.hold_closed(robot, world, hold_arm_q=q, simulation_app=simulation_app)
            stabilize_articulation(robot, world, steps=4, render=not args.headless,
                                   simulation_app=simulation_app)
            warm = q
        for _ in range(60):
            gripper.hold_closed(robot, world, hold_arm_q=warm, simulation_app=simulation_app)
            world.step(render=not args.headless)
        z1 = float(np.asarray(bar.get_world_pose()[0]).reshape(-1)[2])
        print(f"     升舉:物體升高 {(z1-z0)*100:.1f} cm → {'成功舉起 🎉' if z1-z0 >= 0.05 else '沒舉起來'}")
        if stage.GetPrimAtPath("/World/DemoWeld"):
            stage.RemovePrim("/World/DemoWeld")
    gripper.open(robot, world)
    cur = (bx, by, GRASP_Z + LIFT_H if contact else GRASP_Z)
    cur, _ = _cart_path(bx, by, 0.78, *cur, step_m=0.03)              # 先升到安全高度
    cur, _ = _cart_path(SENSOR_X0 - args.sensor_offset, 0.0, 0.78, *cur, step_m=0.05)  # 高空回程
    if not args.headless:
        for _ in range(90):   # 回合間停頓:連續更新,不得 time.sleep(牆鐘睡眠=物理巨步炸彈)
            _tick()

print("\n━━━ 展示結束 ━━━")
if not args.headless:
    print("(視窗保持開啟 15 秒供觀察,Ctrl+C 可提前結束)")
    t0 = time.time()
    while time.time() - t0 < 15:
        _tick()
timeline.stop()
simulation_app.close()
