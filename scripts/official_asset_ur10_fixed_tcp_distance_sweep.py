"""Isaac Sim 6.0 official UR10 fixed-TCP distance-sweep RTX Acoustic capture.

Phase 1 formal experiment (Geometry Passport v1.0):
- Solve one conservative TCP pose (~0.80 m radius, 0.65 m height).
- Lock UR10 joints for the entire run.
- Move only the acoustic target along the settled sensor +X axis.
- Capture GenericModelOutput at each requested sensor-target distance.

This replaces the deprecated IK moving-arm distance sweep for thesis-facing work.
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
    ALIGNMENT_TOLERANCE_DEG,
    CAMERA_FACING_WALL_PATH,
    CENTER_FREQUENCY_HZ,
    DEFAULT_MATERIAL_CONDITION,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_STAGE_PATH,
    DISTANCE_TOLERANCE_M,
    DISTANCE_WAYPOINTS_M,
    EE_FRAME,
    EXPERIMENT_MODE,
    IK_MIN_LINK_Z_M,
    IK_ORIENTATION_TOLERANCE_RAD,
    IK_POSITION_TOLERANCE_M,
    IK_ROBOT_DESCRIPTION,
    IK_URDF,
    PASSPORT_ID,
    ROBOT_PRIM_PATH,
    ROOM_PRIM_PATHS,
    SENSOR_LOCAL_OFFSET_M,
    SENSOR_MOUNT_SPACING_M,
    SENSOR_PRIM_NAME,
    TARGET_COLOR,
    TARGET_CUBE_SCALE_M,
    TARGET_PRIM_PATH,
    TICK_RATE_HZ,
    TCP_RADIUS_TOLERANCE_M,
    apply_passport_display_colors,
    create_six_wall_room,
    ee_target_position_m,
    passport_summary,
    set_prim_visibility,
    target_inside_room,
    target_position_from_sensor,
    tcp_radius_xy,
)
from rtx_acoustic_factory import (  # noqa: E402
    PASSPORT_FACTORY_VERSION,
    assess_gmo_capture_quality,
    create_passport_acoustic,
    summarize_gmo_frame,
)
from rtx_material_passport_v1 import apply_room_and_target_materials  # noqa: E402

SEED_POSES_RAD: dict[str, tuple[float, float, float, float, float, float]] = {
    "reach_forward": (0.0, -1.20, 1.20, -1.57, -1.57, 0.0),
    "home": (0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0),
    "reach_left": (0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
    "reach_right": (-0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
}

FIELDNAMES = [
    "sample_index",
    "repeat_id",
    "material_condition",
    "distance_index",
    "distance_label",
    "desired_distance_m",
    "planned_distance_m",
    "distance_error_m",
    "target_x_m",
    "target_y_m",
    "target_z_m",
    "ee_x_m",
    "ee_y_m",
    "ee_z_m",
    "sensor_x_m",
    "sensor_y_m",
    "sensor_z_m",
    "sensor_tcp_radius_xy_m",
    "target_distance_m",
    "alignment_dot",
    "alignment_angle_deg",
    "commanded_joint_positions_rad",
    "actual_joint_positions_rad",
    "writer_frame",
    "timestamp_ns",
    "num_elements",
    "amplitude_min",
    "amplitude_max",
    "amplitude_mean",
    "amplitude_std",
    "num_signal_ways",
    "num_samples_per_sgw",
    "gmo_valid",
    "gmo_modality",
    "gmo_validation_issues",
    "all_sgw_peak_mean",
    "all_sgw_peak_std",
    "primary_sgw_tx",
    "primary_sgw_rx",
    "primary_sgw_ch",
    "primary_sgw_peak",
    "primary_sgw_mean",
    "primary_sgw_early_energy",
    "primary_sgw_first_time_offset_ns",
    "ref_sgw_tx",
    "ref_sgw_rx",
    "ref_sgw_ch",
    "ref_sgw_peak",
    "ref_sgw_mean",
    "ref_sgw_early_energy",
    "ref_sgw_first_time_offset_ns",
    "signal_way_keys",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official UR10 fixed-TCP moving-target RTX Acoustic capture.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--output-stage", type=Path, default=DEFAULT_STAGE_PATH)
    parser.add_argument("--distance-waypoints", type=float, nargs="+", default=list(DISTANCE_WAYPOINTS_M))
    parser.add_argument("--single-distance", type=float, default=None, help="Capture one distance only (repeatability mode).")
    parser.add_argument("--repeat-id", type=str, default="")
    parser.add_argument("--samples-per-distance", type=int, default=8)
    parser.add_argument("--settle-steps", type=int, default=40)
    parser.add_argument("--target-settle-steps", type=int, default=20)
    parser.add_argument("--substeps-per-sample", type=int, default=2)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument(
        "--hide-camera-wall",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Hide the wall between the default camera viewpoint and the robot (default: hidden).",
    )
    parser.add_argument(
        "--gui-camera-light",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use viewport Camera Light in GUI mode (default: enabled).",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument("--pre-run-hold-seconds", type=float, default=0.0)
    parser.add_argument("--step-delay-seconds", type=float, default=0.0)
    parser.add_argument("--tick-rate", type=float, default=TICK_RATE_HZ)
    parser.add_argument("--center-frequency", type=float, default=CENTER_FREQUENCY_HZ)
    parser.add_argument("--sensor-local-offset", type=float, nargs=3, default=SENSOR_LOCAL_OFFSET_M)
    parser.add_argument("--no-room", action="store_true")
    parser.add_argument(
        "--material-condition",
        default=DEFAULT_MATERIAL_CONDITION,
        help="RTX NonVisualMaterial condition: A, B, C, or none.",
    )
    parser.add_argument(
        "--target-scale",
        type=float,
        nargs=3,
        default=TARGET_CUBE_SCALE_M,
        help="Target reflector cube scale in meters (x, y, z).",
    )
    parser.add_argument("--min-samples", type=int, default=6)
    parser.add_argument("--max-ee-motion-m", type=float, default=0.02, help="Fail if ee_link moves more than this during capture.")
    parser.add_argument("--ik-robot-description", type=Path, default=IK_ROBOT_DESCRIPTION)
    parser.add_argument("--ik-urdf", type=Path, default=IK_URDF)
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


def set_target_pose(
    Cube: Any,
    np: Any,
    prim_path: str,
    position: tuple[float, float, float],
    scale: tuple[float, float, float],
    *,
    color: str = TARGET_COLOR,
) -> None:
    """Move the target while preserving its scale and display color.

    Do not call ClearXformOpOrder with translate only — that drops scale and the
    default USD cube becomes ~2 m wide in the viewport.
    """
    Cube(
        prim_path,
        positions=np.array(position, dtype=float),
        scales=np.array(scale, dtype=float),
        colors=color,
    )


def configure_gui_viewport(
    simulation_app: Any,
    sensor_position: tuple[float, float, float],
    *,
    use_camera_light: bool,
) -> dict[str, Any]:
    """Frame the robot workspace and enable Camera Light for GUI observation."""
    from isaacsim.core.rendering_manager import ViewportManager

    sx, sy, sz = sensor_position
    viewport_ready, waited_frames = ViewportManager.wait_for_viewport(max_frames=120, sleep_time=0.02)
    print(
        f"GUI viewport: wait_for_viewport ready={viewport_ready} frames={waited_frames}",
        flush=True,
    )
    warmup_frames = max(0, 12 - int(waited_frames))
    for _ in range(warmup_frames):
        simulation_app.update()

    ViewportManager.set_camera_view(
        "/OmniverseKit_Persp",
        eye=[sx - 2.8, sy + 1.8, sz + 1.2],
        target=[sx + 1.2, sy, sz],
    )

    if use_camera_light:
        try:
            import omni.usd
            from omni.kit.viewport.menubar.lighting.actions import _set_lighting_mode

            _set_lighting_mode("camera", usd_context=omni.usd.get_context())
        except Exception as exc:
            print(f"GUI viewport: failed to enable Camera Light ({exc})", flush=True)

    for _ in range(3):
        simulation_app.update()

    return {
        "viewport_ready": bool(viewport_ready),
        "waited_frames": int(waited_frames),
        "camera_light_enabled": bool(use_camera_light),
    }


def solve_fixed_tcp_joints(ik: Any, observe_pose: Any, args: argparse.Namespace) -> tuple[Any, dict[str, Any]]:
    import numpy as np  # noqa: WPS433

    ee_target = np.array(ee_target_position_m(), dtype=float)
    target_orientation = np.array([1.0, 0.0, 0.0, 0.0], dtype=float)
    seed_candidates = [np.asarray(q, dtype=float) for q in SEED_POSES_RAD.values()]
    seed_candidates.append(np.zeros(6, dtype=float))

    best: dict[str, Any] | None = None
    for seed in seed_candidates:
        q_candidate, success = ik.compute_inverse_kinematics(
            EE_FRAME,
            ee_target,
            target_orientation=target_orientation,
            warm_start=seed,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(IK_ORIENTATION_TOLERANCE_RAD),
        )
        if not success:
            continue
        obs = observe_pose(np.asarray(q_candidate, dtype=float), 6, render=False)
        radius = tcp_radius_xy(obs["sensor_position"])
        above_floor = float(obs["min_link_z_m"]) >= float(IK_MIN_LINK_Z_M)
        score = (
            0 if above_floor else 1,
            abs(radius - float(passport_summary()["tcp_radius_m"])),
            -float(obs["min_link_z_m"]),
        )
        candidate = {
            "q": np.asarray(q_candidate, dtype=float),
            "obs": obs,
            "score": score,
            "above_floor": above_floor,
            "tcp_radius_xy_m": radius,
        }
        if best is None or candidate["score"] < best["score"]:
            best = candidate

    if best is None:
        raise RuntimeError("Failed to solve fixed TCP pose with Lula IK.")
    return best["q"], best


def main() -> None:
    args = parse_args()
    if args.output_stage.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output_stage}; pass --overwrite")

    distances = [float(args.single_distance)] if args.single_distance is not None else [float(v) for v in args.distance_waypoints]
    distances = sorted({round(v, 6) for v in distances})

    simulation_app = SimulationApp({"headless": not bool(args.gui)})

    import numpy as np  # noqa: E402
    import omni  # noqa: E402
    import omni.replicator.core as rep  # noqa: E402
    import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.api.robots import Robot  # noqa: E402
    from isaacsim.core.experimental.materials import NonVisualMaterial  # noqa: E402
    from isaacsim.core.experimental.objects import Cube  # noqa: E402
    from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver  # noqa: E402
    from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor, parse_generic_model_output_data  # noqa: E402
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402
    from omni.replicator.core import Writer  # noqa: E402
    from pxr import Gf, Sdf, Usd, UsdGeom  # noqa: E402

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
    ee_path = f"{ROBOT_PRIM_PATH}/{EE_FRAME}"
    sensor_path = f"{ee_path}/{SENSOR_PRIM_NAME}"

    print(f"Fixed-TCP sweep: loading {official_ur10_usd}", flush=True)
    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=ROBOT_PRIM_PATH)
    for _ in range(20):
        simulation_app.update()

    if not stage.GetPrimAtPath(ee_path):
        simulation_app.close()
        raise RuntimeError(f"End-effector frame not found: {ee_path}")

    room_prim_paths: list[str] = []
    if not args.no_room:
        room_prim_paths = create_six_wall_room(Cube, np)
    else:
        Cube("/World/room/floor", positions=np.array([2.0, 0.0, -0.025]), scales=np.array([4.5, 3.0, 0.05]))

    target_scale = tuple(float(v) for v in args.target_scale)
    Cube(
        TARGET_PRIM_PATH,
        positions=np.array(ee_target_position_m(), dtype=float),
        scales=np.array(target_scale, dtype=float),
        colors=TARGET_COLOR,
    )

    material_summary: dict[str, Any] = {"enabled": False, "requested_condition": args.material_condition}
    if not args.no_room and str(args.material_condition).lower() != "none":
        print(f"Fixed-TCP sweep: applying RTX NonVisualMaterial condition {args.material_condition}", flush=True)
        material_summary = apply_room_and_target_materials(
            room_prim_paths or list(ROOM_PRIM_PATHS),
            TARGET_PRIM_PATH,
            str(args.material_condition),
            Cube=Cube,
            NonVisualMaterial=NonVisualMaterial,
        )
        apply_passport_display_colors(Cube, room_prim_paths or list(ROOM_PRIM_PATHS), TARGET_PRIM_PATH)
        for _ in range(5):
            simulation_app.update()

    if not args.no_room and args.hide_camera_wall:
        if set_prim_visibility(stage, CAMERA_FACING_WALL_PATH, visible=False):
            print(f"Fixed-TCP sweep: hid camera-facing wall {CAMERA_FACING_WALL_PATH}", flush=True)
        else:
            print(f"Fixed-TCP sweep: warning — camera-facing wall not found: {CAMERA_FACING_WALL_PATH}", flush=True)

    print(f"Fixed-TCP sweep: creating Acoustic at {sensor_path}", flush=True)
    acoustic, sensor = create_passport_acoustic(
        sensor_path,
        Acoustic=Acoustic,
        AcousticSensor=AcousticSensor,
        np=np,
        tick_rate_hz=float(args.tick_rate),
        center_frequency_hz=float(args.center_frequency),
        sensor_local_offset_m=tuple(float(v) for v in args.sensor_local_offset),
        mount_spacing_m=float(SENSOR_MOUNT_SPACING_M),
        writer_brings_annotator=True,
    )
    acoustic_prim = stage.GetPrimAtPath(sensor_path)
    if not acoustic_prim:
        simulation_app.close()
        raise RuntimeError(f"Acoustic prim was not created: {sensor_path}")

    acoustic_prim.CreateAttribute("research:geometryPassportId", Sdf.ValueTypeNames.String, custom=True).Set(PASSPORT_ID)
    acoustic_prim.CreateAttribute("research:experimentMode", Sdf.ValueTypeNames.String, custom=True).Set(EXPERIMENT_MODE)
    acoustic_prim.CreateAttribute("research:assetSource", Sdf.ValueTypeNames.String, custom=True).Set(official_ur10_usd)
    acoustic_prim.CreateAttribute("research:endEffectorFrame", Sdf.ValueTypeNames.String, custom=True).Set(ee_path)

    rows: list[dict[str, Any]] = []
    writer_state: dict[str, Any] = {
        "sample_context": None,
        "writer_frame": 0,
        "parse_errors": [],
        "raw_empty_frames": 0,
    }

    class FixedTcpDistanceWriter(Writer):
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
                if int(gmo.numElements) <= 0:
                    writer_state["raw_empty_frames"] += 1
                    continue
                row = dict(context_row)
                row.update(
                    {
                        "sample_index": len(rows),
                        "writer_frame": int(writer_state["writer_frame"]),
                    }
                )
                row.update(summarize_gmo_frame(gmo, np))
                rows.append(row)
                break
            writer_state["writer_frame"] += 1

    rep.WriterRegistry.register(FixedTcpDistanceWriter)
    sensor.attach_writer("FixedTcpDistanceWriter")

    world = World()
    robot = world.scene.add(Robot(prim_path=ROBOT_PRIM_PATH, name="ur10"))
    world.reset()

    cache = UsdGeom.XformCache(0)
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    link_paths = [
        f"{ROBOT_PRIM_PATH}/shoulder_link",
        f"{ROBOT_PRIM_PATH}/upper_arm_link",
        f"{ROBOT_PRIM_PATH}/forearm_link",
        f"{ROBOT_PRIM_PATH}/wrist_1_link",
        f"{ROBOT_PRIM_PATH}/wrist_2_link",
        f"{ROBOT_PRIM_PATH}/wrist_3_link",
        ee_path,
    ]

    def min_robot_link_z() -> float:
        min_z = math.inf
        bbox_cache.Clear()
        for link_path in link_paths:
            prim = stage.GetPrimAtPath(link_path)
            if not prim:
                continue
            try:
                box = bbox_cache.ComputeWorldBound(prim).ComputeAlignedBox()
                if not box.IsEmpty():
                    min_z = min(min_z, float(box.GetMin()[2]))
                    continue
            except Exception:
                pass
            try:
                cache.Clear()
                min_z = min(min_z, float(cache.GetLocalToWorldTransform(prim).ExtractTranslation()[2]))
            except Exception:
                pass
        return min_z if math.isfinite(min_z) else float("nan")

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
        return {
            "actual_q": actual_q,
            "ee_position": ee_position,
            "sensor_position": sensor_position,
            "sensor_forward": sensor_forward,
            "min_link_z_m": min_robot_link_z(),
        }

    ik = LulaKinematicsSolver(str(args.ik_robot_description), str(args.ik_urdf))
    ik.set_default_position_tolerance(float(IK_POSITION_TOLERANCE_M))
    if EE_FRAME not in ik.get_all_frame_names():
        simulation_app.close()
        raise RuntimeError(f"IK frame not found: {EE_FRAME}; frames={ik.get_all_frame_names()}")

    fixed_q, tcp_solution = solve_fixed_tcp_joints(ik, observe_pose, args)
    baseline_obs = observe_pose(fixed_q, int(args.settle_steps), render=bool(args.gui))
    baseline_ee = baseline_obs["ee_position"]
    sensor_position = baseline_obs["sensor_position"]
    sensor_forward = baseline_obs["sensor_forward"]
    locked_q = np.asarray(baseline_obs["actual_q"], dtype=float)

    print(
        "Fixed-TCP planner: locked joints "
        f"tcp_radius={tcp_radius_xy(sensor_position):.3f}m "
        f"sensor=({sensor_position[0]:.3f}, {sensor_position[1]:.3f}, {sensor_position[2]:.3f}) "
        f"min_link_z={baseline_obs['min_link_z_m']:.3f}m",
        flush=True,
    )

    gui_viewport_summary: dict[str, Any] = {}
    if args.gui:
        gui_viewport_summary = configure_gui_viewport(
            simulation_app,
            sensor_position,
            use_camera_light=bool(args.gui_camera_light),
        )

    if args.gui and args.pre_run_hold_seconds > 0:
        print(f"GUI pre-run hold: {args.pre_run_hold_seconds:.1f}s before capture", flush=True)
        deadline = time.time() + float(args.pre_run_hold_seconds)
        while simulation_app.is_running() and time.time() < deadline:
            simulation_app.update()

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    planned_conditions: list[dict[str, Any]] = []
    for distance_index, desired_distance in enumerate(distances):
        label = f"d_{str(desired_distance).replace('.', 'p')}m"
        target_position = target_position_from_sensor(sensor_position, sensor_forward, desired_distance)
        inside_room = target_inside_room(target_position)
        set_target_pose(Cube, np, TARGET_PRIM_PATH, target_position, target_scale)
        robot.set_joint_positions(locked_q)
        for _ in range(max(1, int(args.target_settle_steps))):
            world.step(render=bool(args.gui))
            simulation_app.update()

        obs = observe_pose(locked_q, 1, render=bool(args.gui))
        target_direction = vec_sub(target_position, obs["sensor_position"])
        planned_distance = vec_norm(target_direction)
        alignment_dot = vec_dot(obs["sensor_forward"], vec_unit(target_direction))
        alignment_angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, alignment_dot))))
        distance_error = abs(planned_distance - desired_distance)
        within_tolerance = (
            inside_room
            and distance_error <= float(DISTANCE_TOLERANCE_M)
            and alignment_angle_deg <= float(ALIGNMENT_TOLERANCE_DEG)
            and float(obs["min_link_z_m"]) >= float(IK_MIN_LINK_Z_M)
        )
        planned_conditions.append(
            {
                "distance_index": distance_index,
                "label": label,
                "desired_distance_m": desired_distance,
                "planned_distance_m": planned_distance,
                "distance_error_m": distance_error,
                "target_position_m": list(target_position),
                "inside_room": inside_room,
                "alignment_angle_deg": alignment_angle_deg,
                "within_tolerance": within_tolerance,
                "min_link_z_m": float(obs["min_link_z_m"]),
            }
        )
        print(
            f"  {label}: desired={desired_distance:.3f} planned={planned_distance:.3f} "
            f"error={distance_error:.3f} angle={alignment_angle_deg:.2f} inside={inside_room} "
            f"{'OK' if within_tolerance else 'OUT'}",
            flush=True,
        )

        for _sample in range(max(1, int(args.samples_per_distance))):
            robot.set_joint_positions(locked_q)
            for _ in range(max(1, int(args.substeps_per_sample))):
                world.step(render=bool(args.gui))
            obs = observe_pose(locked_q, 1, render=bool(args.gui))
            target_direction = vec_sub(target_position, obs["sensor_position"])
            planned_distance = vec_norm(target_direction)
            alignment_dot = vec_dot(obs["sensor_forward"], vec_unit(target_direction))
            alignment_angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, alignment_dot))))
            writer_state["sample_context"] = {
                "repeat_id": args.repeat_id,
                "material_condition": str(args.material_condition),
                "distance_index": distance_index,
                "distance_label": label,
                "desired_distance_m": desired_distance,
                "planned_distance_m": planned_distance,
                "distance_error_m": abs(planned_distance - desired_distance),
                "target_x_m": target_position[0],
                "target_y_m": target_position[1],
                "target_z_m": target_position[2],
                "ee_x_m": obs["ee_position"][0],
                "ee_y_m": obs["ee_position"][1],
                "ee_z_m": obs["ee_position"][2],
                "sensor_x_m": obs["sensor_position"][0],
                "sensor_y_m": obs["sensor_position"][1],
                "sensor_z_m": obs["sensor_position"][2],
                "sensor_tcp_radius_xy_m": tcp_radius_xy(obs["sensor_position"]),
                "target_distance_m": planned_distance,
                "alignment_dot": alignment_dot,
                "alignment_angle_deg": alignment_angle_deg,
                "commanded_joint_positions_rad": semicolon_floats(locked_q.tolist()),
                "actual_joint_positions_rad": semicolon_floats(obs["actual_q"].tolist()),
            }
            simulation_app.update()
            if args.gui and args.step_delay_seconds > 0:
                deadline = time.time() + float(args.step_delay_seconds)
                while simulation_app.is_running() and time.time() < deadline:
                    simulation_app.update()

    timeline.stop()
    writer_state["sample_context"] = None
    try:
        rep.orchestrator.wait_until_complete()
    except Exception as exc:
        writer_state["orchestrator_wait_error"] = str(exc)

    ee_positions = [(float(r["ee_x_m"]), float(r["ee_y_m"]), float(r["ee_z_m"])) for r in rows]
    if len(ee_positions) > 1:
        max_motion = max(distance(a, b) for i, a in enumerate(ee_positions) for b in ee_positions[i + 1 :])
    else:
        max_motion = 0.0

    distances_observed = [float(r["target_distance_m"]) for r in rows]
    amp_max_values = [float(r["amplitude_max"]) for r in rows if math.isfinite(float(r["amplitude_max"]))]
    distance_min = min(distances_observed) if distances_observed else 0.0
    distance_max = max(distances_observed) if distances_observed else 0.0
    amplitude_max_min = min(amp_max_values) if amp_max_values else 0.0
    amplitude_max_max = max(amp_max_values) if amp_max_values else 0.0

    api_schemas = token_list_op_items(acoustic_prim.GetMetadata("apiSchemas"))
    sensor_parent_ok = sensor_path.startswith(f"{ee_path}/")
    all_conditions_ok = all(c["within_tolerance"] for c in planned_conditions)
    gmo_capture_quality = assess_gmo_capture_quality(rows)
    nv_material_verification = material_summary.get("nv_material_verification") or {
        "enabled": False,
        "valid": True,
        "skipped": True,
    }
    nv_material_ok = bool(nv_material_verification.get("valid", True))
    passed = (
        len(rows) >= int(args.min_samples)
        and max_motion <= float(args.max_ee_motion_m)
        and acoustic_prim.GetTypeName() == "OmniAcoustic"
        and "OmniSensorGenericAcousticWpmAPI" in api_schemas
        and sensor_parent_ok
        and all_conditions_ok
        and abs(tcp_radius_xy(sensor_position) - passport_summary()["tcp_radius_m"]) <= float(TCP_RADIUS_TOLERANCE_M)
        and bool(gmo_capture_quality.get("valid"))
        and nv_material_ok
    )

    csv_path = args.output_dir / "official_asset_ur10_fixed_tcp_distance_sweep_timeseries.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "pass": passed,
        "geometry_passport": passport_summary(),
        "rtx_acoustic_factory_version": PASSPORT_FACTORY_VERSION,
        "gmo_capture_quality": gmo_capture_quality,
        "nv_material_verification": nv_material_verification,
        "gui_viewport": gui_viewport_summary,
        "rtx_material_passport": material_summary,
        "target_scale_m": list(target_scale),
        "experiment_mode": EXPERIMENT_MODE,
        "repeat_id": args.repeat_id,
        "official_ur10_asset": official_ur10_usd,
        "robot_path": ROBOT_PRIM_PATH,
        "end_effector_frame": ee_path,
        "sensor_path": sensor_path,
        "sensor_parent_ok": sensor_parent_ok,
        "sensor_prim_type": acoustic_prim.GetTypeName(),
        "sensor_api_schemas": api_schemas,
        "planner_mode": "fixed_tcp_lula_ik_once",
        "locked_joint_positions_rad": locked_q.tolist(),
        "baseline_sensor_position_m": list(sensor_position),
        "baseline_sensor_forward_m": list(sensor_forward),
        "baseline_ee_position_m": list(baseline_ee),
        "baseline_tcp_radius_xy_m": tcp_radius_xy(sensor_position),
        "tcp_solution": {
            "above_floor": bool(tcp_solution["above_floor"]),
            "tcp_radius_xy_m": float(tcp_solution["tcp_radius_xy_m"]),
        },
        "requested_distance_waypoints_m": distances,
        "planned_conditions": planned_conditions,
        "missing_or_out_of_tolerance_conditions": [c["label"] for c in planned_conditions if not c["within_tolerance"]],
        "ik_robot_description": args.ik_robot_description,
        "ik_urdf": args.ik_urdf,
        "pre_run_hold_seconds": float(args.pre_run_hold_seconds),
        "step_delay_seconds": float(args.step_delay_seconds),
        "samples_per_distance": int(args.samples_per_distance),
        "captured_samples": len(rows),
        "min_required_samples": int(args.min_samples),
        "max_observed_ee_motion_m": max_motion,
        "max_allowed_ee_motion_m": float(args.max_ee_motion_m),
        "target_distance_min_m": distance_min,
        "target_distance_max_m": distance_max,
        "amplitude_max_min": amplitude_max_min,
        "amplitude_max_max": amplitude_max_max,
        "parse_errors": writer_state["parse_errors"],
        "raw_empty_frames": writer_state["raw_empty_frames"],
        "csv_path": csv_path,
        "output_stage": args.output_stage,
    }
    summary_path = args.output_dir / "official_asset_ur10_fixed_tcp_distance_sweep_summary.json"
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stage.GetRootLayer().Export(str(args.output_stage))

    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print(f"Captured samples: {len(rows)}")
    print(f"Max observed ee_link motion: {max_motion:.6f} m (limit {args.max_ee_motion_m:.3f} m)")
    print(f"Target distance range: [{distance_min:.6f}, {distance_max:.6f}] m")
    print(f"Requested distances: {distances}")
    print("Out-of-tolerance conditions: " + str(summary["missing_or_out_of_tolerance_conditions"]))
    print(f"Amplitude max range: [{amplitude_max_min:.6f}, {amplitude_max_max:.6f}]")
    print(
        "GMO capture quality: "
        f"valid={gmo_capture_quality.get('valid')} "
        f"rate={float(gmo_capture_quality.get('gmo_valid_rate', 0.0)):.3f} "
        f"modality_acoustic={gmo_capture_quality.get('all_modality_acoustic')} "
        f"issues={gmo_capture_quality.get('issues')}",
        flush=True,
    )
    if nv_material_verification.get("enabled"):
        print(
            "NV material verification: "
            f"valid={nv_material_verification.get('valid')} "
            f"room_id={nv_material_verification.get('unique_room_material_id')} "
            f"target_id={nv_material_verification.get('target_material_id')} "
            f"issues={nv_material_verification.get('issues')}",
            flush=True,
        )
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