"""Phase C: UR10e + Robotiq 2F-85 ultrasonic closed-loop approach + grasp/lift."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

from isaacsim import SimulationApp

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from geometry_passport_v1 import (  # noqa: E402
    CAMERA_FACING_WALL_PATH,
    CENTER_FREQUENCY_HZ,
    DEFAULT_MATERIAL_CONDITION,
    GUI_DEFAULT_EPISODE_PAUSE_S,
    IK_POSITION_TOLERANCE_M,
    ROOM_PRIM_PATHS,
    SENSOR_LOCAL_OFFSET_M,
    SENSOR_MOUNT_SPACING_M,
    SENSOR_PRIM_NAME,
    TICK_RATE_HZ,
    apply_passport_display_colors,
    create_six_wall_room,
    GRASP_COLLISION_PRIM_PATHS,
    grasp_room_layout_note,
    grasp_scene_camera_focus_m,
    log_sensor_mount_summary,
    spawn_rtx_sensor_visual_markers,
    GUI_DEFAULT_PRE_START_WAIT_S,
    enable_static_collisions,
    prepare_gui_observation,
    set_prim_visibility,
    wait_gui_episode_pause,
)
from grasp_passport_v1 import (  # noqa: E402
    GMO_SUBSTEPS,
    SETTLE_STEPS_PER_MOVE,
    TABLE_PRIM_PATH,
    TABLE_SCALE_M,
    TABLE_TOP_Z_M,
    WRENCH_PHYSICS_FRICTION,
    WRENCH_PHYSICS_MASS_KG,
    WRENCH_PRIM_PATH,
    WRENCH_SCALE_M,
    oracle_distance_m,
    passport_summary as grasp_passport_summary,
    approach_ee_target_z_m,
    GRASP_TOOL0_MIN_Z_M,
    passport_grasp_contact_ee_z_m,
    search_start_ee_position_m,
    spawn_wrench_position,
    open_loop_pregrasp_candidates_m,
)
from rtx_acoustic_factory import create_passport_acoustic, enrich_gmo_summary, summarize_gmo_frame  # noqa: E402
from rtx_material_passport_v1 import apply_room_and_target_materials  # noqa: E402
from ultrasonic_grasp_common import (  # noqa: E402
    GraspRuntime,
    execute_grasp_and_lift,
    reset_scene_for_next_episode,
    run_approach_loop,
    setup_surface_gripper,
    to_jsonable,
    vec_tuple,
)
from ur10e_robotiq_common import (
    configure_grasp_contact_stability,  # noqa: E402
    apply_wrench_physics_material,
    bootstrap_arm_after_world_reset,
    get_arm_q,
    hold_arm_joint_positions,
    home_arm_to_search_corridor,
    make_arm_hold_tick,
    initialize_ur10e_manipulator,
    read_prim_world_z,
    resolve_ee_path,
    resolve_sensor_mount_path,
    set_arm_joint_positions,
    stabilize_articulation,
    spawn_ur10e_robotiq,
    spawn_solid_work_table,
    spawn_ur10e_single_manipulator,
)
from ur10e_robotiq_passport_v1 import (  # noqa: E402
    ENABLE_WELD_FALLBACK,
    IK_APPROACH_POSITION_ONLY,
    IK_GRASP_ORIENTATION_TOLERANCE_RAD,
    IK_MAX_JOINT_JUMP_APPROACH_RAD,
    IK_MAX_JOINT_JUMP_GRASP_RAD,
    IK_MAX_JOINT_JUMP_LIFT_RAD,
    IK_MAX_WRIST_3_JUMP_RAD,
    IK_ROBOT_DESCRIPTION,
    IK_URDF,
    ROBOT_PRIM_PATH,
    SEED_POSES_RAD,
    passport_summary as robot_passport_summary,
    solve_tool0_ik,
    tool0_grasp_orientation_wxyz,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase C UR10e+Robotiq ultrasonic closed-loop grasp smoke.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10e_robotiq_ultrasonic_grasp_smoke_v1"),
    )
    parser.add_argument(
        "--output-stage",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10e_robotiq_ultrasonic_grasp_smoke_v1.usda"),
    )
    parser.add_argument("--trial-id", type=int, default=0)
    parser.add_argument("--spawn-seed", type=int, default=20260629)
    parser.add_argument("--material-condition", default=DEFAULT_MATERIAL_CONDITION)
    parser.add_argument("--settle-steps", type=int, default=SETTLE_STEPS_PER_MOVE)
    parser.add_argument("--substeps-per-sample", type=int, default=GMO_SUBSTEPS)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument(
        "--gui-pre-start-wait-seconds",
        type=float,
        default=GUI_DEFAULT_PRE_START_WAIT_S,
        help="GUI only: wait before approach/grasp motion (default 15s for loading).",
    )
    parser.add_argument(
        "--no-gui-camera-light",
        action="store_true",
        help="GUI only: do not enable viewport Camera Light.",
    )
    parser.add_argument(
        "--control-mode",
        choices=("closed_loop", "open_loop_baseline"),
        default="closed_loop",
        help="closed_loop uses ultrasonic approach; open_loop_baseline uses oracle wrench pose.",
    )
    parser.add_argument(
        "--claim-mode",
        choices=("scaffold", "acoustic_only"),
        default="scaffold",
        help="scaffold keeps oracle safety/geometry assists; acoustic_only disables oracle-assisted approach exits and pre-grasp XY alignment.",
    )
    parser.add_argument(
        "--episode-count",
        type=int,
        default=1,
        help="Run this many approach+grasp cycles in one Sim session (same trial-id unless --episode-trial-ids).",
    )
    parser.add_argument(
        "--episode-trial-ids",
        default="",
        help="Comma-separated trial ids for each episode, e.g. 1,3,5,7,9 (overrides --episode-count).",
    )
    parser.add_argument(
        "--episode-pause-seconds",
        type=float,
        default=0.0,
        help="GUI: pause between episodes so motion is visible (0 = no pause).",
    )
    parser.add_argument(
        "--gui-settle-scale",
        type=float,
        default=1.0,
        help="Multiply settle-steps in GUI mode for slower visible arm motion.",
    )
    parser.add_argument(
        "--skip-lift",
        dest="skip_lift",
        action="store_true",
        default=None,
        help="Use contact-only proxy: FixedCuboid target and no physics lift.",
    )
    parser.add_argument(
        "--enable-lift",
        dest="skip_lift",
        action="store_false",
        help="Use DynamicCuboid target and physics lift path.",
    )
    parser.add_argument(
        "--final-gripper",
        choices=("robotiq", "surface"),
        default="robotiq",
        help="Final grasp actuator. surface uses Isaac Sim SurfaceGripper as a stable lift baseline.",
    )
    return parser.parse_args()


def resolve_episode_trial_ids(args: argparse.Namespace) -> list[int]:
    if str(args.episode_trial_ids).strip():
        trial_ids = [int(part.strip()) for part in str(args.episode_trial_ids).split(",") if part.strip()]
        if not trial_ids:
            raise SystemExit("--episode-trial-ids was provided but parsed empty")
        return trial_ids
    episode_count = max(1, int(args.episode_count))
    return [int(args.trial_id)] * episode_count


def run_single_episode(
    *,
    episode_id: int,
    trial_id: int,
    spawn: Any,
    runtime: GraspRuntime,
    args: argparse.Namespace,
    controller_cls: Any,
) -> dict[str, Any]:
    import numpy as np

    runtime.episode_id = int(episode_id)
    runtime.spawn = spawn
    runtime.contact_ee_z_m = passport_grasp_contact_ee_z_m()

    if episode_id > 1:
        reset_scene_for_next_episode(
            runtime,
            spawn=spawn,
            start_ee=search_start_ee_position_m(),
            warm_q=SEED_POSES_RAD["search_corridor"],
            reset_settle_steps=max(60, int(runtime.settle_steps) * 2),
        )

    print(
        f"=== Episode {episode_id}: trial_id={trial_id} wrench_x={spawn.wrench_x_m:.3f} m ===",
        flush=True,
    )
    started = time.perf_counter()
    approach_history: list[dict[str, Any]] = []
    approach_end_oracle_m = math.nan
    approach_supervisor_summary: dict[str, Any] | None = None
    if args.control_mode == "open_loop_baseline":
        warm = np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float)
        candidates = open_loop_pregrasp_candidates_m(spawn.position_m)
        q = warm
        ok = False
        pregrasp = candidates[0]
        for candidate in candidates:
            pregrasp = candidate
            ee_target = list(pregrasp)
            q, ok = runtime.solve_ee_target(tuple(ee_target), warm)
            if ok:
                print(f"Open-loop pregrasp IK ok: {pregrasp}", flush=True)
                break
        if not ok:
            raise RuntimeError(f"Open-loop IK failed for all pregrasp candidates: {candidates}")
        obs = runtime.observe_q(q, runtime.settle_steps)
        approach_reason = "open_loop_pregrasp"
        approach_end_oracle_m = float(obs["oracle_distance_m"])
        controller = controller_cls()
    else:
        obs, approach_history, approach_reason, ee_target, controller, approach_supervisor = run_approach_loop(
            runtime,
            start_ee=search_start_ee_position_m(),
            warm_q=SEED_POSES_RAD["search_corridor"],
            enable_grasp_phase=True,
            trial_id=trial_id,
        )
        if approach_history:
            approach_end_oracle_m = float(approach_history[-1].get("oracle_distance_m", math.nan))
        if approach_supervisor is not None:
            approach_supervisor_summary = approach_supervisor.summary()

    grasp_history: list[dict[str, Any]] = []
    grasp_success = False
    grasp_reason = "skipped"
    if approach_reason in (
        "standoff_reached",
        "standoff_reached_ik_limit",
        "standoff_reached_search_limit",
        "standoff_reached_forward_cap",
        "standoff_reached_fusion_saturation",
        "standoff_reached_forward_cap_rescue",
        "standoff_reached_fusion_saturation_rescue",
        "tier_b_lateral_complete",
        "descend_ready",
        "open_loop_pregrasp",
    ):
        obs, grasp_history, grasp_reason, grasp_success = execute_grasp_and_lift(
            runtime,
            ee_target=ee_target,
            obs=obs,
            trial_id=trial_id,
        )

    runtime_s = time.perf_counter() - started
    all_history = approach_history + grasp_history
    success = grasp_success
    terminal_reason = grasp_reason if grasp_reason != "skipped" else approach_reason
    return {
        "episode_id": episode_id,
        "trial_id": trial_id,
        "spawn": spawn,
        "success": success,
        "approach_reason": approach_reason,
        "terminal_reason": terminal_reason,
        "approach_steps": controller.telemetry.step_index,
        "approach_end_oracle_distance_m": approach_end_oracle_m,
        "approach_supervisor": approach_supervisor_summary,
        "runtime_s": runtime_s,
        "final_oracle_distance_m": obs.get("oracle_distance_m"),
        "history": all_history,
        "obs": obs,
    }


def main() -> None:
    args = parse_args()
    if args.output_stage.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output_stage}; pass --overwrite")

    episode_trial_ids = resolve_episode_trial_ids(args)
    first_spawn = spawn_wrench_position(episode_trial_ids[0], args.spawn_seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.output_stage.parent.mkdir(parents=True, exist_ok=True)

    gui_settle_scale = max(1.0, float(args.gui_settle_scale)) if args.gui else 1.0
    effective_settle_steps = max(1, int(round(int(args.settle_steps) * gui_settle_scale)))

    simulation_app = SimulationApp({"headless": not bool(args.gui)})

    import numpy as np  # noqa: E402
    import omni  # noqa: E402
    import omni.replicator.core as rep  # noqa: E402
    import omni.timeline  # noqa: E402
    import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid  # noqa: E402

    from isaacsim.core.experimental.materials import NonVisualMaterial  # noqa: E402
    from isaacsim.core.experimental.objects import Cube  # noqa: E402
    from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver  # noqa: E402
    from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor, parse_generic_model_output_data  # noqa: E402
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402
    from omni.replicator.core import Writer  # noqa: E402
    from pxr import UsdGeom  # noqa: E402

    context = omni.usd.get_context()
    context.new_stage()
    stage = context.get_stage()
    if stage is None:
        simulation_app.close()
        raise RuntimeError("Failed to create stage")
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    robot_path = ROBOT_PRIM_PATH
    assets_root = get_assets_root_path()
    spawn_ur10e_robotiq(
        stage=stage,
        stage_utils=stage_utils,
        assets_root=assets_root,
        simulation_app=simulation_app,
        robot_path=robot_path,
    )

    # Pre-create SurfaceGripper prim AND its attachment point joint BEFORE world.reset()
    # so the C++ plugin registers them during physics scene initialization.
    # The attachment joint uses wrist_3_link as body0 (the actual articulation rigid body)
    # with physics:excludeFromArticulation=true so PhysX handles it as a standalone constraint.
    _pre_sg_path = ""
    if str(args.final_gripper) == "surface":
        from isaacsim.robot.surface_gripper import create_surface_gripper as _pre_csg  # noqa: E402
        from pxr import Gf, Sdf, UsdPhysics
        from usd.schema.isaac import robot_schema as _pre_rs

        _pre_ee = resolve_ee_path(robot_path, stage)
        _pre_mount = resolve_sensor_mount_path(robot_path, stage)  # wrist_3_link
        _pre_sg_prim = _pre_csg(stage, _pre_ee)
        _pre_sg_path = str(_pre_sg_prim.GetPath())

        # Attachment point joint — must exist before world.reset() so physics initializes it.
        # body0 = wrist_3_link (articulation EE link); excludeFromArticulation lets PhysX
        # treat this as a standalone D6 constraint rather than part of the arm's solver.
        try:
            _joint_path = f"{_pre_sg_path}/attachment_point_0"
            _joint = UsdPhysics.Joint.Define(stage, _joint_path)
            _joint.CreateBody0Rel().SetTargets([_pre_mount])
            _joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.03, 0.0, -0.06))
            _joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
            _joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
            _joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
            _pre_rs.ApplyAttachmentPointAPI(_joint.GetPrim())
            _joint.GetPrim().GetAttribute(_pre_rs.Attributes.FORWARD_AXIS.name).Set(UsdPhysics.Tokens.x)
            _joint.GetPrim().CreateAttribute(
                "physics:excludeFromArticulation", Sdf.ValueTypeNames.Bool, True
            ).Set(True)
            _pre_sg_prim.GetRelationship(_pre_rs.Relations.ATTACHMENT_POINTS.name).SetTargets(
                [Sdf.Path(_joint_path)]
            )
            print(f"SurfaceGripper pre-created: {_pre_sg_path} attachment body0={_pre_mount}", flush=True)
        except Exception as _pre_exc:
            print(f"SurfaceGripper pre-setup failed: {_pre_exc}", flush=True)

    world = World()
    robot = spawn_ur10e_single_manipulator(world, robot_path=robot_path, stage=stage, name="ur10e")
    world.reset()
    ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
    q_boot = bootstrap_arm_after_world_reset(
        robot,
        world,
        ik_solver=ik,
        simulation_app=simulation_app,
        render=bool(args.gui),
    )
    arm_q_holder: dict[str, Any] = {"q": get_arm_q(robot)}
    print(
        f"Bootstrap pose after world.reset (all-zero default avoided): q={np.asarray(q_boot).round(3).tolist()}",
        flush=True,
    )

    ee_path = resolve_ee_path(robot_path, stage)
    sensor_mount_path = resolve_sensor_mount_path(robot_path, stage)
    sensor_path = f"{sensor_mount_path}/{SENSOR_PRIM_NAME}"

    room_prim_paths = create_six_wall_room(Cube, np, open_space=True)
    set_prim_visibility(stage, CAMERA_FACING_WALL_PATH, visible=False)

    acoustic, sensor = create_passport_acoustic(
        sensor_path,
        Acoustic=Acoustic,
        AcousticSensor=AcousticSensor,
        np=np,
        tick_rate_hz=TICK_RATE_HZ,
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        sensor_local_offset_m=SENSOR_LOCAL_OFFSET_M,
        mount_spacing_m=SENSOR_MOUNT_SPACING_M,
        writer_brings_annotator=True,
    )

    writer_state: dict[str, Any] = {"pending": None, "last_fields": None, "frame": 0}

    class GraspGmoWriter(Writer):
        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]

        def write(self, data):
            for _rp, rp_data in data.get("renderProducts", {}).items():
                raw = rp_data.get("GenericModelOutput")
                if isinstance(raw, dict):
                    raw = raw.get("data")
                if raw is None or getattr(raw, "size", 0) == 0:
                    continue
                try:
                    gmo = parse_generic_model_output_data(raw)
                except Exception:
                    continue
                if int(gmo.numElements) <= 0:
                    continue
                writer_state["last_fields"] = enrich_gmo_summary(summarize_gmo_frame(gmo, np), gmo, np)
                break
            writer_state["frame"] += 1

    rep.WriterRegistry.register(GraspGmoWriter)
    sensor.attach_writer("GraspGmoWriter")

    sensor_marker_paths: list[str] = []
    if args.gui:
        sensor_marker_paths = spawn_rtx_sensor_visual_markers(
            stage,
            sensor_path,
            mount_spacing_m=SENSOR_MOUNT_SPACING_M,
        )
        print(f"GUI: RTX sensor visual markers: {sensor_marker_paths}", flush=True)

    env_skip_lift = os.environ.get("GRASP_SKIP_LIFT", "1").strip().lower() in ("1", "true", "yes")
    skip_lift = bool(env_skip_lift if args.skip_lift is None else args.skip_lift)
    final_gripper = str(args.final_gripper)
    if final_gripper == "surface":
        skip_lift = False
    grasp_contact_only = skip_lift
    wrench_physics_mode = "fixed" if grasp_contact_only else "dynamic"
    if grasp_contact_only:
        wrench = world.scene.add(
            FixedCuboid(
                prim_path=WRENCH_PRIM_PATH,
                name="wrench_target",
                position=np.array(first_spawn.position_m, dtype=float),
                scale=np.array(WRENCH_SCALE_M, dtype=float),
                color=np.array([0.75, 0.75, 0.78]),
            )
        )
        print(
            "Contact-only proxy: wrench=FixedCuboid (GRASP_SKIP_LIFT=1 / --skip-lift; no physics lift)",
            flush=True,
        )
    else:
        wrench = world.scene.add(
            DynamicCuboid(
                prim_path=WRENCH_PRIM_PATH,
                name="wrench_target",
                position=np.array(first_spawn.position_m, dtype=float),
                scale=np.array(WRENCH_SCALE_M, dtype=float),
                color=np.array([0.75, 0.75, 0.78]),
                mass=float(WRENCH_PHYSICS_MASS_KG),
            )
        )
        print(
            f"Wrench=DynamicCuboid mass={WRENCH_PHYSICS_MASS_KG}kg "
            f"(physics lift enabled, GRASP_SKIP_LIFT=0)",
            flush=True,
        )
    spawn_solid_work_table(
        world,
        stage,
        wrench_y_m=first_spawn.wrench_y_m,
        FixedCuboid=FixedCuboid,
        np=np,
    )
    collision_status = enable_static_collisions(stage, list(GRASP_COLLISION_PRIM_PATHS))
    print(f"Grasp workcell static collision: {collision_status}", flush=True)
    apply_wrench_physics_material(stage, WRENCH_PRIM_PATH, friction=float(WRENCH_PHYSICS_FRICTION))
    material_summary = apply_room_and_target_materials(
        room_prim_paths or list(ROOM_PRIM_PATHS),
        WRENCH_PRIM_PATH,
        str(args.material_condition),
        Cube=Cube,
        NonVisualMaterial=NonVisualMaterial,
        table_prim_path=TABLE_PRIM_PATH,
    )
    apply_passport_display_colors(Cube, room_prim_paths or list(ROOM_PRIM_PATHS), WRENCH_PRIM_PATH)
    print(f"RTX materials ({args.material_condition}): {material_summary.get('label', 'disabled')}", flush=True)
    print(grasp_room_layout_note(), flush=True)

    from ur10e_robotiq_common import summarize_prim_physics_state  # noqa: E402

    wrench_physics_at_spawn = summarize_prim_physics_state(stage, WRENCH_PRIM_PATH)
    print(f"Wrench physics at spawn: {wrench_physics_at_spawn}", flush=True)

    grasp_stability_mode: dict[str, Any] = {
        "gui_only": not bool(args.gui),
        "wrench_physics_mode": wrench_physics_mode,
        "grasp_skip_lift": skip_lift,
        "grasp_contact_only": grasp_contact_only,
        "wrench_physics_at_spawn": wrench_physics_at_spawn,
    }
    if grasp_contact_only:
        grasp_stability_mode = configure_grasp_contact_stability(
            stage,
            robot_path=robot_path,
            wrench_prim_path=WRENCH_PRIM_PATH,
            disable_finger_collision=True,
            disable_wrench_collision=True,
            wrench_kinematic=False,
        )
        grasp_stability_mode["wrench_physics_mode"] = wrench_physics_mode
        grasp_stability_mode["grasp_skip_lift"] = skip_lift
        grasp_stability_mode["grasp_contact_only"] = grasp_contact_only
        for _ in range(3):
            world.step(render=False)
            simulation_app.update()
    sensor_mount_summary = log_sensor_mount_summary(
        stage,
        sensor_mount_path=sensor_mount_path,
        sensor_path=sensor_path,
        sensor_local_offset_m=SENSOR_LOCAL_OFFSET_M,
        mount_spacing_m=SENSOR_MOUNT_SPACING_M,
    )
    if sensor_marker_paths:
        sensor_mount_summary["visual_marker_paths"] = sensor_marker_paths

    robotiq_gripper = initialize_ur10e_manipulator(
        robot,
        world,
        simulation_app,
        stage=stage,
        robot_path=robot_path,
        open_gripper=False,
    )
    surface_gripper_path = ""
    surface_gripper_iface = None
    surface_gripper_view = None
    if final_gripper == "surface":
        from isaacsim.robot.surface_gripper import GripperView, create_surface_gripper  # noqa: E402

        surface_gripper_path, surface_gripper_iface, surface_gripper_view = setup_surface_gripper(
            stage,
            ee_path,
            GripperView=GripperView,
            create_surface_gripper=create_surface_gripper,
        )
        robotiq_gripper.open(robot, world)
        robotiq_gripper = None
        print(f"SurfaceGripper final baseline: path={surface_gripper_path} iface={surface_gripper_iface is not None}", flush=True)
    else:
        print(f"Robotiq finger joints: {robotiq_gripper.finger_joint_names}", flush=True)
    from acoustic_calibration_v1 import load_tier_b_calibration  # noqa: E402

    _, _, cal_meta = load_tier_b_calibration()
    print(f"Tier B calibration source: {cal_meta}", flush=True)

    cache = UsdGeom.XformCache(0)
    grasp_orientation = tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"])
    print(f"IK tool0 grasp orientation (wxyz): {grasp_orientation.tolist()}", flush=True)
    print(
        f"Homing arm to search corridor start {search_start_ee_position_m()} "
        f"(approach IK position-only={IK_APPROACH_POSITION_ONLY})",
        flush=True,
    )
    q_corridor = home_arm_to_search_corridor(
        robot,
        world,
        ik,
        settle_steps=max(100, effective_settle_steps * 4),
        max_step_rad=0.03,
        render=bool(args.gui),
        simulation_app=simulation_app if args.gui else None,
    )
    print(f"Search corridor arm q: {np.asarray(q_corridor, dtype=float).round(3).tolist()}", flush=True)
    arm_q_holder["q"] = get_arm_q(robot)
    if robotiq_gripper is not None:
        robotiq_gripper.open(robot, world)
    arm_q_holder["q"] = get_arm_q(robot)

    def read_wrench_z_oracle() -> float:
        return read_prim_world_z(stage, WRENCH_PRIM_PATH, cache, world=world)

    current_spawn_holder: dict[str, Any] = {"spawn": first_spawn}

    def observe_q(arm_q: np.ndarray, settle: int) -> dict[str, Any]:
        arm_q_holder["q"] = np.asarray(arm_q, dtype=float).reshape(-1)[:6]
        set_arm_joint_positions(
            robot,
            arm_q,
            world,
            settle_steps=settle,
            render=bool(args.gui),
            simulation_app=simulation_app if args.gui else None,
            arm_only_kinematic=True,
        )
        stabilize_articulation(robot, world, steps=2, render=bool(args.gui))
        cache.Clear()
        sensor_matrix = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(sensor_path))
        sensor_position = vec_tuple(sensor_matrix.ExtractTranslation())
        arm_q_out = np.asarray(arm_q, dtype=float).reshape(-1)[:6]
        return {
            "q": arm_q_out,
            "sensor_position": sensor_position,
            "oracle_distance_m": oracle_distance_m(sensor_position, current_spawn_holder["spawn"].position_m),
        }

    def solve_ee_target(ee_target: tuple[float, float, float], warm: np.ndarray) -> tuple[np.ndarray, bool]:
        orient = None if IK_APPROACH_POSITION_ONLY else grasp_orientation
        orient_tol = IK_GRASP_ORIENTATION_TOLERANCE_RAD
        wrist_guard = None if IK_APPROACH_POSITION_ONLY else float(IK_MAX_WRIST_3_JUMP_RAD)
        q, ok = solve_tool0_ik(
            ik,
            ee_target,
            warm,
            target_orientation=orient,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(orient_tol),
            max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_APPROACH_RAD),
            max_wrist_3_jump_rad=wrist_guard,
            min_tool0_z_m=approach_ee_target_z_m(),
        )
        return np.asarray(q, dtype=float), bool(ok)

    def solve_ee_approach_target(ee_target: tuple[float, float, float], warm: np.ndarray) -> tuple[np.ndarray, bool]:
        """MoveIt-style approach IK: wrist joints may participate; no per-step wrist lock."""
        orient = None if IK_APPROACH_POSITION_ONLY else grasp_orientation
        orient_tol = IK_GRASP_ORIENTATION_TOLERANCE_RAD
        q, ok = solve_tool0_ik(
            ik,
            ee_target,
            warm,
            target_orientation=orient,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(orient_tol),
            max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_APPROACH_RAD),
            max_wrist_3_jump_rad=None,
            min_tool0_z_m=approach_ee_target_z_m(),
        )
        return np.asarray(q, dtype=float), bool(ok)

    def solve_ee_grasp_target(ee_target: tuple[float, float, float], warm: np.ndarray) -> tuple[np.ndarray, bool]:
        q, ok = solve_tool0_ik(
            ik,
            ee_target,
            warm,
            target_orientation=grasp_orientation,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(IK_GRASP_ORIENTATION_TOLERANCE_RAD),
            max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_GRASP_RAD),
            min_tool0_z_m=float(GRASP_TOOL0_MIN_Z_M),
        )
        return np.asarray(q, dtype=float), bool(ok)

    def solve_ee_motion_target(ee_target: tuple[float, float, float], warm: np.ndarray) -> tuple[np.ndarray, bool]:
        q, ok = solve_tool0_ik(
            ik,
            ee_target,
            warm,
            target_orientation=grasp_orientation,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(IK_GRASP_ORIENTATION_TOLERANCE_RAD),
            max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_GRASP_RAD),
            max_wrist_3_jump_rad=float(IK_MAX_WRIST_3_JUMP_RAD),
            min_tool0_z_m=float(GRASP_TOOL0_MIN_Z_M),
        )
        return np.asarray(q, dtype=float), bool(ok)

    def solve_ee_lift_target(ee_target: tuple[float, float, float], warm: np.ndarray) -> tuple[np.ndarray, bool]:
        q, ok = solve_tool0_ik(
            ik,
            ee_target,
            warm,
            target_orientation=grasp_orientation,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(IK_GRASP_ORIENTATION_TOLERANCE_RAD),
            max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_LIFT_RAD),
            max_wrist_3_jump_rad=None,
            min_tool0_z_m=float(GRASP_TOOL0_MIN_Z_M),
        )
        return np.asarray(q, dtype=float), bool(ok)

    def capture_gmo() -> dict[str, Any] | None:
        timeline = omni.timeline.get_timeline_interface()
        if not timeline.is_playing():
            timeline.play()
        writer_state["last_fields"] = None
        held_q = arm_q_holder.get("q")
        for i in range(max(1, int(args.substeps_per_sample))):
            if held_q is not None:
                hold_arm_joint_positions(
                    robot,
                    held_q,
                    world,
                    render=(i == int(args.substeps_per_sample) - 1) and bool(args.gui),
                    simulation_app=simulation_app if args.gui else None,
                    arm_only_kinematic=True,
                )
            else:
                world.step(render=(i == int(args.substeps_per_sample) - 1))
                simulation_app.update()
        for _ in range(5):
            simulation_app.update()
        return writer_state.get("last_fields")

    live_status_path = None
    if args.gui:
        live_status_path = args.output_dir / "approach_live_status.json"
    runtime = GraspRuntime(
        world=world,
        robot=robot,
        ik=ik,
        stage=stage,
        sensor_path=sensor_path,
        ee_path=ee_path,
        spawn=first_spawn,
        writer_state=writer_state,
        capture_gmo=capture_gmo,
        observe_q=observe_q,
        solve_ee_target=solve_ee_target,
        solve_ee_grasp_target=solve_ee_grasp_target,
        solve_ee_motion_target=solve_ee_motion_target,
        solve_ee_lift_target=solve_ee_lift_target,
        solve_ee_approach_target=solve_ee_approach_target,
        arm_q_holder=arm_q_holder,
        read_wrench_z_oracle=read_wrench_z_oracle,
        gripper_path=surface_gripper_path,
        gripper_iface=surface_gripper_iface,
        gripper_view=surface_gripper_view,
        robotiq_gripper=robotiq_gripper,
        wrench_scene_object=wrench,
        enable_weld_fallback=ENABLE_WELD_FALLBACK or (bool(args.gui) and not skip_lift),
        settle_steps=effective_settle_steps,
        contact_ee_z_m=passport_grasp_contact_ee_z_m(),
        gui_motion=bool(args.gui),
        simulation_app=simulation_app,
        live_status_path=live_status_path,
        enable_approach_supervisor=True,
        wrench_prim_path=WRENCH_PRIM_PATH,
        wrench_allow_velocity_reset=wrench_physics_mode == "dynamic",
        robot_path=robot_path,
        wrench_physics_mode=wrench_physics_mode,
        skip_lift=skip_lift,
        grasp_contact_only=grasp_contact_only,
        claim_mode=str(args.claim_mode),
    )

    if args.gui:
        hold_tick = make_arm_hold_tick(
            robot,
            world,
            arm_q_holder,
            simulation_app=simulation_app,
            render=True,
        )
        prepare_gui_observation(
            simulation_app,
            stage,
            focus_position=grasp_scene_camera_focus_m(first_spawn.position_m),
            hide_camera_wall=True,
            use_camera_light=not bool(args.no_gui_camera_light),
            pre_start_wait_s=float(args.gui_pre_start_wait_seconds),
            on_tick=hold_tick,
        )

    class _StubController:
        telemetry = type("T", (), {"step_index": 0})()

    episode_pause_s = float(args.episode_pause_seconds)
    episode_results: list[dict[str, Any]] = []
    all_history: list[dict[str, Any]] = []
    session_started = time.perf_counter()

    for episode_idx, trial_id in enumerate(episode_trial_ids, start=1):
        if episode_idx > 1 and episode_pause_s > 0 and args.gui:
            wait_gui_episode_pause(
                simulation_app,
                episode_index=episode_idx - 1,
                episode_count=len(episode_trial_ids),
                seconds=episode_pause_s,
                trial_id=episode_trial_ids[episode_idx - 2],
                on_tick=make_arm_hold_tick(
                    robot,
                    world,
                    arm_q_holder,
                    simulation_app=simulation_app,
                    render=True,
                ),
            )

        spawn = spawn_wrench_position(trial_id, args.spawn_seed)
        current_spawn_holder["spawn"] = spawn
        result = run_single_episode(
            episode_id=episode_idx,
            trial_id=trial_id,
            spawn=spawn,
            runtime=runtime,
            args=args,
            controller_cls=_StubController,
        )
        episode_results.append(result)
        all_history.extend(result["history"])
        print(
            f"Episode {episode_idx}/{len(episode_trial_ids)} done: success={result['success']} "
            f"terminal={result['terminal_reason']} runtime={result['runtime_s']:.1f}s",
            flush=True,
        )

    session_runtime_s = time.perf_counter() - session_started
    last_result = episode_results[-1]
    success_count = sum(1 for row in episode_results if row["success"])

    history_csv = args.output_dir / "ultrasonic_closed_loop_grasp_history.csv"
    with history_csv.open("w", newline="", encoding="utf-8") as handle:
        if all_history:
            writer = csv.DictWriter(handle, fieldnames=sorted({k for row in all_history for k in row.keys()}))
            writer.writeheader()
            writer.writerows(all_history)

    summary = {
        "phase": "C",
        "mode": args.control_mode,
        "claim_mode": str(args.claim_mode),
        "trial_id": int(args.trial_id),
        "spawn_seed": args.spawn_seed,
        "episode_count": len(episode_trial_ids),
        "episode_trial_ids": episode_trial_ids,
        "episode_pause_seconds": episode_pause_s,
        "gui_settle_scale": gui_settle_scale,
        "success": bool(last_result["success"]),
        "success_count": success_count,
        "approach_reason": last_result["approach_reason"],
        "terminal_reason": last_result["terminal_reason"],
        "approach_steps": last_result["approach_steps"],
        "approach_end_oracle_distance_m": last_result["approach_end_oracle_distance_m"],
        "runtime_s": last_result["runtime_s"],
        "session_runtime_s": session_runtime_s,
        "final_oracle_distance_m": last_result["final_oracle_distance_m"],
        "wrench_oracle_position_m": list(last_result["spawn"].position_m),
        "ee_path": ee_path,
        "robot_passport": robot_passport_summary(),
        "grasp_passport": grasp_passport_summary(),
        "room_layout_note": grasp_room_layout_note(),
        "material_summary": to_jsonable(material_summary),
        "collision_prims_enabled": collision_status,
        "grasp_stability_mode": to_jsonable(grasp_stability_mode),
        "grasp_skip_lift": skip_lift,
        "wrench_physics_mode": wrench_physics_mode,
        "sensor_mount_summary": to_jsonable(sensor_mount_summary),
        "tool0_grasp_orientation_wxyz": grasp_orientation.tolist(),
        "ik_approach_position_only": IK_APPROACH_POSITION_ONLY,
        "claim_boundary": (
            "claim_mode=acoustic_only disables oracle supervisor exits, spawn-based approach caps, "
            "pre-grasp oracle XY alignment, and oracle-distance weld fallback. "
            "Oracle pose/distance remains logged for evaluation only. "
            "claim_mode=scaffold preserves safety and geometry assists for GUI/engineering runs. "
            "Open-loop baseline intentionally uses oracle wrench pose for IK."
        ),
        "approach_supervisor": last_result.get("approach_supervisor"),
        "live_status_path": str(live_status_path) if live_status_path is not None else None,
    }
    summary_path = args.output_dir / "ultrasonic_closed_loop_grasp_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(to_jsonable(summary), handle, indent=2)

    episodes_summary = {
        "phase": "C",
        "mode": args.control_mode,
        "claim_mode": str(args.claim_mode),
        "spawn_seed": args.spawn_seed,
        "episode_count": len(episode_trial_ids),
        "success_count": success_count,
        "episodes": [
            {
                "episode_id": row["episode_id"],
                "trial_id": row["trial_id"],
                "success": row["success"],
                "terminal_reason": row["terminal_reason"],
                "approach_reason": row["approach_reason"],
                "runtime_s": row["runtime_s"],
                "wrench_oracle_position_m": list(row["spawn"].position_m),
                "approach_supervisor": row.get("approach_supervisor"),
            }
            for row in episode_results
        ],
    }
    episodes_summary_path = args.output_dir / "episodes_summary.json"
    with episodes_summary_path.open("w", encoding="utf-8") as handle:
        json.dump(to_jsonable(episodes_summary), handle, indent=2)

    context.save_as_stage(str(args.output_stage))
    print(
        f"Phase C grasp complete: episodes={len(episode_trial_ids)} success={success_count}/{len(episode_trial_ids)} "
        f"last_terminal={last_result['terminal_reason']}"
    )
    print(f"Wrote {summary_path}")
    print(f"Wrote {episodes_summary_path}")

    if args.keep_open_seconds > 0:
        time.sleep(float(args.keep_open_seconds))
    simulation_app.close()


if __name__ == "__main__":
    main()