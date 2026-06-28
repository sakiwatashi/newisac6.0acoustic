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

# Visual display colors (independent of RTX NonVisualMaterial acoustic properties).
ROOM_FLOOR_COLOR = "#9a9a9a"
ROOM_CEILING_COLOR = "#b8b8b8"
ROOM_WALL_COLOR = "#6b8cae"
TARGET_COLOR = "#ff6600"

# Default GUI camera looks from -X toward +X; this wall sits between the viewer and the robot.
CAMERA_FACING_WALL_PATH = "/World/room/wall_x_min"

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