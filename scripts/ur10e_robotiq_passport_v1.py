"""UR10e + Robotiq 2F-85 passport for Phase B/C ultrasonic grasp."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

PASSPORT_VERSION = "v1.0"
PASSPORT_ID = "ur10e_robotiq_ultrasonic_closed_loop_grasp"
EXPERIMENT_MODE = "ur10e_robotiq_ultrasonic_grasp_v1"

ROBOT_PRIM_PATH = "/World/ur10"
ROBOT_USD_REL = "Isaac/Robots/UniversalRobots/ur10e/ur10e.usd"
GRIPPER_VARIANT = "Robotiq_2f_85"

# Lula IK uses arm URDF only (6 DOF); gripper joints are controlled separately.
IK_ROBOT_DESCRIPTION = Path(
    "/home/lab109/song/isaacsim6.0/app/extsDeprecated/isaacsim.robot_motion.motion_generation/"
    "motion_policy_configs/universal_robots/ur10e/rmpflow/ur10e_robot_description.yaml"
)
IK_URDF = Path(
    "/home/lab109/song/isaacsim6.0/app/extsDeprecated/isaacsim.robot_motion.motion_generation/"
    "motion_policy_configs/universal_robots/ur10e/ur10e.urdf"
)
IK_EE_FRAME = "tool0"
USD_EE_FRAME = "ee_link"
# Grasp IK must lock tool0 to the reach_forward FK orientation. Identity quaternion makes tool +Z
# point at the ceiling (verified 2026-06-30); reach_forward makes tool +Z point down for table grasp.
IK_GRASP_ORIENTATION_TOLERANCE_RAD = 0.15
# Approach corridor: lock tool0 to downward grasp orientation (position-only leaves gripper pointing up).
IK_APPROACH_POSITION_ONLY = False
IK_MAX_JOINT_JUMP_APPROACH_RAD = 2.0
IK_MAX_JOINT_JUMP_GRASP_RAD = 0.85
IK_MAX_JOINT_JUMP_LIFT_RAD = 1.25
# wrist_3 is the free tool-spin DOF; orientation-locked IK can flip it by 2*pi without this guard.
IK_MAX_WRIST_3_JUMP_RAD = 0.75
ARM_MOTION_MAX_STEP_RAD = 0.04
ARM_HOME_MAX_STEP_RAD = 0.03
# Ultrasonic approach/grasp: drive joints kinematically (set_joint_positions) so PhysX
# does not leave the arm in world.reset()'s all-zero default (gripper z≈0.06 under table).
ARM_KINEMATIC_CONTROL = True
# Grasp close: finger joints via apply_action (PhysX) while arm stays kinematically held.
# Default off — PhysX finger PD + table/target contact causes GUI spin/crash (2026-06-30).
GRASP_FINGER_PHYSICS_CONTROL = os.environ.get("GRASP_FINGER_PHYSICS_CONTROL", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
ROBOTIQ_FINGER_CLOSE_RAMP_STEPS = 10

ARM_JOINT_NAMES: tuple[str, ...] = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)

# Isaac Lab gear-assembly reference widths for Robotiq 2F-85 (radians, main finger_joint).
ROBOTIQ_FINGER_OPEN_RAD = 0.0
# Isaac manipulator tests use ~45 deg closed for Robotiq mimic finger_joint.
ROBOTIQ_FINGER_CLOSE_RAD = 45.0 * 3.141592653589793 / 180.0
# Physics pilot: partial close grips 8 cm wrench (0.58 rad ≈ 33° — stronger hold for lift).
ROBOTIQ_FINGER_PHYSICS_CLOSE_RAD = 0.52
ROBOTIQ_GRIPPER_SETTLE_STEPS = 40
GRASP_POST_CLOSE_SETTLE_STEPS = 60
GRASP_LIFT_PHYSICS_SETTLE_STEPS = 18

# Sensor remains on ee_link; offset passport unchanged from geometry_passport_v1.
# UR10e Lula default_q (ur10e_robot_description.yaml) — safe FK warm start for corridor IK.
UR10E_DEFAULT_Q_RAD: tuple[float, float, float, float, float, float] = (
    -0.0,
    -1.2,
    1.1,
    0.0,
    0.0,
    0.0,
)

SEED_POSES_RAD: dict[str, tuple[float, float, float, float, float, float]] = {
    # Orientation reference only — tool0 reaches x≈0.91 and upper-arm links slice through the table.
    "reach_forward": (0.0, -1.20, 1.20, -1.57, -1.57, 0.0),
    "isaaclab_home": (3.14159, -1.5708, 1.5708, -1.5708, -1.5708, 0.0),
    # FK-verified corridor start (tool0≈0.47,0.16,0.65, grasp-down); orientation-locked IK 2026-06-30.
    "search_corridor": (-0.031, -1.949, 1.92, -1.541, -1.569, -0.031),
}

ENABLE_WELD_FALLBACK = os.environ.get("GRASP_ENABLE_WELD_FALLBACK", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)


def rotation_matrix_to_quat_wxyz(rotation: Any) -> Any:
    """Convert a 3x3 rotation matrix to an Isaac/Lula wxyz quaternion."""
    import numpy as np

    m = np.asarray(rotation, dtype=float).reshape(3, 3)
    trace = float(m[0, 0] + m[1, 1] + m[2, 2])
    if trace > 0.0:
        s = (trace + 1.0) ** 0.5 * 2.0
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = (1.0 + m[0, 0] - m[1, 1] - m[2, 2]) ** 0.5 * 2.0
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = (1.0 + m[1, 1] - m[0, 0] - m[2, 2]) ** 0.5 * 2.0
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = (1.0 + m[2, 2] - m[0, 0] - m[1, 1]) ** 0.5 * 2.0
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z], dtype=float)
    norm = float(np.linalg.norm(q))
    if norm <= 0.0:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=float)
    return q / norm


def joint_delta_rad(current_q: Any, target_q: Any) -> float:
    """Minimum angular distance per joint (handles +/- pi wrap)."""
    import numpy as np

    current = np.asarray(current_q, dtype=float).reshape(-1)
    target = np.asarray(target_q, dtype=float).reshape(-1)
    n = min(current.size, target.size)
    if n == 0:
        return 0.0
    delta = (target[:n] - current[:n] + np.pi) % (2.0 * np.pi) - np.pi
    if not np.all(np.isfinite(delta)):
        return float("inf")
    return float(np.max(np.abs(delta)))


def interpolate_arm_joints(current_q: Any, target_q: Any, alpha: float) -> Any:
    import numpy as np

    current = np.asarray(current_q, dtype=float).reshape(-1)
    target = np.asarray(target_q, dtype=float).reshape(-1)
    n = min(current.size, target.size, len(ARM_JOINT_NAMES))
    delta = (target[:n] - current[:n] + np.pi) % (2.0 * np.pi) - np.pi
    return current[:n] + float(alpha) * delta


def solve_tool0_ik(
    ik_solver: Any,
    ee_target: tuple[float, float, float] | Any,
    warm_q: Any,
    *,
    target_orientation: Any | None,
    position_tolerance: float,
    orientation_tolerance: float,
    max_joint_jump_rad: float = IK_MAX_JOINT_JUMP_APPROACH_RAD,
    max_wrist_3_jump_rad: float | None = IK_MAX_WRIST_3_JUMP_RAD,
    min_tool0_z_m: float | None = None,
) -> tuple[Any, bool]:
    """IK with optional orientation lock and rejection of discontinuous joint flips."""
    import numpy as np

    warm = np.asarray(warm_q, dtype=float).reshape(-1)[:6]
    target = np.asarray(ee_target, dtype=float).reshape(3)
    if min_tool0_z_m is not None:
        target[2] = max(float(target[2]), float(min_tool0_z_m))
    orient = None if target_orientation is None else np.asarray(target_orientation, dtype=float)
    orient_tol = None if target_orientation is None else float(orientation_tolerance)
    q, ok = ik_solver.compute_inverse_kinematics(
        IK_EE_FRAME,
        target,
        target_orientation=orient,
        warm_start=warm,
        position_tolerance=float(position_tolerance),
        orientation_tolerance=orient_tol,
    )
    q = np.asarray(q, dtype=float)
    if ok and joint_delta_rad(warm, q) > float(max_joint_jump_rad):
        return q, False
    if ok and max_wrist_3_jump_rad is not None and q.size >= 6 and warm.size >= 6:
        wrist_delta = abs((float(q[5]) - float(warm[5]) + math.pi) % (2.0 * math.pi) - math.pi)
        if wrist_delta > float(max_wrist_3_jump_rad):
            return q, False
    if ok and min_tool0_z_m is not None:
        pos, _ = ik_solver.compute_forward_kinematics(IK_EE_FRAME, q)
        if float(pos[2]) < float(min_tool0_z_m) - 0.01:
            return q, False
    return q, bool(ok)


def resolve_search_corridor_pose_rad(ik_solver: Any) -> Any:
    """Startup/search-corridor joint pose — tool0 above table, x before table span."""
    import numpy as np

    from geometry_passport_v1 import IK_POSITION_TOLERANCE_M
    from grasp_passport_v1 import approach_ee_target_z_m, search_start_ee_position_m

    warm = np.asarray(UR10E_DEFAULT_Q_RAD, dtype=float)
    grasp_orient = tool0_grasp_orientation_wxyz(ik_solver)
    q, ok = solve_tool0_ik(
        ik_solver,
        search_start_ee_position_m(),
        warm,
        target_orientation=grasp_orient,
        position_tolerance=float(IK_POSITION_TOLERANCE_M),
        orientation_tolerance=float(IK_GRASP_ORIENTATION_TOLERANCE_RAD),
        max_joint_jump_rad=float(IK_MAX_JOINT_JUMP_APPROACH_RAD),
        max_wrist_3_jump_rad=float(IK_MAX_WRIST_3_JUMP_RAD),
        min_tool0_z_m=approach_ee_target_z_m(),
    )
    if ok:
        return np.asarray(q, dtype=float)
    return np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float)


def tool0_z_m(ik_solver: Any, arm_q: Any) -> float:
    """FK tool0 height for table-clearance guards."""
    import numpy as np

    q = np.asarray(arm_q, dtype=float).reshape(-1)[:6]
    pos, _ = ik_solver.compute_forward_kinematics(IK_EE_FRAME, q)
    return float(pos[2])


def tool0_grasp_orientation_wxyz(ik_solver: Any, seed_pose_rad: tuple[float, ...] | None = None) -> Any:
    """Return the tool0 orientation (wxyz) for downward table grasp from a seed joint pose."""
    import numpy as np

    seed = (
        np.asarray(SEED_POSES_RAD["reach_forward"], dtype=float)
        if seed_pose_rad is None
        else np.asarray(seed_pose_rad, dtype=float)
    )
    _, rot = ik_solver.compute_forward_kinematics(IK_EE_FRAME, seed)
    return rotation_matrix_to_quat_wxyz(rot)


def passport_summary() -> dict[str, Any]:
    return {
        "passport_version": PASSPORT_VERSION,
        "passport_id": PASSPORT_ID,
        "experiment_mode": EXPERIMENT_MODE,
        "robot_asset": ROBOT_USD_REL,
        "gripper_variant": GRIPPER_VARIANT,
        "ik_ee_frame": IK_EE_FRAME,
        "usd_ee_frame": USD_EE_FRAME,
        "ik_grasp_orientation_tolerance_rad": IK_GRASP_ORIENTATION_TOLERANCE_RAD,
        "ik_grasp_orientation_seed_pose": "reach_forward",
        "ik_approach_position_only": IK_APPROACH_POSITION_ONLY,
        "ik_max_joint_jump_approach_rad": IK_MAX_JOINT_JUMP_APPROACH_RAD,
        "ik_max_joint_jump_grasp_rad": IK_MAX_JOINT_JUMP_GRASP_RAD,
        "arm_motion_max_step_rad": ARM_MOTION_MAX_STEP_RAD,
        "robotiq_finger_open_rad": ROBOTIQ_FINGER_OPEN_RAD,
        "robotiq_finger_close_rad": ROBOTIQ_FINGER_CLOSE_RAD,
        "enable_weld_fallback": ENABLE_WELD_FALLBACK,
        "claim_boundary": (
            "Simulation uses official UR10e + Robotiq 2F-85 as parallel electric gripper proxy. "
            "Real lab uses DH Robotics PGEA; sim-to-real gripper alignment is out of scope for this pilot."
        ),
    }