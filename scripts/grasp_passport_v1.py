"""Grasp Passport v1 — ultrasonic closed-loop approach/grasp task geometry.

Phase B: closed-loop approach without reading target world coordinates.
Phase C: add gripper close + lift success check (same passport).

Control policy must only use:
  - search corridor bounds (known workspace, not target pose)
  - RTX acoustic features (primary_sgw_early_energy, etc.)

Oracle target pose is logged for evaluation only and must not be passed to the controller.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

from geometry_passport_v1 import (
    CENTER_FREQUENCY_HZ,
    EE_FRAME,
    ROBOT_PRIM_PATH,
    ROOM_DIM_M,
    SENSOR_LOCAL_OFFSET_M,
    SENSOR_PRIM_NAME,
    TCP_HEIGHT_M,
    TCP_Y_M,
    TICK_RATE_HZ,
    room_axis_bounds,
)

PASSPORT_VERSION = "v1.0"
PASSPORT_ID = "ur10_ultrasonic_closed_loop_grasp"
EXPERIMENT_MODE = "ultrasonic_closed_loop_grasp_v1"

# Peak-sample distance calibration (arm-free sweep 2026-07-06, r=0.9991, n=280).
# dist_m = peak_sample_idx * PEAK_SAMPLE_T_US * PEAK_SAMPLE_V_SOUND_M_S / 2
# Valid range: 0.20–1.50 m; sample period empirically confirmed frequency-agnostic.
PEAK_SAMPLE_T_US: float = 132.5e-6     # s/sample (40 kHz sweep calibration)
PEAK_SAMPLE_V_SOUND_M_S: float = 343.0  # m/s (indoor air ~20°C)

# Scene prims
TABLE_PRIM_PATH = "/World/work_table"
WRENCH_PRIM_PATH = "/World/wrench_target"
SURFACE_GRIPPER_PARENT_PATH = "/World/ur10/ee_link"
SURFACE_GRIPPER_SUFFIX = "SurfaceGripper"

# Wrench proxy geometry (Phase B/C smoke: metallic cube; replace with mesh later)
WRENCH_SCALE_M = (0.18, 0.04, 0.04)
WRENCH_PHYSICS_MASS_KG = 0.15
WRENCH_PHYSICS_FRICTION = 3.0
WRENCH_COLOR = "#c0c0c0"
# Legacy thin-slab dims (visual only); runtime uses solid_work_table_scale_m() below.
TABLE_SCALE_M = (1.2, 0.8, 0.05)
TABLE_TOP_Z_M = 0.40
# Solid block from floor (z=0) to table top — no cavity for the arm to pass underneath.
TABLE_SOLID_SIZE_XY_M = (1.2, 0.8)
TABLE_SOLID_HEIGHT_M = TABLE_TOP_Z_M
# Nearer the UR10 base — shorter coarse reach; fine motion uses wrist joints only.
TABLE_DEFAULT_X_M = 0.78
# Minimum tool0 Z during approach/cruise (position-only IK otherwise dips under the table).
APPROACH_TABLE_CLEARANCE_M = 0.22
APPROACH_TOOL0_MIN_Z_M = TABLE_TOP_Z_M + APPROACH_TABLE_CLEARANCE_M
# Keep tool0 high enough that open Robotiq pads do not spear the table in GUI physics.
GRASP_TOOL0_MIN_Z_M = TABLE_TOP_Z_M + 0.08
WRENCH_CENTER_Z_M = TABLE_TOP_Z_M + WRENCH_SCALE_M[2] / 2.0

# Random spawn: horizontal offset only by default; v8 can override Y via env.
SPAWN_SEED_DEFAULT = 20260629


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return float(default)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a finite float, got {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {raw!r}")
    return value


WRENCH_Y_M = _env_float("GRASP_WRENCH_Y_M", TCP_Y_M)

# Search corridor: arm starts here; controller may only know these bounds.
# v8 randomized data collection can override these to break pose shortcuts.
SEARCH_START_X_M = _env_float("GRASP_SEARCH_START_X_M", 0.55)
SEARCH_START_Y_M = _env_float("GRASP_SEARCH_START_Y_M", TCP_Y_M)
APPROACH_AXIS = (1.0, 0.0, 0.0)

# Closed-loop motion (needed for reach-envelope algebra below)
GRASP_STANDOFF_M = 0.35

# --- UR10 reach envelope (reach_forward seed, TCP_HEIGHT_M, pilot 2026-06-29) ---
# EE +X ceiling before corridor IK failures; sensor sits SENSOR_LOCAL_OFFSET_M ahead of EE.
EE_X_MAX_REACH_M = 1.28
SENSOR_X_MAX_REACH_M = EE_X_MAX_REACH_M + SENSOR_LOCAL_OFFSET_M[0]
IK_REACH_SAFETY_MARGIN_M = 0.15
# Robotiq 2F-85 tool0→contact reach along +X (pilot; not sim-to-real calibrated).
ROBOTIQ_FORWARD_REACH_M = 0.10
# tool0 X offset behind wrench center for finger straddle (matches grasp_alignment candidates).
GRASP_TOOL0_X_BACKOFF_M = 0.03
# Hard ceiling during approach: do not let tool0 pass this far beyond wrench center (+X).
GRASP_APPROACH_MAX_TOOL0_X_MARGIN_M = 0.08
# tool0 Z at contact: wrench top + clearance (fingers hang below tool0; pilot 2026-06-30).
ROBOTIQ_TOOL0_ABOVE_WRENCH_TOP_M = 0.04
WRENCH_HALF_LENGTH_M = WRENCH_SCALE_M[0] / 2.0
SEARCH_END_X_M = SENSOR_X_MAX_REACH_M + 0.05

# Wrench center x: keep standoff point inside sensor reach (center-distance standoff model).
# sensor_x_required ≈ wrench_x - GRASP_STANDOFF_M → wrench_x <= sensor_max + standoff - margin
WRENCH_X_MAX_M = min(
    SENSOR_X_MAX_REACH_M + GRASP_STANDOFF_M - IK_REACH_SAFETY_MARGIN_M,
    TABLE_DEFAULT_X_M + TABLE_SOLID_SIZE_XY_M[0] / 2.0 - 0.08,
)
# Acoustic contrast vs search start without full-arm extension to the far table.
WRENCH_X_MIN_M = SEARCH_START_X_M + 0.15

# Closed-loop motion
APPROACH_STEP_M = 0.04
MAX_APPROACH_STEPS = 40
SETTLE_STEPS_PER_MOVE = 30
GMO_SUBSTEPS = 2

# Phase C grasp/lift (UR10e+Robotiq: cruise z~0.65, wrench top~0.44)
GRASP_EE_Z_ABOVE_WRENCH_TOP_M = 0.0
DESCEND_DELTA_Z_M = 0.18
JOINT_DESCEND_MAX_STEPS = 6
LIFT_DELTA_Z_M = 0.03
LIFT_MICRO_STEPS = 12
LIFT_HOLD_STEPS = 40
GRIPPER_MAX_GRIP_DISTANCE_M = 0.08
GRIPPER_SETTLE_STEPS = 45
LIFT_SUCCESS_MIN_Z_DELTA_M = 0.04

# Open-loop baseline only (oracle target pose — not used by closed-loop controller)
OPEN_LOOP_PREGRASP_IK_BACKOFFS_M = (0.0, 0.05, 0.12, 0.20)

# [DEPRECATED] early_energy → distance lookup.
# Only reliable for d < 0.45 m (first 20 samples); collapses to noise floor beyond that.
# Retained for backward compatibility. Use PEAK_SAMPLE_T_US formula instead.
DEFAULT_CALIBRATION: tuple[tuple[float, float], ...] = (
    (192.8, 0.90),
    (160.7, 0.80),
    (154.1, 0.60),
    (140.2, 0.50),
    (138.5, 0.45),
    (131.8, 0.35),
    (106.2, 0.20),
    (87.2, 0.10),
)

# Tier B: fuse RTX GMO features (energy + TOF + dual-RX + lateral micro-align).
ACOUSTIC_CONTROL_TIER = "B"
ACOUSTIC_FUSION_ENERGY_WEIGHT = 0.72
# first_time_offset_ns → distance (m); aligned to DEFAULT_CALIBRATION distances (recalibrate via sweep).
DEFAULT_TOF_CALIBRATION: tuple[tuple[float, float], ...] = (
    (0.72e6, 0.22),
    (0.80e6, 0.28),
    (0.88e6, 0.35),
    (0.96e6, 0.45),
    (1.04e6, 0.55),
    (1.14e6, 0.65),
    (1.28e6, 0.85),
)
LATERAL_ALIGN_STEP_M = 0.012
MAX_LATERAL_ALIGN_STEPS = 6
LATERAL_RX_BALANCE_TOLERANCE = 0.12
FINAL_APPROACH_STEP_M = 0.02
MAX_FINAL_APPROACH_STEPS = 8
FINAL_APPROACH_STANDOFF_M = 0.14
ECHO_CONTACT_ENERGY_DROP_RATIO = 0.28
ECHO_GRASP_OCCLUSION_RATIO = 0.08
ACOUSTIC_LIFT_SUCCESS_ENERGY_RATIO = 0.55


@dataclass(frozen=True)
class WrenchSpawn:
    trial_id: int
    seed: int
    wrench_x_m: float
    wrench_y_m: float
    wrench_z_m: float

    @property
    def position_m(self) -> tuple[float, float, float]:
        return (self.wrench_x_m, self.wrench_y_m, self.wrench_z_m)


def wrench_spawn_x_bounds_m() -> tuple[float, float]:
    """Reachable wrench center x range for the current UR10 + corridor passport."""
    room = room_axis_bounds()
    x_min = max(float(WRENCH_X_MIN_M), float(room["x_min"]))
    x_max = min(float(WRENCH_X_MAX_M), float(room["x_max"]))
    if x_min > x_max:
        raise ValueError(f"Empty wrench spawn envelope: [{x_min}, {x_max}]")
    return x_min, x_max


def spawn_wrench_position(trial_id: int, seed: int) -> WrenchSpawn:
    """Deterministic pseudo-random x inside the UR10 reach envelope."""
    x_min, x_max = wrench_spawn_x_bounds_m()
    span = float(x_max - x_min)
    frac = ((trial_id + 1) * 1103515245 + seed) % 10000 / 10000.0
    x = float(x_min) + span * frac
    return WrenchSpawn(
        trial_id=int(trial_id),
        seed=int(seed),
        wrench_x_m=x,
        wrench_y_m=float(WRENCH_Y_M),
        wrench_z_m=float(WRENCH_CENTER_Z_M),
    )


def surface_gripper_path() -> str:
    return f"{SURFACE_GRIPPER_PARENT_PATH}/{SURFACE_GRIPPER_SUFFIX}"


def open_loop_pregrasp_ee_position_m(wrench_position: tuple[float, float, float]) -> tuple[float, float, float]:
    """Oracle-derived EE pose: sensor at grasp standoff along +X, EE at TCP cruise height."""
    sensor_x = float(wrench_position[0]) - float(GRASP_STANDOFF_M)
    ee_x = sensor_x - float(SENSOR_LOCAL_OFFSET_M[0])
    return clamp_ee_target_for_approach(
        (
            ee_x,
            float(wrench_position[1]),
            float(TCP_HEIGHT_M),
        )
    )


def max_tool0_x_before_wrench_center_m(wrench_x_m: float) -> float:
    """Forward (+X) limit for tool0 during approach — prevents driving past the wrench."""
    return float(wrench_x_m) - float(GRASP_APPROACH_MAX_TOOL0_X_MARGIN_M)


def grasp_alignment_tool0_x_m(wrench_x_m: float) -> float:
    """Passport grasp X: slightly retracted from wrench center (episode spawn geometry, not live sensing)."""
    return max(
        float(SEARCH_START_X_M) - float(SENSOR_LOCAL_OFFSET_M[0]),
        float(wrench_x_m) - float(GRASP_TOOL0_X_BACKOFF_M),
    )


def robotiq_grasp_contact_ee_z_m(wrench_center_z_m: float) -> float:
    wrench_top_z = float(wrench_center_z_m) + float(WRENCH_SCALE_M[2]) / 2.0
    return wrench_top_z + float(ROBOTIQ_TOOL0_ABOVE_WRENCH_TOP_M)


def passport_grasp_contact_ee_z_m() -> float:
    """Workspace geometry contact height — no per-trial oracle pose."""
    return robotiq_grasp_contact_ee_z_m(float(WRENCH_CENTER_Z_M))


def grasp_alignment_ee_candidates_m(wrench_position: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    """Oracle EE poses for Phase-C contact alignment (evaluation/IK only, not closed-loop sensing)."""
    wx, wy, wz = wrench_position
    grasp_z = robotiq_grasp_contact_ee_z_m(wz)
    reach_x = min(float(wx), float(EE_X_MAX_REACH_M))
    # Prefer slightly retracted X first — full reach_x often IK-ok but unreachable on UR10e+Robotiq.
    return [
        clamp_ee_target_for_grasp((max(float(SEARCH_START_X_M), reach_x - 0.02), float(wy), grasp_z)),
        clamp_ee_target_for_grasp((max(float(SEARCH_START_X_M), reach_x - 0.05), float(wy), grasp_z)),
        clamp_ee_target_for_grasp((max(float(SEARCH_START_X_M), reach_x - 0.10), float(wy), grasp_z)),
        clamp_ee_target_for_grasp((reach_x, float(wy), grasp_z)),
        clamp_ee_target_for_approach((reach_x, float(wy), float(TCP_HEIGHT_M))),
    ]


def open_loop_pregrasp_candidates_m(wrench_position: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    """Ordered IK fallbacks when the ideal oracle standoff pose is unreachable."""
    wx, wy, _ = wrench_position
    sensor_offset = float(SENSOR_LOCAL_OFFSET_M[0])
    standoff = float(GRASP_STANDOFF_M)
    return [
        clamp_ee_target_for_approach(
            (
                float(wx) - standoff - sensor_offset - float(backoff),
                float(wy),
                float(TCP_HEIGHT_M),
            )
        )
        for backoff in OPEN_LOOP_PREGRASP_IK_BACKOFFS_M
    ]


def solid_work_table_center_m(
    wrench_y_m: float,
    *,
    table_x_m: float = TABLE_DEFAULT_X_M,
) -> tuple[float, float, float]:
    """Center of a floor-to-top solid workbench block (bottom sits on z=0)."""
    return (
        float(table_x_m),
        float(wrench_y_m),
        float(TABLE_SOLID_HEIGHT_M) / 2.0,
    )


def solid_work_table_scale_m() -> tuple[float, float, float]:
    return (
        float(TABLE_SOLID_SIZE_XY_M[0]),
        float(TABLE_SOLID_SIZE_XY_M[1]),
        float(TABLE_SOLID_HEIGHT_M),
    )


def approach_ee_target_z_m() -> float:
    """Cruise tool0 height during closed-loop approach — always above the work table."""
    return max(float(TCP_HEIGHT_M), float(APPROACH_TOOL0_MIN_Z_M))


def clamp_ee_target_z(
    ee_target: tuple[float, float, float] | list[float],
    *,
    min_z_m: float,
) -> tuple[float, float, float]:
    x, y, z = ee_target
    return (float(x), float(y), max(float(z), float(min_z_m)))


def clamp_ee_target_for_approach(
    ee_target: tuple[float, float, float] | list[float],
) -> tuple[float, float, float]:
    return clamp_ee_target_z(ee_target, min_z_m=approach_ee_target_z_m())


def clamp_ee_target_for_grasp(
    ee_target: tuple[float, float, float] | list[float],
) -> tuple[float, float, float]:
    return clamp_ee_target_z(ee_target, min_z_m=float(GRASP_TOOL0_MIN_Z_M))


def search_start_ee_position_m() -> tuple[float, float, float]:
    """Conservative EE pose at the search corridor start (known, not target-derived)."""
    return clamp_ee_target_for_approach(
        (
            float(SEARCH_START_X_M) - SENSOR_LOCAL_OFFSET_M[0],
            float(SEARCH_START_Y_M),
            float(TCP_HEIGHT_M),
        )
    )


def sensor_forward_world() -> tuple[float, float, float]:
    return APPROACH_AXIS


def oracle_distance_m(sensor_position: tuple[float, float, float], wrench_position: tuple[float, float, float]) -> float:
    dx = wrench_position[0] - sensor_position[0]
    dy = wrench_position[1] - sensor_position[1]
    dz = wrench_position[2] - sensor_position[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def passport_summary() -> dict[str, Any]:
    return {
        "passport_version": PASSPORT_VERSION,
        "passport_id": PASSPORT_ID,
        "experiment_mode": EXPERIMENT_MODE,
        "robot_prim_path": ROBOT_PRIM_PATH,
        "ee_frame": EE_FRAME,
        "sensor_prim_name": SENSOR_PRIM_NAME,
        "wrench_prim_path": WRENCH_PRIM_PATH,
        "table_prim_path": TABLE_PRIM_PATH,
        "room_dim_m": list(ROOM_DIM_M),
        "wrench_spawn_x_range_m": list(wrench_spawn_x_bounds_m()),
        "wrench_y_m": WRENCH_Y_M,
        "search_corridor_x_range_m": [SEARCH_START_X_M, SEARCH_END_X_M],
        "search_start_y_m": SEARCH_START_Y_M,
        "reach_envelope_m": {
            "ee_x_max_reach_m": EE_X_MAX_REACH_M,
            "sensor_x_max_reach_m": SENSOR_X_MAX_REACH_M,
            "ik_reach_safety_margin_m": IK_REACH_SAFETY_MARGIN_M,
        },
        "table_top_z_m": TABLE_TOP_Z_M,
        "table_solid_scale_m": list(solid_work_table_scale_m()),
        "table_solid_height_m": TABLE_SOLID_HEIGHT_M,
        "approach_tool0_min_z_m": approach_ee_target_z_m(),
        "grasp_tool0_min_z_m": GRASP_TOOL0_MIN_Z_M,
        "approach_step_m": APPROACH_STEP_M,
        "grasp_standoff_m": GRASP_STANDOFF_M,
        "max_approach_steps": MAX_APPROACH_STEPS,
        "center_frequency_hz": CENTER_FREQUENCY_HZ,
        "tick_rate_hz": TICK_RATE_HZ,
        "peak_sample_t_us": PEAK_SAMPLE_T_US,
        "peak_sample_v_sound_m_s": PEAK_SAMPLE_V_SOUND_M_S,
        "calibration_points": list(DEFAULT_CALIBRATION),
        "tof_calibration_points": list(DEFAULT_TOF_CALIBRATION),
        "acoustic_control_tier": ACOUSTIC_CONTROL_TIER,
        "lateral_align_step_m": LATERAL_ALIGN_STEP_M,
        "final_approach_standoff_m": FINAL_APPROACH_STANDOFF_M,
        "claim_boundary": (
            "Tier B: controller uses fused RTX GMO features only (energy, TOF, dual-RX, waveform). "
            "Oracle distance/pose is evaluation-only. Grasp uses passport table geometry, not wrench prim pose."
        ),
    }