"""Official Isaac Sim 6.0 RTX Acoustic smoke test for the UR10 EE scene.

This script intentionally uses the current Isaac Sim 6.0 RTX Acoustic API:
`isaacsim.sensors.experimental.rtx.Acoustic`, `AcousticSensor`, and
`parse_generic_model_output_data`. It follows the Isaac Sim 6.0 standalone
acoustic examples by collecting GenericModelOutput through a Replicator Writer.
It does not use deprecated Ultrasonic/USS commands or raw GMO pointer readers.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

from isaacsim import SimulationApp

PROJECT_ROOT = Path(
    os.environ.get("ISAAC_ACOUSTIC_PROJECT", "/home/lab109/song/isaac_acoustic_research")
)
DEFAULT_INPUT_SCENE = PROJECT_ROOT / "scenes/ur10_ee_articulated_debug/ur10_ee_articulated_debug_1m.usda"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results/official_rtx_acoustic_smoke"
DEFAULT_OUTPUT_STAGE = PROJECT_ROOT / "scenes/rtx_acoustic_official_smoke/ur10_official_acoustic_smoke.usda"

TOOL_LINK_PATH = (
    "/World/ur10/Geometry/base_link/shoulder_link/upper_arm_link/forearm_link/"
    "wrist_1_link/wrist_2_link/wrist_3_link"
)
SENSOR_PATH = f"{TOOL_LINK_PATH}/official_rtx_acoustic"
DEBUG_SENSOR_MARKER_PATH = f"{TOOL_LINK_PATH}/ee_acoustic_sensor_body"
DEBUG_MARKER_PATHS = (
    DEBUG_SENSOR_MARKER_PATH,
    "/World/tool_frame_marker",
)
SENSOR_LOCAL_OFFSET = (0.08, 0.0, 0.0)
SENSOR_MOUNT_SPACING_M = 0.10

OFFICIAL_DOCS = (
    "https://docs.isaacsim.omniverse.nvidia.com/latest/sensors/isaacsim_sensors_rtx_acoustic.html",
    "https://docs.isaacsim.omniverse.nvidia.com/latest/migration_guides/isaac_sim_6_0/sensors_rtx_to_experimental_rtx.html",
    "https://docs.isaacsim.omniverse.nvidia.com/latest/sensors/isaacsim_sensors_rtx_annotators.html",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run official RTX Acoustic smoke test on the UR10 EE scene.")
    parser.add_argument("--input-scene", type=Path, default=DEFAULT_INPUT_SCENE)
    parser.add_argument(
        "--scene-mode",
        choices=("articulated", "procedural"),
        default="articulated",
        help="Use the full articulated debug USD or a lightweight procedural UR10 wrist-path smoke scene.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-stage", type=Path, default=DEFAULT_OUTPUT_STAGE)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--tick-rate", type=float, default=20.0)
    parser.add_argument("--center-frequency", type=float, default=40000.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--gui", action="store_true", help="Run SimulationApp in non-headless GUI mode.")
    parser.add_argument("--keep-open-seconds", type=float, default=0.0, help="Keep the GUI open after writing reports.")
    parser.add_argument("--max-runtime-seconds", type=float, default=300.0, help="Stop frame loop after this many seconds.")
    parser.add_argument("--progress-interval", type=int, default=10, help="Print frame-loop progress every N frames.")
    parser.add_argument(
        "--max-direct-parse-errors",
        type=int,
        default=3,
        help="Stop direct raw-buffer parsing after this many parser failures.",
    )
    parser.add_argument(
        "--gui-use-timeline",
        action="store_true",
        help="Start timeline.play() in GUI mode (matches minimal runtime probe PASS pattern).",
    )
    return parser.parse_args()


def vec_tuple(values: Any) -> tuple[float, float, float]:
    return tuple(float(values[i]) for i in range(3))


def fmt_vec(values: Any) -> str:
    return "[" + ", ".join(f"{float(v):.6g}" for v in values) + "]"


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


def prim_type_and_apis(prim) -> tuple[str, list[str]]:
    api_attr = prim.GetMetadata("apiSchemas")
    return prim.GetTypeName(), token_list_op_items(api_attr)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def summarize_raw(raw: Any) -> dict[str, Any]:
    summary = {"python_type": type(raw).__name__, "repr": repr(raw)[:240]}
    for name in ("shape", "dtype", "device", "size", "ndim"):
        if hasattr(raw, name):
            try:
                summary[name] = str(getattr(raw, name))
            except Exception as exc:  # pragma: no cover - diagnostic only
                summary[name] = f"<error: {exc}>"
    return summary


def main() -> None:
    args = parse_args()
    if args.scene_mode == "articulated" and not args.input_scene.exists():
        raise SystemExit(f"Input scene not found: {args.input_scene}")
    if args.output_stage.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output_stage}; pass --overwrite")

    print(
        f"UR10 smoke starting: gui={bool(args.gui)} input_scene={args.input_scene} frames={int(args.frames)}",
        flush=True,
    )

    simulation_app = SimulationApp({"headless": not bool(args.gui)})

    import numpy as np  # noqa: E402
    import omni  # noqa: E402
    import time  # noqa: E402
    import omni.replicator.core as rep  # noqa: E402
    from isaacsim.core.experimental.objects import Cube  # noqa: E402
    from isaacsim.sensors.experimental.rtx import (  # noqa: E402
        Acoustic,
        AcousticSensor,
        parse_generic_model_output_data,
    )
    from omni.replicator.core import Writer  # noqa: E402
    from pxr import Gf, Sdf, UsdGeom, Vt  # noqa: E402

    print("UR10 smoke: Isaac imports loaded", flush=True)

    def set_custom(prim, name: str, type_name, value) -> None:
        attr = prim.CreateAttribute(f"research:{name}", type_name, custom=True)
        attr.Set(value)

    def summarize_gmo(gmo, frame: int) -> dict[str, Any] | None:
        n = int(gmo.numElements)
        if n <= 0:
            return None

        tx_ids = np.ctypeslib.as_array(gmo.x, shape=(n,))
        rx_ids = np.ctypeslib.as_array(gmo.y, shape=(n,))
        ch_ids = np.ctypeslib.as_array(gmo.z, shape=(n,))
        amplitudes = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
        finite_amplitudes = amplitudes[np.isfinite(amplitudes)]
        if finite_amplitudes.size == 0:
            amp_min = amp_max = amp_mean = amp_std = math.nan
        else:
            amp_min = float(np.min(finite_amplitudes))
            amp_max = float(np.max(finite_amplitudes))
            amp_mean = float(np.mean(finite_amplitudes))
            amp_std = float(np.std(finite_amplitudes))

        ways: dict[str, int] = {}
        sample_limit = min(n, 10000)
        for i in range(sample_limit):
            key = f"tx={int(tx_ids[i])},rx={int(rx_ids[i])},ch={int(ch_ids[i])}"
            ways[key] = ways.get(key, 0) + 1

        return {
            "frame": int(frame),
            "num_elements": n,
            "timestamp_ns": int(gmo.timestampNs),
            "unique_transmitter_ids": [int(x) for x in np.unique(tx_ids).tolist()],
            "unique_receiver_ids": [int(x) for x in np.unique(rx_ids).tolist()],
            "unique_channel_ids": [int(x) for x in np.unique(ch_ids).tolist()],
            "amplitude_min": amp_min,
            "amplitude_max": amp_max,
            "amplitude_mean": amp_mean,
            "amplitude_std": amp_std,
            "signal_way_sample_counts": ways,
        }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.output_stage.parent.mkdir(parents=True, exist_ok=True)

    context = omni.usd.get_context()
    if args.scene_mode == "procedural":
        print("UR10 smoke: building procedural UR10 wrist smoke scene", flush=True)
        opened = True
        stage = context.get_stage()
        if stage is None:
            context.new_stage()
            stage = context.get_stage()
        if stage is None:
            simulation_app.close()
            raise RuntimeError("Failed to create procedural stage")
        current_path = ""
        for part in TOOL_LINK_PATH.strip("/").split("/"):
            current_path = f"{current_path}/{part}" if current_path else f"/{part}"
            UsdGeom.Xform.Define(stage, current_path)
        Cube("/World/target_near", positions=np.array([1.0, 0.0, 0.0]), scales=np.array([0.5, 0.5, 0.5]))
        Cube("/World/target_far", positions=np.array([5.0, 0.0, 0.0]), scales=np.array([2.0, 2.0, 2.0]))
    else:
        print(f"UR10 smoke: opening input scene {args.input_scene}", flush=True)
        opened = context.open_stage(str(args.input_scene))
        print(f"UR10 smoke: open_stage returned {opened}", flush=True)
        stage = context.get_stage()
        if stage is None or not args.gui:
            print("UR10 smoke: settling opened stage", flush=True)
            for _ in range(3):
                simulation_app.update()
            stage = context.get_stage()
    print(f"UR10 smoke: stage available={stage is not None}", flush=True)
    if not opened or stage is None:
        simulation_app.close()
        raise RuntimeError(f"Failed to open input scene: {args.input_scene}")

    tool_prim = stage.GetPrimAtPath(TOOL_LINK_PATH)
    if not tool_prim:
        simulation_app.close()
        raise RuntimeError(f"Tool link candidate not found: {TOOL_LINK_PATH}")

    deactivated_markers: list[str] = []
    for path in DEBUG_MARKER_PATHS:
        prim = stage.GetPrimAtPath(path)
        if prim:
            prim.SetActive(False)
            deactivated_markers.append(path)

    existing_sensor = stage.GetPrimAtPath(SENSOR_PATH)
    if existing_sensor:
        stage.RemovePrim(SENSOR_PATH)

    cache = UsdGeom.XformCache(0)
    tool_matrix = cache.GetLocalToWorldTransform(tool_prim)
    tool_position = vec_tuple(tool_matrix.ExtractTranslation())
    forward = tool_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()
    forward_tuple = vec_tuple(forward)

    print("UR10 smoke: creating official Acoustic prim", flush=True)
    acoustic = Acoustic(
        SENSOR_PATH,
        tick_rate=float(args.tick_rate),
        aux_output_level="BASIC",
        translations=np.array(SENSOR_LOCAL_OFFSET, dtype=float),
        attributes={
            "omni:sensor:WpmAcoustic:centerFrequency": float(args.center_frequency),
            "omni:sensor:WpmAcoustic:sensorMount:m001:position": (0.0, 0.0, 0.0),
            "omni:sensor:WpmAcoustic:sensorMount:m001:rotation": (0.0, 0.0, 0.0),
            "omni:sensor:WpmAcoustic:sensorMount:m002:position": (SENSOR_MOUNT_SPACING_M, 0.0, 0.0),
            "omni:sensor:WpmAcoustic:sensorMount:m002:rotation": (0.0, 0.0, 0.0),
            "omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices": [0, 1],
        },
    )
    sensor = AcousticSensor(acoustic, annotators=["generic-model-output"], render_vars=["GenericModelOutput"])
    print("UR10 smoke: AcousticSensor runtime wrapper created", flush=True)

    acoustic_prim = stage.GetPrimAtPath(SENSOR_PATH)
    if not acoustic_prim:
        simulation_app.close()
        raise RuntimeError(f"Acoustic prim was not created: {SENSOR_PATH}")

    set_custom(acoustic_prim, "officialMethod", Sdf.ValueTypeNames.String, "isaacsim.sensors.experimental.rtx.Acoustic")
    set_custom(acoustic_prim, "officialRuntime", Sdf.ValueTypeNames.String, "AcousticSensor + GenericModelOutput Writer")
    set_custom(acoustic_prim, "parser", Sdf.ValueTypeNames.String, "parse_generic_model_output_data")
    set_custom(acoustic_prim, "inputScene", Sdf.ValueTypeNames.String, str(args.input_scene))
    set_custom(acoustic_prim, "toolLinkCandidate", Sdf.ValueTypeNames.String, TOOL_LINK_PATH)
    set_custom(acoustic_prim, "sensorLocalOffsetM", Sdf.ValueTypeNames.Double3, SENSOR_LOCAL_OFFSET)
    set_custom(acoustic_prim, "toolPositionM", Sdf.ValueTypeNames.Double3, tool_position)
    set_custom(acoustic_prim, "toolForwardVector", Sdf.ValueTypeNames.Double3, forward_tuple)
    set_custom(acoustic_prim, "deactivatedDebugMarkers", Sdf.ValueTypeNames.StringArray, Vt.StringArray(deactivated_markers))

    sensor_matrix = cache.GetLocalToWorldTransform(acoustic_prim)
    sensor_position = vec_tuple(sensor_matrix.ExtractTranslation())
    set_custom(acoustic_prim, "sensorWorldPositionM", Sdf.ValueTypeNames.Double3, sensor_position)

    try:
        render_product_path = str(sensor.render_product.GetPath())
    except Exception as exc:  # pragma: no cover - diagnostic smoke path
        render_product_path = f"<unavailable: {exc}>"
    print(f"UR10 smoke: render product path {render_product_path}", flush=True)

    writer_state: dict[str, Any] = {
        "first_gmo_data": None,
        "first_gmo_source": None,
        "parse_errors": [],
        "direct_parse_errors": [],
        "frames_seen": 0,
        "writer_calls": 0,
        "writer_empty_frames": 0,
        "writer_missing_render_products": 0,
        "writer_missing_gmo": 0,
        "direct_poll_frames": 0,
        "direct_empty_frames": 0,
        "direct_missing_frames": 0,
        "direct_parse_error_count": 0,
        "direct_parse_skipped_after_errors": 0,
        "raw_zero_length_frames": 0,
        "raw_samples": [],
        "timed_out": False,
        "orchestrator_wait_error": None,
    }

    class OfficialUr10AcousticSmokeWriter(Writer):
        """Writer matching the official Isaac Sim RTX Acoustic standalone examples."""

        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]
            self._frame_count = 0

        def write(self, data):
            writer_state["frames_seen"] = self._frame_count
            writer_state["writer_calls"] += 1
            if writer_state["first_gmo_data"] is not None:
                self._frame_count += 1
                return
            if "renderProducts" not in data:
                writer_state["writer_missing_render_products"] += 1
                self._frame_count += 1
                return
            saw_gmo = False
            for _rp_name, rp_data in data["renderProducts"].items():
                gmo_raw = rp_data.get("GenericModelOutput")
                if isinstance(gmo_raw, dict):
                    gmo_raw = gmo_raw.get("data")
                if gmo_raw is None:
                    continue
                saw_gmo = True
                if len(writer_state["raw_samples"]) < 3:
                    writer_state["raw_samples"].append({"source": "writer", **summarize_raw(gmo_raw)})
                raw_summary = summarize_raw(gmo_raw)
                if raw_summary.get("size") == "0" or raw_summary.get("shape") == "(0,)":
                    writer_state["raw_zero_length_frames"] += 1
                    writer_state["writer_empty_frames"] += 1
                    continue
                try:
                    gmo = parse_generic_model_output_data(gmo_raw)
                except Exception as exc:  # pragma: no cover - defensive in smoke script
                    if len(writer_state["parse_errors"]) < 5:
                        writer_state["parse_errors"].append(str(exc))
                    continue
                summary = summarize_gmo(gmo, self._frame_count)
                if summary is not None:
                    writer_state["first_gmo_data"] = summary
                    writer_state["first_gmo_source"] = "writer"
                    break
                writer_state["writer_empty_frames"] += 1
            if not saw_gmo:
                writer_state["writer_missing_gmo"] += 1
            self._frame_count += 1

    rep.WriterRegistry.register(OfficialUr10AcousticSmokeWriter)
    sensor.attach_writer("OfficialUr10AcousticSmokeWriter")
    print("UR10 smoke: writer attached", flush=True)

    timeline = omni.timeline.get_timeline_interface()
    timeline_started = False
    if args.gui and not args.gui_use_timeline:
        print("UR10 smoke: GUI mode using app-update loop without timeline.play", flush=True)
    else:
        print("UR10 smoke: starting timeline", flush=True)
        timeline.play()
        timeline_started = True
    start_time = time.time()
    for frame in range(max(1, int(args.frames))):
        if args.max_runtime_seconds > 0 and time.time() - start_time > float(args.max_runtime_seconds):
            writer_state["timed_out"] = True
            print(f"UR10 smoke timeout after {time.time() - start_time:.1f}s at frame {frame}")
            break
        simulation_app.update()
        if args.progress_interval > 0 and frame % int(args.progress_interval) == 0:
            print(
                f"ur10 smoke frame={frame}/{int(args.frames)} "
                f"direct_empty={writer_state['direct_empty_frames']} "
                f"raw_zero={writer_state['raw_zero_length_frames']} "
                f"writer_calls={writer_state['writer_calls']}"
            )
        if writer_state["first_gmo_data"] is not None:
            break
        writer_state["direct_poll_frames"] += 1
        try:
            gmo_raw, _info = sensor.get_data("generic-model-output")
        except Exception as exc:  # pragma: no cover - diagnostic smoke path
            if len(writer_state["direct_parse_errors"]) < 5:
                writer_state["direct_parse_errors"].append(f"get_data: {exc}")
            continue
        if gmo_raw is None:
            writer_state["direct_missing_frames"] += 1
            continue
        raw_summary = summarize_raw(gmo_raw)
        if len(writer_state["raw_samples"]) < 3:
            writer_state["raw_samples"].append({"source": "direct", **raw_summary})
        if raw_summary.get("size") == "0" or raw_summary.get("shape") == "(0,)":
            writer_state["raw_zero_length_frames"] += 1
            writer_state["direct_empty_frames"] += 1
            continue
        if writer_state["direct_parse_error_count"] >= int(args.max_direct_parse_errors):
            writer_state["direct_parse_skipped_after_errors"] += 1
            continue
        try:
            gmo = parse_generic_model_output_data(gmo_raw)
        except Exception as exc:  # pragma: no cover - diagnostic smoke path
            writer_state["direct_parse_error_count"] += 1
            if len(writer_state["direct_parse_errors"]) < 5:
                writer_state["direct_parse_errors"].append(f"parse: {exc}")
            continue
        summary = summarize_gmo(gmo, frame)
        if summary is None:
            writer_state["direct_empty_frames"] += 1
            continue
        writer_state["first_gmo_data"] = summary
        writer_state["first_gmo_source"] = "direct_annotator"
        break
    if timeline_started:
        timeline.stop()
    try:
        rep.orchestrator.wait_until_complete()
    except Exception as exc:  # pragma: no cover - diagnostic smoke path
        writer_state["orchestrator_wait_error"] = str(exc)
    for _ in range(2):
        simulation_app.update()

    stage.GetRootLayer().Export(str(args.output_stage))

    prim_type, api_schemas = prim_type_and_apis(acoustic_prim)
    attrs_to_check = {
        "center_frequency_hz": "omni:sensor:WpmAcoustic:centerFrequency",
        "mount_m001_position": "omni:sensor:WpmAcoustic:sensorMount:m001:position",
        "mount_m002_position": "omni:sensor:WpmAcoustic:sensorMount:m002:position",
        "rx_group_g001_indices": "omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices",
        "tick_rate": "omni:sensor:tickRate",
    }
    attr_values: dict[str, Any] = {}
    for key, attr_name in attrs_to_check.items():
        attr = acoustic_prim.GetAttribute(attr_name)
        attr_values[key] = attr.Get() if attr else None

    first_data = writer_state["first_gmo_data"]
    passed = first_data is not None and prim_type == "OmniAcoustic" and "OmniSensorGenericAcousticWpmAPI" in api_schemas
    summary = {
        "pass": bool(passed),
        "input_scene": args.input_scene,
        "scene_mode": args.scene_mode,
        "output_stage": args.output_stage,
        "official_docs": OFFICIAL_DOCS,
        "sensor_path": SENSOR_PATH,
        "sensor_prim_type": prim_type,
        "sensor_api_schemas": api_schemas,
        "runtime_collection": "AcousticSensor(annotators=['generic-model-output'], render_vars=['GenericModelOutput']) + attach_writer",
        "render_product_path": render_product_path,
        "tool_link_candidate": TOOL_LINK_PATH,
        "tool_position_m": tool_position,
        "tool_forward_vector": forward_tuple,
        "sensor_local_offset_m": SENSOR_LOCAL_OFFSET,
        "sensor_world_position_m": sensor_position,
        "deactivated_debug_markers": deactivated_markers,
        "attribute_values": attr_values,
        "frames_requested": int(args.frames),
        "gui_mode": bool(args.gui),
        "keep_open_seconds": float(args.keep_open_seconds),
        "max_runtime_seconds": float(args.max_runtime_seconds),
        "progress_interval": int(args.progress_interval),
        "max_direct_parse_errors": int(args.max_direct_parse_errors),
        "frames_seen_by_writer": writer_state["frames_seen"],
        "writer_calls": writer_state["writer_calls"],
        "writer_empty_frames": writer_state["writer_empty_frames"],
        "writer_missing_render_products": writer_state["writer_missing_render_products"],
        "writer_missing_gmo": writer_state["writer_missing_gmo"],
        "direct_poll_frames": writer_state["direct_poll_frames"],
        "direct_empty_frames": writer_state["direct_empty_frames"],
        "direct_missing_frames": writer_state["direct_missing_frames"],
        "direct_parse_error_count": writer_state["direct_parse_error_count"],
        "direct_parse_skipped_after_errors": writer_state["direct_parse_skipped_after_errors"],
        "raw_zero_length_frames": writer_state["raw_zero_length_frames"],
        "raw_samples": writer_state["raw_samples"],
        "timed_out": writer_state["timed_out"],
        "first_gmo_source": writer_state["first_gmo_source"],
        "orchestrator_wait_error": writer_state["orchestrator_wait_error"],
        "parse_errors": writer_state["parse_errors"],
        "direct_parse_errors": writer_state["direct_parse_errors"],
        "first_gmo_data": first_data,
    }

    summary_path = args.output_dir / "official_rtx_acoustic_ur10_smoke_summary.json"
    report_path = args.output_dir / "OFFICIAL_RTX_ACOUSTIC_UR10_SMOKE_REPORT.md"
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    status = "PASS" if passed else "FAIL"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("# Official RTX Acoustic UR10 Smoke Report\n\n")
        f.write(f"Status: **{status}**\n\n")
        f.write("## Official Method\n\n")
        f.write("This smoke test uses `isaacsim.sensors.experimental.rtx.Acoustic`, `AcousticSensor`, ")
        f.write("a GenericModelOutput Writer/direct annotator probe, and `parse_generic_model_output_data`, matching the ")
        f.write("Isaac Sim 6.0 standalone acoustic examples.\n\n")
        f.write("It does not use deprecated Ultrasonic/USS commands or old raw-GMO pointer readers.\n\n")
        f.write("## Files\n\n")
        f.write(f"- input scene: `{args.input_scene}`\n")
        f.write(f"- scene mode: `{args.scene_mode}`\n")
        f.write(f"- output stage: `{args.output_stage}`\n")
        f.write(f"- JSON summary: `{summary_path}`\n\n")
        f.write("## Runtime Mode\n\n")
        f.write(f"- GUI mode: `{bool(args.gui)}`\n")
        f.write(f"- frames requested: `{int(args.frames)}`\n")
        f.write(f"- max runtime seconds: `{float(args.max_runtime_seconds)}`\n")
        f.write(f"- writer calls: `{writer_state['writer_calls']}`\n")
        f.write(f"- direct poll frames: `{writer_state['direct_poll_frames']}`\n")
        f.write(f"- direct empty frames: `{writer_state['direct_empty_frames']}`\n")
        f.write(f"- raw zero-length frames: `{writer_state['raw_zero_length_frames']}`\n")
        f.write(f"- timed out: `{writer_state['timed_out']}`\n\n")
        f.write("## Stage Checks\n\n")
        f.write("| Check | Value |\n")
        f.write("|---|---|\n")
        f.write(f"| sensor path | `{SENSOR_PATH}` |\n")
        f.write(f"| render product path | `{render_product_path}` |\n")
        f.write(f"| sensor prim type | `{prim_type}` |\n")
        f.write(f"| api schemas | `{api_schemas}` |\n")
        f.write(f"| tool link candidate | `{TOOL_LINK_PATH}` |\n")
        f.write(f"| tool position m | `{fmt_vec(tool_position)}` |\n")
        f.write(f"| sensor world position m | `{fmt_vec(sensor_position)}` |\n")
        f.write(f"| deactivated debug markers | `{deactivated_markers}` |\n\n")
        f.write("## GMO Data Check\n\n")
        if first_data is None:
            f.write("No non-empty GenericModelOutput frame was received.\n")
            if writer_state["parse_errors"]:
                f.write(f"\nParse errors: `{writer_state['parse_errors']}`\n")
            if writer_state["direct_parse_errors"]:
                f.write(f"\nDirect parse errors: `{writer_state['direct_parse_errors']}`\n")
            f.write(
                "\nRuntime diagnostics: "
                f"writer_calls={writer_state['writer_calls']}, "
                f"writer_missing_render_products={writer_state['writer_missing_render_products']}, "
                f"writer_missing_gmo={writer_state['writer_missing_gmo']}, "
                f"writer_empty_frames={writer_state['writer_empty_frames']}, "
                f"direct_poll_frames={writer_state['direct_poll_frames']}, "
                f"direct_missing_frames={writer_state['direct_missing_frames']}, "
                f"direct_empty_frames={writer_state['direct_empty_frames']}, "
                f"raw_zero_length_frames={writer_state['raw_zero_length_frames']}, "
                f"timed_out={writer_state['timed_out']}.\n"
            )
        else:
            f.write("| Field | Value |\n")
            f.write("|---|---|\n")
            f.write(f"| first frame | `{first_data['frame']}` |\n")
            f.write(f"| source | `{writer_state['first_gmo_source']}` |\n")
            f.write(f"| num elements | `{first_data['num_elements']}` |\n")
            f.write(f"| timestamp ns | `{first_data['timestamp_ns']}` |\n")
            f.write(f"| transmitter IDs | `{first_data['unique_transmitter_ids']}` |\n")
            f.write(f"| receiver IDs | `{first_data['unique_receiver_ids']}` |\n")
            f.write(f"| channel IDs | `{first_data['unique_channel_ids']}` |\n")
            f.write(f"| amplitude min | `{first_data['amplitude_min']:.8g}` |\n")
            f.write(f"| amplitude max | `{first_data['amplitude_max']:.8g}` |\n")
            f.write(f"| amplitude mean | `{first_data['amplitude_mean']:.8g}` |\n")
            f.write(f"| amplitude std | `{first_data['amplitude_std']:.8g}` |\n")
        f.write("\n## Boundary\n\n")
        f.write("This is a method smoke test, not the final formal experiment. ")
        if passed:
            f.write("It proves the current Isaac Sim 6.0 RTX Acoustic API can create a real ")
            f.write("`OmniAcoustic` sensor on the UR10 EE geometry and receive parsed GMO amplitude samples. ")
        else:
            f.write("It proves official `OmniAcoustic` authoring on the UR10 EE geometry, but it does not ")
            f.write("yet prove runtime GMO capture for this scene. ")
        f.write("Target geometry and non-visual material settings still need a controlled formal design.\n")

    print(f"Status: {status}")
    print(f"Wrote {report_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {args.output_stage}")
    if first_data is not None:
        print(f"GMO num elements: {first_data['num_elements']}")
        print(f"Amplitude range: [{first_data['amplitude_min']:.8g}, {first_data['amplitude_max']:.8g}]")
    elif writer_state["parse_errors"]:
        print(f"Parse errors: {writer_state['parse_errors']}")

    if args.gui and args.keep_open_seconds > 0:
        deadline = time.time() + float(args.keep_open_seconds)
        while simulation_app.is_running() and time.time() < deadline:
            simulation_app.update()

    simulation_app.close()

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
