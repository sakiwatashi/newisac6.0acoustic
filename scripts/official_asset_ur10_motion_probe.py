"""Isaac Sim 6.0 official UR10 articulation motion probe.

This validates the missing step between the static acoustic smoke and the
thesis-facing robot experiment: the official UR10 asset must accept joint
commands, and `/World/ur10/ee_link` must move in world space.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path
from typing import Any

from isaacsim import SimulationApp


POSES_RAD: dict[str, tuple[float, float, float, float, float, float]] = {
    "home": (0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0),
    "reach_forward": (0.0, -1.20, 1.20, -1.57, -1.57, 0.0),
    "reach_left": (0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
    "reach_right": (-0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official UR10 ee_link robot-motion probe.")
    parser.add_argument("--output-dir", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_motion_probe"))
    parser.add_argument("--output-stage", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10_official_asset_motion_probe.usda"))
    parser.add_argument("--end-effector-frame", choices=("ee_link",), default="ee_link")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--settle-steps", type=int, default=80)
    parser.add_argument("--render-steps", type=int, default=20)
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument("--min-ee-motion-m", type=float, default=0.05)
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


def distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


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
    from pxr import Gf, Sdf, UsdGeom  # noqa: E402

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

    print(f"Motion probe: loading {official_ur10_usd}", flush=True)
    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=robot_path)
    for _ in range(20):
        simulation_app.update()

    if not stage.GetPrimAtPath(ee_path):
        simulation_app.close()
        raise RuntimeError(f"End-effector frame not found: {ee_path}")

    Cube("/World/room/floor", positions=np.array([1.5, 0.0, -0.025]), scales=np.array([4.0, 3.0, 0.05]))
    Cube("/World/fixed_target", positions=np.array([1.2, 0.0, 0.8]), scales=np.array([0.2, 0.2, 0.2]))

    world = World()
    robot = world.scene.add(Robot(prim_path=robot_path, name="ur10"))
    world.reset()

    rows: list[dict[str, Any]] = []
    cache = UsdGeom.XformCache(0)

    for pose_index, (pose_name, requested_q) in enumerate(POSES_RAD.items()):
        requested = np.array(requested_q, dtype=float)
        print(f"Motion probe: commanding pose {pose_index}: {pose_name} q={requested.tolist()}", flush=True)
        robot.set_joint_positions(requested)

        for _ in range(max(1, int(args.settle_steps))):
            world.step(render=bool(args.gui))
        for _ in range(max(0, int(args.render_steps))):
            simulation_app.update()

        actual_q = np.asarray(robot.get_joint_positions(), dtype=float)
        cache.Clear()
        ee_prim = stage.GetPrimAtPath(ee_path)
        ee_matrix = cache.GetLocalToWorldTransform(ee_prim)
        ee_position = vec_tuple(ee_matrix.ExtractTranslation())
        ee_forward = vec_tuple(ee_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized())

        marker_path = f"/World/motion_markers/{pose_name}"
        Cube(marker_path, positions=np.array(ee_position, dtype=float), scales=np.array([0.05, 0.05, 0.05]))
        marker_prim = stage.GetPrimAtPath(marker_path)
        marker_prim.CreateAttribute("research:poseName", Sdf.ValueTypeNames.String, custom=True).Set(pose_name)

        rows.append(
            {
                "pose_index": pose_index,
                "pose_name": pose_name,
                "requested_joint_positions_rad": ";".join(f"{v:.9g}" for v in requested.tolist()),
                "actual_joint_positions_rad": ";".join(f"{v:.9g}" for v in actual_q.tolist()),
                "ee_x_m": ee_position[0],
                "ee_y_m": ee_position[1],
                "ee_z_m": ee_position[2],
                "ee_forward_x": ee_forward[0],
                "ee_forward_y": ee_forward[1],
                "ee_forward_z": ee_forward[2],
            }
        )
        print(f"Motion probe: {pose_name} ee_position={ee_position}", flush=True)

    max_motion = 0.0
    if rows:
        positions = [(float(r["ee_x_m"]), float(r["ee_y_m"]), float(r["ee_z_m"])) for r in rows]
        for i, pos_a in enumerate(positions):
            for pos_b in positions[i + 1 :]:
                max_motion = max(max_motion, distance(pos_a, pos_b))

    passed = len(rows) == len(POSES_RAD) and max_motion >= float(args.min_ee_motion_m)

    csv_path = args.output_dir / "official_asset_ur10_motion_probe.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "pass": passed,
        "official_ur10_asset": official_ur10_usd,
        "robot_path": robot_path,
        "end_effector_frame": ee_path,
        "pose_count": len(rows),
        "min_required_ee_motion_m": float(args.min_ee_motion_m),
        "max_observed_ee_motion_m": max_motion,
        "csv_path": csv_path,
        "output_stage": args.output_stage,
        "poses": rows,
    }
    summary_path = args.output_dir / "official_asset_ur10_motion_probe_summary.json"
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stage.GetRootLayer().Export(str(args.output_stage))

    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print(f"Max observed ee_link motion: {max_motion:.6f} m")
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {args.output_stage}")

    if args.gui and args.keep_open_seconds > 0:
        deadline = time.time() + float(args.keep_open_seconds)
        while simulation_app.is_running() and time.time() < deadline:
            simulation_app.update()

    simulation_app.close()
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
