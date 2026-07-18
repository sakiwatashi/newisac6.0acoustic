"""Shared UR10 RTX acoustic scene bootstrap for Lab smoke and DirectRLEnv."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LAB_DIR = Path(__file__).resolve().parent
DEFAULT_TCP_CACHE = LAB_DIR.parent / "runtime/outputs/lab_dynamic_smoke_v1/locked_tcp_cache.json"

from geometry_passport_v1 import (
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
    tcp_radius_xy,
)
from rtx_acoustic_factory import (  # noqa: E402
    create_passport_acoustic,
    extract_primary_raw_amplitudes,
    summarize_gmo_frame,
)
from rtx_material_passport_v1 import apply_room_and_target_materials

LAB_EXPERIMENT_MODE = "fixed_tcp_moving_target_dynamic"

SEED_POSES_RAD: dict[str, tuple[float, float, float, float, float, float]] = {
    "reach_forward": (0.0, -1.20, 1.20, -1.57, -1.57, 0.0),
    "home": (0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0),
    "reach_left": (0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
    "reach_right": (-0.45, -1.25, 1.35, -1.67, -1.57, 0.0),
}


def vec_tuple(values: Any) -> tuple[float, float, float]:
    return tuple(float(values[i]) for i in range(3))


def vec_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


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


@dataclass
class GmoWriterState:
    pending_step: dict[str, Any] | None = None
    writer_frame: int = 0
    parse_errors: list[str] = field(default_factory=list)
    raw_empty_frames: int = 0
    last_gmo_fields: dict[str, Any] | None = None
    # Raw primary-way amplitudes for gated ToF peak (D4 grasp / ranging).
    last_primary_amps: Any | None = None
    captured_this_step: bool = False


def make_gmo_writer_class(writer_state: GmoWriterState, np: Any):
    """Build a Replicator Writer that captures GMO into writer_state."""

    import omni.replicator.core as rep  # noqa: WPS433
    from isaacsim.sensors.experimental.rtx import parse_generic_model_output_data  # noqa: WPS433
    from omni.replicator.core import Writer  # noqa: WPS433

    class LabGmoWriter(Writer):
        def __init__(self):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]

        def write(self, data):
            pending = writer_state.pending_step
            for _rp_name, rp_data in data.get("renderProducts", {}).items():
                gmo_raw = rp_data.get("GenericModelOutput")
                if isinstance(gmo_raw, dict):
                    gmo_raw = gmo_raw.get("data")
                if gmo_raw is None:
                    continue
                if getattr(gmo_raw, "size", None) == 0:
                    if pending is not None:
                        writer_state.raw_empty_frames += 1
                    continue
                try:
                    gmo = parse_generic_model_output_data(gmo_raw)
                except Exception as exc:
                    if pending is not None and len(writer_state.parse_errors) < 10:
                        writer_state.parse_errors.append(str(exc))
                    continue
                if int(gmo.numElements) <= 0:
                    if pending is not None:
                        writer_state.raw_empty_frames += 1
                    continue
                gmo_fields = summarize_gmo_frame(gmo, np)
                writer_state.last_gmo_fields = gmo_fields
                try:
                    writer_state.last_primary_amps = extract_primary_raw_amplitudes(gmo, np)
                except Exception:
                    writer_state.last_primary_amps = None
                writer_state.captured_this_step = True
                if pending is not None:
                    pending["captured"] = True
                break
            writer_state.writer_frame += 1

    return LabGmoWriter


def capture_rtx_gmo(
    *,
    writer_state: GmoWriterState,
    simulation_app: Any,
    advance_sim: Any,
    substeps: int = 2,
    post_update_ticks: int = 5,
    after_substeps: Any | None = None,
) -> bool:
    """Trigger one GMO capture (Phase-4 + acoustic example: timeline.play + SimulationApp.update)."""
    import omni.timeline  # noqa: WPS433

    timeline = omni.timeline.get_timeline_interface()
    if not timeline.is_playing():
        timeline.play()

    writer_state.pending_step = {"captured": False}
    writer_state.captured_this_step = False
    n = max(1, int(substeps))
    for i in range(n):
        advance_sim(render=(i == n - 1))
        simulation_app.update()
    if after_substeps is not None:
        after_substeps()
    for _ in range(max(1, int(post_update_ticks))):
        simulation_app.update()
    gmo = writer_state.last_gmo_fields or {}
    captured = bool(
        writer_state.captured_this_step
        or (writer_state.pending_step and writer_state.pending_step.get("captured"))
        or gmo.get("gmo_valid", False)
    )
    writer_state.pending_step = None
    return captured


@dataclass
class RtxSceneStage:
    """USD + RTX assets spawned before physics play (DirectRLEnv _setup_scene)."""

    stage: Any
    target_scale: tuple[float, float, float]
    ee_path: str
    sensor_path: str
    writer_state: GmoWriterState
    material_summary: dict[str, Any]
    simulation_app: Any
    acoustic_sensor: Any = None


def rebind_rtx_gmo_writer(stage_assets: RtxSceneStage, *, writer_name: str = "LabGmoWriter") -> None:
    """Re-attach GMO writer after Isaac Lab sim.reset() (replicator hooks need physics playing)."""
    import numpy as np  # noqa: WPS433
    import omni.replicator.core as rep  # noqa: WPS433

    if stage_assets.acoustic_sensor is None:
        raise RuntimeError("acoustic_sensor missing on RtxSceneStage; cannot rebind GMO writer.")
    rep.WriterRegistry.register(make_gmo_writer_class(stage_assets.writer_state, np))
    stage_assets.acoustic_sensor.attach_writer(writer_name)
    for _ in range(5):
        stage_assets.simulation_app.update()


UR10_JOINT_NAMES: tuple[str, ...] = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)


def discover_ur10_joint_paths(stage: Any) -> dict[str, str]:
    """Map UR10 joint names to prim paths under ROBOT_PRIM_PATH."""
    from pxr import UsdPhysics  # noqa: WPS433

    found: dict[str, str] = {}
    robot_prefix = ROBOT_PRIM_PATH.rstrip("/") + "/"
    for prim in stage.Traverse():
        path = prim.GetPath().pathString
        if not path.startswith(robot_prefix):
            continue
        name = prim.GetName()
        if name not in UR10_JOINT_NAMES:
            continue
        if prim.IsA(UsdPhysics.RevoluteJoint) or prim.HasAPI(UsdPhysics.RevoluteJoint):
            found[name] = path
    missing = [name for name in UR10_JOINT_NAMES if name not in found]
    if missing:
        raise RuntimeError(f"Could not find UR10 joints under {ROBOT_PRIM_PATH}: {missing}")
    return found


def set_ur10_joint_positions_usd(stage: Any, q: Any, joint_paths: dict[str, str] | None = None) -> None:
    """Set UR10 joint targets via USD drive API."""
    from pxr import UsdPhysics  # noqa: WPS433

    paths = joint_paths or discover_ur10_joint_paths(stage)
    for joint_name, angle in zip(UR10_JOINT_NAMES, q, strict=True):
        joint_prim = stage.GetPrimAtPath(paths[joint_name])
        if not joint_prim:
            raise RuntimeError(f"Missing UR10 joint prim: {paths[joint_name]}")
        drive = UsdPhysics.DriveAPI.Get(joint_prim, "angular")
        if not drive:
            drive = UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
        drive.GetTargetPositionAttr().Set(float(angle))


@dataclass
class RtxSceneHandles:
    stage: Any
    joint_ids: Any
    locked_q: Any
    locked_q_tensor: Any
    ik: Any
    sensor_position: tuple[float, float, float]
    sensor_forward: tuple[float, float, float]
    target_scale: tuple[float, float, float]
    ee_path: str
    sensor_path: str
    writer_state: GmoWriterState
    material_summary: dict[str, Any]
    tcp_solution: dict[str, Any]
    observe_pose: Any
    simulation_app: Any


def bootstrap_rtx_stage(
    *,
    simulation_app: Any,
    material_condition: str = DEFAULT_MATERIAL_CONDITION,
    tick_rate_hz: float = TICK_RATE_HZ,
    center_frequency_hz: float = CENTER_FREQUENCY_HZ,
    lab_experiment_mode: str = LAB_EXPERIMENT_MODE,
    stage: Any | None = None,
    spawn_robot: bool = True,
) -> RtxSceneStage:
    """Spawn UR10 + room + RTX acoustic USD assets (before physics play)."""
    import numpy as np  # noqa: WPS433
    import omni  # noqa: WPS433
    import omni.replicator.core as rep  # noqa: WPS433
    import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: WPS433
    from isaacsim.core.experimental.materials import NonVisualMaterial  # noqa: WPS433
    from isaacsim.core.experimental.objects import Cube  # noqa: WPS433
    from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor  # noqa: WPS433
    from isaacsim.storage.native import get_assets_root_path  # noqa: WPS433
    from pxr import Sdf, Usd, UsdGeom  # noqa: WPS433

    if stage is None:
        context = omni.usd.get_context()
        context.new_stage()
        stage = context.get_stage()
        if stage is None:
            raise RuntimeError("Failed to create stage")
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    assets_root = get_assets_root_path()
    official_ur10_usd = f"{assets_root}/Isaac/Robots/UniversalRobots/ur10/ur10.usd"
    ee_path = f"{ROBOT_PRIM_PATH}/{EE_FRAME}"
    sensor_path = f"{ee_path}/{SENSOR_PRIM_NAME}"

    if spawn_robot:
        stage_utils.add_reference_to_stage(usd_path=official_ur10_usd, path=ROBOT_PRIM_PATH)
        for _ in range(20):
            simulation_app.update()

    room_prim_paths = create_six_wall_room(Cube, np)
    target_scale = tuple(float(v) for v in TARGET_CUBE_SCALE_M)
    set_target_pose(Cube, np, TARGET_PRIM_PATH, ee_target_position_m(), target_scale)

    material_summary = apply_room_and_target_materials(
        list(ROOM_PRIM_PATHS),
        TARGET_PRIM_PATH,
        str(material_condition),
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
        tick_rate_hz=float(tick_rate_hz),
        center_frequency_hz=float(center_frequency_hz),
        sensor_local_offset_m=SENSOR_LOCAL_OFFSET_M,
        mount_spacing_m=float(SENSOR_MOUNT_SPACING_M),
        writer_brings_annotator=True,
    )
    acoustic_prim = stage.GetPrimAtPath(sensor_path)
    if not acoustic_prim:
        raise RuntimeError(f"Acoustic prim was not created: {sensor_path}")

    acoustic_prim.CreateAttribute("research:geometryPassportId", Sdf.ValueTypeNames.String, custom=True).Set(PASSPORT_ID)
    acoustic_prim.CreateAttribute("research:experimentMode", Sdf.ValueTypeNames.String, custom=True).Set(lab_experiment_mode)
    acoustic_prim.CreateAttribute("research:parentExperimentMode", Sdf.ValueTypeNames.String, custom=True).Set(EXPERIMENT_MODE)

    writer_state = GmoWriterState()
    rep.WriterRegistry.register(make_gmo_writer_class(writer_state, np))
    sensor.attach_writer("LabGmoWriter")

    return RtxSceneStage(
        stage=stage,
        target_scale=target_scale,
        ee_path=ee_path,
        sensor_path=sensor_path,
        writer_state=writer_state,
        material_summary=material_summary,
        simulation_app=simulation_app,
        acoustic_sensor=sensor,
    )


def finalize_rtx_robot_handles(
    stage_assets: RtxSceneStage,
    *,
    articulation: Any,
    settle_steps: int = 40,
    step_fn: Any | None = None,
) -> RtxSceneHandles:
    """Solve fixed TCP and lock joints after Isaac Lab physics is playing."""
    import numpy as np  # noqa: WPS433
    import torch  # noqa: WPS433
    from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver  # noqa: WPS433
    from pxr import Gf, Usd, UsdGeom  # noqa: WPS433

    stage = stage_assets.stage
    simulation_app = stage_assets.simulation_app
    ee_path = stage_assets.ee_path
    sensor_path = stage_assets.sensor_path

    def default_step(render: bool = False) -> None:
        simulation_app.update()

    physics_step = step_fn or default_step
    joint_ids, joint_names = articulation.find_joints(list(UR10_JOINT_NAMES))
    if list(joint_names) != list(UR10_JOINT_NAMES):
        reorder = [joint_names.index(name) for name in UR10_JOINT_NAMES]
        joint_ids = [joint_ids[i] for i in reorder]

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

    def observe_pose(q: np.ndarray, settle_count: int, render: bool = False) -> dict[str, Any]:
        q_t = torch.tensor(q, device=articulation.device, dtype=torch.float32).reshape(1, -1)
        articulation.write_joint_position_to_sim_index(position=q_t, joint_ids=joint_ids)
        articulation.write_data_to_sim()
        for _ in range(max(1, int(settle_count))):
            physics_step(render=render)
        cache.Clear()
        ee_prim = stage.GetPrimAtPath(ee_path)
        sensor_prim = stage.GetPrimAtPath(sensor_path)
        ee_matrix = cache.GetLocalToWorldTransform(ee_prim)
        sensor_matrix = cache.GetLocalToWorldTransform(sensor_prim)
        actual_q = articulation.data.joint_pos[0, joint_ids].detach().cpu().numpy()
        return {
            "actual_q": np.asarray(actual_q, dtype=float),
            "ee_position": vec_tuple(ee_matrix.ExtractTranslation()),
            "sensor_position": vec_tuple(sensor_matrix.ExtractTranslation()),
            "sensor_forward": vec_tuple(sensor_matrix.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()),
            "min_link_z_m": min_robot_link_z(),
        }

    ik = None
    cache_path = Path(DEFAULT_TCP_CACHE)
    if cache_path.is_file():
        tcp_cache = json.loads(cache_path.read_text(encoding="utf-8"))
        locked_q = np.asarray(tcp_cache["locked_q_rad"], dtype=float)
        sensor_position = tuple(float(v) for v in tcp_cache["sensor_position_m"])
        sensor_forward = tuple(float(v) for v in tcp_cache["sensor_forward_m"])
        tcp_solution = {"from_cache": True, "cache_path": str(cache_path)}
        observe_pose(locked_q, int(settle_steps), render=False)
    else:
        ik = LulaKinematicsSolver(str(IK_ROBOT_DESCRIPTION), str(IK_URDF))
        ik.set_default_position_tolerance(float(IK_POSITION_TOLERANCE_M))
        fixed_q, tcp_solution = solve_fixed_tcp_joints(ik, observe_pose)
        baseline_obs = observe_pose(fixed_q, int(settle_steps), render=False)
        sensor_position = baseline_obs["sensor_position"]
        sensor_forward = baseline_obs["sensor_forward"]
        locked_q = np.asarray(baseline_obs["actual_q"], dtype=float)
    locked_q_tensor = torch.tensor(locked_q, device=articulation.device, dtype=torch.float32).unsqueeze(0)
    return RtxSceneHandles(
        stage=stage,
        joint_ids=joint_ids,
        locked_q=locked_q,
        locked_q_tensor=locked_q_tensor,
        ik=ik,
        sensor_position=sensor_position,
        sensor_forward=sensor_forward,
        target_scale=stage_assets.target_scale,
        ee_path=ee_path,
        sensor_path=sensor_path,
        writer_state=stage_assets.writer_state,
        material_summary=stage_assets.material_summary,
        tcp_solution=tcp_solution,
        observe_pose=observe_pose,
        simulation_app=simulation_app,
    )


def bootstrap_rtx_scene(
    *,
    simulation_app: Any,
    material_condition: str = DEFAULT_MATERIAL_CONDITION,
    tick_rate_hz: float = TICK_RATE_HZ,
    center_frequency_hz: float = CENTER_FREQUENCY_HZ,
    settle_steps: int = 40,
    lab_experiment_mode: str = LAB_EXPERIMENT_MODE,
    stage: Any | None = None,
) -> RtxSceneHandles:
    """Standalone smoke helper: stage bootstrap + robot finalize in one call."""
    stage_assets = bootstrap_rtx_stage(
        simulation_app=simulation_app,
        material_condition=material_condition,
        tick_rate_hz=tick_rate_hz,
        center_frequency_hz=center_frequency_hz,
        lab_experiment_mode=lab_experiment_mode,
        stage=stage,
    )
    raise RuntimeError("bootstrap_rtx_scene requires articulation; use bootstrap_rtx_stage + finalize_rtx_robot_handles.")