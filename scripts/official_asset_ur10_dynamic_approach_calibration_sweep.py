"""Open-loop EE sweep to fit dynamic-approach energy→distance calibration (UR10e+Robotiq)."""

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
    CAMERA_FACING_WALL_PATH,
    CENTER_FREQUENCY_HZ,
    DEFAULT_MATERIAL_CONDITION,
    GRASP_COLLISION_PRIM_PATHS,
    IK_ORIENTATION_TOLERANCE_RAD,
    IK_POSITION_TOLERANCE_M,
    ROOM_PRIM_PATHS,
    SENSOR_LOCAL_OFFSET_M,
    SENSOR_MOUNT_SPACING_M,
    SENSOR_PRIM_NAME,
    TCP_HEIGHT_M,
    TCP_Y_M,
    TICK_RATE_HZ,
    apply_passport_display_colors,
    create_six_wall_room,
    enable_static_collisions,
    set_prim_visibility,
)
from grasp_passport_v1 import (  # noqa: E402
    APPROACH_STEP_M,
    GMO_SUBSTEPS,
    SEARCH_END_X_M,
    SETTLE_STEPS_PER_MOVE,
    TABLE_PRIM_PATH,
    WRENCH_COLOR,
    WRENCH_PRIM_PATH,
    WRENCH_SCALE_M,
    oracle_distance_m,
    search_start_ee_position_m,
    spawn_wrench_position,
)
from acoustic_calibration_v1 import (  # noqa: E402
    build_energy_calibration_points,
    build_tof_calibration_points,
    tier_b_calibration_payload,
)
from rtx_acoustic_factory import (  # noqa: E402
    create_passport_acoustic,
    enrich_gmo_summary,
    summarize_gmo_frame,
)
from rtx_material_passport_v1 import apply_room_and_target_materials  # noqa: E402
from ur10e_robotiq_common import (  # noqa: E402
    bootstrap_arm_after_world_reset,
    resolve_sensor_mount_path,
    set_arm_joint_positions,
    setup_robotiq_gripper,
    spawn_solid_work_table,
    spawn_ur10e_robotiq,
)
from ur10e_robotiq_passport_v1 import (  # noqa: E402
    IK_EE_FRAME,
    IK_GRASP_ORIENTATION_TOLERANCE_RAD,
    IK_ROBOT_DESCRIPTION,
    IK_URDF,
    ROBOT_PRIM_PATH,
    SEED_POSES_RAD,
    solve_tool0_ik,
    tool0_grasp_orientation_wxyz,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dynamic approach calibration sweep (UR10e+Robotiq).")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ur10e_dynamic_approach_calibration_v1"),
    )
    parser.add_argument("--trial-id", type=int, default=9)
    parser.add_argument("--spawn-seed", type=int, default=20260629)
    parser.add_argument("--material-condition", default=DEFAULT_MATERIAL_CONDITION)
    parser.add_argument("--settle-steps", type=int, default=SETTLE_STEPS_PER_MOVE)
    parser.add_argument("--substeps-per-sample", type=int, default=GMO_SUBSTEPS)
    parser.add_argument("--step-m", type=float, default=APPROACH_STEP_M)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def vec_tuple(values: Any) -> tuple[float, float, float]:
    return tuple(float(values[i]) for i in range(3))


build_calibration_points = build_energy_calibration_points


