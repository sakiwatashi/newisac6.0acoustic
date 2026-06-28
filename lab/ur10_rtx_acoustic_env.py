"""Isaac Lab Phase 4 — UR10 RTX Acoustic dynamic target smoke environment.

Reuses Sim Phase 3 Passport + Factory on a sinusoidal moving-target trajectory.
Run via Isaac Lab launcher:

  ./isaaclab.sh -p /path/to/ur10_rtx_acoustic_env.py --headless --steps 128
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

from isaaclab.app import AppLauncher

LAB_DIR = Path(__file__).resolve().parent
ISAACSIM_ROOT = LAB_DIR.parent
SCRIPTS_DIR = ISAACSIM_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(LAB_DIR) not in sys.path:
    sys.path.insert(0, str(LAB_DIR))

from geometry_passport_v1 import (  # noqa: E402
    CAMERA_FACING_WALL_PATH,
    CENTER_FREQUENCY_HZ,
    DEFAULT_MATERIAL_CONDITION,
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
    apply_passport_display_colors,
    create_six_wall_room,
    ee_target_position_m,
    passport_summary,
    set_prim_visibility,
    target_inside_room,
    target_position_from_sensor,
    tcp_radius_xy,
)
from moving_target_controller import SinusoidalDistanceTrajectory  # noqa: E402
from rtx_acoustic_factory import (  # noqa: E402
    PASSPORT_FACTORY_VERSION,
    assess_gmo_capture_quality,
    create_passport_acoustic,
    summarize_gmo_frame,
)
from rtx_material_passport_v1 import apply_room_and_target_materials  # noqa: E402

LAB_EXPERIMENT_MODE = "fixed_tcp_moving_target_dynamic"
DEFAULT_OUTPUT_DIR = ISAACSIM_ROOT / "runtime/outputs/lab_dynamic_smoke_v1"

SEED_POSES_RAD: dict[str, tuple[float, float, float, float, float, float]] = {
    "reach_forward": (0.0, -1.20, 1.20, -1.57, -1.57, 0.0),
    "home": (0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0),
    "reach_left": (0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
    "reach_right": (-0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
}

CSV_FIELDNAMES = [
    "step_index",
    "sim_time_s",
    "target_distance_m_gt",
    "target_x_m",
    "target_y_m",
    "target_z_m",
    "sensor_x_m",
    "sensor_y_m",
    "sensor_z_m",
    "primary_sgw_early_energy",
    "primary_sgw_peak",
    "gmo_valid",
    "gmo_modality",
    "gmo_captured",
    "material_condition",
    "experiment_mode",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UR10 RTX Acoustic Lab dynamic-target smoke.")
    AppLauncher.add_app_launcher_args(parser)
    parser.add_argument("--steps", type=int, default=128, help="Total env steps (target updates).")
    parser.add_argument("--decimation", type=int, default=4, help="Capture GMO every N steps.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--period-steps", type=int, default=64)
    parser.add_argument("--center-distance-m", type=float, default=1.5)
    parser.add_argument("--amplitude-m", type=float, default=0.5)
    parser.add_argument("--settle-steps", type=int, default=40)
    parser.add_argument("--target-settle-steps", type=int, default=12)
    parser.add_argument("--substeps-per-step", type=int, default=2)
    parser.add_argument("--sim-dt", type=float, default=0.01)
    parser.add_argument("--material-condition", default=DEFAULT_MATERIAL_CONDITION)
    parser.add_argument("--tick-rate", type=float, default=TICK_RATE_HZ)
    parser.add_argument("--center-frequency", type=float, default=CENTER_FREQUENCY_HZ)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


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


def set_target_pose(
    Cube: Any,
    np: Any,
    prim_path: str,
    position: tuple[float, float, float],
    scale: tuple[float, float, float],
) -> None:
    Cube(
        prim_path,
        positions=np.array(position, dtype=float),
        scales=np.array(scale, dtype=float),
        colors=TARGET_COLOR,
    )


def solve_fixed_tcp_joints(ik: Any, observe_pose: Any) -> tuple[Any, dict[str, Any]]:
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


def build_observation_row(
    *,
    step_index: int,
    sim_time_s: float,
    target_position: tuple[float, float, float],
    sensor_position: tuple[float, float, float],
    gt_distance_m: float,
    material_condition: str,
    gmo_captured: bool,
    gmo_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "step_index": step_index,
        "sim_time_s": sim_time_s,
        "target_distance_m_gt": gt_distance_m,
        "target_x_m": target_position[0],
        "target_y_m": target_position[1],
        "target_z_m": target_position[2],
        "sensor_x_m": sensor_position[0],
        "sensor_y_m": sensor_position[1],
        "sensor_z_m": sensor_position[2],
        "primary_sgw_early_energy": math.nan,
        "primary_sgw_peak": math.nan,
        "gmo_valid": False,
        "gmo_modality": "",
        "gmo_captured": gmo_captured,
        "material_condition": material_condition,
        "experiment_mode": LAB_EXPERIMENT_MODE,
    }
    if gmo_fields:
        row["primary_sgw_early_energy"] = gmo_fields.get("primary_sgw_early_energy", math.nan)
        row["primary_sgw_peak"] = gmo_fields.get("primary_sgw_peak", math.nan)
        row["gmo_valid"] = gmo_fields.get("gmo_valid", False)
        row["gmo_modality"] = gmo_fields.get("gmo_modality", "")
    return row


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "lab_dynamic_obs_timeseries.csv"
    summary_path = args.output_dir / "lab_dynamic_obs_summary.json"
    if csv_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {csv_path}; pass --overwrite")

    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app

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

    trajectory = SinusoidalDistanceTrajectory(
        center_distance_m=float(args.center_distance_m),
        amplitude_m=float(args.amplitude_m),
        period_steps=int(args.period_steps),
    )
    dist_min, dist_max = trajectory.distance_bounds_m()
    print(
        f"Lab dynamic smoke: steps={args.steps} decimation={args.decimation} "
        f"distance=[{dist_min:.2f}, {dist_max:.2f}] m period={args.period_steps}",
        flush=True,
    )

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

    stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=ROBOT_PRIM_PATH)
    for _ in range(20):
        simulation_app.update()

    room_prim_paths = create_six_wall_room(Cube, np)
    target_scale = tuple(float(v) for v in TARGET_CUBE_SCALE_M)
    set_target_pose(Cube, np, TARGET_PRIM_PATH, ee_target_position_m(), target_scale)

    material_summary = apply_room_and_target_materials(
        list(ROOM_PRIM_PATHS),
        TARGET_PRIM_PATH,
        str(args.material_condition),
        Cube=Cube,
        NonVisualMaterial=NonVisualMaterial,
    )
    apply_passport_display_colors(Cube, room_prim_paths, TARGET_PRIM_PATH)
    set_prim_visibility(stage, CAMERA_FACING_WALL_PATH, visible=False)

    acoustic, sensor = create_passport_acoustic(
        sensor_path,
        Acoustic=Acoustic,
        AcousticSensor=AcousticSensor,
        np=np,
        tick_rate_hz=float(args.tick_rate),
        center_frequency_hz=float(args.center_frequency),
        sensor_local_offset_m=SENSOR_LOCAL_OFFSET_M,
        mount_spacing_m=float(SENSOR_MOUNT_SPACING_M),
        writer_brings_annotator=True,
    )
    acoustic_prim = stage.GetPrimAtPath(sensor_path)
    if not acoustic_prim:
        simulation_app.close()
        raise RuntimeError(f"Acoustic prim was not created: {sensor_path}")

    acoustic_prim.CreateAttribute("research:geometryPassportId", Sdf.ValueTypeNames.String, custom=True).Set(PASSPORT_ID)
    acoustic_prim.CreateAttribute("research:experimentMode", Sdf.ValueTypeNames.String, custom=True).Set(LAB_EXPERIMENT_MODE)
    acoustic_prim.CreateAttribute("research:parentExperimentMode", Sdf.ValueTypeNames.String, custom=True).Set(EXPERIMENT_MODE)

    rows: list[dict[str, Any]] = []
    writer_state: dict[str, Any] = {
        "pending_step": None,
        "writer_frame": 0,
        "parse_errors": [],
        "raw_empty_frames": 0,
    }

    class LabDynamicWriter(Writer):
        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]

        def write(self, data):
            pending = writer_state.get("pending_step")
            if pending is None:
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
                gmo_fields = summarize_gmo_frame(gmo, np)
                row = build_observation_row(
                    step_index=int(pending["step_index"]),
                    sim_time_s=float(pending["sim_time_s"]),
                    target_position=pending["target_position"],
                    sensor_position=pending["sensor_position"],
                    gt_distance_m=float(pending["gt_distance_m"]),
                    material_condition=str(args.material_condition),
                    gmo_captured=True,
                    gmo_fields=gmo_fields,
                )
                rows.append(row)
                pending["captured"] = True
                break
            writer_state["writer_frame"] += 1

    rep.WriterRegistry.register(LabDynamicWriter)
    sensor.attach_writer("LabDynamicWriter")

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
        cache.Clear()
        ee_prim = stage.GetPrimAtPath(ee_path)
        sensor_prim = stage.GetPrimAtPath(sensor_path)
        ee_matrix = cache.GetLocalToWorldTransform(ee_prim)
        sensor_matrix = cache.GetLocalToWorldTransform(sensor_prim)
        return {
            "actual_q": np.asarray(robot.get_joint_positions(), dtype=float),
            "ee_position": vec_tuple(ee_matrix.ExtractTranslation()),
            "sensor_position": vec_tuple(sensor_matrix.ExtractTranslation()),
            "sensor_forward": vec_tuple(sensor_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()),
            "min_link_z_m": min_robot_link_z(),
        }

    ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
    ik.set_default_position_tolerance(float(IK_POSITION_TOLERANCE_M))
    fixed_q, tcp_solution = solve_fixed_tcp_joints(ik, observe_pose)
    baseline_obs = observe_pose(fixed_q, int(args.settle_steps), render=False)
    sensor_position = baseline_obs["sensor_position"]
    sensor_forward = baseline_obs["sensor_forward"]
    locked_q = np.asarray(baseline_obs["actual_q"], dtype=float)

    print(
        "Lab dynamic smoke: locked TCP "
        f"radius={tcp_radius_xy(sensor_position):.3f}m "
        f"sensor=({sensor_position[0]:.3f}, {sensor_position[1]:.3f}, {sensor_position[2]:.3f})",
        flush=True,
    )

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    decimation = max(1, int(args.decimation))
    total_steps = max(1, int(args.steps))
    all_rows: list[dict[str, Any]] = []
    gmo_capture_steps = 0

    for step_index in range(total_steps):
        desired_distance = trajectory.distance_at_step(step_index)
        target_position = target_position_from_sensor(sensor_position, sensor_forward, desired_distance)
        if not target_inside_room(target_position):
            raise RuntimeError(f"Step {step_index}: target outside room at distance {desired_distance:.3f} m")

        set_target_pose(Cube, np, TARGET_PRIM_PATH, target_position, target_scale)
        robot.set_joint_positions(locked_q)
        for _ in range(max(1, int(args.target_settle_steps))):
            world.step(render=False)
            simulation_app.update()

        obs = observe_pose(locked_q, 1, render=False)
        gt_distance = vec_norm(vec_sub(target_position, obs["sensor_position"]))
        sim_time_s = float(step_index) * float(args.sim_dt)
        capture_gmo = (step_index % decimation) == 0

        if capture_gmo:
            writer_state["pending_step"] = {
                "step_index": step_index,
                "sim_time_s": sim_time_s,
                "target_position": target_position,
                "sensor_position": obs["sensor_position"],
                "gt_distance_m": gt_distance,
                "captured": False,
            }
            for _ in range(max(1, int(args.substeps_per_step))):
                world.step(render=False)
            simulation_app.update()
            pending = writer_state.get("pending_step")
            if pending and pending.get("captured"):
                all_rows.append(rows[-1])
                gmo_capture_steps += 1
            else:
                all_rows.append(
                    build_observation_row(
                        step_index=step_index,
                        sim_time_s=sim_time_s,
                        target_position=target_position,
                        sensor_position=obs["sensor_position"],
                        gt_distance_m=gt_distance,
                        material_condition=str(args.material_condition),
                        gmo_captured=False,
                        gmo_fields=None,
                    )
                )
            writer_state["pending_step"] = None
        else:
            all_rows.append(
                build_observation_row(
                    step_index=step_index,
                    sim_time_s=sim_time_s,
                    target_position=target_position,
                    sensor_position=obs["sensor_position"],
                    gt_distance_m=gt_distance,
                    material_condition=str(args.material_condition),
                    gmo_captured=False,
                    gmo_fields=None,
                )
            )

        if (step_index + 1) % 16 == 0:
            print(f"  progress: step {step_index + 1}/{total_steps}", flush=True)

    timeline.stop()
    try:
        rep.orchestrator.wait_until_complete()
    except Exception as exc:
        writer_state["orchestrator_wait_error"] = str(exc)

    gmo_rows = [row for row in all_rows if row.get("gmo_captured")]
    gmo_capture_quality = assess_gmo_capture_quality(gmo_rows)

    ee_positions = [
        (float(row["sensor_x_m"]), float(row["sensor_y_m"]), float(row["sensor_z_m"])) for row in all_rows
    ]
    max_sensor_motion = 0.0
    if len(ee_positions) > 1:
        max_sensor_motion = max(
            vec_norm(vec_sub(a, b)) for i, a in enumerate(ee_positions) for b in ee_positions[i + 1 :]
        )

    expected_captures = max(1, total_steps // decimation)
    capture_rate = float(len(gmo_rows)) / float(expected_captures)
    passed = (
        len(all_rows) >= total_steps
        and len(gmo_rows) >= max(8, int(0.75 * expected_captures))
        and float(gmo_capture_quality.get("gmo_valid_rate", 0.0)) >= 0.9
    )

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    summary = {
        "pass": passed,
        "lab_experiment_mode": LAB_EXPERIMENT_MODE,
        "parent_experiment_mode": EXPERIMENT_MODE,
        "geometry_passport": passport_summary(),
        "rtx_acoustic_factory_version": PASSPORT_FACTORY_VERSION,
        "isaac_lab_phase": 4,
        "trajectory": {
            "type": "sinusoidal_distance",
            "center_distance_m": trajectory.center_distance_m,
            "amplitude_m": trajectory.amplitude_m,
            "period_steps": trajectory.period_steps,
            "distance_bounds_m": [dist_min, dist_max],
        },
        "run_config": {
            "steps": total_steps,
            "decimation": decimation,
            "settle_steps": int(args.settle_steps),
            "target_settle_steps": int(args.target_settle_steps),
            "material_condition": str(args.material_condition),
        },
        "locked_tcp": {
            "sensor_position_m": list(sensor_position),
            "sensor_forward_m": list(sensor_forward),
            "tcp_radius_xy_m": tcp_radius_xy(sensor_position),
            "tcp_solution": {
                "above_floor": bool(tcp_solution["above_floor"]),
                "tcp_radius_xy_m": float(tcp_solution["tcp_radius_xy_m"]),
            },
        },
        "gmo_capture_quality": gmo_capture_quality,
        "rtx_material_passport": material_summary,
        "row_count": len(all_rows),
        "gmo_capture_count": len(gmo_rows),
        "gmo_capture_rate": capture_rate,
        "gmo_capture_expected": expected_captures,
        "max_sensor_position_motion_m": max_sensor_motion,
        "writer_state": {
            "parse_errors": writer_state["parse_errors"],
            "raw_empty_frames": writer_state["raw_empty_frames"],
        },
        "csv_path": str(csv_path),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    summary_path.write_text(json.dumps(to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print(f"Rows: {len(all_rows)} (GMO captures: {len(gmo_rows)})")
    print(
        "GMO quality: "
        f"valid_rate={float(gmo_capture_quality.get('gmo_valid_rate', 0.0)):.3f} "
        f"issues={gmo_capture_quality.get('issues')}",
        flush=True,
    )
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_path}")

    simulation_app.close()
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()