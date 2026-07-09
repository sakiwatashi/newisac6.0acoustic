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
    extract_primary_raw_amplitudes,
    matched_filter_tof,
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
    parser.add_argument("--baseline-steps", type=int, default=3)
    parser.add_argument("--baseline-mode", action="store_true")
    parser.add_argument("--baseline-npy", type=Path, default=None)
    parser.add_argument("--save-baseline-npy", type=Path, default=None)
    parser.add_argument("--mf-sample-period-us", type=float, default=132.5)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--az-span-deg", type=float, default=90.0,
                        help="WPM beam azimuth span in degrees (default 90=omnidirectional; 45=CH201-like directional)")
    parser.add_argument("--el-span-deg", type=float, default=90.0,
                        help="WPM beam elevation span in degrees (default 90=omnidirectional; 45=CH201-like directional)")
    parser.add_argument("--trace-tree-depth", type=int, default=2,
                        help="WPM max ray bounces (default 2; set 1 for direct-echo only)")
    parser.add_argument("--open-space", action="store_true",
                        help="Remove ceiling and x_max wall (open-space mode: wrench is primary forward reflector)")
    # WPM parametric model tuning (schema defaults: closeIndirectAmpl=17.64, closeDirectAmpl=12.66)
    parser.add_argument("--close-indirect-ampl", type=float, default=None,
                        help="WPM indirect echo amplitude multiplier (schema default 17.64). Set near 0 to suppress room model.")
    parser.add_argument("--close-direct-ampl", type=float, default=None,
                        help="WPM direct echo amplitude multiplier (schema default 12.66). Boost to emphasise target echo.")
    parser.add_argument("--close-range", type=float, default=None,
                        help="WPM close-range threshold in metres (schema default 1.42m).")
    parser.add_argument("--close-range-decay", type=float, default=None,
                        help="WPM close-range amplitude decay factor (schema default 1.26).")
    parser.add_argument("--close-direct-ampl-base", type=float, default=None,
                        help="WPM direct echo base amplitude (schema default 1.39).")
    parser.add_argument("--close-indirect-ampl-base", type=float, default=None,
                        help="WPM indirect echo base amplitude (schema default 1.12).")
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

    room_prim_paths = create_six_wall_room(Cube, np, open_space=args.open_space)
    Cube(
        WRENCH_PRIM_PATH,
        positions=np.array(spawn.position_m, dtype=float),
        scales=np.array(WRENCH_SCALE_M, dtype=float),
        colors=WRENCH_COLOR,
    )
    set_prim_visibility(stage, CAMERA_FACING_WALL_PATH, visible=False)
    if args.baseline_mode:
        set_prim_visibility(stage, WRENCH_PRIM_PATH, visible=False)
        print("Baseline mode: wrench hidden from scene", flush=True)

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
        az_span_deg=args.az_span_deg,
        el_span_deg=args.el_span_deg,
        trace_tree_depth=args.trace_tree_depth,
        close_indirect_ampl=args.close_indirect_ampl,
        close_direct_ampl=args.close_direct_ampl,
        close_range=args.close_range,
        close_range_decay=args.close_range_decay,
        close_direct_ampl_base=args.close_direct_ampl_base,
        close_indirect_ampl_base=args.close_indirect_ampl_base,
    )

    writer_state: dict[str, Any] = {"last_fields": None, "last_primary_amps": None, "frame": 0}

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
                writer_state["last_primary_amps"] = extract_primary_raw_amplitudes(gmo, np)
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
        writer_state["last_primary_amps"] = None
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
    baseline_amps: Any = None
    baseline_accum: list = []

    # Global baseline: load pre-recorded no-wrench waveforms
    global_baseline_arr: Any = None
    if args.baseline_npy is not None and not args.baseline_mode:
        global_baseline_arr = np.load(str(args.baseline_npy))
        print(f"Loaded global baseline: {global_baseline_arr.shape}", flush=True)

    # Matched filter sample period
    mf_sample_period_s = float(args.mf_sample_period_us) * 1e-6

    # Baseline mode: accumulate waveforms for saving
    baseline_mode_amps: list = []

    for step_idx in range(int(args.max_steps)):
        fields = capture_gmo()
        current_amps = writer_state.get("last_primary_amps")

        # Accumulate baseline from first N valid captures (largest oracle_distance)
        if baseline_amps is None and current_amps is not None:
            baseline_accum.append(np.array(current_amps, dtype=float))
            if len(baseline_accum) >= int(args.baseline_steps):
                baseline_amps = np.mean(np.stack(baseline_accum), axis=0)

        # Compute per-trial differential waveform features (current - per-trial baseline)
        if (
            baseline_amps is not None
            and current_amps is not None
            and len(current_amps) == len(baseline_amps)
        ):
            diff_abs = np.abs(current_amps - baseline_amps)
            n_smp = len(diff_abs)
            _early_n = max(4, int(math.ceil(n_smp * 0.25)))
            _ultra_n = max(4, int(math.ceil(n_smp * 0.10)))
            diff_early_energy = float(np.sum(diff_abs[:_early_n]))
            diff_ultra_early_energy = float(np.sum(diff_abs[:_ultra_n]))
            diff_peak_sample_idx = int(np.argmax(np.abs(current_amps - baseline_amps)))
            diff_early_peak_sample_idx = int(np.argmax(diff_abs[:_ultra_n]))
        else:
            diff_early_energy = math.nan
            diff_ultra_early_energy = math.nan
            diff_peak_sample_idx = -1
            diff_early_peak_sample_idx = -1

        # Matched filter ToF estimation
        if current_amps is not None and len(current_amps) > 0:
            mf_peak_idx, mf_peak_val = matched_filter_tof(
                current_amps,
                float(CENTER_FREQUENCY_HZ),
                mf_sample_period_s,
                np,
            )
            mf_tof_distance_m = float(mf_peak_idx) * mf_sample_period_s * 343.0 / 2.0
        else:
            mf_peak_idx = -1
            mf_peak_val = math.nan
            mf_tof_distance_m = math.nan

        # Global differential (current - no-wrench baseline loaded from .npy)
        if (
            global_baseline_arr is not None
            and current_amps is not None
            and step_idx < len(global_baseline_arr)
            and len(current_amps) == len(global_baseline_arr[step_idx])
        ):
            gbline = global_baseline_arr[step_idx]
            gdiff_abs = np.abs(current_amps - gbline)
            n_gsmp = len(gdiff_abs)
            _ge_n = max(4, int(math.ceil(n_gsmp * 0.25)))
            _gue_n = max(4, int(math.ceil(n_gsmp * 0.10)))
            global_diff_early_energy = float(np.sum(gdiff_abs[:_ge_n]))
            global_diff_ultra_early_energy = float(np.sum(gdiff_abs[:_gue_n]))
            global_diff_early_peak_sample_idx = int(np.argmax(gdiff_abs[:_gue_n]))
        else:
            global_diff_early_energy = math.nan
            global_diff_ultra_early_energy = math.nan
            global_diff_early_peak_sample_idx = -1

        # Baseline mode: collect waveforms for saving
        if args.baseline_mode and current_amps is not None:
            baseline_mode_amps.append(np.array(current_amps, dtype=float))

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
            "diff_early_energy": diff_early_energy,
            "diff_ultra_early_energy": diff_ultra_early_energy,
            "diff_peak_sample_idx": diff_peak_sample_idx,
            "diff_early_peak_sample_idx": diff_early_peak_sample_idx,
            "mf_tof_sample_idx": mf_peak_idx,
            "mf_tof_distance_m": mf_tof_distance_m,
            "global_diff_early_energy": global_diff_early_energy,
            "global_diff_ultra_early_energy": global_diff_ultra_early_energy,
            "global_diff_early_peak_sample_idx": global_diff_early_peak_sample_idx,
        }
        if fields:
            for key in (
                "fused_distance_m",
                "estimated_distance_energy_m",
                "estimated_distance_tof_m",
                "peak_amplitude",
                "amplitude_std",
                "num_signal_ways",
                "primary_sgw_peak_sample_idx",
                "primary_sgw_ultra_early_energy",
                "primary_sgw_early_peak_sample_idx",
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

    # Save baseline waveforms if in baseline mode
    if args.baseline_mode and args.save_baseline_npy and baseline_mode_amps:
        save_arr = np.stack(baseline_mode_amps)
        args.save_baseline_npy.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(args.save_baseline_npy), save_arr)
        print(f"Saved global baseline: {args.save_baseline_npy} shape={save_arr.shape}", flush=True)

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