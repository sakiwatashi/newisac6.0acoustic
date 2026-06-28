"""Plan fixed-base UR10 distance waypoints with Isaac Sim 6.0 Lula IK.

This is a geometry/IK probe for the thesis acoustic experiment. It does not
capture acoustic data. It searches fixed target placements and asks Lula IK for
UR10 ee_link poses that should place the ee-mounted sensor near requested
sensor-target distances.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from isaacsim import SimulationApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official UR10 IK distance waypoint planner.")
    parser.add_argument("--output-dir", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_ik_distance_planner"))
    parser.add_argument("--output-stage", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10_official_asset_ik_distance_planner.usda"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--end-effector-frame", choices=("ee_link",), default="ee_link")
    parser.add_argument("--distance-waypoints", type=float, nargs="+", default=(0.3, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0))
    parser.add_argument("--target-x-values", type=float, nargs="+", default=(1.2, 1.6, 2.0, 2.4, 2.8, 3.2))
    parser.add_argument("--target-y", type=float, default=0.16)
    parser.add_argument("--target-z", type=float, default=0.05)
    parser.add_argument("--sensor-local-offset", type=float, nargs=3, default=(0.08, 0.0, 0.0))
    parser.add_argument("--sweep-z", type=float, default=0.35)
    parser.add_argument("--sweep-y", type=float, default=0.16)
    parser.add_argument("--position-tolerance", type=float, default=0.03)
    parser.add_argument("--accept-distance-error", type=float, default=0.20)
    parser.add_argument("--settle-steps", type=int, default=5)
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


def vec_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


def semicolon_floats(values: Any) -> str:
    return ";".join(f"{float(v):.9g}" for v in values)


def main() -> None:
    args = parse_args()
    if args.output_stage.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output_stage}; pass --overwrite")

    simulation_app = SimulationApp({"headless": not bool(args.gui)})

    import numpy as np  # noqa: E402
    import omni  # noqa: E402
    import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.api.robots import Robot  # noqa: E402
    from isaacsim.core.experimental.objects import Cube  # noqa: E402
    from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver  # noqa: E402
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402
    from pxr import UsdGeom  # noqa: E402

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.output_stage.parent.mkdir(parents=True, exist_ok=True)

    context = omni.usd.get_context()
    context.new_stage()
    stage = context.get_stage()
    if stage is None:
        simulation_app.close()
        raise RuntimeError("Failed to create stage")
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    assets_root = get_assets_root_path()
    official_ur10_usd = f"{assets_root}/Isaac/Robots/UniversalRobots/ur10/ur10.usd"
    robot_path = "/World/ur10"
    ee_path = f"{robot_path}/{args.end_effector_frame}"
    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=robot_path)
    for _ in range(20):
        simulation_app.update()
    if not stage.GetPrimAtPath(ee_path):
        simulation_app.close()
        raise RuntimeError(f"End-effector frame not found: {ee_path}")

    Cube("/World/room/floor", positions=np.array([1.5, 0.0, -0.025]), scales=np.array([5.0, 3.0, 0.05]))
    for x in args.target_x_values:
        Cube(f"/World/target_candidates/x_{str(x).replace('.', 'p')}", positions=np.array([x, args.target_y, args.target_z]), scales=np.array([0.08, 0.08, 0.08]))

    world = World()
    robot = world.scene.add(Robot(prim_path=robot_path, name="ur10"))
    world.reset()

    robot_description_path = "/home/lab109/song/isaacsim6.0/app/extsDeprecated/isaacsim.robot_motion.motion_generation/motion_policy_configs/universal_robots/ur10/rmpflow/ur10_robot_description.yaml"
    urdf_path = "/home/lab109/song/isaacsim6.0/app/extsDeprecated/isaacsim.robot_motion.motion_generation/motion_policy_configs/universal_robots/ur10/ur10_robot.urdf"
    ik = LulaKinematicsSolver(robot_description_path, urdf_path)
    ik.set_default_position_tolerance(float(args.position_tolerance))
    print("IK planner: frames include ee_link=", "ee_link" in ik.get_all_frame_names(), flush=True)
    print("IK planner: joints=", ik.get_joint_names(), flush=True)

    cache = UsdGeom.XformCache(0)
    rows: list[dict[str, Any]] = []
    best_by_target: list[dict[str, Any]] = []
    warm_start = None

    for target_x in [float(v) for v in args.target_x_values]:
        target = (target_x, float(args.target_y), float(args.target_z))
        target_rows: list[dict[str, Any]] = []
        for desired in [float(v) for v in args.distance_waypoints]:
            # Place sensor on the negative-X side of the fixed target. Approximate
            # ee_link by subtracting the sensor local X offset; orientation is solved position-only.
            ee_target = np.array([
                target_x - desired - float(args.sensor_local_offset[0]),
                float(args.sweep_y),
                float(args.sweep_z),
            ], dtype=float)
            q, success = ik.compute_inverse_kinematics(
                args.end_effector_frame,
                ee_target,
                target_orientation=None,
                warm_start=warm_start,
                position_tolerance=float(args.position_tolerance),
                orientation_tolerance=None,
            )
            if success:
                warm_start = q
                robot.set_joint_positions(np.asarray(q, dtype=float))
                for _ in range(max(1, int(args.settle_steps))):
                    world.step(render=bool(args.gui))
                cache.Clear()
                ee_prim = stage.GetPrimAtPath(ee_path)
                ee_matrix = cache.GetLocalToWorldTransform(ee_prim)
                ee_position = vec_tuple(ee_matrix.ExtractTranslation())
                # Sensor position is approximate because IK is position-only; use ee + fixed local x offset in world X.
                sensor_position = (ee_position[0] + float(args.sensor_local_offset[0]), ee_position[1], ee_position[2])
                actual_distance = vec_norm(vec_sub(target, sensor_position))
                distance_error = abs(actual_distance - desired)
            else:
                ee_position = (math.nan, math.nan, math.nan)
                sensor_position = (math.nan, math.nan, math.nan)
                actual_distance = math.nan
                distance_error = math.inf
            row = {
                "target_x_m": target_x,
                "target_y_m": target[1],
                "target_z_m": target[2],
                "desired_distance_m": desired,
                "ee_target_x_m": float(ee_target[0]),
                "ee_target_y_m": float(ee_target[1]),
                "ee_target_z_m": float(ee_target[2]),
                "ik_success": bool(success),
                "actual_distance_m": actual_distance,
                "distance_error_m": distance_error,
                "within_tolerance": bool(success and distance_error <= float(args.accept_distance_error)),
                "ee_x_m": ee_position[0],
                "ee_y_m": ee_position[1],
                "ee_z_m": ee_position[2],
                "sensor_x_m": sensor_position[0],
                "sensor_y_m": sensor_position[1],
                "sensor_z_m": sensor_position[2],
                "joint_positions_rad": semicolon_floats(q) if success else "",
            }
            rows.append(row)
            target_rows.append(row)
            print(
                f"target_x={target_x:.2f} desired={desired:.2f} ik={success} "
                f"actual={actual_distance:.3f} error={distance_error:.3f}",
                flush=True,
            )
        ok_count = sum(1 for r in target_rows if r["within_tolerance"])
        finite = [r for r in target_rows if r["ik_success"]]
        best_by_target.append(
            {
                "target_x_m": target_x,
                "ok_count": ok_count,
                "requested_count": len(target_rows),
                "max_finite_distance_m": max((float(r["actual_distance_m"]) for r in finite), default=None),
                "min_finite_distance_m": min((float(r["actual_distance_m"]) for r in finite), default=None),
                "out_of_tolerance": [float(r["desired_distance_m"]) for r in target_rows if not r["within_tolerance"]],
                "total_abs_error_m": sum(float(r["distance_error_m"]) for r in finite),
            }
        )

    csv_path = args.output_dir / "official_asset_ur10_ik_distance_planner_detail.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_csv = args.output_dir / "official_asset_ur10_ik_distance_planner_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(best_by_target[0].keys()))
        writer.writeheader()
        writer.writerows(best_by_target)

    best = sorted(best_by_target, key=lambda r: (-int(r["ok_count"]), float(r["total_abs_error_m"])))[0]
    summary = {
        "pass": bool(rows),
        "best_target": best,
        "distance_waypoints_m": [float(v) for v in args.distance_waypoints],
        "target_x_values_m": [float(v) for v in args.target_x_values],
        "robot_description_path": robot_description_path,
        "urdf_path": urdf_path,
        "csv_path": csv_path,
        "summary_csv": summary_csv,
        "output_stage": args.output_stage,
    }
    summary_path = args.output_dir / "official_asset_ur10_ik_distance_planner_summary.json"
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stage.GetRootLayer().Export(str(args.output_stage))

    print("Status: PASS")
    print(f"Best target x: {best['target_x_m']} ok {best['ok_count']}/{best['requested_count']}")
    print(f"Best out-of-tolerance: {best['out_of_tolerance']}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {args.output_stage}")
    simulation_app.close()


if __name__ == "__main__":
    main()
