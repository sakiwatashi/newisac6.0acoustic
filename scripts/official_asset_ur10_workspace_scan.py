"""Scan official UR10 joint poses for sensor-target distance candidates.

This is a planning helper for the continuous acoustic experiment. It does not
capture acoustic data; it finds joint poses that place the ee-mounted sensor at
useful distances from a fixed target.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path
from typing import Any

from isaacsim import SimulationApp


SEED_POSES_RAD: dict[str, tuple[float, float, float, float, float, float]] = {
    "home": (0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0),
    "reach_forward": (0.0, -1.20, 1.20, -1.57, -1.57, 0.0),
    "reach_left": (0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
    "reach_right": (-0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official UR10 workspace scan for acoustic sweep planning.")
    parser.add_argument("--output-dir", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_workspace_scan"))
    parser.add_argument("--output-stage", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10_official_asset_workspace_scan.usda"))
    parser.add_argument("--end-effector-frame", choices=("ee_link",), default="ee_link")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--samples", type=int, default=160)
    parser.add_argument("--settle-steps", type=int, default=8)
    parser.add_argument("--seed", type=int, default=109)
    parser.add_argument("--sensor-local-offset", type=float, nargs=3, default=(0.08, 0.0, 0.0))
    parser.add_argument("--fixed-target-position", type=float, nargs=3, default=(0.8, 0.16, 0.05))
    return parser.parse_args()


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def vec_tuple(values: Any) -> tuple[float, float, float]:
    return tuple(float(values[i]) for i in range(3))


def vec_add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_scale(v: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    return (v[0] * s, v[1] * s, v[2] * s)


def vec_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


def vec_dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def vec_unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = max(vec_norm(v), 1e-12)
    return (v[0] / n, v[1] / n, v[2] / n)


def sample_joint_positions(rng: random.Random, count: int) -> list[tuple[str, tuple[float, ...]]]:
    poses: list[tuple[str, tuple[float, ...]]] = [(name, q) for name, q in SEED_POSES_RAD.items()]
    while len(poses) < count:
        q0 = rng.uniform(-1.2, 1.2)
        q1 = rng.uniform(-2.25, -0.75)
        q2 = rng.uniform(0.45, 2.15)
        q3 = rng.uniform(-2.35, -0.85)
        q4 = rng.uniform(-1.85, -1.20)
        q5 = 0.0
        poses.append((f"random_{len(poses):03d}", (q0, q1, q2, q3, q4, q5)))
    return poses[:count]


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
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402
    from pxr import Gf, UsdGeom  # noqa: E402

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
    fixed_target_position = tuple(float(v) for v in args.fixed_target_position)

    print(f"Workspace scan: loading {official_ur10_usd}", flush=True)
    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=robot_path)
    for _ in range(20):
        simulation_app.update()
    if not stage.GetPrimAtPath(ee_path):
        simulation_app.close()
        raise RuntimeError(f"End-effector frame not found: {ee_path}")

    Cube("/World/room/floor", positions=np.array([1.5, 0.0, -0.025]), scales=np.array([4.0, 3.0, 0.05]))
    Cube("/World/fixed_target", positions=np.array(fixed_target_position, dtype=float), scales=np.array([0.25, 0.25, 0.10]))

    world = World()
    robot = world.scene.add(Robot(prim_path=robot_path, name="ur10"))
    world.reset()

    rng = random.Random(int(args.seed))
    poses = sample_joint_positions(rng, max(1, int(args.samples)))
    cache = UsdGeom.XformCache(0)
    rows: list[dict[str, Any]] = []

    for i, (pose_name, q) in enumerate(poses):
        requested = np.array(q, dtype=float)
        robot.set_joint_positions(requested)
        for _ in range(max(1, int(args.settle_steps))):
            world.step(render=False)
        cache.Clear()
        ee_prim = stage.GetPrimAtPath(ee_path)
        ee_matrix = cache.GetLocalToWorldTransform(ee_prim)
        ee_position = vec_tuple(ee_matrix.ExtractTranslation())
        ee_forward = vec_tuple(ee_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized())
        sensor_position = vec_add(ee_position, vec_scale(ee_forward, float(args.sensor_local_offset[0])))
        target_direction = vec_sub(fixed_target_position, sensor_position)
        target_distance = vec_norm(target_direction)
        alignment_dot = vec_dot(ee_forward, vec_unit(target_direction))
        alignment_angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, alignment_dot))))
        actual_q = np.asarray(robot.get_joint_positions(), dtype=float)
        rows.append(
            {
                "sample_index": i,
                "pose_name": pose_name,
                "requested_joint_positions_rad": ";".join(f"{v:.9g}" for v in requested.tolist()),
                "actual_joint_positions_rad": ";".join(f"{v:.9g}" for v in actual_q.tolist()),
                "ee_x_m": ee_position[0],
                "ee_y_m": ee_position[1],
                "ee_z_m": ee_position[2],
                "sensor_x_m": sensor_position[0],
                "sensor_y_m": sensor_position[1],
                "sensor_z_m": sensor_position[2],
                "target_distance_m": target_distance,
                "alignment_dot": alignment_dot,
                "alignment_angle_deg": alignment_angle_deg,
            }
        )
        if i % 25 == 0:
            print(f"Workspace scan: sample={i}/{len(poses)} distance={target_distance:.3f} angle={alignment_angle_deg:.1f}", flush=True)

    csv_path = args.output_dir / "official_asset_ur10_workspace_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    by_distance = sorted(rows, key=lambda r: float(r["target_distance_m"]))
    by_alignment = sorted(rows, key=lambda r: abs(float(r["alignment_angle_deg"])))
    forwardish = [r for r in rows if float(r["alignment_angle_deg"]) <= 60.0]
    forwardish_by_distance = sorted(forwardish, key=lambda r: float(r["target_distance_m"]))
    summary = {
        "pass": bool(rows),
        "official_ur10_asset": official_ur10_usd,
        "robot_path": robot_path,
        "end_effector_frame": ee_path,
        "fixed_target_position_m": fixed_target_position,
        "samples": len(rows),
        "distance_min_m": float(by_distance[0]["target_distance_m"]),
        "distance_max_m": float(by_distance[-1]["target_distance_m"]),
        "best_near_pose": by_distance[0],
        "best_far_pose": by_distance[-1],
        "best_aligned_pose": by_alignment[0],
        "forwardish_angle_threshold_deg": 60.0,
        "forwardish_count": len(forwardish),
        "forwardish_distance_min_m": float(forwardish_by_distance[0]["target_distance_m"]) if forwardish_by_distance else None,
        "forwardish_distance_max_m": float(forwardish_by_distance[-1]["target_distance_m"]) if forwardish_by_distance else None,
        "forwardish_near_pose": forwardish_by_distance[0] if forwardish_by_distance else None,
        "forwardish_far_pose": forwardish_by_distance[-1] if forwardish_by_distance else None,
        "csv_path": csv_path,
        "output_stage": args.output_stage,
    }
    summary_path = args.output_dir / "official_asset_ur10_workspace_scan_summary.json"
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stage.GetRootLayer().Export(str(args.output_stage))

    print("Status: PASS")
    print(f"Distance range: [{summary['distance_min_m']:.6f}, {summary['distance_max_m']:.6f}] m")
    print(f"Forward-ish count: {len(forwardish)}")
    if forwardish_by_distance:
        print(f"Forward-ish distance range: [{summary['forwardish_distance_min_m']:.6f}, {summary['forwardish_distance_max_m']:.6f}] m")
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {args.output_stage}")

    simulation_app.close()


if __name__ == "__main__":
    main()