def main() -> None:
    args = parse_args()
    if args.output_dir.exists() and not args.overwrite:
        existing = list(args.output_dir.glob("*"))
        if existing:
            raise SystemExit(f"Refusing to overwrite {args.output_dir}; pass --overwrite")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    spawn = spawn_wrench_position(args.trial_id, args.spawn_seed)
    simulation_app = SimulationApp({"headless": not bool(args.gui)})

    import numpy as np  # noqa: E402
    import omni  # noqa: E402
    import omni.replicator.core as rep  # noqa: E402
    import omni.timeline  # noqa: E402
    import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.api.objects import FixedCuboid  # noqa: E402
    from isaacsim.core.api.robots import Robot  # noqa: E402
    from isaacsim.core.experimental.materials import NonVisualMaterial  # noqa: E402
    from isaacsim.core.experimental.objects import Cube  # noqa: E402
    from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver  # noqa: E402
    from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor, parse_generic_model_output_data  # noqa: E402
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402
    from omni.replicator.core import Writer  # noqa: E402
    from pxr import UsdGeom  # noqa: E402

    context = omni.usd.get_context()
    context.new_stage()
    stage = context.get_stage()
    if stage is None:
        simulation_app.close()
        raise RuntimeError("Failed to create stage")
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    robot_path = ROBOT_PRIM_PATH
    spawn_ur10e_robotiq(
        stage=stage,
        stage_utils=stage_utils,
        assets_root=get_assets_root_path(),
        simulation_app=simulation_app,
        robot_path=robot_path,
    )
    sensor_mount_path = resolve_sensor_mount_path(robot_path, stage)
    sensor_path = f"{sensor_mount_path}/{SENSOR_PRIM_NAME}"

    room_prim_paths = create_six_wall_room(Cube, np)
    Cube(
        WRENCH_PRIM_PATH,
        positions=np.array(spawn.position_m, dtype=float),
        scales=np.array(WRENCH_SCALE_M, dtype=float),
        colors=WRENCH_COLOR,
    )
    set_prim_visibility(stage, CAMERA_FACING_WALL_PATH, visible=False)

    acoustic, sensor = create_passport_acoustic(
        sensor_path,
        Acoustic=Acoustic,
        AcousticSensor=AcousticSensor,
        np=np,
        tick_rate_hz=TICK_RATE_HZ,
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        sensor_local_offset_m=SENSOR_LOCAL_OFFSET_M,
        mount_spacing_m=SENSOR_MOUNT_SPACING_M,
        writer_brings_annotator=True,
    )

    writer_state: dict[str, Any] = {"last_fields": None, "frame": 0}

    class SweepGmoWriter(Writer):
        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]

        def write(self, data):
            for _rp, rp_data in data.get("renderProducts", {}).items():
                raw = rp_data.get("GenericModelOutput")
                if isinstance(raw, dict):
                    raw = raw.get("data")
                if raw is None or getattr(raw, "size", 0) == 0:
                    continue
                try:
                    gmo = parse_generic_model_output_data(raw)
                except Exception:
                    continue
                if int(gmo.numElements) <= 0:
                    continue
                writer_state["last_fields"] = enrich_gmo_summary(summarize_gmo_frame(gmo, np), gmo, np)
                break
            writer_state["frame"] += 1

    rep.WriterRegistry.register(SweepGmoWriter)
    sensor.attach_writer("SweepGmoWriter")

    world = World()
    robot = world.scene.add(Robot(prim_path=robot_path, name="ur10e"))
    world.reset()
    ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
    bootstrap_arm_after_world_reset(robot, world, ik_solver=ik)
    spawn_solid_work_table(
        world,
        stage,
        wrench_y_m=spawn.wrench_y_m,
        FixedCuboid=FixedCuboid,
        np=np,
    )
    collision_paths = list(GRASP_COLLISION_PRIM_PATHS) + [TABLE_PRIM_PATH]
    collision_status = enable_static_collisions(stage, collision_paths)
    print(f"Calibration sweep static collision: {collision_status}", flush=True)
    apply_room_and_target_materials(
        room_prim_paths or list(ROOM_PRIM_PATHS),
        WRENCH_PRIM_PATH,
        str(args.material_condition),
        Cube=Cube,
        NonVisualMaterial=NonVisualMaterial,
        table_prim_path=TABLE_PRIM_PATH,
    )
    apply_passport_display_colors(Cube, room_prim_paths or list(ROOM_PRIM_PATHS), WRENCH_PRIM_PATH)
    setup_robotiq_gripper(robot, world)

    cache = UsdGeom.XformCache(0)
    grasp_orientation = tool0_grasp_orientation_wxyz(ik, SEED_POSES_RAD["reach_forward"])

    def capture_gmo() -> dict[str, Any] | None:
        timeline = omni.timeline.get_timeline_interface()
        if not timeline.is_playing():
            timeline.play()
        writer_state["last_fields"] = None
        for i in range(max(1, int(args.substeps_per_sample))):
            world.step(render=(i == int(args.substeps_per_sample) - 1))
            simulation_app.update()
        for _ in range(5):
            simulation_app.update()
        return writer_state.get("last_fields")

    def observe_q(arm_q: np.ndarray, settle: int) -> dict[str, Any]:
        set_arm_joint_positions(robot, arm_q, world, settle_steps=settle)
        cache.Clear()
        sensor_matrix = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(sensor_path))
        sensor_position = vec_tuple(sensor_matrix.ExtractTranslation())
        arm_q_out = np.asarray(arm_q, dtype=float).reshape(-1)[:6]
        return {
            "q": arm_q_out,
            "sensor_position": sensor_position,
            "oracle_distance_m": oracle_distance_m(sensor_position, spawn.position_m),
        }

    def solve_ee_target(ee_target: tuple[float, float, float], warm: np.ndarray) -> tuple[np.ndarray, bool]:
        q, ok = solve_tool0_ik(
            ik,
            ee_target,
            warm,
            target_orientation=grasp_orientation,
            position_tolerance=float(IK_POSITION_TOLERANCE_M),
            orientation_tolerance=float(IK_GRASP_ORIENTATION_TOLERANCE_RAD),
        )
        return np.asarray(q, dtype=float), bool(ok)

    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    ee_target = list(search_start_ee_position_m())
    warm = np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float)
    q, ok = solve_ee_target(tuple(ee_target), warm)
    if not ok:
        simulation_app.close()
        raise RuntimeError(f"IK failed at search start {ee_target}")

    obs = observe_q(q, int(args.settle_steps))
    for step_idx in range(int(args.max_steps)):
        fields = capture_gmo()
        obs = observe_q(obs["q"], 1)
        sensor_x = float(obs["sensor_position"][0])
        row = {
            "step_index": step_idx,
            "ee_x_m": float(ee_target[0]),
            "ee_y_m": float(ee_target[1]),
            "ee_z_m": float(ee_target[2]),
            "sensor_x_m": sensor_x,
            "oracle_distance_m": float(obs["oracle_distance_m"]),
            "gmo_valid": bool(fields and fields.get("gmo_valid")),
            "primary_sgw_early_energy": float(fields.get("primary_sgw_early_energy", math.nan)) if fields else math.nan,
            "primary_sgw_first_time_offset_ns": float(fields.get("primary_sgw_first_time_offset_ns", math.nan))
            if fields
            else math.nan,
            "ref_sgw_early_energy": float(fields.get("ref_sgw_early_energy", math.nan)) if fields else math.nan,
            "rx_energy_balance": float(fields.get("rx_energy_balance", math.nan)) if fields else math.nan,
            "waveform_early_fraction": float(fields.get("waveform_early_fraction", math.nan)) if fields else math.nan,
        }
        if fields:
            for key in (
                "fused_distance_m",
                "estimated_distance_energy_m",
                "estimated_distance_tof_m",
                "peak_amplitude",
                "amplitude_std",
                "num_signal_ways",
            ):
                if key in fields:
                    row[key] = fields[key]
        rows.append(row)
        if sensor_x >= float(SEARCH_END_X_M):
            break
        ee_target[0] += float(args.step_m)
        q_next, ok_next = solve_ee_target(tuple(ee_target), obs["q"])
        if not ok_next:
            break
        obs = observe_q(q_next, int(args.settle_steps))

    calibration_points = build_calibration_points(rows)
    tof_points = build_tof_calibration_points(rows)
    tier_b_payload = tier_b_calibration_payload(
        rows,
        trial_id=int(args.trial_id),
        spawn_seed=int(args.spawn_seed),
        wrench_position_m=spawn.position_m,
    )
    runtime_s = time.perf_counter() - started

    sweep_csv = args.output_dir / "dynamic_approach_calibration_sweep.csv"
    with sweep_csv.open("w", newline="", encoding="utf-8") as handle:
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    summary = {
        "trial_id": args.trial_id,
        "spawn_seed": args.spawn_seed,
        "wrench_position_m": list(spawn.position_m),
        "num_samples": len(rows),
        "runtime_s": runtime_s,
        "calibration_points": calibration_points,
        "tof_calibration_points": tof_points,
        "claim_boundary": "Calibration uses oracle_distance_m for labeling only; runtime controller must not read wrench pose.",
    }
    summary_path = args.output_dir / "dynamic_approach_calibration_summary.json"
    tier_b_path = args.output_dir / "tier_b_calibration.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    with tier_b_path.open("w", encoding="utf-8") as handle:
        json.dump(tier_b_payload, handle, indent=2)

    print(f"Calibration sweep: {len(rows)} samples, {len(calibration_points)} energy points", flush=True)
    for energy, distance in calibration_points:
        print(f"  energy={energy:.2f} -> distance={distance:.3f}m", flush=True)
    print(f"TOF points: {len(tof_points)}", flush=True)
    for tof_ns, distance in tof_points:
        print(f"  tof_ns={tof_ns:.0f} -> distance={distance:.3f}m", flush=True)
    print(f"Wrote {sweep_csv}", flush=True)
    print(f"Wrote {summary_path}", flush=True)
    print(f"Wrote {tier_b_path}", flush=True)
    simulation_app.close()


if __name__ == "__main__":
    main()