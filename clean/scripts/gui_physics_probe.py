"""GUI physics probe: load the UR10e (with or without the Robotiq gripper),
apply ZERO writes of any kind, and log joint states once per second.

Purpose: locate the energy source of the GUI wild-spinning. If joints diverge
with no writer at all, the instability is intrinsic (gripper closed-chain vs
GUI stepping); comparing --bare isolates the gripper's contribution.

    ./app/python.sh scripts/gui_physics_probe.py            # with gripper
    ./app/python.sh scripts/gui_physics_probe.py --bare     # bare arm
    ./app/python.sh scripts/gui_physics_probe.py --headless # cadence control
"""
from __future__ import annotations
import argparse, sys, pathlib
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

p = argparse.ArgumentParser()
p.add_argument("--bare", action="store_true")
p.add_argument("--headless", action="store_true")
p.add_argument("--seconds", type=int, default=25)
args, _ = p.parse_known_args()

from isaacsim import SimulationApp
app = SimulationApp({"headless": bool(args.headless)})

import numpy as np
import omni.usd, omni.timeline
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.api import World
from isaacsim.core.api.robots import Robot
from isaacsim.storage.native import get_assets_root_path
from pxr import UsdGeom
from ur10e_robotiq_common import GRIPPER_VARIANT, ROBOT_USD_REL

ARM = "/World/ur10e"
ctx = omni.usd.get_context(); ctx.new_stage(); stage = ctx.get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
stage_utils.add_reference_to_stage(usd_path=f"{get_assets_root_path()}/{ROBOT_USD_REL}", path=ARM)
for _ in range(20):
    app.update()
prim = stage.GetPrimAtPath(ARM)
if prim.GetVariantSets().HasVariantSet("Gripper"):
    sel = "None" if args.bare else GRIPPER_VARIANT
    names = list(prim.GetVariantSets().GetVariantSet("Gripper").GetVariantNames())
    if args.bare:
        sel = next((c for c in ("None","none","No_Gripper","Bare") if c in names), names[0])
    prim.GetVariantSets().GetVariantSet("Gripper").SetVariantSelection(sel)
    print(f"Gripper variant = {sel!r}")

world = World()
robot = world.scene.add(Robot(prim_path=ARM, name="ur10e"))
world.reset()
omni.timeline.get_timeline_interface().play()


p2 = argparse.ArgumentParser()  # staged ignition flags parsed from leftovers
import numpy as _np
from ur10e_robotiq_common import (initialize_ur10e_manipulator, SEED_POSES_RAD,
                                  hold_arm_joint_positions, set_arm_joint_positions)
from ur10e_robotiq_passport_v1 import (IK_EE_FRAME, IK_ROBOT_DESCRIPTION, IK_URDF,
                                        solve_tool0_ik, tool0_grasp_orientation_wxyz,
                                        IK_MAX_JOINT_JUMP_APPROACH_RAD, IK_MAX_WRIST_3_JUMP_RAD)
from geometry_passport_v1 import IK_POSITION_TOLERANCE_M
from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver


def observe(tag, secs=8):
    print(f"\n════ 階段:{tag} ════(觀察 {secs} 秒)")
    prev = None
    t0 = time.time(); fr = 0
    while time.time() - t0 < secs:
        app.update(); fr += 1
        if fr % 30 == 0:
            q = _np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)
            fin = bool(_np.all(_np.isfinite(q)))
            dq = float(_np.max(_np.abs(q[:6]-prev[:6]))) if prev is not None and fin else float("nan")
            print(f"  t={time.time()-t0:4.1f} finite={fin} max|dq|={dq:.4f} fingers={_np.round(q[6:],2)}")
            prev = q if fin else prev


import time
observe("靜置(基線)", 6)

grip = initialize_ur10e_manipulator(robot, world, app, stage=stage, robot_path=ARM, open_gripper=False)
observe("A1: manipulator.initialize(未開爪)", 8)

grip.open(robot, world)
observe("A2: 開爪之後", 8)

ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
QUAT = _np.asarray(tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"]), dtype=float)
q0, ok = solve_tool0_ik(ik, (0.35, 0.0, 0.65), _np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float),
                        target_orientation=QUAT, position_tolerance=float(IK_POSITION_TOLERANCE_M),
                        orientation_tolerance=0.08,
                        max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_APPROACH_RAD),
                        max_wrist_3_jump_rad=float(IK_MAX_WRIST_3_JUMP_RAD), min_tool0_z_m=None)
q0 = _np.asarray(q0, dtype=float).reshape(-1)
print("IK ok:", ok)

set_arm_joint_positions(robot, q0, world, settle_steps=60, render=not args.headless,
                        simulation_app=app, arm_only_kinematic=True)
