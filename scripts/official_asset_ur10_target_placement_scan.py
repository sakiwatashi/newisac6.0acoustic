"""Evaluate fixed target placements for official UR10 continuous acoustic sweeps.

This planning script scans one shared set of UR10 joint poses, then evaluates
multiple candidate fixed-target positions against the ee-mounted sensor pose.
It helps decide whether a 0-3 m sweep is feasible before running acoustic.
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
    parser = argparse.ArgumentParser(description="Official UR10 target placement scan.")
    parser.add_argument("--output-dir", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_target_placement_scan"))
    parser.add_argument("--output-stage", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10_official_asset_target_placement_scan.usda"))
    parser.add_argument("--end-effector-frame", choices=("ee_link",), default="ee_link")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--samples", type=int, default=220)
    parser.add_argument("--settle-steps", type=int, default=6)
    parser.add_argument("--seed", type=int, default=109)
    parser.add_argument("--sensor-local-offset", type=float, nargs=3, default=(0.08, 0.0, 0.0))
    parser.add_argument("--target-y", type=float, default=0.16)
    parser.add_argument("--target-z", type=float, default=0.05)
    parser.add_argument("--target-x-values", type=float, nargs="+", default=(0.4, 0.8, 1.2, 1.6, 2.0, 2.4, 2.8))
    parser.add_argument("--forward-angle-threshold-deg", type=float, default=60.0)
    parser.add_argument("--analysis-min-distance", type=float, default=0.3)
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
        q0 = rng.uniform(-1.35, 1.35)
        q1 = rng.uniform(-2.35, -0.65)
        q2 = rng.uniform(0.35, 2.25)
        q3 = rng.uniform(-2.45, -0.70)
        q4 = rng.uniform(-1.95, -1.10)
        q5 = 0.0
        poses.append((f"random_{len(poses):03d}", (q0, q1, q2, q3, q4, q5)))
    return poses[:count]


def main() -> None:
    args = parse_args()
    if args.output_stage.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output_stage}; pass --overwrite")

    simulation_app = SimulationApp({"headless": True})

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

    print(f"Target placement scan: loading {official_ur10_usd}", flush=True)
    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=robot_path)
    for _ in range(20):
        simulation_app.update()
    if not stage.GetPrimAtPath(ee_path):
        simulation_app.close()
        raise RuntimeError(f"End-effector frame not found: {ee_path}")

    Cube("/World/room/floor", positions=np.array([1.5, 0.0, -0.025]), scales=np.array([5.0, 3.0, 0.05]))
    for x in args.target_x_values:
        Cube(f"/World/target_candidates/x_{str(x).replace('.', 'p')}", positions=np.array([float(x), args.target_y, args.target_z]), scales=np.array([0.08, 0.08, 0.08]))

    world = World()
    robot = world.scene.add(Robot(prim_path=robot_path, name="ur10"))
    world.reset()

    rng = random.Random(int(args.seed))
    poses = sample_joint_positions(rng, max(1, int(args.samples)))
    cache = UsdGeom.XformCache(0)
    sensor_rows: list[dict[str, Any]] = []

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
        sensor_rows.append(
            {
                "pose_name": pose_name,
                "joint_positions_rad": ";".join(f"{v:.9g}" for v in requested.tolist()),
                "sensor_position": sensor_position,
                "sensor_forward": ee_forward,
            }
        )
        if i % 50 == 0:
            print(f"Target placement scan: sampled pose {i}/{len(poses)}", flush=True)

    target_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    angle_threshold = float(args.forward_angle_threshold_deg)
    analysis_min = float(args.analysis_min_distance)

    for target_index, x in enumerate(args.target_x_values):
        target = (float(x), float(args.target_y), float(args.target_z))
        rows_for_target = []
        for pose_index, pose in enumerate(sensor_rows):
            sensor_position = pose["sensor_position"]
            sensor_forward = pose["sensor_forward"]
            target_direction = vec_sub(target, sensor_position)
            target_distance = vec_norm(target_direction)
            alignment_dot = vec_dot(sensor_forward, vec_unit(target_direction))
            alignment_angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, alignment_dot))))
            row = {
                "target_index": target_index,
                "target_x_m": target[0],
                "target_y_m": target[1],
                "target_z_m": target[2],
                "pose_index": pose_index,
                "pose_name": pose["pose_name"],
                "joint_positions_rad": pose["joint_positions_rad"],
                "sensor_x_m": sensor_position[0],
                "sensor_y_m": sensor_position[1],
                "sensor_z_m": sensor_position[2],
                "target_distance_m": target_distance,
                "alignment_dot": alignment_dot,
                "alignment_angle_deg": alignment_angle_deg,
            }
            rows_for_target.append(row)
            detail_rows.append(row)

        by_dist = sorted(rows_for_target, key=lambda r: float(r["target_distance_m"]))
        forwardish = [r for r in rows_for_target if float(r["alignment_angle_deg"]) <= angle_threshold]
        forwardish_safe = [r for r in forwardish if float(r["target_distance_m"]) >= analysis_min]
        forwardish_by_dist = sorted(forwardish, key=lambda r: float(r["target_distance_m"]))
        forwardish_safe_by_dist = sorted(forwardish_safe, key=lambda r: float(r["target_distance_m"]))
        target_rows.append(
            {
                "target_index": target_index,
                "target_x_m": target[0],
                "target_y_m": target[1],
                "target_z_m": target[2],
                "raw_distance_min_m": float(by_dist[0]["target_distance_m"]),
                "raw_distance_max_m": float(by_dist[-1]["target_distance_m"]),
                "forwardish_count": len(forwardish),
                "forwardish_distance_min_m": float(forwardish_by_dist[0]["target_distance_m"]) if forwardish_by_dist else "",
                "forwardish_distance_max_m": float(forwardish_by_dist[-1]["target_distance_m"]) if forwardish_by_dist else "",
                "forwardish_safe_count": len(forwardish_safe),
                "forwardish_safe_distance_min_m": float(forwardish_safe_by_dist[0]["target_distance_m"]) if forwardish_safe_by_dist else "",
                "forwardish_safe_distance_max_m": float(forwardish_safe_by_dist[-1]["target_distance_m"]) if forwardish_safe_by_dist else "",
                "forwardish_near_pose": forwardish_by_dist[0]["pose_name"] if forwardish_by_dist else "",
                "forwardish_far_pose": forwardish_by_dist[-1]["pose_name"] if forwardish_by_dist else "",
                "forwardish_near_joints": forwardish_by_dist[0]["joint_positions_rad"] if forwardish_by_dist else "",
                "forwardish_far_joints": forwardish_by_dist[-1]["joint_positions_rad"] if forwardish_by_dist else "",
            }
        )

    summary_csv = args.output_dir / "official_asset_ur10_target_placement_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(target_rows[0].keys()))
        writer.writeheader()
        writer.writerows(target_rows)

    detail_csv = args.output_dir / "official_asset_ur10_target_placement_detail.csv"
    with detail_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    def safe_span(row: dict[str, Any]) -> float:
        if row["forwardish_safe_distance_max_m"] == "" or row["forwardish_safe_distance_min_m"] == "":
            return -1.0
        return float(row["forwardish_safe_distance_max_m"]) - float(row["forwardish_safe_distance_min_m"])

    best = max(target_rows, key=safe_span)
    summary = {
        "pass": bool(target_rows),
        "official_ur10_asset": official_ur10_usd,
        "robot_path": robot_path,
        "end_effector_frame": ee_path,
        "samples": len(sensor_rows),
        "target_x_values": [float(x) for x in args.target_x_values],
        "target_y_m": float(args.target_y),
        "target_z_m": float(args.target_z),
        "forward_angle_threshold_deg": angle_threshold,
        "analysis_min_distance_m": analysis_min,
        "best_target_by_forwardish_safe_span": best,
        "summary_csv": summary_csv,
        "detail_csv": detail_csv,
        "output_stage": args.output_stage,
    }
    summary_json = args.output_dir / "official_asset_ur10_target_placement_summary.json"
    summary_json.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stage.GetRootLayer().Export(str(args.output_stage))

    print("Status: PASS")
    print(
        "Best target x="
        f"{best['target_x_m']} safe forward-ish range "
        f"[{best['forwardish_safe_distance_min_m']}, {best['forwardish_safe_distance_max_m']}] m",
        flush=True,
    )
    print(f"Wrote {summary_csv}")
    print(f"Wrote {detail_csv}")
    print(f"Wrote {summary_json}")
    print(f"Wrote {args.output_stage}")
    simulation_app.close()


if __name__ == "__main__":
    main()
