"""Geometry Passport v1.0 — shared RTX / PyRoom experiment geometry.

Phase 1 redesign (2026-06-27):
- UR10 base fixed at world origin.
- TCP locked in a conservative workspace (radius ~0.80 m, height 0.65 m).
- Target distances 0.5–3.0 m are defined along the settled sensor +X axis.
- The arm does not move during distance sweeps; only the target moves.

Canonical path:
  /home/lab109/song/isaacsim6.0/scripts/geometry_passport_v1.py

PyRoom scripts should import this file by path until isaac_acoustic_research/config
is writable again.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

PASSPORT_VERSION = "v1.0"
PASSPORT_ID = "formal_ur10_fixed_tcp_reference"
EXPERIMENT_MODE = "fixed_tcp_moving_target"

ROOM_DIM_M = (4.5, 3.0, 2.8)
ROOM_CENTER_M = (2.0, 0.0, 0.0)
WALL_THICKNESS_M = 0.05
ROOM_INNER_MARGIN_M = 0.10

ROBOT_PRIM_PATH = "/World/ur10"
EE_FRAME = "ee_link"
SENSOR_PRIM_NAME = "official_rtx_acoustic"
TARGET_PRIM_PATH = "/World/fixed_target"

SENSOR_LOCAL_OFFSET_M = (0.08, 0.0, 0.0)
SENSOR_MOUNT_SPACING_M = 0.10
CENTER_FREQUENCY_HZ = 40_000.0
TICK_RATE_HZ = 20.0

TCP_RADIUS_M = 0.80
TCP_HEIGHT_M = 0.65
TCP_Y_M = 0.16
TCP_RADIUS_TOLERANCE_M = 0.08

DISTANCE_WAYPOINTS_M = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
DISTANCE_TOLERANCE_M = 0.05
ALIGNMENT_TOLERANCE_DEG = 5.0

# Acoustic reflector plate (center = measurement anchor). Edge lengths in meters.
# Note: Isaac Cube uses xform scale on a 1 m base prim unless sizes= is set.
TARGET_CUBE_SCALE_M = (0.08, 0.08, 0.02)

IK_ROBOT_DESCRIPTION = Path(
    "/home/lab109/song/isaacsim6.0/app/extsDeprecated/isaacsim.robot_motion.motion_generation/"
    "motion_policy_configs/universal_robots/ur10/rmpflow/ur10_robot_description.yaml"
)
IK_URDF = Path(
    "/home/lab109/song/isaacsim6.0/app/extsDeprecated/isaacsim.robot_motion.motion_generation/"
    "motion_policy_configs/universal_robots/ur10/ur10_robot.urdf"
)
IK_POSITION_TOLERANCE_M = 0.03
IK_ORIENTATION_TOLERANCE_RAD = 0.70
IK_MIN_LINK_Z_M = 0.0

PRA_GEOMETRY_POLICY = PASSPORT_ID
PRA_ROOM_DIM_M = list(ROOM_DIM_M)
PRA_MIC_POSITION_M = [TCP_RADIUS_M, TCP_Y_M, TCP_HEIGHT_M]
PRA_ABSORPTION_LABEL = "medium_absorption"
PRA_ABSORPTION_VALUE = 0.35
DEFAULT_MATERIAL_CONDITION = "B"

ROOM_PRIM_PATHS = (
    "/World/room/floor",
    "/World/room/ceiling",
    "/World/room/wall_x_min",
    "/World/room/wall_x_max",
    "/World/room/wall_y_min",
    "/World/room/wall_y_max",
)
# Grasp workcell: floor + table need PhysX collision. Walls/ceiling are RTX acoustic boundaries.
GRASP_COLLISION_PRIM_PATHS = (
    "/World/room/floor",
    "/World/room/wall_x_min",
    "/World/room/wall_x_max",
    "/World/room/wall_y_min",
    "/World/room/wall_y_max",
)

# Visual display colors (independent of RTX NonVisualMaterial acoustic properties).
ROOM_FLOOR_COLOR = "#9a9a9a"
ROOM_CEILING_COLOR = "#b8b8b8"
ROOM_WALL_COLOR = "#6b8cae"
TARGET_COLOR = "#ff6600"

# Default GUI camera looks from -X toward +X; this wall sits between the viewer and the robot.
CAMERA_FACING_WALL_PATH = "/World/room/wall_x_min"
GUI_DEFAULT_PRE_START_WAIT_S = 15.0
GUI_DEFAULT_EPISODE_PAUSE_S = 25.0

ISAACSIM_ROOT = Path("/home/lab109/song/isaacsim6.0")
DEFAULT_OUTPUT_ROOT = ISAACSIM_ROOT / "runtime/outputs/ur10_official_asset_fixed_tcp_distance_sweep"
DEFAULT_STAGE_PATH = ISAACSIM_ROOT / "runtime/scenes/ur10_official_asset_fixed_tcp_distance_sweep.usda"


def room_axis_bounds() -> dict[str, float]:
    length, width, height = ROOM_DIM_M
    cx, cy, _ = ROOM_CENTER_M
    half_l = length / 2.0
    half_w = width / 2.0
    return {
        "x_min": cx - half_l + ROOM_INNER_MARGIN_M,
        "x_max": cx + half_l - ROOM_INNER_MARGIN_M,
        "y_min": cy - half_w + ROOM_INNER_MARGIN_M,
        "y_max": cy + half_w - ROOM_INNER_MARGIN_M,
        "z_min": ROOM_INNER_MARGIN_M,
        "z_max": height - ROOM_INNER_MARGIN_M,
    }


def ee_target_position_m() -> tuple[float, float, float]:
    return (
        TCP_RADIUS_M - SENSOR_LOCAL_OFFSET_M[0],
        TCP_Y_M,
        TCP_HEIGHT_M,
    )


def target_position_from_sensor(
    sensor_position: tuple[float, float, float],
    sensor_forward: tuple[float, float, float],
    distance_m: float,
) -> tuple[float, float, float]:
    forward = _unit(sensor_forward)
    return (
        sensor_position[0] + distance_m * forward[0],
        sensor_position[1] + distance_m * forward[1],
        sensor_position[2] + distance_m * forward[2],
    )


def pra_source_position_for_distance(distance_m: float) -> list[float]:
    mic = PRA_MIC_POSITION_M
    return [mic[0] + distance_m, mic[1], mic[2]]


def target_inside_room(target_position: tuple[float, float, float]) -> bool:
    bounds = room_axis_bounds()
    x, y, z = target_position
    return (
        bounds["x_min"] <= x <= bounds["x_max"]
        and bounds["y_min"] <= y <= bounds["y_max"]
        and bounds["z_min"] <= z <= bounds["z_max"]
    )


def tcp_radius_xy(position: tuple[float, float, float]) -> float:
    return math.hypot(position[0], position[1])


def passport_summary() -> dict[str, Any]:
    bounds = room_axis_bounds()
    return {
        "passport_version": PASSPORT_VERSION,
        "passport_id": PASSPORT_ID,
        "experiment_mode": EXPERIMENT_MODE,
        "room_dim_m": list(ROOM_DIM_M),
        "room_center_m": list(ROOM_CENTER_M),
        "room_inner_bounds_m": bounds,
        "robot_prim_path": ROBOT_PRIM_PATH,
        "ee_frame": EE_FRAME,
        "sensor_local_offset_m": list(SENSOR_LOCAL_OFFSET_M),
        "tcp_radius_m": TCP_RADIUS_M,
        "tcp_height_m": TCP_HEIGHT_M,
        "tcp_y_m": TCP_Y_M,
        "distance_waypoints_m": list(DISTANCE_WAYPOINTS_M),
        "distance_tolerance_m": DISTANCE_TOLERANCE_M,
        "pra_geometry_policy": PRA_GEOMETRY_POLICY,
        "pra_room_dim_m": PRA_ROOM_DIM_M,
        "pra_mic_position_m": PRA_MIC_POSITION_M,
        "pra_absorption_label": PRA_ABSORPTION_LABEL,
        "pra_absorption_value": PRA_ABSORPTION_VALUE,
        "default_material_condition": DEFAULT_MATERIAL_CONDITION,
        "ee_target_position_m": list(ee_target_position_m()),
    }


def enable_static_collision(stage: Any, prim_path: str) -> bool:
    """Attach a kinematic static collider to a Cube/visual prim (experimental Cube has no collision by default)."""
    from pxr import PhysxSchema, UsdPhysics

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return False
    UsdPhysics.CollisionAPI.Apply(prim)
    if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
        rigid_body = UsdPhysics.RigidBodyAPI.Apply(prim)
        rigid_body.CreateKinematicEnabledAttr(True)
    if prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
        physx_body = PhysxSchema.PhysxRigidBodyAPI(prim)
    else:
        physx_body = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
    physx_body.CreateDisableGravityAttr(True)
    return True


def enable_static_collisions(stage: Any, prim_paths: list[str]) -> dict[str, bool]:
    return {path: enable_static_collision(stage, path) for path in prim_paths}


def spawn_rtx_sensor_visual_markers(
    stage: Any,
    sensor_path: str,
    *,
    mount_spacing_m: float = SENSOR_MOUNT_SPACING_M,
) -> list[str]:
    """Orange spheres at dual-mount TX/RX sites — OmniAcoustic has no visible mesh by default."""
    from pxr import Gf, UsdGeom

    marker_paths: list[str] = []
    offsets = (
        ("rx_mount_0", (0.0, 0.0, 0.0)),
        ("rx_mount_1", (float(mount_spacing_m), 0.0, 0.0)),
    )
    for label, offset in offsets:
        path = f"{sensor_path}/visual_{label}"
        sphere = UsdGeom.Sphere.Define(stage, path)
        sphere.CreateRadiusAttr(0.028)
        sphere.CreateDisplayColorAttr([(1.0, 0.45, 0.05)])
        sphere.CreateDisplayOpacityAttr([0.92])
        xform = UsdGeom.Xformable(sphere)
        xform.AddTranslateOp().Set(Gf.Vec3d(*offset))
        marker_paths.append(path)
    return marker_paths


def log_sensor_mount_summary(
    stage: Any,
    *,
    sensor_mount_path: str,
    sensor_path: str,
    sensor_local_offset_m: tuple[float, float, float] = SENSOR_LOCAL_OFFSET_M,
    mount_spacing_m: float = SENSOR_MOUNT_SPACING_M,
) -> dict[str, Any]:
    """Print where the RTX acoustic sensor lives (evaluation + GUI orientation)."""
    from pxr import UsdGeom

    cache = UsdGeom.XformCache(0)
    mount_prim = stage.GetPrimAtPath(sensor_mount_path)
    sensor_prim = stage.GetPrimAtPath(sensor_path)
    mount_pos = (
        tuple(float(x) for x in cache.GetLocalToWorldTransform(mount_prim).ExtractTranslation())
        if mount_prim and mount_prim.IsValid()
        else (math.nan, math.nan, math.nan)
    )
    sensor_pos = (
        tuple(float(x) for x in cache.GetLocalToWorldTransform(sensor_prim).ExtractTranslation())
        if sensor_prim and sensor_prim.IsValid()
        else (math.nan, math.nan, math.nan)
    )
    summary = {
        "sensor_mount_link": sensor_mount_path,
        "sensor_prim_path": sensor_path,
        "sensor_prim_type": "OmniAcoustic",
        "sensor_local_offset_m": list(sensor_local_offset_m),
        "dual_rx_spacing_m": float(mount_spacing_m),
        "mount_world_xyz_m": list(mount_pos),
        "sensor_world_xyz_m": list(sensor_pos),
        "visual_note": (
            "RTX Acoustic is a sensor prim (invisible). GUI shows orange spheres at "
            f"{sensor_path}/visual_rx_mount_0 and visual_rx_mount_1."
        ),
    }
    print("=== RTX Ultrasonic Sensor Mount ===", flush=True)
    print(f"  Parent link (moves with arm): {sensor_mount_path}", flush=True)
    print(f"  Sensor prim: {sensor_path}", flush=True)
    print(
        f"  Local offset from parent +X: {sensor_local_offset_m[0]:.3f} m "
        f"(forward = approach direction toward target)",
        flush=True,
    )
    print(f"  Dual receiver spacing along sensor +X: {mount_spacing_m:.3f} m", flush=True)
    print(f"  World position (approx): ({sensor_pos[0]:.3f}, {sensor_pos[1]:.3f}, {sensor_pos[2]:.3f}) m", flush=True)
    print(
        "  Why invisible: OmniAcoustic has no render mesh — look for the two orange spheres on wrist_3.",
        flush=True,
    )
    return summary


def create_six_wall_room(Cube: Any, np: Any) -> list[str]:
    length, width, height = ROOM_DIM_M
    cx, cy, _ = ROOM_CENTER_M
    t = WALL_THICKNESS_M
    min_x = cx - length / 2.0
    max_x = cx + length / 2.0
    min_y = cy - width / 2.0
    max_y = cy + width / 2.0
    specs = [
        ("/World/room/floor", (cx, cy, -t / 2.0), (length, width, t), ROOM_FLOOR_COLOR),
        ("/World/room/ceiling", (cx, cy, height + t / 2.0), (length, width, t), ROOM_CEILING_COLOR),
        ("/World/room/wall_x_min", (min_x - t / 2.0, cy, height / 2.0), (t, width, height), ROOM_WALL_COLOR),
        ("/World/room/wall_x_max", (max_x + t / 2.0, cy, height / 2.0), (t, width, height), ROOM_WALL_COLOR),
        ("/World/room/wall_y_min", (cx, min_y - t / 2.0, height / 2.0), (length, t, height), ROOM_WALL_COLOR),
        ("/World/room/wall_y_max", (cx, max_y + t / 2.0, height / 2.0), (length, t, height), ROOM_WALL_COLOR),
    ]
    for path, position, scale, color in specs:
        Cube(
            path,
            positions=np.array(position, dtype=float),
            scales=np.array(scale, dtype=float),
            colors=color,
        )
    return [path for path, _, _, _ in specs]


def grasp_room_layout_note() -> str:
    return (
        "Six walls: required for RTX ultrasonic room reflections (Phase B/C). "
        "Grasp physics only needs floor+table collision; walls are static acoustic boundaries. "
        "Ceiling is optional for grasp but kept for acoustic enclosure. "
        "Camera-facing wall_x_min is hidden in GUI."
    )


def apply_passport_display_colors(
    Cube: Any,
    room_prim_paths: list[str],
    target_prim_path: str,
) -> None:
    """Re-apply viewport display colors after RTX NonVisualMaterial binding."""
    wall_paths = [path for path in room_prim_paths if "/wall_" in path]
    if wall_paths:
        Cube(wall_paths, colors=ROOM_WALL_COLOR)
    if "/World/room/floor" in room_prim_paths:
        Cube("/World/room/floor", colors=ROOM_FLOOR_COLOR)
    if "/World/room/ceiling" in room_prim_paths:
        Cube("/World/room/ceiling", colors=ROOM_CEILING_COLOR)
    Cube(target_prim_path, colors=TARGET_COLOR)


def grasp_scene_camera_focus_m(
    wrench_position: tuple[float, float, float] | None = None,
) -> tuple[float, float, float]:
    """Default viewport look-at for UR10e grasp / approach scenes."""
    if wrench_position is not None:
        wx, wy, wz = wrench_position
        return (float(wx) * 0.55 + 0.45, float(wy), max(0.45, float(wz) + 0.08))
    return (1.0, float(TCP_Y_M), 0.55)


def configure_gui_viewport(
    simulation_app: Any,
    focus_position: tuple[float, float, float],
    *,
    use_camera_light: bool = True,
) -> dict[str, Any]:
    """Frame the workspace and enable viewport Camera Light (GUI mode)."""
    from isaacsim.core.rendering_manager import ViewportManager

    fx, fy, fz = focus_position
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
        eye=[fx - 2.8, fy + 1.8, fz + 1.2],
        target=[fx + 1.0, fy, fz],
    )

    camera_light_enabled = False
    if use_camera_light:
        try:
            import omni.usd
            from omni.kit.viewport.menubar.lighting.actions import _set_lighting_mode

            _set_lighting_mode("camera", usd_context=omni.usd.get_context())
            camera_light_enabled = True
        except Exception as exc:
            print(f"GUI viewport: failed to enable Camera Light ({exc})", flush=True)

    for _ in range(3):
        simulation_app.update()

    return {
        "viewport_ready": bool(viewport_ready),
        "waited_frames": int(waited_frames),
        "camera_light_enabled": camera_light_enabled,
        "focus_position_m": [fx, fy, fz],
    }


def wait_gui_pre_start(simulation_app: Any, seconds: float, on_tick: Any | None = None) -> None:
    """Count down before motion starts so the GUI can finish loading."""
    import time

    wait_s = max(0.0, float(seconds))
    if wait_s <= 0.0:
        return
    remaining = int(math.ceil(wait_s))
    print(f"GUI pre-start wait: {remaining}s (scene loading / camera settle)", flush=True)
    deadline = time.perf_counter() + wait_s
    while True:
        if on_tick is not None:
            on_tick()
        else:
            simulation_app.update()
        left = deadline - time.perf_counter()
        if left <= 0.0:
            break
        time.sleep(min(1.0, left))
        new_remaining = int(math.ceil(max(0.0, deadline - time.perf_counter())))
        if new_remaining != remaining:
            remaining = new_remaining
            if remaining > 0:
                print(f"GUI pre-start wait: {remaining}s remaining", flush=True)
    print("GUI pre-start wait: done — starting experiment", flush=True)


def wait_gui_episode_pause(
    simulation_app: Any,
    *,
    episode_index: int,
    episode_count: int,
    seconds: float,
    trial_id: int | None = None,
    on_tick: Any | None = None,
) -> None:
    """Pause between in-session episodes so motion/results are visible in the GUI."""
    import time

    wait_s = max(0.0, float(seconds))
    if wait_s <= 0.0:
        return
    trial_label = f" trial_id={trial_id}" if trial_id is not None else ""
    remaining = int(math.ceil(wait_s))
    print(
        f"GUI episode pause: episode {episode_index}/{episode_count}{trial_label} — "
        f"{remaining}s before next motion",
        flush=True,
    )
    deadline = time.perf_counter() + wait_s
    while True:
        if on_tick is not None:
            on_tick()
        else:
            simulation_app.update()
        left = deadline - time.perf_counter()
        if left <= 0.0:
            break
        time.sleep(min(1.0, left))
        new_remaining = int(math.ceil(max(0.0, deadline - time.perf_counter())))
        if new_remaining != remaining:
            remaining = new_remaining
            if remaining > 0:
                print(f"GUI episode pause: {remaining}s remaining", flush=True)
    print(f"GUI episode pause: done — starting episode {episode_index + 1}/{episode_count}", flush=True)


def prepare_gui_observation(
    simulation_app: Any,
    stage: Any,
    *,
    focus_position: tuple[float, float, float],
    hide_camera_wall: bool = True,
    use_camera_light: bool = True,
    pre_start_wait_s: float = GUI_DEFAULT_PRE_START_WAIT_S,
    on_tick: Any | None = None,
) -> dict[str, Any]:
    """Default GUI setup: hide viewer wall, camera framing, Camera Light, pre-start wait."""
    wall_hidden = False
    if hide_camera_wall:
        wall_hidden = set_prim_visibility(stage, CAMERA_FACING_WALL_PATH, visible=False)
        if wall_hidden:
            print(f"GUI: hid camera-facing wall {CAMERA_FACING_WALL_PATH}", flush=True)
    viewport = configure_gui_viewport(
        simulation_app,
        focus_position,
        use_camera_light=use_camera_light,
    )
    wait_gui_pre_start(simulation_app, pre_start_wait_s, on_tick=on_tick)
    return {
        "camera_facing_wall_hidden": wall_hidden,
        "pre_start_wait_s": float(pre_start_wait_s),
        **viewport,
    }


def set_prim_visibility(stage: Any, prim_path: str, visible: bool) -> bool:
    """Toggle USD prim visibility; returns False if the prim is missing."""
    from pxr import UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        return False
    imageable = UsdGeom.Imageable(prim)
    if not imageable:
        return False
    imageable.GetVisibilityAttr().Set(
        UsdGeom.Tokens.inherited if visible else UsdGeom.Tokens.invisible
    )
    return True


def _unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = max(math.sqrt(sum(float(x) * float(x) for x in v)), 1e-12)
    return (v[0] / n, v[1] / n, v[2] / n)