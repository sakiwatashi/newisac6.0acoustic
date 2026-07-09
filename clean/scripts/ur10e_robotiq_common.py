"""UR10e + Robotiq 2F-85 spawn and gripper helpers for Phase B/C scripts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ur10e_robotiq_passport_v1 import (
    ARM_HOME_MAX_STEP_RAD,
    ARM_JOINT_NAMES,
    ARM_KINEMATIC_CONTROL,
    GRASP_FINGER_PHYSICS_CONTROL,
    GRASP_LIFT_PHYSICS_SETTLE_STEPS,
    GRASP_POST_CLOSE_SETTLE_STEPS,
    ARM_MOTION_MAX_STEP_RAD,
    GRIPPER_VARIANT,
    IK_EE_FRAME,
    ROBOT_PRIM_PATH,
    ROBOT_USD_REL,
    ROBOTIQ_FINGER_CLOSE_RAD,
    ROBOTIQ_FINGER_CLOSE_RAMP_STEPS,
    ROBOTIQ_FINGER_PHYSICS_CLOSE_RAD,
    ROBOTIQ_FINGER_OPEN_RAD,
    ROBOTIQ_GRIPPER_SETTLE_STEPS,
    SEED_POSES_RAD,
    USD_EE_FRAME,
    interpolate_arm_joints,
    joint_delta_rad,
)


# ParallelGripper passport for Isaac UR10e Robotiq uses degrees (see test_single_manipulators.py).
ROBOTIQ_FINGER_CLOSE_DEG = 45.0
ROBOTIQ_FINGER_ACTION_DELTA_DEG = 45.0
ROBOTIQ_FINGER_DRIVE_STIFFNESS = 3.5e3
ROBOTIQ_FINGER_DRIVE_DAMPING = 5.0e2
ROBOTIQ_FINGER_RAMP_SETTLE_STEPS = 6


def _ensure_finite_vector(name: str, values: Any, *, min_size: int | None = None) -> Any:
    import numpy as np

    arr = np.asarray(values, dtype=float).reshape(-1)
    if min_size is not None and arr.size < int(min_size):
        raise ValueError(f"{name} expected at least {min_size} values, got {arr.size}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite joint values: {arr}")
    return arr


@dataclass
class RobotiqGripperRuntime:
    finger_joint_names: tuple[str, ...]
    settle_steps: int = ROBOTIQ_GRIPPER_SETTLE_STEPS
    close_ramp_steps: int = ROBOTIQ_FINGER_CLOSE_RAMP_STEPS

    def _finger_joint_index(self, robot: Any) -> int | None:
        dof_names = list(_robot_dof_names(robot))
        if "finger_joint" in dof_names:
            return dof_names.index("finger_joint")
        return None

    def _write_finger_targets(
        self,
        robot: Any,
        finger_position_rad: float,
        *,
        hold_arm_q: Any | None = None,
    ) -> Any:
        import numpy as np

        q = _try_read_robot_joint_q(robot)
        if q is None:
            if hold_arm_q is None:
                raise RuntimeError(
                    "PhysX articulation view not ready and no hold_arm_q fallback for finger close"
                )
            return _build_joint_q_from_arm_hold(robot, hold_arm_q, finger_rad=finger_position_rad)
        finger_idx = self._finger_joint_index(robot)
        if finger_idx is not None:
            q[finger_idx] = float(finger_position_rad)
        dof_names = list(_robot_dof_names(robot))
        for joint_name in self.finger_joint_names:
            if joint_name not in dof_names:
                continue
            idx = dof_names.index(joint_name)
            if joint_name == "finger_joint":
                q[idx] = float(finger_position_rad)
            elif "inner_finger_joint" in joint_name and "knuckle" not in joint_name:
                q[idx] = -float(finger_position_rad)
            elif "knuckle" in joint_name:
                q[idx] = -float(finger_position_rad) if "right" in joint_name else float(finger_position_rad)
            else:
                q[idx] = float(finger_position_rad)
        for idx, value in enumerate(q):
            if np.isfinite(float(value)):
                continue
            joint_name = dof_names[idx] if idx < len(dof_names) else ""
            if joint_name == "finger_joint":
                q[idx] = float(finger_position_rad)
            elif "inner_finger_joint" in joint_name and "knuckle" not in joint_name:
                q[idx] = -float(finger_position_rad)
            elif "knuckle" in joint_name:
                q[idx] = -float(finger_position_rad) if "right" in joint_name else float(finger_position_rad)
            elif "finger" in joint_name:
                q[idx] = float(finger_position_rad)
        return q

    def apply_finger_position(
        self,
        robot: Any,
        finger_position_rad: float,
        world: Any,
        *,
        physics: bool | None = None,
        hold_arm_q: Any | None = None,
        simulation_app: Any | None = None,
        render: bool = False,
    ) -> None:
        q = self._write_finger_targets(robot, finger_position_rad, hold_arm_q=hold_arm_q)
        use_physics = bool(GRASP_FINGER_PHYSICS_CONTROL if physics is None else physics)
        if use_physics and hold_arm_q is not None:
            _apply_arm_only_kinematic(robot, hold_arm_q)
            _apply_finger_physics_targets(robot, q)
        else:
            if hold_arm_q is not None:
                _apply_arm_only_kinematic(robot, hold_arm_q)
            q = self._write_finger_targets(robot, finger_position_rad, hold_arm_q=hold_arm_q)
            _apply_finger_kinematic_targets(robot, q, hold_arm_q=hold_arm_q)
        stabilize_articulation(
            robot,
            world,
            steps=max(1, ROBOTIQ_FINGER_RAMP_SETTLE_STEPS),
            render=render,
            simulation_app=simulation_app,
        )

    def open(
        self,
        robot: Any,
        world: Any,
        *,
        simulation_app: Any | None = None,
        render: bool = False,
    ) -> None:
        self.apply_finger_position(
            robot,
            ROBOTIQ_FINGER_OPEN_RAD,
            world,
            physics=False,
            simulation_app=simulation_app,
            render=render,
        )

    def close(
        self,
        robot: Any,
        world: Any,
        *,
        hold_arm_q: Any | None = None,
        kinematic_only: bool = False,
        simulation_app: Any | None = None,
        render: bool = False,
    ) -> None:
        """Kinematic pre-close; physics squeeze only when stable (headless). GUI defaults to kinematic-only."""
        import numpy as np

        open_rad = float(ROBOTIQ_FINGER_OPEN_RAD)
        close_rad = float(ROBOTIQ_FINGER_PHYSICS_CLOSE_RAD)
        arm_hold = np.asarray(hold_arm_q, dtype=float).reshape(-1) if hold_arm_q is not None else get_arm_q(robot)
        if kinematic_only and render:
            q = self._write_finger_targets(robot, close_rad, hold_arm_q=arm_hold)
            _apply_arm_only_kinematic(robot, arm_hold)
            _apply_finger_kinematic_targets(robot, q, hold_arm_q=arm_hold)
            _apply_arm_only_kinematic(robot, arm_hold)
            world.step(render=True)
            if simulation_app is not None:
                simulation_app.update()
            return
        ensure_articulation_physics_ready(robot, world, simulation_app, render=render)
        ramp = max(1, int(self.close_ramp_steps))
        physics_from = ramp + 1 if kinematic_only else max(2, int(math.ceil(ramp * 0.55)))
        _apply_arm_only_kinematic(robot, arm_hold)
        stabilize_articulation(robot, world, steps=4, render=render, simulation_app=simulation_app)
        for step_idx in range(1, ramp + 1):
            frac = step_idx / float(ramp)
            target = open_rad + (close_rad - open_rad) * frac
            use_physics = step_idx >= physics_from
            _apply_arm_only_kinematic(robot, arm_hold)
            self.apply_finger_position(
                robot,
                target,
                world,
                physics=use_physics,
                hold_arm_q=arm_hold,
                simulation_app=simulation_app,
                render=render,
            )
            stabilize_articulation(
                robot,
                world,
                steps=max(2, ROBOTIQ_FINGER_RAMP_SETTLE_STEPS // 2),
                render=render,
                simulation_app=simulation_app,
            )
        _apply_arm_only_kinematic(robot, arm_hold)
        # Final kinematic squeeze — reliable even when PhysX finger PD is unstable (GUI) or not ready.
        self.apply_finger_position(
            robot,
            close_rad,
            world,
            physics=False,
            hold_arm_q=arm_hold,
            simulation_app=simulation_app,
            render=render,
        )
        stabilize_articulation(
            robot,
            world,
            steps=max(8, int(GRASP_POST_CLOSE_SETTLE_STEPS) // 4),
            render=render,
            simulation_app=simulation_app,
        )
        self.hold_closed(
            robot,
            world,
            hold_arm_q=arm_hold,
            kinematic_only=kinematic_only,
            simulation_app=simulation_app,
            render=render,
        )

    def hold_closed(
        self,
        robot: Any,
        world: Any,
        *,
        hold_arm_q: Any,
        kinematic_only: bool = False,
        simulation_app: Any | None = None,
        render: bool = False,
    ) -> None:
        """Re-assert finger close while arm stays kinematically fixed."""
        close_rad = float(ROBOTIQ_FINGER_PHYSICS_CLOSE_RAD)
        if kinematic_only and render:
            q = self._write_finger_targets(robot, close_rad, hold_arm_q=hold_arm_q)
            _apply_arm_only_kinematic(robot, hold_arm_q)
            _apply_finger_kinematic_targets(robot, q, hold_arm_q=hold_arm_q)
            _apply_arm_only_kinematic(robot, hold_arm_q)
            return
        self.apply_finger_position(
            robot,
            close_rad,
            world,
            physics=not kinematic_only,
            hold_arm_q=hold_arm_q,
            simulation_app=simulation_app,
            render=render,
        )
        stabilize_articulation(
            robot,
            world,
            steps=max(4, int(GRASP_LIFT_PHYSICS_SETTLE_STEPS) // 2),
            render=render,
            simulation_app=simulation_app,
        )


def configure_robotiq_finger_gains(
    stage: Any,
    robot_path: str,
    *,
    stiffness: float = ROBOTIQ_FINGER_DRIVE_STIFFNESS,
    damping: float = ROBOTIQ_FINGER_DRIVE_DAMPING,
) -> None:
    """Raise finger_joint drive gains so closed fingers can hold a dynamic target."""
    from pxr import PhysxSchema, UsdPhysics

    finger_joint_paths = (
        f"{robot_path}/ee_link/Robotiq_2F_85/Joints/finger_joint",
        f"{robot_path}/ee_link/Robotiq_2F_85/finger_joint",
    )
    for joint_path in finger_joint_paths:
        prim = stage.GetPrimAtPath(joint_path)
        if not prim or not prim.IsValid():
            continue
        drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
        drive.CreateStiffnessAttr(float(stiffness))
        drive.CreateDampingAttr(float(damping))
        if prim.HasAPI(PhysxSchema.PhysxJointAPI):
            physx_joint = PhysxSchema.PhysxJointAPI(prim)
        else:
            physx_joint = PhysxSchema.PhysxJointAPI.Apply(prim)
        physx_joint.CreateJointFrictionAttr(0.35)
        break


def _robot_dof_names(robot: Any) -> tuple[str, ...]:
    if hasattr(robot, "dof_names"):
        return tuple(robot.dof_names)
    return tuple(robot.get_dof_names())


def _try_read_robot_joint_q(robot: Any) -> Any | None:
    """Return 1-D joint vector or None when PhysX articulation view is not ready."""
    import numpy as np

    try:
        raw = robot.get_joint_positions()
        q = np.asarray(raw, dtype=float).reshape(-1)
        if q.size == 0:
            return None
        dof_names = list(_robot_dof_names(robot))
        if dof_names and q.size < len(dof_names):
            return None
        return q.copy()
    except Exception:
        return None


def _build_joint_q_from_arm_hold(robot: Any, hold_arm_q: Any, *, finger_rad: float | None = None) -> Any:
    """Construct a full-DOF joint vector without reading PhysX (safe during GUI close)."""
    import numpy as np

    dof_names = list(_robot_dof_names(robot))
    n = len(dof_names)
    q = np.zeros(n, dtype=float)
    arm_values = np.asarray(hold_arm_q, dtype=float).reshape(-1)
    for joint_name, value in zip(ARM_JOINT_NAMES, arm_values[: len(ARM_JOINT_NAMES)]):
        if joint_name in dof_names:
            q[dof_names.index(joint_name)] = float(value)
    if finger_rad is not None:
        finger_idx = dof_names.index("finger_joint") if "finger_joint" in dof_names else None
        if finger_idx is not None:
            q[finger_idx] = float(finger_rad)
        for joint_name in dof_names:
            if joint_name == "finger_joint":
                continue
            idx = dof_names.index(joint_name)
            if "inner_finger_joint" in joint_name and "knuckle" not in joint_name:
                q[idx] = -float(finger_rad)
            elif "knuckle" in joint_name and "finger" in joint_name:
                q[idx] = -float(finger_rad) if "right" in joint_name else float(finger_rad)
    return q


def ensure_articulation_physics_ready(
    robot: Any,
    world: Any,
    simulation_app: Any | None = None,
    *,
    render: bool = False,
    min_steps: int = 8,
) -> None:
    """Play timeline and warm PhysX before gripper reads/writes in GUI."""
    import omni.timeline

    timeline = omni.timeline.get_timeline_interface()
    if not timeline.is_playing():
        timeline.play()
    if hasattr(robot, "initialize"):
        try:
            robot.initialize()
        except Exception as _e:
            print(f"WARN [ur10e_robotiq_common] robot.initialize() failed: {_e}", flush=True)
    for _ in range(max(1, int(min_steps))):
        world.step(render=bool(render))
        if simulation_app is not None:
            simulation_app.update()


def spawn_ur10e_robotiq(
    *,
    stage: Any,
    stage_utils: Any,
    assets_root: str,
    simulation_app: Any,
    robot_path: str = ROBOT_PRIM_PATH,
) -> str:
    usd_path = f"{assets_root}/{ROBOT_USD_REL}"
    print(f"Loading UR10e + Robotiq: {usd_path}", flush=True)
    stage_utils.add_reference_to_stage(usd_path=usd_path, path=robot_path)
    for _ in range(20):
        simulation_app.update()
    prim = stage.GetPrimAtPath(robot_path)
    if not prim:
        raise RuntimeError(f"Robot prim missing after spawn: {robot_path}")
    variant_sets = prim.GetVariantSets()
    if variant_sets.HasVariantSet("Gripper"):
        variant_sets.GetVariantSet("Gripper").SetVariantSelection(GRIPPER_VARIANT)
        print(f"Set Gripper variant={GRIPPER_VARIANT}", flush=True)
    for _ in range(10):
        simulation_app.update()
    return usd_path


def resolve_ee_path(robot_path: str, stage: Any) -> str:
    for frame in (USD_EE_FRAME, IK_EE_FRAME, "wrist_3_link"):
        path = f"{robot_path}/{frame}"
        if stage.GetPrimAtPath(path):
            return path
    raise RuntimeError(f"No EE frame found under {robot_path}")


def resolve_robotiq_gripper_prim_path(robot_path: str, stage: Any) -> str:
    """Robotiq grip root for ParallelGripper (2F-85 nests under Robotiq_2F_85)."""
    candidates = (
        f"{robot_path}/ee_link/robotiq_base_link",
        f"{robot_path}/ee_link/robotiq_85_base_link",
        f"{robot_path}/ee_link/Robotiq_2F_85/base_link",
    )
    for path in candidates:
        if stage.GetPrimAtPath(path):
            return path
    raise RuntimeError(f"No Robotiq gripper prim found under {robot_path}/ee_link")


def resolve_manipulator_ee_path(robot_path: str, stage: Any) -> str:
    """Kinematic EE rigid body for SingleManipulator (must be an articulation link that moves)."""
    for frame in ("wrist_3_link", IK_EE_FRAME, USD_EE_FRAME):
        path = f"{robot_path}/{frame}"
        if stage.GetPrimAtPath(path):
            return path
    raise RuntimeError(f"No manipulator EE frame found under {robot_path}")


def resolve_sensor_mount_path(robot_path: str, stage: Any) -> str:
    """Kinematic mount for RTX sensor (UR10e USD: wrist_3_link moves; ee_link is static)."""
    for frame in ("wrist_3_link", IK_EE_FRAME, USD_EE_FRAME):
        path = f"{robot_path}/{frame}"
        if stage.GetPrimAtPath(path):
            return path
    raise RuntimeError(f"No sensor mount frame found under {robot_path}")


def discover_robotiq_finger_joints(robot: Any) -> tuple[str, ...]:
    names = [n for n in _robot_dof_names(robot) if "finger" in n or n == "finger_joint"]
    if not names:
        names = ["finger_joint"]
    return tuple(sorted(set(names), key=lambda n: (0 if n == "finger_joint" else 1, n)))


def setup_robotiq_gripper(robot: Any, world: Any) -> RobotiqGripperRuntime:
    runtime = RobotiqGripperRuntime(finger_joint_names=discover_robotiq_finger_joints(robot))
    runtime.open(robot, world)
    return runtime


def spawn_ur10e_single_manipulator(
    world: Any,
    *,
    robot_path: str,
    stage: Any,
    name: str = "ur10e",
) -> Any:
    """UR10e + Robotiq via SingleManipulator (physics-aligned gripper base)."""
    import numpy as np
    from isaacsim.robot.manipulators import SingleManipulator
    from isaacsim.robot.manipulators.grippers import ParallelGripper

    gripper_root = resolve_robotiq_gripper_prim_path(robot_path, stage)
    ee_path = resolve_manipulator_ee_path(robot_path, stage)
    gripper = ParallelGripper(
        end_effector_prim_path=gripper_root,
        joint_prim_names=["finger_joint"],
        joint_opened_positions=np.array([0.0]),
        joint_closed_positions=np.array([float(ROBOTIQ_FINGER_CLOSE_DEG)]),
        action_deltas=np.array([float(ROBOTIQ_FINGER_ACTION_DELTA_DEG)]),
        use_mimic_joints=True,
    )
    return world.scene.add(
        SingleManipulator(
            prim_path=robot_path,
            name=name,
            end_effector_prim_path=ee_path,
            gripper=gripper,
        )
    )


def _write_arm_targets_into_q(robot: Any, arm_q: Any) -> Any:
    import numpy as np

    dof_names = list(_robot_dof_names(robot))
    arm_values = _ensure_finite_vector("arm_q", arm_q, min_size=len(ARM_JOINT_NAMES))
    q = _try_read_robot_joint_q(robot)
    if q is None:
        return _build_joint_q_from_arm_hold(robot, arm_values)
    for joint_name, value in zip(ARM_JOINT_NAMES, arm_values[: len(ARM_JOINT_NAMES)]):
        if joint_name in dof_names:
            q[dof_names.index(joint_name)] = float(value)
    return q


def snap_arm_to_pose(robot: Any, arm_q: Any) -> None:
    """Instant kinematic joint set — used right after world.reset() to escape all-zero default."""
    q = _write_arm_targets_into_q(robot, arm_q)
    robot.set_joint_positions(q)


def bootstrap_arm_after_world_reset(
    robot: Any,
    world: Any,
    *,
    ik_solver: Any | None = None,
    simulation_app: Any | None = None,
    render: bool = False,
) -> Any:
    """First-priority pose after world.reset(): all-zero default puts gripper under the table."""
    import numpy as np

    robot.initialize()
    snap_arm_to_pose(robot, SEED_POSES_RAD["search_corridor"])
    world.step(render=bool(render))
    if render and simulation_app is not None:
        simulation_app.update()
    if ik_solver is not None:
        from ur10e_robotiq_passport_v1 import resolve_search_corridor_pose_rad

        q_refined = resolve_search_corridor_pose_rad(ik_solver)
        snap_arm_to_pose(robot, q_refined)
        world.step(render=bool(render))
        if render and simulation_app is not None:
            simulation_app.update()
        return np.asarray(q_refined, dtype=float)
    return np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float)


def initialize_ur10e_manipulator(
    manipulator: Any,
    world: Any,
    simulation_app: Any,
    *,
    stage: Any | None = None,
    robot_path: str = ROBOT_PRIM_PATH,
    open_gripper: bool = True,
) -> RobotiqGripperRuntime:
    import omni.timeline

    timeline = omni.timeline.get_timeline_interface()
    if not timeline.is_playing():
        timeline.play()
    for _ in range(5):
        simulation_app.update()
    manipulator.initialize()
    if stage is not None:
        configure_robotiq_finger_gains(stage, robot_path)
    runtime = RobotiqGripperRuntime(finger_joint_names=discover_robotiq_finger_joints(manipulator))
    if open_gripper:
        runtime.open(manipulator, world)
    return runtime


def set_arm_joint_positions(
    robot: Any,
    arm_q: Any,
    world: Any,
    *,
    settle_steps: int,
    render: bool = False,
    simulation_app: Any | None = None,
    max_step_rad: float = ARM_MOTION_MAX_STEP_RAD,
    arm_only_kinematic: bool = False,
) -> None:
    import numpy as np

    dof_names = list(_robot_dof_names(robot))
    arm_values = _ensure_finite_vector("arm_q", arm_q, min_size=len(ARM_JOINT_NAMES))
    current_arm = _ensure_finite_vector("current_arm_q", get_arm_q(robot), min_size=len(ARM_JOINT_NAMES))[: len(ARM_JOINT_NAMES)]
    target_arm = _ensure_finite_vector("target_arm_q", arm_values[: len(ARM_JOINT_NAMES)], min_size=len(ARM_JOINT_NAMES))
    jump = joint_delta_rad(current_arm, target_arm)
    if int(settle_steps) <= 0:
        hold_arm_joint_positions(
            robot,
            target_arm,
            world,
            render=render,
            simulation_app=simulation_app,
            arm_only_kinematic=arm_only_kinematic,
        )
        return
    if not math.isfinite(jump) or jump <= 1e-6:
        ramp_steps = 1
    else:
        ramp_steps = max(1, int(math.ceil(jump / max(float(max_step_rad), 1e-6))))
    steps_per_ramp = max(1, int(settle_steps) // ramp_steps)
    for ramp_idx in range(1, ramp_steps + 1):
        alpha = ramp_idx / float(ramp_steps)
        interp_arm = interpolate_arm_joints(current_arm, target_arm, alpha)
        q = _try_read_robot_joint_q(robot)
        if q is None:
            q = _build_joint_q_from_arm_hold(robot, interp_arm)
        if arm_only_kinematic:
            _apply_arm_only_kinematic(robot, interp_arm)
        else:
            for joint_name, value in zip(ARM_JOINT_NAMES, interp_arm):
                if joint_name in dof_names:
                    q[dof_names.index(joint_name)] = float(value)
            _apply_robot_joint_positions(robot, q)
        for _ in range(steps_per_ramp):
            world.step(render=bool(render))
            if render and simulation_app is not None:
                simulation_app.update()


def hold_arm_joint_positions(
    robot: Any,
    arm_q: Any,
    world: Any,
    *,
    render: bool = False,
    simulation_app: Any | None = None,
    arm_only_kinematic: bool = False,
) -> None:
    """Re-assert arm PD targets without ramping — use between sensor polls."""
    if arm_only_kinematic:
        _apply_arm_only_kinematic(robot, arm_q)
    else:
        q = _write_arm_targets_into_q(robot, arm_q)
        _apply_robot_joint_positions(robot, q)
    world.step(render=bool(render))
    if render and simulation_app is not None:
        simulation_app.update()


def stabilize_articulation(
    robot: Any,
    world: Any,
    *,
    steps: int = 1,
    render: bool = False,
    simulation_app: Any | None = None,
    zero_velocities: bool = True,
) -> None:
    """Let PhysX settle and bleed off stray joint velocities after mixed arm/gripper commands."""
    import numpy as np

    if zero_velocities and hasattr(robot, "set_joint_velocities"):
        try:
            q = _try_read_robot_joint_q(robot)
            if q is not None:
                robot.set_joint_velocities(np.zeros(q.size, dtype=float))
        except Exception as _e:
            print(f"WARN [ur10e_robotiq_common] set_joint_velocities failed: {_e}", flush=True)
    for _ in range(max(0, int(steps))):
        world.step(render=bool(render))
        if simulation_app is not None:
            simulation_app.update()


def _arm_dof_indices(robot: Any) -> tuple[Any, Any]:
    import numpy as np

    dof_names = list(_robot_dof_names(robot))
    indices: list[int] = []
    values: list[float] = []
    current = np.asarray(robot.get_joint_positions(), dtype=float).reshape(-1)
    for joint_name in ARM_JOINT_NAMES:
        if joint_name not in dof_names:
            continue
        idx = dof_names.index(joint_name)
        indices.append(idx)
        values.append(float(current[idx]))
    return np.asarray(indices, dtype=int), np.asarray(values, dtype=float)


def _apply_arm_only_kinematic(robot: Any, arm_q: Any) -> None:
    """Set only the 6 arm DOFs — leaves finger physics state untouched."""
    import numpy as np

    dof_names = list(_robot_dof_names(robot))
    indices: list[int] = []
    values: list[float] = []
    arm_values = _ensure_finite_vector("arm_q", arm_q, min_size=len(ARM_JOINT_NAMES))
    for joint_name, value in zip(ARM_JOINT_NAMES, arm_values[: len(ARM_JOINT_NAMES)]):
        if joint_name not in dof_names:
            continue
        indices.append(dof_names.index(joint_name))
        values.append(float(value))
    if not indices:
        return
    idx_arr = np.asarray(indices, dtype=int)
    val_arr = _ensure_finite_vector("arm_only_joint_values", values, min_size=len(values))
    try:
        robot.set_joint_positions(val_arr, joint_indices=idx_arr)
        return
    except Exception:
        pass  # fallback: use _apply_arm_kinematic_hold below
    _apply_arm_kinematic_hold(robot, arm_q)


def _apply_arm_kinematic_hold(robot: Any, arm_q: Any) -> None:
    """Keep the 6-DOF arm fixed while fingers use physics during grasp."""
    _apply_arm_only_kinematic(robot, arm_q)


def _finger_dof_indices(robot: Any) -> list[int]:
    dof_names = list(_robot_dof_names(robot))
    indices: list[int] = []
    for joint_name in dof_names:
        if joint_name == "finger_joint" or "finger" in joint_name:
            indices.append(dof_names.index(joint_name))
    return indices


def _finite_finger_values(robot: Any, joint_positions: Any) -> tuple[Any, Any]:
    """Return finite finger DOF indices/values; tolerate NaN mimic joints from Isaac."""
    import numpy as np

    q = np.asarray(joint_positions, dtype=float).reshape(-1)
    dof_names = list(_robot_dof_names(robot))
    finger_indices = _finger_dof_indices(robot)
    if not finger_indices:
        return np.asarray([], dtype=int), np.asarray([], dtype=float)
    main_idx = dof_names.index("finger_joint") if "finger_joint" in dof_names else finger_indices[0]
    main_value = float(q[main_idx]) if main_idx < q.size and np.isfinite(q[main_idx]) else float(ROBOTIQ_FINGER_PHYSICS_CLOSE_RAD)
    values: list[float] = []
    for idx in finger_indices:
        joint_name = dof_names[idx] if idx < len(dof_names) else ""
        raw = float(q[idx]) if idx < q.size and np.isfinite(q[idx]) else math.nan
        if math.isfinite(raw):
            values.append(raw)
        elif joint_name == "finger_joint":
            values.append(main_value)
        elif "inner_finger_joint" in joint_name and "knuckle" not in joint_name:
            values.append(-main_value)
        elif "knuckle" in joint_name:
            values.append(-main_value if "right" in joint_name else main_value)
        else:
            values.append(main_value)
    return np.asarray(finger_indices, dtype=int), np.asarray(values, dtype=float)


def _apply_finger_kinematic_targets(robot: Any, joint_positions: Any, *, hold_arm_q: Any | None = None) -> None:
    """Set finger DOFs kinematically without disturbing the 6-DOF arm."""
    import numpy as np

    finger_indices, finger_values = _finite_finger_values(robot, joint_positions)
    if finger_indices.size == 0:
        if hold_arm_q is not None:
            _apply_arm_only_kinematic(robot, hold_arm_q)
        return
    idx_arr = finger_indices
    try:
        robot.set_joint_positions(finger_values, joint_indices=idx_arr)
    except Exception:
        if hold_arm_q is not None:
            merged = _build_joint_q_from_arm_hold(
                robot,
                hold_arm_q,
                finger_rad=float(finger_values[0]) if finger_values.size else None,
            )
            robot.set_joint_positions(merged)


def _apply_finger_physics_targets(robot: Any, joint_positions: Any) -> None:
    """PD-drive finger DOFs only; arm pose must be held separately."""
    import numpy as np
    from isaacsim.core.utils.types import ArticulationAction

    q = np.asarray(joint_positions, dtype=float).reshape(-1)
    finger_indices, finger_values = _finite_finger_values(robot, joint_positions)
    if finger_indices.size == 0:
        _apply_robot_joint_positions(robot, q, physics=True)
        return
    if hasattr(robot, "apply_action"):
        robot.apply_action(
            ArticulationAction(joint_positions=finger_values, joint_indices=finger_indices)
        )
    else:
        robot.set_joint_positions(q)


def _apply_robot_joint_positions(robot: Any, joint_positions: Any, *, physics: bool = False) -> None:
    """Drive arm/gripper joints. Kinematic mode avoids PhysX sag during approach."""
    import numpy as np
    from isaacsim.core.utils.types import ArticulationAction

    q = _ensure_finite_vector("robot_joint_positions", joint_positions)
    if ARM_KINEMATIC_CONTROL and not physics:
        robot.set_joint_positions(q)
        return
    if hasattr(robot, "apply_action"):
        robot.apply_action(ArticulationAction(joint_positions=q))
    else:
        robot.set_joint_positions(q)


def make_arm_hold_tick(
    robot: Any,
    world: Any,
    arm_q_holder: dict[str, Any],
    *,
    simulation_app: Any | None = None,
    render: bool = False,
) -> Any:
    """Callback for GUI idle waits — re-apply corridor pose each frame."""

    def on_tick() -> None:
        held_q = arm_q_holder.get("q")
        if held_q is None:
            if simulation_app is not None:
                simulation_app.update()
            return
        hold_arm_joint_positions(
            robot,
            held_q,
            world,
            render=render,
            simulation_app=simulation_app,
            arm_only_kinematic=True,
        )

    return on_tick


def home_arm_to_search_corridor(
    robot: Any,
    world: Any,
    ik_solver: Any,
    *,
    settle_steps: int = 100,
    max_step_rad: float = ARM_HOME_MAX_STEP_RAD,
    render: bool = False,
    simulation_app: Any | None = None,
) -> Any:
    """Ramp to the ultrasonic search-corridor start (not reach_forward — that pose cuts through the table)."""
    from ur10e_robotiq_passport_v1 import resolve_search_corridor_pose_rad

    q_corridor = resolve_search_corridor_pose_rad(ik_solver)
    home_arm_to_pose(
        robot,
        world,
        q_corridor,
        settle_steps=settle_steps,
        max_step_rad=max_step_rad,
        render=render,
        simulation_app=simulation_app,
    )
    return q_corridor


def home_arm_to_pose(
    robot: Any,
    world: Any,
    arm_q: Any,
    *,
    settle_steps: int = 80,
    max_step_rad: float = ARM_HOME_MAX_STEP_RAD,
    render: bool = False,
    simulation_app: Any | None = None,
) -> None:
    """Ramp from the current USD pose to a known seed without a single-frame teleport."""
    set_arm_joint_positions(
        robot,
        arm_q,
        world,
        settle_steps=settle_steps,
        render=render,
        simulation_app=simulation_app,
        max_step_rad=max_step_rad,
    )


def read_prim_world_xyz(stage: Any, prim_path: str, cache: Any, *, world: Any | None = None) -> tuple[float, float, float]:
    if world is not None:
        for _ in range(3):
            world.step(render=False)
    from pxr import Usd

    cache.SetTime(Usd.TimeCode.Default())
    cache.Clear()
    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return math.nan, math.nan, math.nan
    translation = cache.GetLocalToWorldTransform(prim).ExtractTranslation()
    return float(translation[0]), float(translation[1]), float(translation[2])


def read_prim_world_z(stage: Any, prim_path: str, cache: Any, *, world: Any | None = None) -> float:
    _, _, z = read_prim_world_xyz(stage, prim_path, cache, world=world)
    return z


def read_scene_object_world_z(scene_object: Any, *, world: Any | None = None) -> float:
    import numpy as np

    if world is not None:
        for _ in range(3):
            world.step(render=False)
    if scene_object is None:
        return math.nan
    if hasattr(scene_object, "get_world_pose"):
        position, _ = scene_object.get_world_pose()
        coords = np.asarray(position, dtype=float).reshape(-1)
        if coords.size >= 3 and math.isfinite(float(coords[2])):
            return float(coords[2])
    return math.nan


def get_arm_q(robot: Any, *, fallback: Any | None = None) -> Any:
    import numpy as np

    q = _try_read_robot_joint_q(robot)
    if q is None:
        if fallback is not None:
            return np.asarray(fallback, dtype=float).reshape(-1)[: len(ARM_JOINT_NAMES)]
        return np.asarray(SEED_POSES_RAD["search_corridor"], dtype=float)
    dof_names = list(_robot_dof_names(robot))
    return np.asarray([q[dof_names.index(name)] for name in ARM_JOINT_NAMES if name in dof_names], dtype=float)


WRIST_JOINT_SLICE = slice(3, 6)


def wrist_fine_delta_rad(motion: str, step_idx: int) -> tuple[tuple[float, float, float, float, float, float], ...]:
    """Empirical wrist-only deltas (shoulder/elbow fixed) for near-target fine motion."""
    wrist_patterns: dict[str, tuple[tuple[float, float, float, float, float, float], ...]] = {
        "forward_x": (
            (0.0, 0.0, 0.0, 0.040, 0.000, 0.000),
            (0.0, 0.0, 0.0, 0.035, 0.012, 0.000),
            (0.0, 0.0, 0.0, 0.030, 0.018, 0.006),
        ),
        "lateral_y_pos": (
            (0.0, 0.0, 0.0, 0.000, 0.040, 0.000),
            (0.0, 0.0, 0.0, 0.006, 0.035, 0.010),
        ),
        "lateral_y_neg": (
            (0.0, 0.0, 0.0, 0.000, -0.040, 0.000),
            (0.0, 0.0, 0.0, 0.006, -0.035, -0.010),
        ),
        "lower_z": (
            (0.0, 0.0, 0.0, 0.045, 0.020, 0.000),
            (0.0, 0.0, 0.0, 0.040, 0.028, 0.008),
            (0.0, 0.0, 0.0, 0.035, 0.032, 0.012),
        ),
    }
    patterns = wrist_patterns.get(motion, ())
    if not patterns:
        return ()
    idx = min(int(step_idx), len(patterns) - 1)
    return patterns[idx : idx + 1]


def apply_arm_delta_rad(arm_q: Any, delta: tuple[float, float, float, float, float, float]) -> Any:
    import numpy as np

    q = np.asarray(arm_q, dtype=float).reshape(-1).copy()
    q[:6] += np.asarray(delta, dtype=float)[:6]
    return q


def joint_space_lower_ee(arm_q: Any, step_idx: int) -> Any:
    """Heuristic UR10e joint nudge to lower tool0 when Cartesian IK fails."""
    import numpy as np

    q = np.asarray(arm_q, dtype=float).reshape(-1).copy()
    if q.size < 6:
        return q
    # Empirical deltas for reach-forward family poses (pilot 2026-06-30).
    deltas = (
        (0.0, 0.07, -0.06, 0.05, 0.0, 0.0),
        (0.0, 0.06, -0.05, 0.04, 0.0, 0.0),
        (0.0, 0.05, -0.04, 0.03, 0.0, 0.0),
        (0.0, 0.04, -0.03, 0.02, 0.0, 0.0),
        (0.0, 0.03, -0.02, 0.02, 0.0, 0.0),
        (0.0, 0.02, -0.02, 0.01, 0.0, 0.0),
    )
    delta = deltas[min(step_idx, len(deltas) - 1)]
    q[:6] += np.asarray(delta, dtype=float)
    return q


def spawn_solid_work_table(
    world: Any,
    stage: Any,
    *,
    wrench_y_m: float,
    FixedCuboid: Any,
    np: Any,
    table_x_m: float | None = None,
) -> Any:
    """Spawn a floor-to-top solid workbench with PhysX collision (no under-table gap)."""
    from geometry_passport_v1 import enable_static_collision
    from grasp_passport_v1 import (
        TABLE_DEFAULT_X_M,
        TABLE_PRIM_PATH,
        solid_work_table_center_m,
        solid_work_table_scale_m,
    )

    center = solid_work_table_center_m(
        wrench_y_m,
        table_x_m=float(table_x_m if table_x_m is not None else TABLE_DEFAULT_X_M),
    )
    scale = solid_work_table_scale_m()
    table = world.scene.add(
        FixedCuboid(
            prim_path=TABLE_PRIM_PATH,
            name="work_table_solid",
            position=np.array(center, dtype=float),
            scale=np.array(scale, dtype=float),
            color=np.array([0.45, 0.42, 0.38]),
        )
    )
    enable_static_collision(stage, TABLE_PRIM_PATH)
    print(
        f"Solid work table: center={center} scale={scale} top_z={center[2] + scale[2] / 2.0:.3f} m",
        flush=True,
    )
    return table


def apply_physics_friction_material(
    stage: Any,
    prim_path: str,
    *,
    friction: float,
    require_collision: bool = False,
) -> bool:
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return False
    if require_collision and not prim.HasAPI(UsdPhysics.CollisionAPI):
        return False
    if not prim.HasAPI(UsdPhysics.CollisionAPI):
        UsdPhysics.CollisionAPI.Apply(prim)
    material = UsdPhysics.MaterialAPI.Apply(prim)
    material.CreateStaticFrictionAttr(float(friction))
    material.CreateDynamicFrictionAttr(float(friction))
    return True


def apply_wrench_physics_material(stage: Any, prim_path: str, *, friction: float) -> None:
    apply_physics_friction_material(stage, prim_path, friction=float(friction))


def summarize_prim_physics_state(stage: Any, prim_path: str) -> dict[str, Any]:
    """Diagnostic snapshot for wrench / target physics (Tier B lift debugging)."""
    from pxr import Usd, UsdGeom, UsdPhysics

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return {"prim_path": prim_path, "valid": False}
    state: dict[str, Any] = {
        "prim_path": prim_path,
        "valid": True,
        "prim_type": prim.GetTypeName(),
        "has_rigid_body_api": prim.HasAPI(UsdPhysics.RigidBodyAPI),
        "has_collision_api": prim.HasAPI(UsdPhysics.CollisionAPI),
        "kinematic_enabled": is_rigid_body_kinematic(stage, prim_path),
        "collision_enabled": None,
        "mass_kg": None,
        "collision_child_paths": [],
    }
    if prim.HasAPI(UsdPhysics.CollisionAPI):
        attr = UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr()
        if attr and attr.IsAuthored():
            state["collision_enabled"] = bool(attr.Get())
    if prim.HasAPI(UsdPhysics.MassAPI):
        mass_attr = UsdPhysics.MassAPI(prim).GetMassAttr()
        if mass_attr and mass_attr.IsAuthored():
            state["mass_kg"] = float(mass_attr.Get())
    for child in Usd.PrimRange(prim):
        cpath = str(child.GetPath())
        if cpath == prim_path:
            continue
        if child.HasAPI(UsdPhysics.CollisionAPI) or "/collisions/" in cpath.lower():
            state["collision_child_paths"].append(cpath)
    if prim.IsA(UsdGeom.Cube) and not state["has_rigid_body_api"]:
        state["likely_static_primitive"] = True
    return state


def set_prim_collision_enabled(stage: Any, prim_path: str, enabled: bool) -> bool:
    """Toggle PhysX collision on a prim (finger pads, wrench proxy, etc.)."""
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return False
    try:
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            if not enabled:
                return False
            UsdPhysics.CollisionAPI.Apply(prim)
        UsdPhysics.CollisionAPI(prim).CreateCollisionEnabledAttr(bool(enabled))
        return True
    except Exception:
        return False


def _robotiq_gripper_search_roots(stage: Any, robot_path: str) -> list[str]:
    """USD roots to scan for Robotiq finger / knuckle collision meshes."""
    candidates = (
        f"{robot_path}/ee_link/Robotiq_2F_85",
        f"{robot_path}/ee_link/Robotiq_2f_85",
        f"{robot_path}/ee_link/robotiq_base_link",
        f"{robot_path}/ee_link/robotiq_85_base_link",
        f"{robot_path}/ee_link",
    )
    roots: list[str] = []
    for path in candidates:
        prim = stage.GetPrimAtPath(path)
        if prim and prim.IsValid():
            roots.append(path)
    return roots or [f"{robot_path}/ee_link"]


def is_rigid_body_kinematic(stage: Any, prim_path: str) -> bool:
    """True when a prim has RigidBodyAPI with KinematicEnabled authored and set."""
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid() or not prim.HasAPI(UsdPhysics.RigidBodyAPI):
        return False
    attr = UsdPhysics.RigidBodyAPI(prim).GetKinematicEnabledAttr()
    return bool(attr and attr.IsAuthored() and attr.Get())


def safe_zero_rigid_body_velocities(
    scene_object: Any,
    *,
    stage: Any | None = None,
    prim_path: str = "",
) -> bool:
    """Zero rigid-body velocities only when the target is a non-kinematic dynamic body."""
    import numpy as np

    if scene_object is None:
        return False
    if stage is not None and prim_path and is_rigid_body_kinematic(stage, prim_path):
        return False
    try:
        if hasattr(scene_object, "set_linear_velocity"):
            scene_object.set_linear_velocity(np.zeros(3, dtype=float))
        if hasattr(scene_object, "set_angular_velocity"):
            scene_object.set_angular_velocity(np.zeros(3, dtype=float))
        return True
    except Exception:
        return False


def set_dynamic_prim_kinematic(stage: Any, prim_path: str, kinematic: bool) -> bool:
    """Make a dynamic target kinematic so contact does not launch the arm (Tier B GUI stability)."""
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return False
    if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
        UsdPhysics.RigidBodyAPI.Apply(prim)
    UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr(bool(kinematic))
    return True


def set_robotiq_finger_collision_enabled(stage: Any, robot_path: str, enabled: bool) -> list[str]:
    """Enable/disable collision on Robotiq finger/knuckle collision prims (Isaac 6.0 safe)."""
    from pxr import Usd, UsdPhysics

    touched: list[str] = []
    seen: set[str] = set()
    finger_link_names = (
        "base_link",
        "left_outer_finger",
        "left_inner_finger",
        "left_outer_knuckle",
        "left_inner_knuckle",
        "right_outer_finger",
        "right_inner_finger",
        "right_outer_knuckle",
        "right_inner_knuckle",
    )
    for prefix in (
        f"{robot_path}/ee_link/Robotiq_2F_85",
        f"{robot_path}/ee_link/Robotiq_2f_85",
    ):
        if not stage.GetPrimAtPath(prefix):
            continue
        for link_name in finger_link_names:
            path = f"{prefix}/{link_name}"
            if path in seen:
                continue
            prim = stage.GetPrimAtPath(path)
            if not prim or not prim.IsValid():
                continue
            if set_prim_collision_enabled(stage, path, enabled):
                seen.add(path)
                touched.append(path)

    for grip_root in _robotiq_gripper_search_roots(stage, robot_path):
        root = stage.GetPrimAtPath(grip_root)
        if not root or not root.IsValid():
            continue
        for prim in Usd.PrimRange(root):
            path = str(prim.GetPath())
            if path in seen or "/visuals/" in path:
                continue
            name_lower = prim.GetName().lower()
            has_collision = prim.HasAPI(UsdPhysics.CollisionAPI)
            is_collision_mesh = "/collisions/" in path.lower() or "collision" in name_lower
            if not has_collision and not is_collision_mesh:
                continue
            if is_collision_mesh and not has_collision and not enabled:
                UsdPhysics.CollisionAPI.Apply(prim)
            if set_prim_collision_enabled(stage, path, enabled):
                seen.add(path)
                touched.append(path)
    return touched


def configure_grasp_contact_stability(
    stage: Any,
    *,
    robot_path: str,
    wrench_prim_path: str,
    disable_finger_collision: bool = True,
    disable_wrench_collision: bool = False,
    wrench_kinematic: bool = True,
) -> dict[str, Any]:
    """Reduce PhysX explosions when the open gripper touches the table or wrench in GUI."""
    finger_paths = (
        set_robotiq_finger_collision_enabled(stage, robot_path, enabled=not disable_finger_collision)
        if disable_finger_collision
        else []
    )
    wrench_collision_paths: list[str] = []
    if disable_wrench_collision and set_prim_collision_enabled(stage, wrench_prim_path, False):
        wrench_collision_paths.append(wrench_prim_path)
    wrench_ok = False
    if wrench_kinematic:
        wrench_ok = set_dynamic_prim_kinematic(stage, wrench_prim_path, kinematic=True)
    mode = {
        "finger_collision_disabled": bool(disable_finger_collision),
        "finger_collision_paths": finger_paths,
        "wrench_collision_disabled": bool(disable_wrench_collision),
        "wrench_collision_paths": wrench_collision_paths,
        "wrench_kinematic": bool(wrench_kinematic),
        "wrench_kinematic_applied": wrench_ok,
        "wrench_physics_mode": "kinematic_dynamic" if wrench_ok else "unchanged",
    }
    print(
        "Grasp contact stability: "
        f"finger_collision_disabled={disable_finger_collision} "
        f"finger_paths={len(finger_paths)} "
        f"wrench_collision_disabled={disable_wrench_collision} "
        f"wrench_kinematic={wrench_kinematic} "
        f"(prevents GUI spin when touching table/block)",
        flush=True,
    )
    return mode


def enable_wrench_collision(stage: Any, wrench_prim_path: str, *, enabled: bool = True) -> bool:
    return set_prim_collision_enabled(stage, wrench_prim_path, enabled)


def apply_robotiq_contact_friction(stage: Any, robot_path: str, *, friction: float) -> list[str]:
    """Raise friction on Robotiq finger / pad collision meshes for grasp lift."""
    from pxr import Usd, UsdGeom, UsdPhysics

    grip_root = f"{robot_path}/ee_link/Robotiq_2F_85"
    finger_suffixes = (
        "left_outer_finger",
        "left_inner_finger",
        "left_outer_knuckle",
        "left_inner_knuckle",
        "right_outer_finger",
        "right_inner_finger",
        "right_outer_knuckle",
        "right_inner_knuckle",
    )
    touched: list[str] = []
    for suffix in finger_suffixes:
        link = stage.GetPrimAtPath(f"{grip_root}/{suffix}")
        if not link or not link.IsValid():
            continue
        link_path = f"{grip_root}/{suffix}"
        prim = stage.GetPrimAtPath(link_path)
        if prim is None or not prim.IsValid():
            continue
        material = UsdPhysics.MaterialAPI.Apply(prim)
        material.CreateStaticFrictionAttr(float(friction))
        material.CreateDynamicFrictionAttr(float(friction))
        touched.append(link_path)
        for child in Usd.PrimRange(prim):
            child_path = str(child.GetPath())
            if child_path == link_path:
                continue
            if not child.HasAPI(UsdPhysics.CollisionAPI) and not child.IsA(UsdGeom.Mesh):
                continue
            child_material = UsdPhysics.MaterialAPI.Apply(child)
            child_material.CreateStaticFrictionAttr(float(friction))
            child_material.CreateDynamicFrictionAttr(float(friction))
            touched.append(child_path)
    return touched


def grasp_target_ee_z_m(wrench_center_z_m: float, wrench_height_m: float, clearance_m: float) -> float:
    wrench_top_z = float(wrench_center_z_m) + float(wrench_height_m) / 2.0
    return wrench_top_z + float(clearance_m)