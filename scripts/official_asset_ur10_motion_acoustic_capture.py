"""Isaac Sim 6.0 official UR10 motion-controlled RTX Acoustic capture.

This is the thesis-facing bridge between the static acoustic smoke and a real
robot experiment:

- load the Isaac Sim 6.0 packaged UR10 asset
- parent `OmniAcoustic` under `/World/ur10/ee_link`
- keep one fixed world target
- command several UR10 joint poses
- after each pose settles, capture GenericModelOutput from the ee-mounted sensor
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
    parser = argparse.ArgumentParser(description="Official UR10 ee_link motion-controlled RTX Acoustic capture.")
    parser.add_argument("--output-dir", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_motion_acoustic"))
    parser.add_argument("--output-stage", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10_official_asset_motion_acoustic.usda"))
    parser.add_argument("--end-effector-frame", choices=("ee_link",), default="ee_link")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--settle-steps", type=int, default=80)
    parser.add_argument("--capture-frames", type=int, default=80)
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument("--tick-rate", type=float, default=20.0)
    parser.add_argument("--center-frequency", type=float, default=40000.0)
    parser.add_argument("--sensor-local-offset", type=float, nargs=3, default=(0.08, 0.0, 0.0))
    parser.add_argument("--fixed-target-position", type=float, nargs=3, default=(0.8, 0.16, 0.05))
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


def summarize_raw(raw: Any) -> dict[str, Any]:
    summary = {"python_type": type(raw).__name__, "repr": repr(raw)[:240]}
    for name in ("shape", "dtype", "device", "size", "ndim"):
        if hasattr(raw, name):
            summary[name] = str(getattr(raw, name))
    return summary


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

    print(f"Motion acoustic: loading {official_ur10_usd}", flush=True)
    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=robot_path)
    for _ in range(20):
        simulation_app.update()

    if not stage.GetPrimAtPath(ee_path):
        simulation_app.close()
        raise RuntimeError(f"End-effector frame not found: {ee_path}")

    Cube("/World/room/floor", positions=np.array([1.5, 0.0, -0.025]), scales=np.array([4.0, 3.0, 0.05]))
    Cube("/World/fixed_target", positions=np.array(fixed_target_position, dtype=float), scales=np.array([0.25, 0.25, 0.10]))

    print(f"Motion acoustic: creating Acoustic at {sensor_path}", flush=True)
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

    acoustic_prim.CreateAttribute("research:officialMethod", Sdf.ValueTypeNames.String, custom=True).Set("isaacsim.sensors.experimental.rtx.Acoustic")
    acoustic_prim.CreateAttribute("research:assetSource", Sdf.ValueTypeNames.String, custom=True).Set(official_ur10_usd)
    acoustic_prim.CreateAttribute("research:endEffectorFrame", Sdf.ValueTypeNames.String, custom=True).Set(ee_path)
    acoustic_prim.CreateAttribute("research:fixedTargetPositionM", Sdf.ValueTypeNames.Double3, custom=True).Set(fixed_target_position)

    writer_state: dict[str, Any] = {
        "active_pose": None,
        "pose_frame": 0,
        "pose_data": {},
        "raw_samples": {},
        "parse_errors": {},
        "writer_calls": 0,
    }

    def summarize_gmo(gmo, pose_name: str, frame: int) -> dict[str, Any] | None:
        n = int(gmo.numElements)
        if n <= 0:
            return None
        amplitudes = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
        finite = amplitudes[np.isfinite(amplitudes)]
        return {
            "pose_name": pose_name,
            "capture_frame": int(frame),
            "num_elements": n,
            "timestamp_ns": int(gmo.timestampNs),
            "amplitude_min": float(np.min(finite)) if finite.size else math.nan,
            "amplitude_max": float(np.max(finite)) if finite.size else math.nan,
            "amplitude_mean": float(np.mean(finite)) if finite.size else math.nan,
            "amplitude_std": float(np.std(finite)) if finite.size else math.nan,
        }

    class MotionAcousticWriter(Writer):
        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]

        def write(self, data):
            writer_state["writer_calls"] += 1
            pose_name = writer_state.get("active_pose")
            if not pose_name or pose_name in writer_state["pose_data"]:
                return
            for _rp_name, rp_data in data.get("renderProducts", {}).items():
                gmo_raw = rp_data.get("GenericModelOutput")
                if isinstance(gmo_raw, dict):
                    gmo_raw = gmo_raw.get("data")
                if gmo_raw is None:
                    continue
                writer_state["raw_samples"].setdefault(pose_name, summarize_raw(gmo_raw))
                raw_summary = summarize_raw(gmo_raw)
                if raw_summary.get("size") == "0" or raw_summary.get("shape") == "(0,)":
                    continue
                try:
                    gmo = parse_generic_model_output_data(gmo_raw)
                except Exception as exc:
                    writer_state["parse_errors"].setdefault(pose_name, str(exc))
                    continue
                summary = summarize_gmo(gmo, pose_name, int(writer_state["pose_frame"]))
                if summary is not None:
                    writer_state["pose_data"][pose_name] = summary
                    break

    rep.WriterRegistry.register(MotionAcousticWriter)
    sensor.attach_writer("MotionAcousticWriter")

    world = World()
    robot = world.scene.add(Robot(prim_path=robot_path, name="ur10"))
    world.reset()

    rows: list[dict[str, Any]] = []
    cache = UsdGeom.XformCache(0)
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    for pose_index, (pose_name, requested_q) in enumerate(POSES_RAD.items()):
        requested = np.array(requested_q, dtype=float)
        print(f"Motion acoustic: commanding pose {pose_index}: {pose_name} q={requested.tolist()}", flush=True)
        robot.set_joint_positions(requested)

        for _ in range(max(1, int(args.settle_steps))):
            world.step(render=bool(args.gui))
        for _ in range(5):
            simulation_app.update()

        actual_q = np.asarray(robot.get_joint_positions(), dtype=float)
        writer_state["active_pose"] = pose_name
        writer_state["pose_frame"] = 0

        for frame in range(max(1, int(args.capture_frames))):
            writer_state["pose_frame"] = frame
            simulation_app.update()
            if pose_name in writer_state["pose_data"]:
                break

        cache.Clear()
        ee_prim = stage.GetPrimAtPath(ee_path)
        sensor_prim = stage.GetPrimAtPath(sensor_path)
        ee_matrix = cache.GetLocalToWorldTransform(ee_prim)
        sensor_matrix = cache.GetLocalToWorldTransform(sensor_prim)
        ee_position = vec_tuple(ee_matrix.ExtractTranslation())
        ee_forward = vec_tuple(ee_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized())
        sensor_position = vec_tuple(sensor_matrix.ExtractTranslation())
        sensor_forward = vec_tuple(sensor_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized())
        target_direction = vec_sub(fixed_target_position, sensor_position)
        target_distance = vec_norm(target_direction)
        target_unit = vec_unit(target_direction)
        alignment_dot = vec_dot(sensor_forward, target_unit)
        alignment_angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, alignment_dot))))

        marker_path = f"/World/motion_markers/{pose_name}"
        Cube(marker_path, positions=np.array(ee_position, dtype=float), scales=np.array([0.05, 0.05, 0.05]))

        gmo = writer_state["pose_data"].get(pose_name)
        row = {
            "pose_index": pose_index,
            "pose_name": pose_name,
            "pass": bool(gmo is not None),
            "requested_joint_positions_rad": ";".join(f"{v:.9g}" for v in requested.tolist()),
            "actual_joint_positions_rad": ";".join(f"{v:.9g}" for v in actual_q.tolist()),
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
            "num_elements": gmo["num_elements"] if gmo else 0,
            "amplitude_min": gmo["amplitude_min"] if gmo else "",
            "amplitude_max": gmo["amplitude_max"] if gmo else "",
            "amplitude_mean": gmo["amplitude_mean"] if gmo else "",
            "amplitude_std": gmo["amplitude_std"] if gmo else "",
            "capture_frame": gmo["capture_frame"] if gmo else "",
        }
        rows.append(row)
        print(
            "Motion acoustic: "
            f"{pose_name} pass={row['pass']} distance={target_distance:.4f} "
            f"angle={alignment_angle_deg:.2f} amp_max={row['amplitude_max']}",
            flush=True,
        )

    timeline.stop()
    try:
        rep.orchestrator.wait_until_complete()
    except Exception as exc:
        writer_state["orchestrator_wait_error"] = str(exc)

    max_motion = 0.0
    if rows:
        positions = [(float(r["ee_x_m"]), float(r["ee_y_m"]), float(r["ee_z_m"])) for r in rows]
        for i, pos_a in enumerate(positions):
            for pos_b in positions[i + 1 :]:
                max_motion = max(max_motion, distance(pos_a, pos_b))

    api_schemas = token_list_op_items(acoustic_prim.GetMetadata("apiSchemas"))
    sensor_parent_ok = sensor_path.startswith(f"{ee_path}/")
    all_poses_captured = all(bool(r["pass"]) for r in rows)
    passed = (
        len(rows) == len(POSES_RAD)
        and all_poses_captured
        and max_motion >= float(args.min_ee_motion_m)
        and acoustic_prim.GetTypeName() == "OmniAcoustic"
        and "OmniSensorGenericAcousticWpmAPI" in api_schemas
        and sensor_parent_ok
    )

    csv_path = args.output_dir / "official_asset_ur10_motion_acoustic_capture.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
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
        "pose_count": len(rows),
        "all_poses_captured": all_poses_captured,
        "min_required_ee_motion_m": float(args.min_ee_motion_m),
        "max_observed_ee_motion_m": max_motion,
        "writer_calls": writer_state["writer_calls"],
        "parse_errors": writer_state["parse_errors"],
        "csv_path": csv_path,
        "output_stage": args.output_stage,
        "poses": rows,
    }
    summary_path = args.output_dir / "official_asset_ur10_motion_acoustic_capture_summary.json"
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stage.GetRootLayer().Export(str(args.output_stage))

    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print(f"Captured poses: {sum(bool(r['pass']) for r in rows)}/{len(rows)}")
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
