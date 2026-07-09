"""Shared helpers for Phase C ultrasonic grasp and open-loop baseline."""

from __future__ import annotations

import dataclasses
import math
import os
from dataclasses import dataclass
from typing import Any, Callable

from grasp_passport_v1 import (
    ACOUSTIC_FUSION_ENERGY_WEIGHT,
    ACOUSTIC_LIFT_SUCCESS_ENERGY_RATIO,
    DEFAULT_CALIBRATION,
    DEFAULT_TOF_CALIBRATION,
    ECHO_CONTACT_ENERGY_DROP_RATIO,
    ECHO_GRASP_OCCLUSION_RATIO,
    GRASP_TOOL0_X_BACKOFF_M,
    WRENCH_HALF_LENGTH_M,
    WRENCH_SCALE_M,
    approach_ee_target_z_m,
    clamp_ee_target_for_approach,
    clamp_ee_target_for_grasp,
    DESCEND_DELTA_Z_M,
    grasp_alignment_tool0_x_m,
    GRASP_TOOL0_MIN_Z_M,
    GRIPPER_MAX_GRIP_DISTANCE_M,
    GRIPPER_SETTLE_STEPS,
    JOINT_DESCEND_MAX_STEPS,
    LIFT_DELTA_Z_M,
    LIFT_HOLD_STEPS,
    LIFT_MICRO_STEPS,
    LIFT_SUCCESS_MIN_Z_DELTA_M,
    max_tool0_x_before_wrench_center_m,
    TCP_Y_M,
    WRENCH_PRIM_PATH,
    WrenchSpawn,
    oracle_distance_m,
    passport_grasp_contact_ee_z_m,
    robotiq_grasp_contact_ee_z_m,
    surface_gripper_path,
)
from acoustic_calibration_v1 import load_tier_b_calibration
from rtx_acoustic_factory import acoustic_features_from_summary
from ur10e_robotiq_common import (
    apply_arm_delta_rad,
    joint_space_lower_ee,
    read_prim_world_z,
    read_scene_object_world_z,
    set_arm_joint_positions,
    stabilize_articulation,
    wrist_fine_delta_rad,
)
from ur10e_robotiq_passport_v1 import GRASP_LIFT_PHYSICS_SETTLE_STEPS, GRASP_POST_CLOSE_SETTLE_STEPS
from ur10e_robotiq_passport_v1 import ENABLE_WELD_FALLBACK as DEFAULT_ENABLE_WELD_FALLBACK
from ur10e_robotiq_passport_v1 import SEED_POSES_RAD, tool0_z_m
from ultrasonic_closed_loop_controller import (
    ControllerConfig,
    ControllerState,
    DistanceCalibration,
    UltrasonicClosedLoopController,
)

_TIER_B_CAL: tuple | None = None


def _tier_b_calibration_tables() -> tuple:
    global _TIER_B_CAL
    if _TIER_B_CAL is None:
        _TIER_B_CAL = load_tier_b_calibration()
    return _TIER_B_CAL


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__fspath__"):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def vec_tuple(values: Any) -> tuple[float, float, float]:
    return tuple(float(values[i]) for i in range(3))


@dataclass
class GraspRuntime:
    world: Any
    robot: Any
    ik: Any
    stage: Any
    sensor_path: str
    ee_path: str
    spawn: WrenchSpawn
    writer_state: dict[str, Any]
    capture_gmo: Callable[[], dict[str, Any] | None]
    observe_q: Callable[[Any, int], dict[str, Any]]
    solve_ee_target: Callable[[tuple[float, float, float], Any], tuple[Any, bool]]
    read_wrench_z_oracle: Callable[[], float]
    gripper_path: str = ""
    gripper_iface: Any | None = None
    gripper_view: Any | None = None
    robotiq_gripper: Any | None = None
    wrench_scene_object: Any | None = None
    enable_weld_fallback: bool = DEFAULT_ENABLE_WELD_FALLBACK
    settle_steps: int = 30
    contact_ee_z_m: float | None = None
    gui_motion: bool = False
    simulation_app: Any | None = None
    episode_id: int = 1
    solve_ee_grasp_target: Callable[[tuple[float, float, float], Any], tuple[Any, bool]] | None = None
    solve_ee_motion_target: Callable[[tuple[float, float, float], Any], tuple[Any, bool]] | None = None
    solve_ee_lift_target: Callable[[tuple[float, float, float], Any], tuple[Any, bool]] | None = None
    solve_ee_approach_target: Callable[[tuple[float, float, float], Any], tuple[Any, bool]] | None = None
    arm_q_holder: dict[str, Any] | None = None
    live_status_path: Any | None = None
    enable_approach_supervisor: bool = True
    wrench_prim_path: str = ""
    wrench_allow_velocity_reset: bool = True
    robot_path: str = ""
    wrench_physics_mode: str = "dynamic"
    skip_lift: bool = True
    grasp_contact_only: bool = False
    claim_mode: str = "scaffold"


def _acoustic_only_claim(runtime: GraspRuntime) -> bool:
    return str(getattr(runtime, "claim_mode", "scaffold")) == "acoustic_only"


def _sim_steps(runtime: GraspRuntime, count: int, *, render_override: bool | None = None) -> None:
    render = bool(runtime.gui_motion) if render_override is None else bool(render_override)
    for _ in range(max(0, int(count))):
        runtime.world.step(render=render)
        if render and runtime.simulation_app is not None:
            runtime.simulation_app.update()


def reset_scene_for_next_episode(
    runtime: GraspRuntime,
    *,
    spawn: WrenchSpawn,
    start_ee: tuple[float, float, float],
    warm_q: Any,
    reset_settle_steps: int = 60,
) -> dict[str, Any]:
    """Between in-session episodes: open gripper, reset wrench, return arm to search start."""
    import numpy as np

    wrench = _resolve_wrench_scene_object(runtime)
    if wrench is not None and hasattr(wrench, "set_world_pose"):
        position = np.array(spawn.position_m, dtype=float)
        orientation = np.array([1.0, 0.0, 0.0, 0.0], dtype=float)
        wrench.set_world_pose(position, orientation)
        if runtime.wrench_allow_velocity_reset:
            from ur10e_robotiq_common import safe_zero_rigid_body_velocities

            safe_zero_rigid_body_velocities(
                wrench,
                stage=runtime.stage,
                prim_path=runtime.wrench_prim_path,
            )
    _sim_steps(runtime, max(30, reset_settle_steps // 2))

    if runtime.robotiq_gripper is not None:
        runtime.robotiq_gripper.open(runtime.robot, runtime.world)

    runtime.spawn = spawn
    runtime.contact_ee_z_m = passport_grasp_contact_ee_z_m()

    q, ok = runtime.solve_ee_target(start_ee, np.asarray(warm_q, dtype=float))
    if not ok:
        raise RuntimeError(f"Episode reset failed: IK for search start {start_ee}")
    return runtime.observe_q(q, reset_settle_steps)


def setup_surface_gripper(stage: Any, ee_path: str, *, GripperView: Any, create_surface_gripper: Any) -> tuple[str, Any | None, Any | None]:
    # Parent the gripper under ee_link so it moves with the arm and is registered
    # correctly by the SurfaceGripper C++ plugin. The expected path matches
    # surface_gripper_path() from grasp_passport_v1.
    #
    # If the prim was pre-created before world.reset() (so the C++ plugin can register it
    # during physics init), reuse it rather than creating a duplicate via get_stage_next_free_path.
    _expected = f"{ee_path}/SurfaceGripper"
    if stage.GetPrimAtPath(_expected):
        gripper_prim = stage.GetPrimAtPath(_expected)
    else:
        gripper_prim = create_surface_gripper(stage, ee_path)
    path = str(gripper_prim.GetPath())

    # Isaac SurfaceGripper requires at least one attachment point. Place it at
    # the contact tip ahead of the ee_link origin along +X.
    # If the joint was pre-created before world.reset() (so physics initializes it), reuse it.
    joint_path = f"{path}/attachment_point_0"
    if not stage.GetPrimAtPath(joint_path):
        try:
            from pxr import Gf, Sdf, UsdPhysics
            from usd.schema.isaac import robot_schema

            joint = UsdPhysics.Joint.Define(stage, joint_path)
            joint.CreateBody0Rel().SetTargets([ee_path])
            joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.03, 0.0, -0.06))
            joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
            joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
            joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
            robot_schema.ApplyAttachmentPointAPI(joint.GetPrim())
            joint.GetPrim().GetAttribute(robot_schema.Attributes.FORWARD_AXIS.name).Set(UsdPhysics.Tokens.x)
            stage.GetPrimAtPath(path).GetRelationship(robot_schema.Relations.ATTACHMENT_POINTS.name).SetTargets(
                [Sdf.Path(joint_path)]
            )
        except Exception as exc:
            print(f"SurfaceGripper attachment point setup failed: {exc}", flush=True)
    else:
        print(f"SurfaceGripper reusing pre-created attachment point: {joint_path}", flush=True)

    view = GripperView(paths=path)
    view.set_surface_gripper_properties(
        max_grip_distance=[max(0.50, float(GRIPPER_MAX_GRIP_DISTANCE_M))],
        coaxial_force_limit=[5000.0],
        shear_force_limit=[5000.0],
        retry_interval=[0.05],
    )
    iface = None
    try:
        from isaacsim.robot.surface_gripper.bindings._surface_gripper import acquire_surface_gripper_interface

        iface = acquire_surface_gripper_interface()
        iface.open_gripper(path)
    except Exception:
        iface = None
    return path, iface, view


