"""Isolated UR10e + Robotiq 2F-85 physics grasp pilot (no ultrasonic).

Oracle IK align → gradual finger close → gentle lift; success = lift_delta_z >= threshold.
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
    GUI_DEFAULT_PRE_START_WAIT_S,
    IK_POSITION_TOLERANCE_M,
    ROOM_CENTER_M,
    ROOM_DIM_M,
    ROOM_FLOOR_COLOR,
    TCP_Y_M,
    WALL_THICKNESS_M,
    enable_static_collision,
    grasp_scene_camera_focus_m,
    prepare_gui_observation,
)
from grasp_passport_v1 import (  # noqa: E402
    LIFT_SUCCESS_MIN_Z_DELTA_M,
    ROBOTIQ_TOOL0_ABOVE_WRENCH_TOP_M,
    SETTLE_STEPS_PER_MOVE,
    TABLE_PRIM_PATH,
    TABLE_TOP_Z_M,
    WRENCH_PHYSICS_FRICTION,
    WRENCH_PHYSICS_MASS_KG,
    WRENCH_PRIM_PATH,
    WRENCH_SCALE_M,
    grasp_alignment_ee_candidates_m,
    oracle_distance_m,
    spawn_wrench_position,
)
from ultrasonic_grasp_common import (  # noqa: E402
    GraspRuntime,
    execute_grasp_and_lift,
    to_jsonable,
    vec_tuple,
)
from ur10e_robotiq_common import (  # noqa: E402
    apply_wrench_physics_material,
    home_arm_to_search_corridor,
    initialize_ur10e_manipulator,
    read_prim_world_z,
    read_scene_object_world_z,
    resolve_ee_path,
    set_arm_joint_positions,
    spawn_solid_work_table,
    spawn_ur10e_robotiq,
    spawn_ur10e_single_manipulator,
)
from ur10e_robotiq_passport_v1 import (  # noqa: E402
    ENABLE_WELD_FALLBACK,
    IK_EE_FRAME,
    IK_GRASP_ORIENTATION_TOLERANCE_RAD,
    IK_ROBOT_DESCRIPTION,
    IK_URDF,
    ROBOT_PRIM_PATH,
    SEED_POSES_RAD,
    passport_summary as robot_passport_summary,
    solve_tool0_ik,
    tool0_grasp_orientation_wxyz,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Isolated Robotiq physics grasp pilot.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10e_robotiq_physics_grasp_pilot_v1"),
    )
    parser.add_argument(
        "--output-stage",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10e_robotiq_physics_grasp_pilot_v1.usda"),
    )
    parser.add_argument("--trial-id", type=int, default=9)
    parser.add_argument("--spawn-seed", type=int, default=20260629)
    parser.add_argument("--settle-steps", type=int, default=SETTLE_STEPS_PER_MOVE)
    parser.add_argument("--tool0-above-wrench-top-m", type=float, default=ROBOTIQ_TOOL0_ABOVE_WRENCH_TOP_M)
    parser.add_argument("--wrench-y-scale-m", type=float, default=WRENCH_SCALE_M[1])
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument(
        "--gui-pre-start-wait-seconds",
        type=float,
        default=GUI_DEFAULT_PRE_START_WAIT_S,
    )
    parser.add_argument("--no-gui-camera-light", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_stage.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output_stage}; pass --overwrite")

    spawn = spawn_wrench_position(args.trial_id, args.spawn_seed)
    wrench_scale = (float(WRENCH_SCALE_M[0]), float(args.wrench_y_scale_m), float(WRENCH_SCALE_M[2]))
    wrench_center_z = TABLE_TOP_Z_M + wrench_scale[2] / 2.0
    spawn_pos = (spawn.wrench_x_m, spawn.wrench_y_m, wrench_center_z)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.output_stage.parent.mkdir(parents=True, exist_ok=True)

    simulation_app = SimulationApp({"headless": not bool(args.gui)})

    import numpy as np  # noqa: E402
    import omni  # noqa: E402
    import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid  # noqa: E402
    from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver  # noqa: E402
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402
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

    length, width, _ = ROOM_DIM_M
    cx, cy, _ = ROOM_CENTER_M
    t = WALL_THICKNESS_M
    from isaacsim.core.experimental.objects import Cube  # noqa: E402

    Cube(
        "/World/room/floor",
        positions=np.array([cx, cy, -t / 2.0], dtype=float),
        scales=np.array([length, width, t], dtype=float),
        colors=ROOM_FLOOR_COLOR,
    )
    world = World()
    wrench = world.scene.add(
        DynamicCuboid(
            prim_path=WRENCH_PRIM_PATH,
            name="wrench_target",
            position=np.array(spawn_pos, dtype=float),
            scale=np.array(wrench_scale, dtype=float),
            color=np.array([0.75, 0.75, 0.78]),
            mass=float(WRENCH_PHYSICS_MASS_KG),
        )
    )
    robot = spawn_ur10e_single_manipulator(world, robot_path=robot_path, stage=stage, name="ur10e")
    world.reset()
    spawn_solid_work_table(
        world,
        stage,
        wrench_y_m=spawn.wrench_y_m,
        FixedCuboid=FixedCuboid,
        np=np,
    )
    enable_static_collision(stage, "/World/room/floor")
    apply_wrench_physics_material(stage, WRENCH_PRIM_PATH, friction=float(WRENCH_PHYSICS_FRICTION))

    robotiq_gripper = initialize_ur10e_manipulator(
        robot, world, simulation_app, stage=stage, robot_path=robot_path
    )
    print(f"Robotiq finger joints: {robotiq_gripper.finger_joint_names}", flush=True)

    ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
    cache = UsdGeom.XformCache(0)
    grasp_orientation = tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"])
    home_arm_to_search_corridor(robot, world, ik, settle_steps=max(100, int(args.settle_steps) * 4))
    tool0_path = f"{robot_path}/{IK_EE_FRAME}"

    def read_wrench_z_oracle() -> float:
        return read_prim_world_z(stage, WRENCH_PRIM_PATH, cache, world=world)

    def read_tool0_pose() -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
        if hasattr(robot, "end_effector") and robot.end_effector is not None:
            return robot.end_effector.get_world_pose()
        cache.Clear()
        matrix = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(tool0_path))
        return vec_tuple(matrix.ExtractTranslation()), grasp_orientation

    def observe_q(arm_q: np.ndarray, settle: int) -> dict[str, Any]:
        set_arm_joint_positions(robot, arm_q, world, settle_steps=settle)
        ee_pos, _ = read_tool0_pose()
        arm_q_out = np.asarray(arm_q, dtype=float).reshape(-1)[:6]
        return {
            "q": arm_q_out,
            "sensor_position": ee_pos,
            "oracle_distance_m": oracle_distance_m(ee_pos, spawn_pos),
        }

    def solve_ee_target(ee_target: tuple[float, float, float], warm: np.ndarray) -> tuple[np.ndarray, bool]:
        q, ok = solve_tool0_ik(
            ik,
            ee_target,
            warm,
            target_orientation=grasp_orientation,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(IK_GRASP_ORIENTATION_TOLERANCE_RAD),
        )
        return np.asarray(q, dtype=float), bool(ok)

    grasp_z = wrench_center_z + wrench_scale[2] / 2.0 + float(args.tool0_above_wrench_top_m)

    runtime = GraspRuntime(
        world=world,
        robot=robot,
        ik=ik,
        stage=stage,
        sensor_path=tool0_path,
        ee_path=ee_path,
        spawn=spawn,
        writer_state={},
        capture_gmo=lambda: None,
        observe_q=observe_q,
        solve_ee_target=solve_ee_target,
        solve_ee_grasp_target=solve_ee_target,
        read_wrench_z_oracle=read_wrench_z_oracle,
        robotiq_gripper=robotiq_gripper,
        wrench_scene_object=wrench,
        enable_weld_fallback=ENABLE_WELD_FALLBACK,
        settle_steps=int(args.settle_steps),
        contact_ee_z_m=grasp_z,
    )

    if args.gui:
        prepare_gui_observation(
            simulation_app,
            stage,
            focus_position=grasp_scene_camera_focus_m(spawn_pos),
            hide_camera_wall=False,
            use_camera_light=not bool(args.no_gui_camera_light),
            pre_start_wait_s=float(args.gui_pre_start_wait_seconds),
        )

    started = time.perf_counter()
    warm = np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float)

    aligned = False
    align_mode = "none"
    ee_target = list(grasp_alignment_ee_candidates_m(spawn_pos)[0])
    ee_target[2] = grasp_z
    obs = observe_q(warm, runtime.settle_steps)
    for candidate in grasp_alignment_ee_candidates_m(spawn_pos):
        candidate = (candidate[0], candidate[1], grasp_z)
        q_align, ok = solve_ee_target(candidate, obs["q"])
        if not ok:
            continue
        obs = observe_q(q_align, runtime.settle_steps)
        ee_target = list(candidate)
        aligned = True
        align_mode = "oracle_ik"
        break

    history: list[dict[str, Any]] = [
        {
            "phase": "pilot_align",
            "trial_id": args.trial_id,
            "ee_x": ee_target[0],
            "ee_y": ee_target[1],
            "ee_z": ee_target[2],
            "grasp_z": grasp_z,
            "align_mode": align_mode,
            "aligned": aligned,
            "tool0_above_wrench_top_m": float(args.tool0_above_wrench_top_m),
            "wrench_y_scale_m": float(args.wrench_y_scale_m),
        }
    ]

    grasp_success = False
    grasp_reason = "align_failed"
    if aligned:
        obs, grasp_history, grasp_reason, grasp_success = execute_grasp_and_lift(
            runtime,
            ee_target=ee_target,
            obs=obs,
            trial_id=args.trial_id,
        )
        history.extend(grasp_history)

    wrench_z_final = read_scene_object_world_z(wrench, world=world)
    if not math.isfinite(wrench_z_final):
        wrench_z_final = read_wrench_z_oracle()
    ee_pos_final, _ = read_tool0_pose()

    runtime_s = time.perf_counter() - started
    summary = {
        "pilot": "robotiq_physics_grasp_v1",
        "trial_id": args.trial_id,
        "spawn_seed": args.spawn_seed,
        "success": grasp_success,
        "terminal_reason": grasp_reason,
        "aligned": aligned,
        "align_mode": align_mode,
        "lift_success_min_z_delta_m": LIFT_SUCCESS_MIN_Z_DELTA_M,
        "wrench_spawn_m": list(spawn_pos),
        "wrench_scale_m": list(wrench_scale),
        "ee_target_m": ee_target,
        "tool0_pose_final_m": list(ee_pos_final),
        "wrench_z_final_m": wrench_z_final,
        "runtime_s": runtime_s,
        "robot_passport": robot_passport_summary(),
        "claim_boundary": "Oracle wrench pose used for IK only; no ultrasonic closed-loop.",
    }

    history_csv = args.output_dir / "robotiq_physics_grasp_history.csv"
    with history_csv.open("w", newline="", encoding="utf-8") as handle:
        if history:
            writer = csv.DictWriter(handle, fieldnames=sorted({k for row in history for k in row.keys()}))
            writer.writeheader()
            writer.writerows(history)

    summary_path = args.output_dir / "robotiq_physics_grasp_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(to_jsonable(summary), handle, indent=2)

    context.save_as_stage(str(args.output_stage))
    print(
        f"Physics grasp pilot: success={grasp_success} reason={grasp_reason} "
        f"wrench_z_final={wrench_z_final:.4f}",
        flush=True,
    )
    print(f"Wrote {summary_path}", flush=True)

    if args.keep_open_seconds > 0:
        time.sleep(float(args.keep_open_seconds))
    simulation_app.close()


if __name__ == "__main__":
    main()