hold_arm_joint_positions(robot, q0, world, render=False, simulation_app=None, arm_only_kinematic=True)
observe("B1: 滑移到預備姿勢(僅狀態寫,無驅動目標)", 8)

from isaacsim.core.utils.types import ArticulationAction
robot.apply_action(ArticulationAction(joint_positions=q0[:6], joint_indices=_np.arange(6)))
observe("B2: 設定手臂驅動目標(apply_action)之後", 8)


# C1: 桌 + 物理 bar + 摩擦材質
from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid
from ur10e_robotiq_common import apply_wrench_physics_material
world.scene.add(FixedCuboid(prim_path="/World/table", name="table",
    position=_np.array([1.05,0.0,0.20]), scale=_np.array([1.2,0.8,0.40]),
    color=_np.array([0.55,0.45,0.35])))
bar = world.scene.add(DynamicCuboid(prim_path="/World/bar", name="bar",
    position=_np.array([1.10,0.0,0.46]), scale=_np.array([0.06,0.06,0.12]),
    mass=0.15, color=_np.array([0.85,0.30,0.25])))
apply_wrench_physics_material(stage, "/World/bar", friction=8.0)
observe("C1: 加桌+物理bar+材質", 8)

# C2: 聲學感測器 + 寫入器
import omni.replicator.core as rep
from omni.replicator.core import Writer
from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor, parse_generic_model_output_data
from rtx_acoustic_factory import create_passport_acoustic
from ur10e_robotiq_common import resolve_sensor_mount_path
mount = resolve_sensor_mount_path(ARM, stage)
class ProbeWriter(Writer):
    def __init__(self):
        self.data_structure = "renderProduct"
        self.annotators = [rep.annotators.get("GenericModelOutput")]
    def write(self, data):
        pass
acoustic, sensor = create_passport_acoustic(f"{mount}/acoustic_sensor",
    Acoustic=Acoustic, AcousticSensor=AcousticSensor, np=_np, tick_rate_hz=30.0,
    center_frequency_hz=40000.0, sensor_local_offset_m=(0.25,0.0,0.0),
    mount_spacing_m=0.10, aux_output_level="BASIC", writer_brings_annotator=True,
    az_span_deg=90.0, el_span_deg=90.0, trace_tree_depth=2)
rep.WriterRegistry.register(ProbeWriter)
sensor.attach_writer("ProbeWriter")
observe("C2: 掛聲學感測器+寫入器", 10)

# C3: 感測器修正變換
from pxr import Gf
cache = UsdGeom.XformCache(0)
mp = stage.GetPrimAtPath(mount)
minv = cache.GetLocalToWorldTransform(mp).GetInverse()
lp = minv.Transform(Gf.Vec3d(0.60, 0.0, 0.65))
lq = minv.ExtractRotationQuat().GetNormalized()
sxf = UsdGeom.Xformable(stage.GetPrimAtPath(f"{mount}/acoustic_sensor"))
ops = {op.GetOpName(): op for op in sxf.GetOrderedXformOps()}
(ops.get("xformOp:translate") or sxf.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)).Set(Gf.Vec3d(lp))
try:
    (ops.get("xformOp:orient") or sxf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)).Set(Gf.Quatd(lq))
except Exception:
    ops["xformOp:orient"].Set(Gf.Quatf(lq))
observe("C3: 感測器修正變換", 8)

# D: 鏡頭與觀察等待
from geometry_passport_v1 import prepare_gui_observation
if not args.headless:
    prepare_gui_observation(app, stage, focus_position=(1.0,0.0,0.45),
                            hide_camera_wall=False, pre_start_wait_s=2.0)
observe("D: 鏡頭設定後", 8)

print("\n分段點火完畢")
app.close()
raise SystemExit(0)
print("DOF ORDER:", list(robot.dof_names))
print(f"probe start: mode={'BARE' if args.bare else 'GRIPPER'} headless={args.headless}")
print(f"{'t(s)':>5} {'finite':>7} {'max|dq_arm|/s':>14} {'arm_q[0:3]':>28}  finger_q...")
prev = None
import time
t0 = time.time()
frame = 0
while time.time() - t0 < args.seconds:
    app.update()
    frame += 1
    if frame % 60 == 0:
        try:
            q = np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)
        except Exception as e:
            print(f"{time.time()-t0:5.1f}  read failed: {e}")
            continue
        fin = bool(np.all(np.isfinite(q)))
        dq = float(np.max(np.abs(q[:6] - prev[:6]))) if (prev is not None and fin and np.all(np.isfinite(prev))) else float("nan")
        print(f"{time.time()-t0:5.1f} {str(fin):>7} {dq:14.4f} {np.round(q[:3],3)}  {np.round(q[6:],2) if q.size>6 else ''}")
        prev = q
print("probe end")
app.close()