# Adjudication spike (health check F1, 2026-07-08): GRASP_BLIND_APPROACH=1 replaces
# fused/energy distance with +inf so the standoff trigger can never fire — the arm walks
# the corridor with zero acoustic information. Control run to test whether closed-loop
# stop behaviour differs from a sensor-blind policy. Default off; no effect otherwise.
BLIND_APPROACH = os.environ.get("GRASP_BLIND_APPROACH", "").strip() == "1"
if BLIND_APPROACH:
    print("BLIND_APPROACH=1: fused/energy distance forced to +inf (F1 adjudication control run)", flush=True)


def _acoustic_features_from_capture(fields: dict[str, Any] | None) -> Any:
    energy_cal, tof_cal, _meta = _tier_b_calibration_tables()
    frame = acoustic_features_from_summary(
        fields,
        energy_calibration=energy_cal,
        tof_calibration=tof_cal,
        fusion_energy_weight=ACOUSTIC_FUSION_ENERGY_WEIGHT,
    )
    if BLIND_APPROACH:
        frame = dataclasses.replace(
            frame,
            fused_distance_m=math.inf,
            estimated_distance_energy_m=math.inf,
        )
    return frame


def _append_approach_history_row(
    history_rows: list[dict[str, Any]],
    *,
    runtime: GraspRuntime,
    trial_id: int,
    controller: UltrasonicClosedLoopController,
    obs: dict[str, Any],
    features: Any,
    phase: str = "approach",
    motion_tier: str = "",
) -> None:
    row = {
        "phase": phase,
        "episode_id": runtime.episode_id,
        "trial_id": trial_id,
        "motion_tier": motion_tier,
        "controller_state": controller.telemetry.state.value,
        "sensor_x_m": obs["sensor_position"][0],
        "sensor_y_m": obs["sensor_position"][1],
        "oracle_distance_m": obs["oracle_distance_m"],
        "estimated_distance_m": controller.telemetry.estimated_distance_m,
        "fused_distance_m": controller.telemetry.fused_distance_m,
        "alignment_score": controller.telemetry.alignment_score,
        "rx_energy_balance": controller.telemetry.rx_energy_balance,
        "primary_sgw_early_energy": features.early_energy,
        "gmo_valid": features.gmo_valid,
    }
    row.update(features.as_log_dict())
    history_rows.append(row)


def _per_joint_delta_rad(current_q: Any, target_q: Any) -> Any:
    import numpy as np

    current = np.asarray(current_q, dtype=float).reshape(-1)[:6]
    target = np.asarray(target_q, dtype=float).reshape(-1)[:6]
    return np.abs((target - current + np.pi) % (2.0 * np.pi) - np.pi)


def _approach_ik_solver(
    runtime: GraspRuntime,
) -> Callable[[tuple[float, float, float], Any], tuple[Any, bool]]:
    if runtime.solve_ee_approach_target is not None:
        return runtime.solve_ee_approach_target
    return runtime.solve_ee_target


def _solve_multi_warm_ik(
    runtime: GraspRuntime,
    ee_target: tuple[float, float, float],
    current_q: Any,
    *,
    clamp_fn: Callable[[tuple[float, float, float]], tuple[float, float, float]],
    solve: Callable[[tuple[float, float, float], Any], tuple[Any, bool]],
) -> tuple[Any, bool]:
    """MoveIt-style IK: try several warm starts; prefer solutions that move all 6 arm joints."""
    import numpy as np

    from ur10e_robotiq_passport_v1 import UR10E_DEFAULT_Q_RAD, joint_delta_rad

    target = clamp_fn(ee_target)
    current = np.asarray(current_q, dtype=float).reshape(-1)[:6]
    warm_candidates = [
        current,
        np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float),
        np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float),
        np.asarray(UR10E_DEFAULT_Q_RAD, dtype=float),
    ]

    best_q = current
    best_ok = False
    best_score = -1.0
    seen: set[tuple[float, ...]] = set()
    for warm in warm_candidates:
        key = tuple(np.round(np.asarray(warm, dtype=float).reshape(-1)[:6], 4))
        if key in seen:
            continue
        seen.add(key)
        q, ok = solve(target, np.asarray(warm, dtype=float))
        if not ok:
            continue
        q_arr = np.asarray(q, dtype=float).reshape(-1)[:6]
        per_joint = _per_joint_delta_rad(current, q_arr)
        total = float(joint_delta_rad(current, q_arr))
        if total < 1e-5:
            continue
        wrist_motion = float(np.sum(per_joint[3:6]))
        shoulder_motion = float(np.sum(per_joint[0:3]))
        # Favor coordinated whole-arm motion (wrist participates, not only shoulder/elbow).
        score = wrist_motion + 0.35 * shoulder_motion + 0.15 * total
        if score > best_score:
            best_score = score
            best_q = q_arr
            best_ok = True
    return best_q, best_ok


def _solve_approach_ik(
    runtime: GraspRuntime,
    ee_target: tuple[float, float, float],
    current_q: Any,
) -> tuple[Any, bool]:
    return _solve_multi_warm_ik(
        runtime,
        ee_target,
        current_q,
        clamp_fn=clamp_ee_target_for_approach,
        solve=_approach_ik_solver(runtime),
    )


def _solve_grasp_ik_multi_warm(
    runtime: GraspRuntime,
    ee_target: tuple[float, float, float],
    current_q: Any,
) -> tuple[Any, bool]:
    solve = _grasp_ik_solver(runtime)
    return _solve_multi_warm_ik(
        runtime,
        ee_target,
        current_q,
        clamp_fn=clamp_ee_target_for_grasp,
        solve=solve,
    )


