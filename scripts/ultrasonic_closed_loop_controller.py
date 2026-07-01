"""Ultrasonic closed-loop approach controller — Tier B multi-feature fusion.

Pure-Python state machine — unit-testable without Isaac Sim.
Uses fused RTX GMO features (energy + TOF + dual-RX balance + alignment score).
Oracle distance is logged for evaluation only; not used for control decisions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from grasp_passport_v1 import (
    APPROACH_STEP_M,
    DEFAULT_CALIBRATION,
    DEFAULT_TOF_CALIBRATION,
    FINAL_APPROACH_STANDOFF_M,
    FINAL_APPROACH_STEP_M,
    GRASP_STANDOFF_M,
    LATERAL_ALIGN_STEP_M,
    LATERAL_RX_BALANCE_TOLERANCE,
    MAX_APPROACH_STEPS,
    MAX_FINAL_APPROACH_STEPS,
    MAX_LATERAL_ALIGN_STEPS,
    SEARCH_END_X_M,
)
from rtx_acoustic_factory import AcousticFeatureFrame


class ControllerState(str, Enum):
    INIT = "init"
    AT_SEARCH_START = "at_search_start"
    APPROACH_STEP = "approach_step"
    LATERAL_ALIGN = "lateral_align"
    FINAL_APPROACH = "final_approach"
    AT_STANDOFF = "at_standoff"
    DESCEND = "descend"
    GRASP = "grasp"
    LIFT = "lift"
    SUCCESS = "success"
    FAIL = "fail"


class FailReason(str, Enum):
    NO_GMO = "no_gmo"
    MAX_STEPS = "max_steps"
    SEARCH_LIMIT = "search_limit"
    INVALID_FEATURE = "invalid_feature"
    LATERAL_LIMIT = "lateral_limit"


@dataclass(frozen=True)
class DistanceCalibration:
    """Monotonic-ish lookup: early_energy -> distance (m)."""

    points: tuple[tuple[float, float], ...] = DEFAULT_CALIBRATION

    def estimate_distance_m(self, early_energy: float) -> float:
        if not math.isfinite(early_energy):
            return math.nan
        sorted_pts = sorted(self.points, key=lambda p: p[0], reverse=True)
        if early_energy >= sorted_pts[0][0]:
            return sorted_pts[0][1]
        if early_energy <= sorted_pts[-1][0]:
            return sorted_pts[-1][1]
        for (e_hi, d_hi), (e_lo, d_lo) in zip(sorted_pts, sorted_pts[1:]):
            if e_lo <= early_energy <= e_hi:
                if abs(e_hi - e_lo) < 1e-9:
                    return d_hi
                t = (early_energy - e_lo) / (e_hi - e_lo)
                return d_lo + t * (d_hi - d_lo)
        return math.nan


@dataclass
class ControllerConfig:
    grasp_standoff_m: float = GRASP_STANDOFF_M
    approach_step_m: float = APPROACH_STEP_M
    max_approach_steps: int = MAX_APPROACH_STEPS
    search_end_x_m: float = SEARCH_END_X_M
    enable_grasp_phase: bool = False
    min_approach_samples_before_standoff: int = 3
    lateral_align_step_m: float = LATERAL_ALIGN_STEP_M
    max_lateral_align_steps: int = MAX_LATERAL_ALIGN_STEPS
    lateral_rx_balance_tolerance: float = LATERAL_RX_BALANCE_TOLERANCE
    final_approach_step_m: float = FINAL_APPROACH_STEP_M
    max_final_approach_steps: int = MAX_FINAL_APPROACH_STEPS
    final_approach_standoff_m: float = FINAL_APPROACH_STANDOFF_M
    acoustic_tier: str = "B"


@dataclass
class ControllerTelemetry:
    state: ControllerState = ControllerState.INIT
    step_index: int = 0
    lateral_step_index: int = 0
    final_step_index: int = 0
    estimated_distance_m: float = math.nan
    fused_distance_m: float = math.nan
    oracle_distance_m: float = math.nan
    early_energy: float = math.nan
    alignment_score: float = math.nan
    rx_energy_balance: float = math.nan
    sensor_x_m: float = math.nan
    fail_reason: FailReason | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    last_features: AcousticFeatureFrame | None = None


class UltrasonicClosedLoopController:
    """Tier-B closed loop: fused distance cruise, dual-RX lateral align, final acoustic creep."""

    def __init__(
        self,
        *,
        config: ControllerConfig | None = None,
        calibration: DistanceCalibration | None = None,
    ) -> None:
        self.config = config or ControllerConfig()
        self.calibration = calibration or DistanceCalibration()
        self.telemetry = ControllerTelemetry()

    def reset(self) -> None:
        self.telemetry = ControllerTelemetry(state=ControllerState.AT_SEARCH_START)

    def observe(
        self,
        *,
        features: AcousticFeatureFrame,
        sensor_x_m: float,
        oracle_distance_m: float | None = None,
    ) -> ControllerState:
        """Ingest one acoustic sample and advance the state machine."""
        t = self.telemetry
        t.last_features = features
        t.early_energy = float(features.early_energy)
        t.fused_distance_m = float(features.fused_distance_m)
        t.estimated_distance_m = float(features.estimated_distance_energy_m)
        t.alignment_score = float(features.alignment_score)
        t.rx_energy_balance = float(features.rx_energy_balance)
        t.sensor_x_m = float(sensor_x_m)
        if oracle_distance_m is not None:
            t.oracle_distance_m = float(oracle_distance_m)

        if not features.gmo_valid or not math.isfinite(features.early_energy):
            t.state = ControllerState.FAIL
            t.fail_reason = FailReason.NO_GMO if not features.gmo_valid else FailReason.INVALID_FEATURE
            self._log_step(action="fail", features=features)
            return t.state

        if t.state in (ControllerState.INIT, ControllerState.AT_SEARCH_START):
            t.state = ControllerState.APPROACH_STEP
            self._log_step(action="begin_approach", features=features)
            return self._approach_decision(features)

        if t.state == ControllerState.APPROACH_STEP:
            return self._approach_decision(features)

        if t.state == ControllerState.LATERAL_ALIGN:
            return self._lateral_decision(features)

        if t.state == ControllerState.FINAL_APPROACH:
            return self._final_approach_decision(features)

        if t.state == ControllerState.AT_STANDOFF and self.config.enable_grasp_phase:
            t.state = ControllerState.DESCEND
            self._log_step(action="descend", features=features)
            return t.state

        return t.state

    def _distance_for_control(self, features: AcousticFeatureFrame) -> float:
        if math.isfinite(features.fused_distance_m):
            return float(features.fused_distance_m)
        return self.calibration.estimate_distance_m(features.early_energy)

    def _approach_decision(self, features: AcousticFeatureFrame) -> ControllerState:
        t = self.telemetry
        cfg = self.config
        distance_m = self._distance_for_control(features)

        if t.step_index >= cfg.max_approach_steps:
            t.state = ControllerState.FAIL
            t.fail_reason = FailReason.MAX_STEPS
            self._log_step(action="fail_max_steps", features=features)
            return t.state

        if t.sensor_x_m >= cfg.search_end_x_m:
            if (
                t.step_index >= cfg.min_approach_samples_before_standoff
                and math.isfinite(distance_m)
                and distance_m <= cfg.grasp_standoff_m + 0.10
            ):
                return self._enter_lateral_align(features, action="standoff_reached_search_limit")
            t.state = ControllerState.FAIL
            t.fail_reason = FailReason.SEARCH_LIMIT
            self._log_step(action="fail_search_limit", features=features)
            return t.state

        if (
            t.step_index >= cfg.min_approach_samples_before_standoff
            and math.isfinite(distance_m)
            and distance_m <= cfg.grasp_standoff_m
        ):
            return self._enter_lateral_align(features, action="standoff_reached")

        t.step_index += 1
        self._log_step(action="step_forward", features=features)
        return ControllerState.APPROACH_STEP

    def _enter_lateral_align(self, features: AcousticFeatureFrame, *, action: str) -> ControllerState:
        t = self.telemetry
        cfg = self.config
        t.state = ControllerState.LATERAL_ALIGN
        t.lateral_step_index = 0
        self._log_step(action=action, features=features)
        if not cfg.enable_grasp_phase:
            t.state = ControllerState.AT_STANDOFF
            return t.state
        if abs(t.rx_energy_balance) <= cfg.lateral_rx_balance_tolerance:
            return self._enter_final_approach(features, action="lateral_skipped_balanced")
        self._log_step(action="step_lateral_y", features=features)
        return ControllerState.LATERAL_ALIGN

    def _lateral_decision(self, features: AcousticFeatureFrame) -> ControllerState:
        t = self.telemetry
        cfg = self.config
        if abs(t.rx_energy_balance) <= cfg.lateral_rx_balance_tolerance:
            return self._enter_final_approach(features, action="lateral_aligned")
        if t.lateral_step_index >= cfg.max_lateral_align_steps:
            return self._enter_final_approach(features, action="lateral_limit_reached")
        t.lateral_step_index += 1
        self._log_step(action="step_lateral_y", features=features)
        return ControllerState.LATERAL_ALIGN

    def _enter_final_approach(self, features: AcousticFeatureFrame, *, action: str) -> ControllerState:
        t = self.telemetry
        cfg = self.config
        t.state = ControllerState.FINAL_APPROACH
        t.final_step_index = 0
        self._log_step(action=action, features=features)
        distance_m = self._distance_for_control(features)
        if math.isfinite(distance_m) and distance_m <= cfg.final_approach_standoff_m:
            t.state = ControllerState.DESCEND
            self._log_step(action="descend", features=features)
            return t.state
        self._log_step(action="step_final_forward", features=features)
        return ControllerState.FINAL_APPROACH

    def _final_approach_decision(self, features: AcousticFeatureFrame) -> ControllerState:
        t = self.telemetry
        cfg = self.config
        distance_m = self._distance_for_control(features)
        if math.isfinite(distance_m) and distance_m <= cfg.final_approach_standoff_m:
            t.state = ControllerState.DESCEND
            self._log_step(action="descend", features=features)
            return t.state
        if t.final_step_index >= cfg.max_final_approach_steps:
            t.state = ControllerState.DESCEND
            self._log_step(action="descend_final_limit", features=features)
            return t.state
        t.final_step_index += 1
        self._log_step(action="step_final_forward", features=features)
        return ControllerState.FINAL_APPROACH

    def should_step_forward(self) -> bool:
        return (
            self.telemetry.state == ControllerState.APPROACH_STEP
            and self.telemetry.history[-1].get("action") == "step_forward"
        )

    def should_step_lateral_y(self) -> bool:
        return (
            self.telemetry.state == ControllerState.LATERAL_ALIGN
            and self.telemetry.history[-1].get("action") == "step_lateral_y"
        )

    def should_step_final_forward(self) -> bool:
        return (
            self.telemetry.state == ControllerState.FINAL_APPROACH
            and self.telemetry.history[-1].get("action") == "step_final_forward"
        )

    def step_forward_delta_x_m(self) -> float:
        return float(self.config.approach_step_m)

    def step_lateral_delta_y_m(self) -> float:
        balance = float(self.telemetry.rx_energy_balance)
        if not math.isfinite(balance) or abs(balance) < 1e-6:
            return 0.0
        return -math.copysign(float(self.config.lateral_align_step_m), balance)

    def step_final_forward_delta_x_m(self) -> float:
        return float(self.config.final_approach_step_m)

    def is_terminal(self) -> bool:
        return self.telemetry.state in (
            ControllerState.SUCCESS,
            ControllerState.FAIL,
            ControllerState.AT_STANDOFF,
            ControllerState.DESCEND,
        )

    def _log_step(self, *, action: str, features: AcousticFeatureFrame) -> None:
        t = self.telemetry
        row = {
            "step_index": t.step_index,
            "lateral_step_index": t.lateral_step_index,
            "final_step_index": t.final_step_index,
            "state": t.state.value,
            "action": action,
            "estimated_distance_m": t.estimated_distance_m,
            "fused_distance_m": t.fused_distance_m,
            "oracle_distance_m": t.oracle_distance_m,
            "early_energy": t.early_energy,
            "alignment_score": t.alignment_score,
            "rx_energy_balance": t.rx_energy_balance,
            "sensor_x_m": t.sensor_x_m,
            "acoustic_tier": self.config.acoustic_tier,
        }
        row.update(features.as_log_dict())
        t.history.append(row)

