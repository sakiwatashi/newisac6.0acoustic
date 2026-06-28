"""Isaac Sim 6.0 official UR10 distance-waypoint RTX Acoustic capture.

The UR10 base remains fixed. A workspace planner samples joint poses, selects
reachable end-effector/sensor waypoints closest to requested target distances,
then moves the ee-mounted acoustic sensor through those waypoints while writing
continuous GenericModelOutput acoustic data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
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


FIELDNAMES = [
    "sample_index",
    "sim_step",
    "path_alpha",
    "planned_waypoint_index",
    "planned_waypoint_label",
    "desired_distance_m",
    "planned_distance_m",
    "waypoint_distance_error_m",
    "commanded_pose_start",
    "commanded_pose_end",
    "commanded_joint_positions_rad",
    "actual_joint_positions_rad",
    "ee_x_m",
    "ee_y_m",
    "ee_z_m",
    "sensor_x_m",
    "sensor_y_m",
    "sensor_z_m",
    "target_x_m",
    "target_y_m",
    "target_z_m",
    "target_distance_m",
    "alignment_dot",
    "alignment_angle_deg",
    "writer_frame",
    "timestamp_ns",
    "num_elements",
    "amplitude_min",
    "amplitude_max",
    "amplitude_mean",
    "amplitude_std",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official UR10 distance-waypoint RTX Acoustic capture.")
    parser.add_argument("--output-dir", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_distance_waypoint_acoustic"))
    parser.add_argument("--output-stage", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10_official_asset_distance_waypoint_acoustic.usda"))
    parser.add_argument("--end-effector-frame", choices=("ee_link",), default="ee_link")
    parser.add_argument("--start-pose", choices=tuple(POSES_RAD.keys()), default="reach_forward")
    parser.add_argument("--end-pose", choices=tuple(POSES_RAD.keys()), default="reach_right")
    parser.add_argument("--start-joints", type=float, nargs=6, default=None)
    parser.add_argument("--end-joints", type=float, nargs=6, default=None)
    parser.add_argument("--steps", type=int, default=120, help="Legacy fallback total steps when no waypoint plan is used.")
    parser.add_argument("--distance-waypoints", type=float, nargs="+", default=(0.3, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0))
    parser.add_argument("--planner-samples", type=int, default=480)
    parser.add_argument("--planner-seed", type=int, default=109)
    parser.add_argument("--planner-settle-steps", type=int, default=5)
    parser.add_argument("--samples-per-segment", type=int, default=24)
    parser.add_argument("--max-waypoint-error-m", type=float, default=0.20)
    parser.add_argument("--forward-angle-threshold-deg", type=float, default=75.0)
    parser.add_argument("--settle-steps", type=int, default=40)
    parser.add_argument("--substeps-per-sample", type=int, default=2)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument("--tick-rate", type=float, default=20.0)
    parser.add_argument("--center-frequency", type=float, default=40000.0)
    parser.add_argument("--sensor-local-offset", type=float, nargs=3, default=(0.08, 0.0, 0.0))
    parser.add_argument("--fixed-target-position", type=float, nargs=3, default=(0.8, 0.16, 0.05))
    parser.add_argument("--room-dim", type=float, nargs=3, default=(4.0, 3.0, 2.5))
    parser.add_argument("--no-room", action="store_true")
    parser.add_argument("--min-samples", type=int, default=20)
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


def vec_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


def vec_dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def vec_unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = max(vec_norm(v), 1e-12)
    return (v[0] / n, v[1] / n, v[2] / n)


def distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return vec_norm(vec_sub(a, b))


def sample_joint_positions(rng: random.Random, count: int) -> list[tuple[str, tuple[float, ...]]]:
    poses: list[tuple[str, tuple[float, ...]]] = [(name, q) for name, q in POSES_RAD.items()]
    while len(poses) < count:
        q0 = rng.uniform(-1.45, 1.45)
        q1 = rng.uniform(-2.45, -0.55)
        q2 = rng.uniform(0.25, 2.35)
        q3 = rng.uniform(-2.55, -0.60)
        q4 = rng.uniform(-2.05, -1.00)
        q5 = 0.0
        poses.append((f"sample_{len(poses):04d}", (q0, q1, q2, q3, q4, q5)))
    return poses[:count]


def semicolon_floats(values: Any) -> str:
    return ";".join(f"{float(v):.9g}" for v in values)


def token_list_op_items(value: Any) -> list[str]:
    if value is None:
        return []
    for method in ("GetAddedOrExplicitItems", "GetExplicitItems", "GetAddedItems"):
        if hasattr(value, method):
            items = getattr(value, method)()
            if items:
                return [str(x) for x in items]
    try:
        return [str(x) for x in value]
    except TypeError:
        return [str(value)]


def main() -> None:
    args = parse_args()
    if args.output_stage.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output_stage}; pass --overwrite")

    simulation_app = SimulationApp({"headless": not bool(args.gui)})

    import numpy as np  # noqa: E402
    import omni  # noqa: E402
    import omni.replicator.core as rep  # noqa: E402
    import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.api.robots import Robot  # noqa: E402
    from isaacsim.core.experimental.objects import Cube  # noqa: E402
    from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor, parse_generic_model_output_data  # noqa: E402
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402
    from omni.replicator.core import Writer  # noqa: E402
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
    sensor_path = f"{ee_path}/official_rtx_acoustic"
    fixed_target_position = tuple(float(v) for v in args.fixed_target_position)

    print(f"Continuous acoustic: loading {official_ur10_usd}", flush=True)
    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=robot_path)
    for _ in range(20):
        simulation_app.update()

    if not stage.GetPrimAtPath(ee_path):
        simulation_app.close()
        raise RuntimeError(f"End-effector frame not found: {ee_path}")

    if not args.no_room:
        room_length, room_width, room_height = (float(v) for v in args.room_dim)
        room_center_x = 1.5
        room_center_y = 0.0
        room_min_x = room_center_x - room_length / 2.0
        room_max_x = room_center_x + room_length / 2.0
        room_min_y = room_center_y - room_width / 2.0
        room_max_y = room_center_y + room_width / 2.0
        wall_t = 0.05
        Cube("/World/room/floor", positions=np.array([room_center_x, room_center_y, -wall_t / 2.0]), scales=np.array([room_length, room_width, wall_t]))
        Cube("/World/room/ceiling", positions=np.array([room_center_x, room_center_y, room_height + wall_t / 2.0]), scales=np.array([room_length, room_width, wall_t]))
        Cube("/World/room/wall_x_min", positions=np.array([room_min_x - wall_t / 2.0, room_center_y, room_height / 2.0]), scales=np.array([wall_t, room_width, room_height]))
        Cube("/World/room/wall_x_max", positions=np.array([room_max_x + wall_t / 2.0, room_center_y, room_height / 2.0]), scales=np.array([wall_t, room_width, room_height]))
        Cube("/World/room/wall_y_min", positions=np.array([room_center_x, room_min_y - wall_t / 2.0, room_height / 2.0]), scales=np.array([room_length, wall_t, room_height]))
        Cube("/World/room/wall_y_max", positions=np.array([room_center_x, room_max_y + wall_t / 2.0, room_height / 2.0]), scales=np.array([room_length, wall_t, room_height]))
    else:
        Cube("/World/room/floor", positions=np.array([1.5, 0.0, -0.025]), scales=np.array([4.0, 3.0, 0.05]))
    Cube("/World/fixed_target", positions=np.array(fixed_target_position, dtype=float), scales=np.array([0.25, 0.25, 0.10]))

    print(f"Continuous acoustic: creating Acoustic at {sensor_path}", flush=True)
    acoustic = Acoustic(
        sensor_path,
        tick_rate=float(args.tick_rate),
        aux_output_level="BASIC",
        translations=np.array(args.sensor_local_offset, dtype=float),
        attributes={
            "omni:sensor:WpmAcoustic:centerFrequency": float(args.center_frequency),
            "omni:sensor:WpmAcoustic:sensorMount:m001:position": (0.0, 0.0, 0.0),
            "omni:sensor:WpmAcoustic:sensorMount:m001:rotation": (0.0, 0.0, 0.0),
            "omni:sensor:WpmAcoustic:sensorMount:m002:position": (0.10, 0.0, 0.0),
            "omni:sensor:WpmAcoustic:sensorMount:m002:rotation": (0.0, 0.0, 0.0),
            "omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices": [0, 1],
        },
    )
    sensor = AcousticSensor(acoustic, annotators=["generic-model-output"], render_vars=["GenericModelOutput"])
    acoustic_prim = stage.GetPrimAtPath(sensor_path)
    if not acoustic_prim:
        simulation_app.close()
        raise RuntimeError(f"Acoustic prim was not created: {sensor_path}")
    acoustic_prim.CreateAttribute("research:continuousCapture", Sdf.ValueTypeNames.Bool, custom=True).Set(True)
    acoustic_prim.CreateAttribute("research:assetSource", Sdf.ValueTypeNames.String, custom=True).Set(official_ur10_usd)
    acoustic_prim.CreateAttribute("research:endEffectorFrame", Sdf.ValueTypeNames.String, custom=True).Set(ee_path)
    acoustic_prim.CreateAttribute("research:fixedTargetPositionM", Sdf.ValueTypeNames.Double3, custom=True).Set(fixed_target_position)

    rows: list[dict[str, Any]] = []
    writer_state: dict[str, Any] = {
        "sample_context": None,
        "writer_frame": 0,
        "parse_errors": [],
        "raw_empty_frames": 0,
    }

    class ContinuousMotionAcousticWriter(Writer):
        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]

        def write(self, data):
            context_row = writer_state.get("sample_context")
            if context_row is None:
                writer_state["writer_frame"] += 1
                return
            for _rp_name, rp_data in data.get("renderProducts", {}).items():
                gmo_raw = rp_data.get("GenericModelOutput")
                if isinstance(gmo_raw, dict):
                    gmo_raw = gmo_raw.get("data")
                if gmo_raw is None:
                    continue
                if getattr(gmo_raw, "size", None) == 0:
                    writer_state["raw_empty_frames"] += 1
                    continue
                try:
                    gmo = parse_generic_model_output_data(gmo_raw)
                except Exception as exc:
                    if len(writer_state["parse_errors"]) < 10:
                        writer_state["parse_errors"].append(str(exc))
                    continue
                n = int(gmo.numElements)
                if n <= 0:
                    writer_state["raw_empty_frames"] += 1
                    continue
                amplitudes = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
                finite = amplitudes[np.isfinite(amplitudes)]
                row = dict(context_row)
                row.update(
                    {
                        "sample_index": len(rows),
                        "writer_frame": int(writer_state["writer_frame"]),
                        "timestamp_ns": int(gmo.timestampNs),
                        "num_elements": n,
                        "amplitude_min": float(np.min(finite)) if finite.size else math.nan,
                        "amplitude_max": float(np.max(finite)) if finite.size else math.nan,
                        "amplitude_mean": float(np.mean(finite)) if finite.size else math.nan,
                        "amplitude_std": float(np.std(finite)) if finite.size else math.nan,
                    }
                )
                rows.append(row)
                break
            writer_state["writer_frame"] += 1

    rep.WriterRegistry.register(ContinuousMotionAcousticWriter)
    sensor.attach_writer("ContinuousMotionAcousticWriter")

    world = World()
    robot = world.scene.add(Robot(prim_path=robot_path, name="ur10"))
    world.reset()

    cache = UsdGeom.XformCache(0)

    def observe_pose(q: np.ndarray, settle_steps: int, render: bool = False) -> dict[str, Any]:
        robot.set_joint_positions(q)
        for _ in range(max(1, int(settle_steps))):
            world.step(render=render)
        actual_q = np.asarray(robot.get_joint_positions(), dtype=float)
        cache.Clear()
        ee_prim = stage.GetPrimAtPath(ee_path)
        sensor_prim = stage.GetPrimAtPath(sensor_path)
        ee_matrix = cache.GetLocalToWorldTransform(ee_prim)
        sensor_matrix = cache.GetLocalToWorldTransform(sensor_prim)
        ee_position = vec_tuple(ee_matrix.ExtractTranslation())
        sensor_position = vec_tuple(sensor_matrix.ExtractTranslation())
        sensor_forward = vec_tuple(sensor_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized())
        target_direction = vec_sub(fixed_target_position, sensor_position)
        target_distance = vec_norm(target_direction)
        alignment_dot = vec_dot(sensor_forward, vec_unit(target_direction))
        alignment_angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, alignment_dot))))
        return {
            "actual_q": actual_q,
            "ee_position": ee_position,
            "sensor_position": sensor_position,
            "target_distance": target_distance,
            "alignment_dot": alignment_dot,
            "alignment_angle_deg": alignment_angle_deg,
        }

    rng = random.Random(int(args.planner_seed))
    candidate_rows: list[dict[str, Any]] = []
    print(
        f"Distance waypoint planner: sampling {args.planner_samples} fixed-base UR10 poses for requested distances "
        f"{list(float(v) for v in args.distance_waypoints)}",
        flush=True,
    )
    for i, (pose_name, q_tuple) in enumerate(sample_joint_positions(rng, max(1, int(args.planner_samples)))):
        q = np.array(q_tuple, dtype=float)
        obs = observe_pose(q, int(args.planner_settle_steps), render=False)
        candidate_rows.append(
            {
                "pose_name": pose_name,
                "joint_positions": q,
                "actual_joint_positions": obs["actual_q"],
                "target_distance_m": float(obs["target_distance"]),
                "alignment_angle_deg": float(obs["alignment_angle_deg"]),
            }
        )
        if i % 80 == 0:
            print(
                f"Distance waypoint planner: sampled={i}/{args.planner_samples} "
                f"distance={obs['target_distance']:.3f} angle={obs['alignment_angle_deg']:.1f}",
                flush=True,
            )

    angle_limit = float(args.forward_angle_threshold_deg)
    aligned_candidates = [r for r in candidate_rows if float(r["alignment_angle_deg"]) <= angle_limit]
    search_pool = aligned_candidates if aligned_candidates else candidate_rows
    planned_waypoints: list[dict[str, Any]] = []
    for waypoint_index, desired in enumerate(float(v) for v in args.distance_waypoints):
        best = min(search_pool, key=lambda r: abs(float(r["target_distance_m"]) - desired))
        error = abs(float(best["target_distance_m"]) - desired)
        planned_waypoints.append(
            {
                "waypoint_index": waypoint_index,
                "label": f"d_{str(desired).replace('.', 'p')}m",
                "desired_distance_m": desired,
                "planned_distance_m": float(best["target_distance_m"]),
                "waypoint_distance_error_m": error,
                "within_tolerance": error <= float(args.max_waypoint_error_m),
                "pose_name": str(best["pose_name"]),
                "joint_positions": np.asarray(best["joint_positions"], dtype=float),
                "alignment_angle_deg": float(best["alignment_angle_deg"]),
            }
        )

    print("Distance waypoint planner: selected waypoints", flush=True)
    for wp in planned_waypoints:
        status = "OK" if wp["within_tolerance"] else "OUT_OF_TOLERANCE"
        print(
            f"  {wp['label']}: desired={wp['desired_distance_m']:.3f}m "
            f"planned={wp['planned_distance_m']:.3f}m error={wp['waypoint_distance_error_m']:.3f}m "
            f"angle={wp['alignment_angle_deg']:.1f} {status}",
            flush=True,
        )

    start_q = planned_waypoints[0]["joint_positions"]
    end_q = planned_waypoints[-1]["joint_positions"]
    start_label = planned_waypoints[0]["label"]
    end_label = planned_waypoints[-1]["label"]

    observe_pose(start_q, int(args.settle_steps), render=bool(args.gui))

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    sim_step = 0
    segment_samples = max(2, int(args.samples_per_segment))
    for segment_index in range(max(1, len(planned_waypoints) - 1)):
        wp_a = planned_waypoints[segment_index]
        wp_b = planned_waypoints[segment_index + 1]
        q_a = np.asarray(wp_a["joint_positions"], dtype=float)
        q_b = np.asarray(wp_b["joint_positions"], dtype=float)
        for local_step in range(segment_samples):
            if segment_index > 0 and local_step == 0:
                continue
            alpha = local_step / float(max(1, segment_samples - 1))
            commanded_q = (1.0 - alpha) * q_a + alpha * q_b
            robot.set_joint_positions(commanded_q)
            for _ in range(max(1, int(args.substeps_per_sample))):
                world.step(render=bool(args.gui))

            obs = observe_pose(commanded_q, 1, render=bool(args.gui))
            actual_q = np.asarray(obs["actual_q"], dtype=float)
            ee_position = obs["ee_position"]
            sensor_position = obs["sensor_position"]
            target_distance = float(obs["target_distance"])
            alignment_dot = float(obs["alignment_dot"])
            alignment_angle_deg = float(obs["alignment_angle_deg"])
            desired_distance = (1.0 - alpha) * float(wp_a["desired_distance_m"]) + alpha * float(wp_b["desired_distance_m"])
            planned_distance = (1.0 - alpha) * float(wp_a["planned_distance_m"]) + alpha * float(wp_b["planned_distance_m"])

            writer_state["sample_context"] = {
                "sim_step": sim_step,
                "path_alpha": (segment_index + alpha) / float(max(1, len(planned_waypoints) - 1)),
                "planned_waypoint_index": segment_index,
                "planned_waypoint_label": f"{wp_a['label']}->{wp_b['label']}",
                "desired_distance_m": desired_distance,
                "planned_distance_m": planned_distance,
                "waypoint_distance_error_m": abs(target_distance - desired_distance),
                "commanded_pose_start": wp_a["label"],
                "commanded_pose_end": wp_b["label"],
                "commanded_joint_positions_rad": semicolon_floats(commanded_q.tolist()),
                "actual_joint_positions_rad": semicolon_floats(actual_q.tolist()),
                "ee_x_m": ee_position[0],
                "ee_y_m": ee_position[1],
                "ee_z_m": ee_position[2],
                "sensor_x_m": sensor_position[0],
                "sensor_y_m": sensor_position[1],
                "sensor_z_m": sensor_position[2],
                "target_x_m": fixed_target_position[0],
                "target_y_m": fixed_target_position[1],
                "target_z_m": fixed_target_position[2],
                "target_distance_m": target_distance,
                "alignment_dot": alignment_dot,
                "alignment_angle_deg": alignment_angle_deg,
            }
            simulation_app.update()
            if sim_step % 20 == 0:
                print(
                    f"Distance waypoint acoustic: step={sim_step} segment={segment_index + 1}/{len(planned_waypoints) - 1} "
                    f"samples={len(rows)} desired={desired_distance:.3f} actual={target_distance:.3f} "
                    f"angle={alignment_angle_deg:.1f}",
                    flush=True,
                )
            sim_step += 1

    timeline.stop()
    writer_state["sample_context"] = None
    try:
        rep.orchestrator.wait_until_complete()
    except Exception as exc:
        writer_state["orchestrator_wait_error"] = str(exc)

    if rows:
        positions = [(float(r["ee_x_m"]), float(r["ee_y_m"]), float(r["ee_z_m"])) for r in rows]
        distances = [float(r["target_distance_m"]) for r in rows]
        amp_max_values = [float(r["amplitude_max"]) for r in rows]
        max_motion = max(distance(a, b) for i, a in enumerate(positions) for b in positions[i + 1 :]) if len(positions) > 1 else 0.0
        distance_min = min(distances)
        distance_max = max(distances)
        amplitude_max_min = min(amp_max_values)
        amplitude_max_max = max(amp_max_values)
    else:
        max_motion = 0.0
        distance_min = distance_max = 0.0
        amplitude_max_min = amplitude_max_max = 0.0

    api_schemas = token_list_op_items(acoustic_prim.GetMetadata("apiSchemas"))
    sensor_parent_ok = sensor_path.startswith(f"{ee_path}/")
    passed = (
        len(rows) >= int(args.min_samples)
        and max_motion >= float(args.min_ee_motion_m)
        and acoustic_prim.GetTypeName() == "OmniAcoustic"
        and "OmniSensorGenericAcousticWpmAPI" in api_schemas
        and sensor_parent_ok
    )

    csv_path = args.output_dir / "official_asset_ur10_distance_waypoint_acoustic_timeseries.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "pass": passed,
        "official_ur10_asset": official_ur10_usd,
        "robot_path": robot_path,
        "end_effector_frame": ee_path,
        "sensor_path": sensor_path,
        "sensor_parent_ok": sensor_parent_ok,
        "sensor_prim_type": acoustic_prim.GetTypeName(),
        "sensor_api_schemas": api_schemas,
        "fixed_target_position_m": fixed_target_position,
        "start_pose": start_label,
        "start_joint_positions_rad": start_q.tolist(),
        "end_pose": end_label,
        "end_joint_positions_rad": end_q.tolist(),
        "requested_distance_waypoints_m": [float(v) for v in args.distance_waypoints],
        "planned_waypoints": [
            {
                "waypoint_index": int(wp["waypoint_index"]),
                "label": wp["label"],
                "desired_distance_m": float(wp["desired_distance_m"]),
                "planned_distance_m": float(wp["planned_distance_m"]),
                "waypoint_distance_error_m": float(wp["waypoint_distance_error_m"]),
                "within_tolerance": bool(wp["within_tolerance"]),
                "pose_name": wp["pose_name"],
                "alignment_angle_deg": float(wp["alignment_angle_deg"]),
                "joint_positions_rad": wp["joint_positions"].tolist(),
            }
            for wp in planned_waypoints
        ],
        "missing_or_out_of_tolerance_waypoints": [wp["label"] for wp in planned_waypoints if not wp["within_tolerance"]],
        "planner_samples": int(args.planner_samples),
        "forward_angle_threshold_deg": float(args.forward_angle_threshold_deg),
        "max_waypoint_error_m": float(args.max_waypoint_error_m),
        "commanded_steps": int(sim_step),
        "captured_samples": len(rows),
        "min_required_samples": int(args.min_samples),
        "max_observed_ee_motion_m": max_motion,
        "target_distance_min_m": distance_min,
        "target_distance_max_m": distance_max,
        "amplitude_max_min": amplitude_max_min,
        "amplitude_max_max": amplitude_max_max,
        "parse_errors": writer_state["parse_errors"],
        "raw_empty_frames": writer_state["raw_empty_frames"],
        "csv_path": csv_path,
        "output_stage": args.output_stage,
    }
    summary_path = args.output_dir / "official_asset_ur10_distance_waypoint_acoustic_summary.json"
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stage.GetRootLayer().Export(str(args.output_stage))

    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print(f"Captured samples: {len(rows)}/{sim_step}")
    print(f"Max observed ee_link motion: {max_motion:.6f} m")
    print(f"Target distance range: [{distance_min:.6f}, {distance_max:.6f}] m")
    print(f"Requested distance waypoints: {[float(v) for v in args.distance_waypoints]}")
    print("Out-of-tolerance waypoints: " + str([wp["label"] for wp in planned_waypoints if not wp["within_tolerance"]]))
    print(f"Amplitude max range: [{amplitude_max_min:.6f}, {amplitude_max_max:.6f}]")
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