def _move_joint_trajectory_to_ee(
    runtime: GraspRuntime,
    obs: dict[str, Any],
    ee_target: tuple[float, float, float] | list[float],
    *,
    settle: int,
    solve_ik: Callable[[GraspRuntime, tuple[float, float, float], Any], tuple[Any, bool]] | None = None,
) -> tuple[dict[str, Any], bool, str]:
    """Solve IK once, then ramp all 6 arm joints together (MoveIt-style joint-space path)."""
    ik_fn = solve_ik or _solve_approach_ik
    q_goal, ok = ik_fn(runtime, tuple(ee_target), obs["q"])
    if not ok:
        return obs, False, "ik_failed"
    try:
        import numpy as np

        q_arr = np.asarray(q_goal, dtype=float).reshape(-1)
        if q_arr.size < 6 or not np.all(np.isfinite(q_arr[:6])):
            return obs, False, "ik_failed_nonfinite"
        obs = runtime.observe_q(q_arr[:6], settle)
    except Exception as exc:
        obs = {**obs, "motion_error": str(exc)}
        return obs, False, "joint_write_failed"
    return obs, True, "joint_trajectory"


def _tool0_xyz_m(runtime: GraspRuntime, arm_q: Any) -> tuple[float, float, float]:
    from ur10e_robotiq_passport_v1 import IK_EE_FRAME

    pos, _ = runtime.ik.compute_forward_kinematics(IK_EE_FRAME, arm_q)
    return float(pos[0]), float(pos[1]), float(pos[2])


def _at_forward_reach_cap(runtime: GraspRuntime, tool0_x: float) -> bool:
    max_x = max_tool0_x_before_wrench_center_m(runtime.spawn.wrench_x_m)
    return float(tool0_x) >= float(max_x) - 0.01


def _oracle_proximity_ok(oracle_m: float, *, slack_m: float = 0.12) -> bool:
    from ultrasonic_closed_loop_controller import ControllerConfig

    standoff = float(ControllerConfig().grasp_standoff_m)
    return math.isfinite(oracle_m) and float(oracle_m) <= standoff + float(slack_m)


def _fusion_saturated_vs_oracle(
    features: Any,
    oracle_m: float,
    *,
    runtime: GraspRuntime,
    tool0_x_m: float,
) -> bool:
    """Peak-dist overestimate only counts when tool0 has reached the forward cap."""
    if not _at_forward_reach_cap(runtime, tool0_x_m):
        return False
    peak_dist = DistanceCalibration().estimate_distance_m(features.primary_sgw_peak_sample_idx)
    standoff = float(ControllerConfig().grasp_standoff_m)
    return (
        math.isfinite(oracle_m)
        and float(oracle_m) <= standoff + 0.08
        and math.isfinite(peak_dist)
        and peak_dist > float(oracle_m) + 0.20
    )


def _check_approach_proximity_exit(
    runtime: GraspRuntime,
    obs: dict[str, Any],
    features: Any,
) -> str | None:
    cx, _, _ = _tool0_xyz_m(runtime, obs["q"])
    oracle_m = float(obs.get("oracle_distance_m", math.nan))
    if _at_forward_reach_cap(runtime, cx) and _oracle_proximity_ok(oracle_m):
        return "standoff_reached_forward_cap"
    if _fusion_saturated_vs_oracle(features, oracle_m, runtime=runtime, tool0_x_m=cx):
        return "standoff_reached_fusion_saturation"
    return None


def _cap_tool0_target_for_spawn(
    ee_target: list[float],
    runtime: GraspRuntime,
) -> list[float]:
    """Prevent acoustic creep from driving tool0 past the wrench along +X."""
    max_x = max_tool0_x_before_wrench_center_m(runtime.spawn.wrench_x_m)
    if float(ee_target[0]) > max_x:
        ee_target[0] = max_x
    return ee_target


def _tool0_grasp_geometry_ok(runtime: GraspRuntime, arm_q: Any) -> bool:
    """True when tool0 sits over the wrench footprint (medium-tier grasp success)."""
    tx, ty, tz = _tool0_xyz_m(runtime, arm_q)
    wx, wy, wz = runtime.spawn.position_m
    half_l = float(WRENCH_HALF_LENGTH_M)
    half_w = float(WRENCH_SCALE_M[1]) / 2.0
    x_ok = (wx - half_l - 0.05) <= tx <= (wx + half_l + 0.04)
    y_ok = abs(ty - wy) <= (half_w + 0.06)
    z_ok = tz <= robotiq_grasp_contact_ee_z_m(wz) + 0.05
    return x_ok and y_ok and z_ok


