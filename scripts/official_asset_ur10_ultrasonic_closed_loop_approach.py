"""Phase B: UR10e + Robotiq 2F-85 ultrasonic closed-loop approach in Isaac Sim 6.0.

The controller does NOT read wrench world coordinates. Oracle pose is logged for evaluation.
Phase C extends this stack with Robotiq grasp + lift.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
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
    IK_POSITION_TOLERANCE_M,
    ROOM_PRIM_PATHS,
    SENSOR_LOCAL_OFFSET_M,
    SENSOR_MOUNT_SPACING_M,
    SENSOR_PRIM_NAME,
    TICK_RATE_HZ,
    GRASP_COLLISION_PRIM_PATHS,
    apply_passport_display_colors,
    create_six_wall_room,
    enable_static_collisions,
    grasp_room_layout_note,
    grasp_scene_camera_focus_m,
    GUI_DEFAULT_PRE_START_WAIT_S,
    prepare_gui_observation,
    set_prim_visibility,
)
from ur10e_robotiq_common import (  # noqa: E402
    bootstrap_arm_after_world_reset,
    get_arm_q,
    hold_arm_joint_positions,
    home_arm_to_search_corridor,
    make_arm_hold_tick,
    initialize_ur10e_manipulator,
    resolve_ee_path,
    resolve_sensor_mount_path,
    set_arm_joint_positions,
    spawn_solid_work_table,
    spawn_ur10e_robotiq,
    spawn_ur10e_single_manipulator,
)
from ur10e_robotiq_passport_v1 import (  # noqa: E402
    IK_APPROACH_POSITION_ONLY,
    IK_GRASP_ORIENTATION_TOLERANCE_RAD,
    IK_MAX_JOINT_JUMP_APPROACH_RAD,
    IK_MAX_WRIST_3_JUMP_RAD,
    IK_ROBOT_DESCRIPTION,
    IK_URDF,
    ROBOT_PRIM_PATH,
    SEED_POSES_RAD,
    passport_summary as robot_passport_summary,
    solve_tool0_ik,
    tool0_grasp_orientation_wxyz,
)
from grasp_passport_v1 import (  # noqa: E402
    GMO_SUBSTEPS,
    SETTLE_STEPS_PER_MOVE,
    TABLE_PRIM_PATH,
    WRENCH_COLOR,
    WRENCH_PRIM_PATH,
    WRENCH_SCALE_M,
    oracle_distance_m,
    passport_summary as grasp_passport_summary,
    approach_ee_target_z_m,
    search_start_ee_position_m,
    spawn_wrench_position,
)
from rtx_acoustic_factory import (  # noqa: E402
    acoustic_features_from_summary,
    create_passport_acoustic,
    enrich_gmo_summary,
    summarize_gmo_frame,
)
from grasp_passport_v1 import (  # noqa: E402
    ACOUSTIC_FUSION_ENERGY_WEIGHT,
    DEFAULT_CALIBRATION,
    DEFAULT_TOF_CALIBRATION,
    TCP_Y_M,
)
from rtx_material_passport_v1 import apply_room_and_target_materials  # noqa: E402
from ultrasonic_closed_loop_controller import (  # noqa: E402
    ControllerConfig,
    ControllerState,
    UltrasonicClosedLoopController,
)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase B UR10e+Robotiq ultrasonic closed-loop approach smoke.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10e_robotiq_ultrasonic_approach_smoke_v1"),
    )
    parser.add_argument(
        "--output-stage",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10e_robotiq_ultrasonic_approach_smoke_v1.usda"),
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
        help="GUI only: wait before approach motion (default 15s for loading).",
    )
    parser.add_argument(
        "--no-gui-camera-light",
        action="store_true",
        help="GUI only: do not enable viewport Camera Light.",
    )
    return parser.parse_args()


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def vec_tuple(values: Any) -> tuple[float, float, float]:
    return tuple(float(values[i]) for i in range(3))


def main() -> None:
    args = parse_args()
    if args.output_stage.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output_stage}; pass --overwrite")

    spawn = spawn_wrench_position(args.trial_id, args.spawn_seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.output_stage.parent.mkdir(parents=True, exist_ok=True)

    simulation_app = SimulationApp({"headless": not bool(args.gui)})

    import numpy as np  # noqa: E402
    import omni  # noqa: E402
    import omni.replicator.core as rep  # noqa: E402
    import omni.timeline  # noqa: E402
    import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.api.objects import FixedCuboid  # noqa: E402
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
    ee_path = resolve_ee_path(robot_path, stage)
    sensor_mount_path = resolve_sensor_mount_path(robot_path, stage)
    sensor_path = f"{sensor_mount_path}/{SENSOR_PRIM_NAME}"

    room_prim_paths = create_six_wall_room(Cube, np)
    Cube(
        WRENCH_PRIM_PATH,
        positions=np.array(spawn.position_m, dtype=float),
        scales=np.array(WRENCH_SCALE_M, dtype=float),
        colors=WRENCH_COLOR,
    )
    set_prim_visibility(stage, CAMERA_FACING_WALL_PATH, visible=False)
    for _ in range(5):
        simulation_app.update()

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

    class ApproachGmoWriter(Writer):
        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]

        def write(self, data):
            pending = writer_state.get("pending")
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
                if pending is not None:
                    pending["captured"] = True
                break
            writer_state["frame"] += 1

    rep.WriterRegistry.register(ApproachGmoWriter)
    sensor.attach_writer("ApproachGmoWriter")

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
        f"Bootstrap pose after world.reset: q={np.asarray(q_boot).round(3).tolist()}",
        flush=True,
    )
    spawn_solid_work_table(
        world,
        stage,
        wrench_y_m=spawn.wrench_y_m,
        FixedCuboid=FixedCuboid,
        np=np,
    )
    collision_paths = list(GRASP_COLLISION_PRIM_PATHS) + [TABLE_PRIM_PATH]
    collision_status = enable_static_collisions(stage, collision_paths)
    print(f"Approach workcell static collision: {collision_status}", flush=True)
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
    robotiq_gripper = initialize_ur10e_manipulator(
        robot,
        world,
        simulation_app,
        stage=stage,
        robot_path=robot_path,
        open_gripper=False,
    )
    print(f"Robotiq finger joints: {robotiq_gripper.finger_joint_names}", flush=True)

    cache = UsdGeom.XformCache(0)
    grasp_orientation = tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"])
    print(
        f"Homing arm to search corridor start {search_start_ee_position_m()} "
        f"(approach IK position-only={IK_APPROACH_POSITION_ONLY})",
        flush=True,
    )
    q_corridor = home_arm_to_search_corridor(
        robot,
        world,
        ik,
        settle_steps=max(100, int(args.settle_steps) * 4),
        max_step_rad=0.03,
        render=bool(args.gui),
        simulation_app=simulation_app if args.gui else None,
    )
    print(f"Search corridor arm q: {np.asarray(q_corridor, dtype=float).round(3).tolist()}", flush=True)
    arm_q_holder["q"] = get_arm_q(robot)
    robotiq_gripper.open(robot, world)
    arm_q_holder["q"] = get_arm_q(robot)

    def observe_q(arm_q: np.ndarray, settle: int) -> dict[str, Any]:
        arm_q_holder["q"] = np.asarray(arm_q, dtype=float).reshape(-1)[:6]
        set_arm_joint_positions(robot, arm_q, world, settle_steps=settle)
        cache.Clear()
        sensor_matrix = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(sensor_path))
        sensor_position = vec_tuple(sensor_matrix.ExtractTranslation())
        arm_q_out = np.asarray(arm_q, dtype=float).reshape(-1)[:6]
        return {
            "q": arm_q_out,
            "sensor_position": sensor_position,
            "oracle_distance_m": oracle_distance_m(sensor_position, spawn.position_m),
        }

    def solve_ee_target(ee_target: tuple[float, float, float], warm: np.ndarray) -> tuple[np.ndarray, bool]:
        orient = None if IK_APPROACH_POSITION_ONLY else grasp_orientation
        wrist_guard = None if IK_APPROACH_POSITION_ONLY else float(IK_MAX_WRIST_3_JUMP_RAD)
        q, ok = solve_tool0_ik(
            ik,
            ee_target,
            warm,
            target_orientation=orient,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(IK_GRASP_ORIENTATION_TOLERANCE_RAD),
            max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_APPROACH_RAD),
            max_wrist_3_jump_rad=wrist_guard,
            min_tool0_z_m=approach_ee_target_z_m(),
        )
        return np.asarray(q, dtype=float), bool(ok)

    def capture_gmo() -> dict[str, Any] | None:
        timeline = omni.timeline.get_timeline_interface()
        if not timeline.is_playing():
            timeline.play()
        writer_state["pending"] = {"captured": False}
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
                )
            else:
                world.step(render=(i == int(args.substeps_per_sample) - 1))
                simulation_app.update()
        for _ in range(5):
            simulation_app.update()
        return writer_state.get("last_fields")

    if args.gui:
        prepare_gui_observation(
            simulation_app,
            stage,
            focus_position=grasp_scene_camera_focus_m(spawn.position_m),
            hide_camera_wall=True,
            use_camera_light=not bool(args.no_gui_camera_light),
            pre_start_wait_s=float(args.gui_pre_start_wait_seconds),
            on_tick=make_arm_hold_tick(
                robot,
                world,
                arm_q_holder,
                simulation_app=simulation_app,
                render=True,
            ),
        )

    start_ee = search_start_ee_position_m()
    warm = np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float)
    q, ok = solve_ee_target(start_ee, warm)
    if not ok:
        simulation_app.close()
        raise RuntimeError(f"IK failed for search start {start_ee}")
    obs = observe_q(q, int(args.settle_steps))
    for _ in range(2):
        capture_gmo()

    controller = UltrasonicClosedLoopController(config=ControllerConfig(enable_grasp_phase=False))
    controller.reset()
    history_rows: list[dict[str, Any]] = []

    ee_target = list(start_ee)
    terminal_reason = "unknown"
    started = time.perf_counter()

    while True:
        fields = capture_gmo()
        features = acoustic_features_from_summary(
            fields,
            energy_calibration=DEFAULT_CALIBRATION,
            tof_calibration=DEFAULT_TOF_CALIBRATION,
            fusion_energy_weight=ACOUSTIC_FUSION_ENERGY_WEIGHT,
        )
        obs = observe_q(obs["q"], 0)
        state = controller.observe(
            features=features,
            sensor_x_m=obs["sensor_position"][0],
            oracle_distance_m=obs["oracle_distance_m"],
        )
        row = {
            "trial_id": args.trial_id,
            "controller_state": state.value,
            "sensor_x_m": obs["sensor_position"][0],
            "oracle_distance_m": obs["oracle_distance_m"],
            "estimated_distance_m": controller.telemetry.estimated_distance_m,
            "fused_distance_m": controller.telemetry.fused_distance_m,
            "primary_sgw_early_energy": features.early_energy,
            "gmo_valid": features.gmo_valid,
        }
        row.update(features.as_log_dict())
        history_rows.append(row)

        if state == ControllerState.AT_STANDOFF:
            terminal_reason = "standoff_reached"
            break
        if state == ControllerState.FAIL:
            terminal_reason = controller.telemetry.fail_reason.value if controller.telemetry.fail_reason else "fail"
            break
        if controller.should_step_forward():
            ee_target[0] += controller.step_forward_delta_x_m()
            q_next, ok = solve_ee_target(tuple(ee_target), obs["q"])
            if not ok:
                if math.isfinite(features.fused_distance_m) and features.fused_distance_m <= ControllerConfig().grasp_standoff_m + 0.10:
                    terminal_reason = "standoff_reached_ik_limit"
                else:
                    terminal_reason = "ik_failed"
                break
            obs = observe_q(q_next, int(args.settle_steps))
            continue
        if controller.should_step_lateral_y():
            ee_target[1] += controller.step_lateral_delta_y_m()
            ee_target[1] = max(float(TCP_Y_M) - 0.08, min(float(TCP_Y_M) + 0.08, float(ee_target[1])))
            q_next, ok = solve_ee_target(tuple(ee_target), obs["q"])
            if ok:
                obs = observe_q(q_next, int(args.settle_steps))
            continue
        break

    runtime_s = time.perf_counter() - started
    success = terminal_reason in (
        "standoff_reached",
        "standoff_reached_ik_limit",
        "standoff_reached_search_limit",
    )
    standoff_error_m = (
        abs(obs["oracle_distance_m"] - ControllerConfig().grasp_standoff_m) if success else None
    )

    history_csv = args.output_dir / "ultrasonic_closed_loop_approach_history.csv"
    with history_csv.open("w", newline="", encoding="utf-8") as handle:
        if history_rows:
            writer = csv.DictWriter(handle, fieldnames=list(history_rows[0].keys()))
            writer.writeheader()
            writer.writerows(history_rows)

    summary = {
        "phase": "B",
        "trial_id": args.trial_id,
        "spawn_seed": args.spawn_seed,
        "success": success,
        "terminal_reason": terminal_reason,
        "approach_steps": controller.telemetry.step_index,
        "runtime_s": runtime_s,
        "final_oracle_distance_m": obs["oracle_distance_m"],
        "standoff_target_m": ControllerConfig().grasp_standoff_m,
        "standoff_error_m": standoff_error_m,
        "wrench_oracle_position_m": list(spawn.position_m),
        "ee_path": ee_path,
        "robot_passport": robot_passport_summary(),
        "grasp_passport": grasp_passport_summary(),
        "claim_boundary": "Controller never received wrench_oracle_position_m.",
    }
    summary_path = args.output_dir / "ultrasonic_closed_loop_approach_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(to_jsonable(summary), handle, indent=2)

    context.save_as_stage(str(args.output_stage))
    print(f"Phase B approach complete: success={success} reason={terminal_reason} steps={controller.telemetry.step_index}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {history_csv}")

    if args.keep_open_seconds > 0:
        time.sleep(float(args.keep_open_seconds))
    simulation_app.close()


if __name__ == "__main__":
    main()