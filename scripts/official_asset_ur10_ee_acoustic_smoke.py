"""Isaac Sim 6.0 official UR10 asset + ee_link RTX Acoustic smoke.

This is a migration smoke test from the project-local converted UR10 USD to
the Isaac Sim 6.0 packaged UR10 asset. The formal check is that the acoustic
sensor is an OmniAcoustic prim parented under the official end-effector frame
(`ee_link` by default), not under the old converted `wrist_3_link` path.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from isaacsim import SimulationApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official UR10 asset ee_link RTX Acoustic smoke.")
    parser.add_argument("--output-dir", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_smoke"))
    parser.add_argument("--output-stage", type=Path, default=Path("/home/lab109/song/isaacsim6.0/runtime/scenes/ur10_official_asset_ee_acoustic_smoke.usda"))
    parser.add_argument("--end-effector-frame", choices=("ee_link", "tool0"), default="ee_link")
    parser.add_argument("--frames", type=int, default=80)
    parser.add_argument("--tick-rate", type=float, default=20.0)
    parser.add_argument("--center-frequency", type=float, default=40000.0)
    parser.add_argument("--sensor-local-offset", type=float, nargs=3, default=(0.08, 0.0, 0.0))
    parser.add_argument("--target-distance", type=float, default=1.0)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-runtime-seconds", type=float, default=300.0)
    parser.add_argument("--progress-interval", type=int, default=10)
    return parser.parse_args()


def vec_tuple(values: Any) -> tuple[float, float, float]:
    return tuple(float(values[i]) for i in range(3))


def vec_add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_scale(v: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    return (v[0] * s, v[1] * s, v[2] * s)


def vec_norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


def vec_dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


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
    from isaacsim.core.experimental.objects import Cube  # noqa: E402
    from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor, parse_generic_model_output_data  # noqa: E402
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402
    from omni.replicator.core import Writer  # noqa: E402
    from pxr import Gf, Sdf, UsdGeom, Vt  # noqa: E402

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
    print(f"Official asset smoke: loading {official_ur10_usd}", flush=True)
    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=robot_path)
    for _ in range(10):
        simulation_app.update()

    ee_path = f"{robot_path}/{args.end_effector_frame}"
    ee_prim = stage.GetPrimAtPath(ee_path)
    if not ee_prim:
        existing = []
        for candidate in ("ee_link", "tool0", "wrist_3_link"):
            path = f"{robot_path}/{candidate}"
            if stage.GetPrimAtPath(path):
                existing.append(path)
        stage.GetRootLayer().Export(str(args.output_stage))
        simulation_app.close()
        raise RuntimeError(f"End-effector frame not found: {ee_path}; existing candidates={existing}")

    # Simple bounded scene. The target itself is the acoustic reflector.
    Cube("/World/room/floor", positions=np.array([2.0, 0.0, -0.025]), scales=np.array([4.0, 3.0, 0.05]))

    cache = UsdGeom.XformCache(0)
    ee_matrix = cache.GetLocalToWorldTransform(ee_prim)
    ee_position = vec_tuple(ee_matrix.ExtractTranslation())
    ee_forward = vec_tuple(ee_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized())

    sensor_path = f"{ee_path}/official_rtx_acoustic"
    if stage.GetPrimAtPath(sensor_path):
        stage.RemovePrim(sensor_path)

    print(f"Official asset smoke: creating Acoustic at {sensor_path}", flush=True)
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

    cache = UsdGeom.XformCache(0)
    sensor_matrix = cache.GetLocalToWorldTransform(acoustic_prim)
    sensor_position = vec_tuple(sensor_matrix.ExtractTranslation())
    sensor_forward = vec_tuple(sensor_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized())
    target_position = vec_add(sensor_position, vec_scale(sensor_forward, float(args.target_distance)))
    Cube("/World/target", positions=np.array(target_position, dtype=float), scales=np.array([0.3, 0.3, 0.3]))
    target_direction = vec_sub(target_position, sensor_position)
    target_direction_norm = vec_scale(target_direction, 1.0 / max(vec_norm(target_direction), 1e-12))
    alignment_dot = vec_dot(sensor_forward, target_direction_norm)
    alignment_angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, alignment_dot))))

    def set_custom(prim, name: str, type_name, value) -> None:
        attr = prim.CreateAttribute(f"research:{name}", type_name, custom=True)
        attr.Set(value)

    set_custom(acoustic_prim, "officialMethod", Sdf.ValueTypeNames.String, "isaacsim.sensors.experimental.rtx.Acoustic")
    set_custom(acoustic_prim, "assetSource", Sdf.ValueTypeNames.String, official_ur10_usd)
    set_custom(acoustic_prim, "endEffectorFrame", Sdf.ValueTypeNames.String, ee_path)
    set_custom(acoustic_prim, "sensorWorldPositionM", Sdf.ValueTypeNames.Double3, sensor_position)
    set_custom(acoustic_prim, "sensorForwardVector", Sdf.ValueTypeNames.Double3, sensor_forward)
    set_custom(acoustic_prim, "targetPositionM", Sdf.ValueTypeNames.Double3, target_position)
    set_custom(acoustic_prim, "targetDistanceM", Sdf.ValueTypeNames.Double, float(args.target_distance))
    set_custom(acoustic_prim, "alignmentDot", Sdf.ValueTypeNames.Double, alignment_dot)
    set_custom(acoustic_prim, "alignmentAngleDeg", Sdf.ValueTypeNames.Double, alignment_angle_deg)

    writer_state: dict[str, Any] = {
        "first_gmo_data": None,
        "writer_calls": 0,
        "writer_empty_frames": 0,
        "raw_zero_length_frames": 0,
        "parse_errors": [],
        "raw_samples": [],
        "timed_out": False,
    }

    def summarize_gmo(gmo, frame: int) -> dict[str, Any] | None:
        n = int(gmo.numElements)
        if n <= 0:
            return None
        amplitudes = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
        finite = amplitudes[np.isfinite(amplitudes)]
        return {
            "frame": int(frame),
            "num_elements": n,
            "timestamp_ns": int(gmo.timestampNs),
            "amplitude_min": float(np.min(finite)) if finite.size else math.nan,
            "amplitude_max": float(np.max(finite)) if finite.size else math.nan,
            "amplitude_mean": float(np.mean(finite)) if finite.size else math.nan,
            "amplitude_std": float(np.std(finite)) if finite.size else math.nan,
        }

    class OfficialAssetUr10AcousticWriter(Writer):
        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]
            self._frame_count = 0

        def write(self, data):
            writer_state["writer_calls"] += 1
            if writer_state["first_gmo_data"] is not None:
                self._frame_count += 1
                return
            for _rp_name, rp_data in data.get("renderProducts", {}).items():
                gmo_raw = rp_data.get("GenericModelOutput")
                if isinstance(gmo_raw, dict):
                    gmo_raw = gmo_raw.get("data")
                if gmo_raw is None:
                    continue
                if len(writer_state["raw_samples"]) < 3:
                    writer_state["raw_samples"].append({"source": "writer", **summarize_raw(gmo_raw)})
                raw_summary = summarize_raw(gmo_raw)
                if raw_summary.get("size") == "0" or raw_summary.get("shape") == "(0,)":
                    writer_state["raw_zero_length_frames"] += 1
                    writer_state["writer_empty_frames"] += 1
                    continue
                try:
                    gmo = parse_generic_model_output_data(gmo_raw)
                except Exception as exc:
                    if len(writer_state["parse_errors"]) < 5:
                        writer_state["parse_errors"].append(str(exc))
                    continue
                summary = summarize_gmo(gmo, self._frame_count)
                if summary is not None:
                    writer_state["first_gmo_data"] = summary
                    break
            self._frame_count += 1

    rep.WriterRegistry.register(OfficialAssetUr10AcousticWriter)
    sensor.attach_writer("OfficialAssetUr10AcousticWriter")

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    start_time = time.time()
    for frame in range(max(1, int(args.frames))):
        if args.max_runtime_seconds > 0 and time.time() - start_time > float(args.max_runtime_seconds):
            writer_state["timed_out"] = True
            break
        simulation_app.update()
        if args.progress_interval > 0 and frame % int(args.progress_interval) == 0:
            print(f"official asset smoke frame={frame}/{args.frames} writer_calls={writer_state['writer_calls']}", flush=True)
        if writer_state["first_gmo_data"] is not None:
            break
    timeline.stop()
    try:
        rep.orchestrator.wait_until_complete()
    except Exception as exc:
        writer_state["orchestrator_wait_error"] = str(exc)

    stage.GetRootLayer().Export(str(args.output_stage))

    api_schemas = token_list_op_items(acoustic_prim.GetMetadata("apiSchemas"))
    first_data = writer_state["first_gmo_data"]
    sensor_parent_ok = sensor_path.startswith(f"{ee_path}/")
    passed = (
        first_data is not None
        and acoustic_prim.GetTypeName() == "OmniAcoustic"
        and "OmniSensorGenericAcousticWpmAPI" in api_schemas
        and sensor_parent_ok
        and alignment_dot > 0.999
    )
    summary = {
        "pass": bool(passed),
        "official_ur10_asset": official_ur10_usd,
        "robot_path": robot_path,
        "end_effector_frame": ee_path,
        "sensor_path": sensor_path,
        "sensor_parent_ok": sensor_parent_ok,
        "sensor_prim_type": acoustic_prim.GetTypeName(),
        "sensor_api_schemas": api_schemas,
        "ee_position_m": ee_position,
        "ee_forward_vector": ee_forward,
        "sensor_world_position_m": sensor_position,
        "sensor_forward_vector": sensor_forward,
        "target_position_m": target_position,
        "target_distance_m": float(args.target_distance),
        "alignment_dot": alignment_dot,
        "alignment_angle_deg": alignment_angle_deg,
        "writer_calls": writer_state["writer_calls"],
        "writer_empty_frames": writer_state["writer_empty_frames"],
        "raw_zero_length_frames": writer_state["raw_zero_length_frames"],
        "raw_samples": writer_state["raw_samples"],
        "parse_errors": writer_state["parse_errors"],
        "timed_out": writer_state["timed_out"],
        "first_gmo_source": "writer" if first_data is not None else None,
        "first_gmo_data": first_data,
        "output_stage": args.output_stage,
    }
    summary_path = args.output_dir / "official_asset_ur10_ee_acoustic_smoke_summary.json"
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {args.output_stage}")
    print(f"Sensor path: {sensor_path}")
    print(f"Alignment dot: {alignment_dot:.9f}, angle deg: {alignment_angle_deg:.6f}")
    if first_data is not None:
        print(f"GMO num elements: {first_data['num_elements']}")
        print(f"Amplitude range: [{first_data['amplitude_min']:.8g}, {first_data['amplitude_max']:.8g}]")

    if args.gui and args.keep_open_seconds > 0:
        deadline = time.time() + float(args.keep_open_seconds)
        while simulation_app.is_running() and time.time() < deadline:
            simulation_app.update()

    simulation_app.close()
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