def _pre_grasp_align_tool0_xy(
    runtime: GraspRuntime,
    obs: dict[str, Any],
    ee_target: list[float],
) -> tuple[dict[str, Any], list[float], str]:
    """Retract/adjust XY after approach — fixes overshoot before Z descend + finger close."""
    wx, wy, _ = runtime.spawn.position_m
    target_x = grasp_alignment_tool0_x_m(wx)
    cx, cy, cz = _tool0_xyz_m(runtime, obs["q"])
    align_z = max(float(approach_ee_target_z_m()), float(cz))
    x_error = cx - target_x
    y_error = cy - wy
    undershoot = cx < target_x - 0.05
    needs_align = undershoot or x_error > 0.015 or abs(y_error) > 0.02
    if not needs_align:
        ee_target[0], ee_target[1], ee_target[2] = cx, cy, cz
        return obs, ee_target, "already_aligned"

    align_mode = "xy_forward" if undershoot else ("xy_retract" if x_error > 0.015 else "xy_lateral")
    moved = False
    forward_candidates = (
        target_x,
        wx - float(GRASP_TOOL0_X_BACKOFF_M) - 0.02,
        wx - float(GRASP_TOOL0_X_BACKOFF_M) - 0.05,
        max(cx + 0.04, cx),
        max(cx + 0.08, cx),
        max(cx + 0.12, cx),
    )
    retract_candidates = (
        target_x,
        wx - float(GRASP_TOOL0_X_BACKOFF_M) - 0.02,
        wx - float(GRASP_TOOL0_X_BACKOFF_M) - 0.05,
    )
    candidate_xs = forward_candidates if undershoot else retract_candidates
    for candidate_x in candidate_xs:
        if undershoot:
            if candidate_x < cx + 0.01:
                continue
            if candidate_x > target_x + 0.02:
                continue
        elif candidate_x > cx + 0.01:
            continue
        trial = [float(candidate_x), float(wy), float(align_z)]
        trial[:] = list(clamp_ee_target_for_approach(trial))
        obs_try, ok, _ = _move_joint_trajectory_to_ee(
            runtime,
            obs,
            tuple(trial),
            settle=max(12, runtime.settle_steps // 2),
            solve_ik=_solve_grasp_ik_multi_warm,
        )
        if not ok:
            continue
        cx, cy, cz = _tool0_xyz_m(runtime, obs_try["q"])
        if cx <= wx + 0.02 and abs(cy - wy) <= 0.05:
            obs = obs_try
            ee_target[0], ee_target[1], ee_target[2] = cx, cy, cz
            moved = True
            break

    if not moved and abs(y_error) > 0.02:
        trial = [float(ee_target[0]), float(wy), float(align_z)]
        trial[:] = list(clamp_ee_target_for_approach(trial))
        obs_try, ok, _ = _move_joint_trajectory_to_ee(
            runtime,
            obs,
            tuple(trial),
            settle=max(10, runtime.settle_steps // 2),
            solve_ik=_solve_grasp_ik_multi_warm,
        )
        if ok:
            obs = obs_try
            cx, cy, cz = _tool0_xyz_m(runtime, obs["q"])
            ee_target[0], ee_target[1], ee_target[2] = cx, cy, cz
            moved = True
            align_mode = "xy_lateral"

    if moved:
        obs = runtime.observe_q(obs["q"], max(8, runtime.settle_steps // 3))
        cx, cy, cz = _tool0_xyz_m(runtime, obs["q"])
        ee_target[0], ee_target[1], ee_target[2] = cx, cy, cz
    return obs, ee_target, align_mode if moved else "align_failed"


def _try_wrist_fine_motion(
    runtime: GraspRuntime,
    obs: dict[str, Any],
    motion: str,
    step_idx: int,
    *,
    settle: int,
    min_tool0_z_m: float | None = None,
) -> tuple[dict[str, Any], bool, str]:
    base_x, base_y, base_z = _tool0_xyz_m(runtime, obs["q"])
    for delta in wrist_fine_delta_rad(motion, step_idx):
        candidate_q = apply_arm_delta_rad(obs["q"], delta)
        try:
            cx, cy, cz = _tool0_xyz_m(runtime, candidate_q)
        except Exception:
            continue
        if min_tool0_z_m is not None and cz < float(min_tool0_z_m):
            continue
        if motion == "forward_x" and cx <= base_x + 0.003:
            continue
        if motion == "lower_z" and cz >= base_z - 0.003:
            continue
        if motion == "lateral_y_pos" and cy <= base_y + 0.002:
            continue
        if motion == "lateral_y_neg" and cy >= base_y - 0.002:
            continue
        obs = runtime.observe_q(candidate_q, settle)
        return obs, True, "wrist_fine"
    return obs, False, "wrist_fine_miss"


def run_approach_loop(
    runtime: GraspRuntime,
    *,
    start_ee: tuple[float, float, float],
    warm_q: Any,
    enable_grasp_phase: bool,
    trial_id: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], str, list[float], UltrasonicClosedLoopController, Any | None]:
    import numpy as np

    from approach_supervisor_v1 import ApproachSupervisor

    approach_min_samples = 10 if enable_grasp_phase else 3
    supervisor: ApproachSupervisor | None = None
    if runtime.enable_approach_supervisor and not _acoustic_only_claim(runtime):
        live_path = runtime.live_status_path
        if live_path is not None and not isinstance(live_path, type(None)):
            from pathlib import Path

            live_path = Path(live_path)
        supervisor = ApproachSupervisor(live_status_path=live_path if live_path else None)
    controller = UltrasonicClosedLoopController(
        config=ControllerConfig(
            enable_grasp_phase=enable_grasp_phase,
            min_approach_samples_before_standoff=approach_min_samples,
        ),
    )
    controller.reset()
    history_rows: list[dict[str, Any]] = []
    ee_target = list(clamp_ee_target_for_approach(start_ee))
    q_start, ok = _solve_approach_ik(runtime, tuple(ee_target), warm_q)
    if not ok:
        return {"oracle_distance_m": math.nan}, history_rows, "ik_failed_search_start", ee_target, controller, supervisor
    obs = runtime.observe_q(q_start, runtime.settle_steps)
    terminal_reason = "unknown"
    last_motion_tier = "joint_trajectory"
    for _ in range(2):
        runtime.capture_gmo()

    while True:
        fields = runtime.capture_gmo()
        features = _acoustic_features_from_capture(fields)
        obs = runtime.observe_q(obs["q"], 0)
        state = controller.observe(
            features=features,
            sensor_x_m=obs["sensor_position"][0],
            oracle_distance_m=obs["oracle_distance_m"],
        )
        _append_approach_history_row(
            history_rows,
            runtime=runtime,
            trial_id=trial_id,
            controller=controller,
            obs=obs,
            features=features,
            motion_tier=last_motion_tier,
        )
        last_motion_tier = "sense_hold"

        if supervisor is not None:
            try:
                tool0_x, _, _ = _tool0_xyz_m(runtime, obs["q"])
            except Exception:
                tool0_x = math.nan
            verdict = supervisor.evaluate(
                obs=obs,
                features=features,
                controller_state=controller.telemetry.state.value,
                tool0_x_m=tool0_x,
                wrench_x_m=runtime.spawn.wrench_x_m,
                step_index=controller.telemetry.step_index,
            )
            history_rows[-1]["supervisor_action"] = verdict.action.value
            history_rows[-1]["supervisor_message"] = verdict.message
            supervisor.publish_console(verdict, gui_only=bool(runtime.gui_motion))
            if verdict.recommended_exit and verdict.action.value in (
                "force_standoff",
            ):
                terminal_reason = verdict.recommended_exit
                break

        if not _acoustic_only_claim(runtime):

            proximity_exit = _check_approach_proximity_exit(runtime, obs, features)

            if proximity_exit is not None:

                terminal_reason = proximity_exit

                break

        if state in (ControllerState.AT_STANDOFF, ControllerState.DESCEND):
            last_action = controller.telemetry.history[-1].get("action") if controller.telemetry.history else ""
            if last_action == "standoff_reached_search_limit":
                terminal_reason = "standoff_reached_search_limit"
            elif last_action in ("lateral_limit_reached", "lateral_aligned", "lateral_skipped_balanced"):
                terminal_reason = "tier_b_lateral_complete"
            elif state == ControllerState.DESCEND:
                terminal_reason = "descend_ready"
            else:
                terminal_reason = "standoff_reached"
            break
        if state == ControllerState.FAIL:
            terminal_reason = controller.telemetry.fail_reason.value if controller.telemetry.fail_reason else "fail"
            if terminal_reason == "max_steps" and not _acoustic_only_claim(runtime):
                rescue = _check_approach_proximity_exit(runtime, obs, features)
                if rescue is not None:
                    terminal_reason = f"{rescue}_rescue"
            break
        if controller.should_step_forward():
            ee_target[0] += controller.step_forward_delta_x_m()
            ee_target[2] = approach_ee_target_z_m()
            ee_target[:] = list(clamp_ee_target_for_approach(ee_target))
            if not _acoustic_only_claim(runtime):
                ee_target[:] = _cap_tool0_target_for_spawn(ee_target, runtime)
            obs, moved, motion_tier = _move_joint_trajectory_to_ee(
                runtime,
                obs,
                tuple(ee_target),
                settle=runtime.settle_steps,
            )
            if not moved:
                standoff_slack = ControllerConfig().grasp_standoff_m + 0.12
                if math.isfinite(features.fused_distance_m) and features.fused_distance_m <= standoff_slack:
                    terminal_reason = "standoff_reached_ik_limit"
                    break
                terminal_reason = "ik_failed"
                break
            cx, cy, cz = _tool0_xyz_m(runtime, obs["q"])
            ee_target[0], ee_target[1], ee_target[2] = cx, cy, cz
            last_motion_tier = motion_tier
            if runtime.gui_motion:
                print(
                    f"Approach forward: step={controller.telemetry.step_index} "
                    f"tool0_x={cx:.3f} sensor_x={obs['sensor_position'][0]:.3f} "
                    f"oracle={obs['oracle_distance_m']:.3f} fused={features.fused_distance_m:.3f}",
                    flush=True,
                )
            if not _acoustic_only_claim(runtime):
                proximity_exit = _check_approach_proximity_exit(runtime, obs, features)
                if proximity_exit is not None:
                    terminal_reason = proximity_exit
                    break
            continue
        if controller.should_step_lateral_y():
            ee_target[1] += controller.step_lateral_delta_y_m()
            ee_target[1] = max(float(TCP_Y_M) - 0.08, min(float(TCP_Y_M) + 0.08, float(ee_target[1])))
            ee_target[:] = list(clamp_ee_target_for_approach(ee_target))
            obs, moved, motion_tier = _move_joint_trajectory_to_ee(
                runtime,
                obs,
                tuple(ee_target),
                settle=max(10, runtime.settle_steps // 2),
            )
            if moved:
                cx, cy, cz = _tool0_xyz_m(runtime, obs["q"])
                ee_target[0], ee_target[1], ee_target[2] = cx, cy, cz
            last_motion_tier = motion_tier
            continue
        if controller.should_step_final_forward():
            ee_target[0] += controller.step_final_forward_delta_x_m()
            ee_target[2] = approach_ee_target_z_m()
            ee_target[:] = list(clamp_ee_target_for_approach(ee_target))
            if not _acoustic_only_claim(runtime):
                ee_target[:] = _cap_tool0_target_for_spawn(ee_target, runtime)
            obs, moved, motion_tier = _move_joint_trajectory_to_ee(
                runtime,
                obs,
                tuple(ee_target),
                settle=max(10, runtime.settle_steps // 2),
            )
            if not moved:
                # Coarse approach already reached standoff; accept current position.
                terminal_reason = "standoff_reached_ik_limit"
                break
            cx, cy, cz = _tool0_xyz_m(runtime, obs["q"])
            ee_target[0], ee_target[1], ee_target[2] = cx, cy, cz
            last_motion_tier = motion_tier
            continue
        break

    return obs, history_rows, terminal_reason, ee_target, controller, supervisor


def _resolve_wrench_scene_object(runtime: GraspRuntime) -> Any:
    if runtime.world is not None and hasattr(runtime.world, "scene"):
        for key in (WRENCH_PRIM_PATH, "wrench_target"):
            fresh = runtime.world.scene.get_object(key)
            if fresh is not None:
                return fresh
    return runtime.wrench_scene_object


def _grasp_ik_solver(
    runtime: GraspRuntime,
) -> Callable[[tuple[float, float, float], Any], tuple[Any, bool]]:
    if runtime.solve_ee_grasp_target is not None:
        return runtime.solve_ee_grasp_target
    return runtime.solve_ee_target


def _summarize_wrench_physics(runtime: GraspRuntime) -> dict[str, Any]:
    from ur10e_robotiq_common import summarize_prim_physics_state

    path = runtime.wrench_prim_path or WRENCH_PRIM_PATH
    summary = summarize_prim_physics_state(runtime.stage, path)
    summary["wrench_physics_mode"] = runtime.wrench_physics_mode
    summary["skip_lift"] = runtime.skip_lift
    summary["oracle_z_m"] = runtime.read_wrench_z_oracle()
    return summary


def _apply_grasp_weld_joint(runtime: GraspRuntime) -> bool:
    """Attach wrench to ee_link for GUI kinematic lift (dynamic wrench only)."""
    if runtime.wrench_physics_mode != "dynamic":
        return False
    try:
        from pxr import Gf, UsdPhysics

        joint_path = f"{runtime.ee_path}/GraspWeldJoint"
        existing = runtime.stage.GetPrimAtPath(joint_path)
        if existing and existing.IsValid():
            return True
        joint = UsdPhysics.FixedJoint.Define(runtime.stage, joint_path)
        joint.CreateBody0Rel().SetTargets([runtime.ee_path])
        joint.CreateBody1Rel().SetTargets([WRENCH_PRIM_PATH])
        joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.08, 0.0, -0.05))
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        _sim_steps(runtime, 20, render_override=bool(runtime.gui_motion))
        return True
    except Exception:
        return False


def _prepare_physics_lift(runtime: GraspRuntime) -> dict[str, Any]:
    """Re-enable wrench collision before lift; optional weld for GUI kinematic carry."""
    from ur10e_robotiq_common import apply_robotiq_contact_friction, enable_wrench_collision

    mode: dict[str, Any] = {"wrench_collision_reenabled": False, "weld_applied": False}
    if runtime.wrench_physics_mode == "dynamic":
        mode["wrench_collision_reenabled"] = enable_wrench_collision(
            runtime.stage,
            runtime.wrench_prim_path or WRENCH_PRIM_PATH,
            enabled=True,
        )
        apply_robotiq_contact_friction(runtime.stage, runtime.robot_path, friction=3.0)
        _sim_steps(runtime, 5, render_override=bool(runtime.gui_motion))
    if runtime.enable_weld_fallback and runtime.gui_motion:
        mode["weld_applied"] = _apply_grasp_weld_joint(runtime)
    return mode


def _apply_gui_grasp_physics_freeze(runtime: GraspRuntime) -> dict[str, Any] | None:
    """Re-apply collision-off right before descend/close (GUI contact-only mode)."""
    if not runtime.gui_motion or not runtime.grasp_contact_only:
        return None
    from ur10e_robotiq_common import configure_grasp_contact_stability
    from ur10e_robotiq_passport_v1 import ROBOT_PRIM_PATH

    robot_path = getattr(runtime, "robot_path", None) or ROBOT_PRIM_PATH
    mode = configure_grasp_contact_stability(
        runtime.stage,
        robot_path=str(robot_path),
        wrench_prim_path=WRENCH_PRIM_PATH,
        disable_finger_collision=True,
        disable_wrench_collision=True,
        wrench_kinematic=False,
    )
    _sim_steps(runtime, 2, render_override=True)
    return mode


def _stabilize_wrench(runtime: GraspRuntime) -> None:
    if not runtime.wrench_allow_velocity_reset:
        _sim_steps(runtime, 15, render_override=False)
        return
    from ur10e_robotiq_common import safe_zero_rigid_body_velocities

    wrench = _resolve_wrench_scene_object(runtime)
    if wrench is None:
        return
    safe_zero_rigid_body_velocities(
        wrench,
        stage=runtime.stage,
        prim_path=runtime.wrench_prim_path,
    )
    _sim_steps(runtime, 15, render_override=False)


def _motion_ik_solver(
    runtime: GraspRuntime,
) -> Callable[[tuple[float, float, float], Any], tuple[Any, bool]]:
    if runtime.solve_ee_motion_target is not None:
        return runtime.solve_ee_motion_target
    return runtime.solve_ee_target


def _solve_ee_with_warm_fallback(
    runtime: GraspRuntime,
    ee_target: tuple[float, float, float],
    obs_q: Any,
    *,
    position_only: bool = False,
) -> tuple[Any, bool]:
    import numpy as np

    solve = _motion_ik_solver(runtime) if position_only else _grasp_ik_solver(runtime)
    warm_candidates = [
        np.asarray(obs_q, dtype=float),
        np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float),
    ]
    grasp_target = clamp_ee_target_for_grasp(ee_target)
    for warm_q in warm_candidates:
        q, ok = solve(grasp_target, warm_q)
        if ok:
            return q, True
    return np.asarray(obs_q, dtype=float), False


def _lift_ik_solver(
    runtime: GraspRuntime,
) -> Callable[[tuple[float, float, float], Any], tuple[Any, bool]]:
    if runtime.solve_ee_lift_target is not None:
        return runtime.solve_ee_lift_target
    if runtime.solve_ee_grasp_target is not None:
        return runtime.solve_ee_grasp_target
    return runtime.solve_ee_target


def _solve_lift_ik(
    runtime: GraspRuntime,
    ee_target: tuple[float, float, float],
    obs_q: Any,
    lift_warm_history: list[Any],
) -> tuple[Any, bool]:
    import numpy as np

    target = clamp_ee_target_for_grasp(ee_target)
    warm_candidates: list[Any] = []
    seen: set[tuple[float, ...]] = set()
    for q in (
        obs_q,
        *reversed(lift_warm_history),
        SEED_POSES_RAD["search_corridor"],
        SEED_POSES_RAD["reach_forward"],
    ):
        key = tuple(np.round(np.asarray(q, dtype=float).reshape(-1)[:6], 4))
        if key in seen:
            continue
        seen.add(key)
        warm_candidates.append(np.asarray(q, dtype=float))

    solvers: list[Callable[[tuple[float, float, float], Any], tuple[Any, bool]]] = [
        _lift_ik_solver(runtime),
    ]
    if runtime.solve_ee_grasp_target is not None:
        solvers.append(runtime.solve_ee_grasp_target)
    if runtime.solve_ee_motion_target is not None:
        solvers.append(runtime.solve_ee_motion_target)

    for solve in solvers:
        for warm_q in warm_candidates:
            q, ok = solve(target, warm_q)
            if ok:
                return q, True
    return np.asarray(obs_q, dtype=float), False


def _wrench_z_in_sane_range(z: float) -> bool:
    return math.isfinite(z) and -0.05 < z < 2.5


def _read_wrench_z(runtime: GraspRuntime) -> float:
    from pxr import UsdGeom

    expected_z = float(runtime.spawn.position_m[2])
    cache = UsdGeom.XformCache(0)

    def _pick_best_z(candidates: list[float]) -> float | None:
        sane = [z for z in candidates if _wrench_z_in_sane_range(z)]
        if not sane:
            return None
        near_spawn = [z for z in sane if abs(z - expected_z) <= 0.12]
        pool = near_spawn if near_spawn else sane
        return min(pool, key=lambda z: abs(z - expected_z))

    for _ in range(4):
        candidates: list[float] = []
        wrench_obj = _resolve_wrench_scene_object(runtime)
        z_obj = read_scene_object_world_z(wrench_obj, world=runtime.world)
        if _wrench_z_in_sane_range(z_obj):
            candidates.append(z_obj)
        z_oracle = runtime.read_wrench_z_oracle()
        if _wrench_z_in_sane_range(z_oracle):
            candidates.append(z_oracle)
        if runtime.stage is not None:
            z_prim = read_prim_world_z(runtime.stage, WRENCH_PRIM_PATH, cache, world=None)
            if _wrench_z_in_sane_range(z_prim):
                candidates.append(z_prim)
        best = _pick_best_z(candidates)
        if best is not None:
            return float(best)
        _sim_steps(runtime, 4, render_override=False)
    return math.nan


def _move_arm_with_grasp_hold(
    runtime: GraspRuntime,
    arm_q: Any,
    *,
    settle_steps: int,
    obs: dict[str, Any],
) -> dict[str, Any]:
    """Move arm kinematically but keep fingers in physics close during lift."""
    from ur10e_robotiq_common import get_arm_q

    set_arm_joint_positions(
        runtime.robot,
        arm_q,
        runtime.world,
        settle_steps=settle_steps,
        render=runtime.gui_motion,
        simulation_app=runtime.simulation_app,
        arm_only_kinematic=True,
    )
    arm_q_out = get_arm_q(runtime.robot)
    obs = {**obs, "q": arm_q_out}
    if runtime.robotiq_gripper is not None:
        runtime.robotiq_gripper.hold_closed(
            runtime.robot,
            runtime.world,
            hold_arm_q=obs["q"],
            kinematic_only=bool(runtime.gui_motion),
            simulation_app=runtime.simulation_app,
            render=bool(runtime.gui_motion),
        )
        stabilize_articulation(
            runtime.robot,
            runtime.world,
            steps=max(6, int(GRASP_LIFT_PHYSICS_SETTLE_STEPS)),
            render=bool(runtime.gui_motion),
            simulation_app=runtime.simulation_app,
        )
        if runtime.arm_q_holder is not None:
            runtime.arm_q_holder["q"] = obs["q"]
    return obs


def _fingers_near_closed(runtime: GraspRuntime) -> bool:
    from ur10e_robotiq_common import _try_read_robot_joint_q
    from ur10e_robotiq_passport_v1 import ROBOTIQ_FINGER_PHYSICS_CLOSE_RAD

    if runtime.robotiq_gripper is None:
        return False
    try:
        dof_names = list(runtime.robot.dof_names) if hasattr(runtime.robot, "dof_names") else list(
            runtime.robot.get_dof_names()
        )
        if "finger_joint" not in dof_names:
            return False
        q = _try_read_robot_joint_q(runtime.robot)
        if q is None:
            return True
        finger_q = float(q[dof_names.index("finger_joint")])
        return finger_q >= float(ROBOTIQ_FINGER_PHYSICS_CLOSE_RAD) * 0.65
    except Exception:
        return False


def _echo_energy_drop_detected(baseline_energy: float, current_energy: float, *, ratio: float) -> bool:
    if not math.isfinite(baseline_energy) or not math.isfinite(current_energy):
        return False
    if baseline_energy <= 1e-6:
        return False
    return current_energy <= baseline_energy * (1.0 - float(ratio))


def _acoustic_contact_sample(runtime: GraspRuntime) -> Any:
    fields = runtime.capture_gmo()
    return _acoustic_features_from_capture(fields)


def execute_grasp_and_lift(
    runtime: GraspRuntime,
    *,
    ee_target: list[float],
    obs: dict[str, Any],
    trial_id: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], str, bool]:
    """Tier B: acoustic echo triggers + passport geometry descend/grasp/lift."""
    history: list[dict[str, Any]] = []
    wrench_physics_before = _summarize_wrench_physics(runtime)
    history.append(
        {
            "phase": "wrench_physics",
            "episode_id": runtime.episode_id,
            "trial_id": trial_id,
            **wrench_physics_before,
        }
    )
    freeze_mode = _apply_gui_grasp_physics_freeze(runtime)
    if freeze_mode is not None:
        history.append(
            {
                "phase": "gui_physics_freeze",
                "episode_id": runtime.episode_id,
                "trial_id": trial_id,
                "finger_collision_paths": len(freeze_mode.get("finger_collision_paths", [])),
                "wrench_collision_disabled": freeze_mode.get("wrench_collision_disabled"),
            }
        )
    _stabilize_wrench(runtime)
    _sim_steps(runtime, 20, render_override=bool(runtime.gui_motion))

    baseline_features = _acoustic_contact_sample(runtime)
    baseline_energy = float(baseline_features.early_energy)
    align_mode = "tier_b_corridor_pose"
    history.append(
        {
            "phase": "align",
            "episode_id": runtime.episode_id,
            "trial_id": trial_id,
            "ee_x": ee_target[0],
            "ee_y": ee_target[1],
            "ee_z": ee_target[2],
            "align_mode": align_mode,
            "skipped": False,
            "baseline_early_energy": baseline_energy,
            "fused_distance_m": baseline_features.fused_distance_m,
        }
    )

    terminal_reason = "grasp_started"
    if _acoustic_only_claim(runtime):
        xy_align_mode = "skipped_acoustic_only_no_oracle_xy"
    else:
        obs, ee_target, xy_align_mode = _pre_grasp_align_tool0_xy(runtime, obs, ee_target)
    history.append(
        {
            "phase": "pre_grasp_align",
            "episode_id": runtime.episode_id,
            "trial_id": trial_id,
            "align_mode": xy_align_mode,
            "ee_x": ee_target[0],
            "ee_y": ee_target[1],
            "ee_z": ee_target[2],
            "oracle_distance_m": obs.get("oracle_distance_m"),
            "geometry_ok": _tool0_grasp_geometry_ok(runtime, obs["q"]),
        }
    )
    contact_z = (
        float(runtime.contact_ee_z_m)
        if runtime.contact_ee_z_m is not None
        else passport_grasp_contact_ee_z_m()
    )
    target_ee_z = max(float(GRASP_TOOL0_MIN_Z_M), contact_z)

    descended = False
    descend_mode = "none"
    if ee_target[2] <= target_ee_z + 0.02:
        descended = True
        descend_mode = "already_at_target"
    elif ee_target[2] > target_ee_z + 0.01:
        descend_steps = 6
        for step_idx in range(descend_steps):
            ee_target[2] = max(target_ee_z, ee_target[2] - float(DESCEND_DELTA_Z_M) / descend_steps)
            obs, moved, _ = _move_joint_trajectory_to_ee(
                runtime,
                obs,
                tuple(ee_target),
                settle=max(10, runtime.settle_steps // 3),
                solve_ik=_solve_grasp_ik_multi_warm,
            )
            if not moved:
                ee_target[2] += float(DESCEND_DELTA_Z_M) / descend_steps
                break
            _, _, cz = _tool0_xyz_m(runtime, obs["q"])
            ee_target[2] = float(cz)
            descended = True
            descend_mode = "joint_trajectory"
            sample = _acoustic_contact_sample(runtime)
            if _echo_energy_drop_detected(
                baseline_energy, sample.early_energy, ratio=ECHO_CONTACT_ENERGY_DROP_RATIO
            ):
                descend_mode = "joint_trajectory_echo_contact"
            if ee_target[2] <= target_ee_z + 0.01:
                break

    if (not descended or ee_target[2] > target_ee_z + 0.03) and ee_target[2] > target_ee_z + 0.05:
        arm_q = obs["q"]
        table_safe_z = float(GRASP_TOOL0_MIN_Z_M) + 0.02
        for step_idx in range(min(2, int(JOINT_DESCEND_MAX_STEPS))):
            candidate_q = joint_space_lower_ee(arm_q, step_idx)
            try:
                candidate_z = tool0_z_m(runtime.ik, candidate_q)
            except Exception:
                candidate_z = math.nan
            if not math.isfinite(candidate_z) or candidate_z < table_safe_z:
                break
            arm_q = candidate_q
            obs = runtime.observe_q(arm_q, max(10, runtime.settle_steps // 3))
            descended = True
            descend_mode = "joint_space_guarded"
            ee_target[2] = min(float(target_ee_z), float(candidate_z))
            if float(candidate_z) <= target_ee_z + 0.04:
                break
    elif not descended:
        descended = True
        descend_mode = "partial_height"

    history.append(
        {
            "phase": "descend",
            "episode_id": runtime.episode_id,
            "trial_id": trial_id,
            "ee_z": ee_target[2],
            "target_ee_z": target_ee_z,
            "descend_mode": descend_mode,
            "skipped": not descended,
        }
    )

    gripped = False
    weld_applied = False
    surface_status = ""
    surface_gripped_objects: list[Any] = []
    surface_error = ""
    gripper_mode = "contact_only_skipped_gripper" if bool(runtime.skip_lift) else "none"
    grasp_ee_z = float(ee_target[2])
    skip_lift = bool(runtime.skip_lift)
    grasp_geometry_ok = _tool0_grasp_geometry_ok(runtime, obs["q"])
    contact_only_echo_ok = bool(skip_lift and grasp_geometry_ok and "echo_contact" in str(descend_mode))
    if skip_lift:
        history.append(
            {
                "phase": "grasp",
                "episode_id": runtime.episode_id,
                "trial_id": trial_id,
                "gripper_mode": gripper_mode,
                "gripper_gripped": False,
                "weld_fallback": False,
                "pre_close_early_energy": math.nan,
                "post_close_early_energy": math.nan,
                "acoustic_grip_detected": False,
                "gripper_skipped_contact_only": True,
            }
        )
        history.append(
            {
                "phase": "verify",
                "episode_id": runtime.episode_id,
                "trial_id": trial_id,
                "wrench_z_before": runtime.read_wrench_z_oracle(),
                "wrench_z_after": runtime.read_wrench_z_oracle(),
                "lift_delta_z": 0.0,
                "gripper_gripped": False,
                "grasp_geometry_ok": grasp_geometry_ok,
                "grasp_contact_ok": False,
                "contact_only_echo_ok": contact_only_echo_ok,
                "contact_only_success": contact_only_echo_ok,
                "descend_mode": descend_mode,
                "acoustic_lift_ok": False,
                "physics_lift_ok": False,
                "arm_lift_ok": False,
                "ee_lift_delta_z": 0.0,
                "lift_skipped": True,
                "gripper_skipped_contact_only": True,
            }
        )
        reason = "contact_only_echo_success" if contact_only_echo_ok else "contact_only_failed"
        return obs, history, reason, contact_only_echo_ok

    from ur10e_robotiq_common import _apply_arm_only_kinematic

    from ur10e_robotiq_common import ensure_articulation_physics_ready

    _apply_arm_only_kinematic(runtime.robot, obs["q"])
    ensure_articulation_physics_ready(
        runtime.robot,
        runtime.world,
        runtime.simulation_app,
        render=bool(runtime.gui_motion),
    )
    stabilize_articulation(
        runtime.robot,
        runtime.world,
        steps=12,
        render=bool(runtime.gui_motion),
        simulation_app=runtime.simulation_app,
        zero_velocities=not bool(runtime.gui_motion),
    )
    _sim_steps(runtime, 15, render_override=bool(runtime.gui_motion))
    wrench_z_before = _read_wrench_z(runtime)
    pre_close_features = _acoustic_contact_sample(runtime)
    if runtime.robotiq_gripper is not None:
        gripper_mode = "robotiq_2f_85"
        kinematic_close = os.environ.get("GRASP_KINEMATIC_CLOSE", "1").strip().lower() in (
            "1",
            "true",
            "yes",
        ) or bool(runtime.gui_motion)
        runtime.robotiq_gripper.close(
            runtime.robot,
            runtime.world,
            hold_arm_q=obs["q"],
            kinematic_only=kinematic_close,
            simulation_app=runtime.simulation_app,
            render=bool(runtime.gui_motion),
        )
        if not runtime.gui_motion:
            stabilize_articulation(
                runtime.robot,
                runtime.world,
                steps=max(12, int(GRASP_POST_CLOSE_SETTLE_STEPS)),
                render=False,
                simulation_app=runtime.simulation_app,
            )
        runtime.robotiq_gripper.hold_closed(
            runtime.robot,
            runtime.world,
            hold_arm_q=obs["q"],
            kinematic_only=kinematic_close,
            simulation_app=runtime.simulation_app,
            render=bool(runtime.gui_motion),
        )
        _sim_steps(runtime, max(10, int(GRASP_POST_CLOSE_SETTLE_STEPS) // 3), render_override=bool(runtime.gui_motion))
        post_close_features = _acoustic_contact_sample(runtime)
        gripped = _echo_energy_drop_detected(
            pre_close_features.early_energy,
            post_close_features.early_energy,
            ratio=ECHO_GRASP_OCCLUSION_RATIO,
        )
        if not gripped:
            gripped = _fingers_near_closed(runtime)
        _, _, tz_close = _tool0_xyz_m(runtime, obs["q"])
        contact_z_close = robotiq_grasp_contact_ee_z_m(runtime.spawn.wrench_z_m)
        if gripped and tz_close <= contact_z_close + 0.08 and not _tool0_grasp_geometry_ok(runtime, obs["q"]):
            gripped = False
    elif runtime.gripper_iface is not None or runtime.gripper_view is not None:
        gripper_mode = "surface_gripper"
        try:
            if runtime.gripper_view is not None:
                runtime.gripper_view.apply_gripper_action([0.5])
            elif runtime.gripper_iface is not None:
                runtime.gripper_iface.close_gripper(runtime.gripper_path)
            _sim_steps(runtime, max(60, int(GRIPPER_SETTLE_STEPS)))
            if runtime.gripper_view is not None:
                statuses = runtime.gripper_view.get_surface_gripper_status()
                objects = runtime.gripper_view.get_gripped_objects()
                surface_status = str(statuses[0]) if statuses else ""
                surface_gripped_objects = list(objects[0]) if objects else []
            elif runtime.gripper_iface is not None:
                surface_status = str(runtime.gripper_iface.get_gripper_status(runtime.gripper_path))
                surface_gripped_objects = list(runtime.gripper_iface.get_gripped_objects(runtime.gripper_path))
            gripped = WRENCH_PRIM_PATH in surface_gripped_objects or len(surface_gripped_objects) > 0
        except Exception as exc:
            surface_error = str(exc)
            gripped = False
    if (
        not gripped
        and not _acoustic_only_claim(runtime)
        and runtime.enable_weld_fallback
        and obs.get("oracle_distance_m", math.inf) < 0.55
    ):
        try:
            from pxr import Gf, UsdPhysics

            joint_path = f"{runtime.ee_path}/GraspWeldJoint"
            joint = UsdPhysics.FixedJoint.Define(runtime.stage, joint_path)
            joint.CreateBody0Rel().SetTargets([runtime.ee_path])
            joint.CreateBody1Rel().SetTargets([WRENCH_PRIM_PATH])
            joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.08, 0.0, -0.05))
            joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
            _sim_steps(runtime, 20, render_override=False)
            weld_applied = True
            gripped = True
        except Exception:
            weld_applied = False
    history.append(
        {
            "phase": "grasp",
            "episode_id": runtime.episode_id,
            "trial_id": trial_id,
            "gripper_mode": gripper_mode,
            "gripper_gripped": gripped,
            "weld_fallback": weld_applied,
            "pre_close_early_energy": pre_close_features.early_energy,
            "post_close_early_energy": post_close_features.early_energy if runtime.robotiq_gripper else math.nan,
            "acoustic_grip_detected": gripped,
            "surface_status": surface_status,
            "surface_gripped_objects": surface_gripped_objects,
            "surface_error": surface_error,
        }
    )

    grasp_ee_z = float(ee_target[2])
    grasp_geometry_ok = _tool0_grasp_geometry_ok(runtime, obs["q"])
    grasp_contact_ok = bool(gripped and grasp_geometry_ok)
    skip_lift = bool(runtime.skip_lift)
    contact_only_echo_ok = bool(skip_lift and grasp_geometry_ok and (gripped or "echo_contact" in str(descend_mode)))
    if skip_lift and (grasp_contact_ok or contact_only_echo_ok):
        history.append(
            {
                "phase": "verify",
                "episode_id": runtime.episode_id,
                "trial_id": trial_id,
                "wrench_z_before": wrench_z_before,
                "wrench_z_after": wrench_z_before,
                "lift_delta_z": 0.0,
                "gripper_gripped": gripped,
                "grasp_geometry_ok": grasp_geometry_ok,
                "grasp_contact_ok": grasp_contact_ok,
                "contact_only_echo_ok": contact_only_echo_ok,
                "contact_only_success": contact_only_echo_ok or grasp_contact_ok,
                "descend_mode": descend_mode,
                "acoustic_lift_ok": False,
                "physics_lift_ok": False,
                "arm_lift_ok": False,
                "ee_lift_delta_z": 0.0,
                "lift_skipped": True,
            }
        )
        reason = "grasp_contact_success" if grasp_contact_ok else "contact_only_echo_success"
        return obs, history, reason, True

    lift_prep = _prepare_physics_lift(runtime)
    history.append(
        {
            "phase": "lift_prep",
            "episode_id": runtime.episode_id,
            "trial_id": trial_id,
            **lift_prep,
            "wrench_physics": _summarize_wrench_physics(runtime),
        }
    )
    if lift_prep.get("weld_applied"):
        gripped = True
        weld_applied = True

    lifted = False
    lift_mode = "none"
    lift_micro_steps = max(4, int(LIFT_MICRO_STEPS))
    lift_settle = max(16, runtime.settle_steps // 2)
    lift_steps_completed = 0
    lift_warm_history: list[Any] = []
    for step_idx in range(lift_micro_steps):
        ee_target[2] += float(LIFT_DELTA_Z_M) / float(lift_micro_steps)
        q_lift, ok = _solve_lift_ik(runtime, tuple(ee_target), obs["q"], lift_warm_history)
        if not ok:
            ee_target[2] -= float(LIFT_DELTA_Z_M) / float(lift_micro_steps)
            break
        lift_warm_history.append(obs["q"])
        obs = _move_arm_with_grasp_hold(runtime, q_lift, settle_steps=lift_settle, obs=obs)
        lift_warm_history.append(obs["q"])
        lift_steps_completed += 1
        lifted = True
        lift_mode = "cartesian_ik_physics_hold"
    if not lifted:
        return obs, history, "ik_failed_lift", False
    for _ in range(int(LIFT_HOLD_STEPS)):
        if runtime.robotiq_gripper is not None:
            runtime.robotiq_gripper.hold_closed(
                runtime.robot,
                runtime.world,
                hold_arm_q=obs["q"],
                kinematic_only=bool(runtime.gui_motion),
                simulation_app=runtime.simulation_app,
                render=bool(runtime.gui_motion),
            )
        runtime.world.step(render=bool(runtime.gui_motion))
        if runtime.gui_motion and runtime.simulation_app is not None:
            runtime.simulation_app.update()
    history.append(
        {
            "phase": "lift",
            "episode_id": runtime.episode_id,
            "trial_id": trial_id,
            "ee_z": ee_target[2],
            "lift_mode": lift_mode,
            "lift_steps_completed": lift_steps_completed,
            "lift_micro_steps": lift_micro_steps,
        }
    )

    if runtime.robotiq_gripper is not None:
        runtime.robotiq_gripper.hold_closed(
            runtime.robot,
            runtime.world,
            hold_arm_q=obs["q"],
            kinematic_only=bool(runtime.gui_motion),
            simulation_app=runtime.simulation_app,
            render=bool(runtime.gui_motion),
        )
    _sim_steps(runtime, 35, render_override=bool(runtime.gui_motion))
    wrench_z_after = _read_wrench_z(runtime)
    lift_delta = wrench_z_after - wrench_z_before
    post_lift_features = _acoustic_contact_sample(runtime)
    acoustic_lift_ok = _echo_energy_drop_detected(
        baseline_energy,
        post_lift_features.early_energy,
        ratio=ACOUSTIC_LIFT_SUCCESS_ENERGY_RATIO,
    )
    ee_lift_delta = float(ee_target[2]) - grasp_ee_z
    physics_lift_ok = (
        math.isfinite(wrench_z_before)
        and math.isfinite(wrench_z_after)
        and lift_delta >= float(LIFT_SUCCESS_MIN_Z_DELTA_M)
    )
    arm_lift_ok = bool(gripped and lifted and ee_lift_delta >= 0.008)
    geometry_ok = _tool0_grasp_geometry_ok(runtime, obs["q"])
    grasp_contact_ok = bool(gripped and geometry_ok)
    success = bool(grasp_contact_ok or (gripped and (physics_lift_ok or arm_lift_ok or acoustic_lift_ok)))
    if success and grasp_contact_ok and not (physics_lift_ok or arm_lift_ok):
        terminal_reason = "grasp_contact_success"
    elif success:
        terminal_reason = "grasp_lift_success"
    else:
        terminal_reason = "grasp_contact_failed" if not gripped else "grasp_lift_failed"
    history.append(
        {
            "phase": "verify",
            "episode_id": runtime.episode_id,
            "trial_id": trial_id,
            "wrench_z_before": wrench_z_before,
            "wrench_z_after": wrench_z_after,
            "lift_delta_z": lift_delta,
            "gripper_gripped": gripped,
            "grasp_geometry_ok": geometry_ok,
            "grasp_contact_ok": grasp_contact_ok,
            "acoustic_lift_ok": acoustic_lift_ok,
            "physics_lift_ok": physics_lift_ok,
            "arm_lift_ok": arm_lift_ok,
            "ee_lift_delta_z": ee_lift_delta,
            "post_lift_early_energy": post_lift_features.early_energy,
        }
    )
    return obs, history, terminal_reason, success