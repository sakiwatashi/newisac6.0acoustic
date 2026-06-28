"""Kinematic target trajectories for Isaac Lab Phase 4 dynamic smoke."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SinusoidalDistanceTrajectory:
    """Target distance oscillates along sensor +X between center ± amplitude."""

    center_distance_m: float = 1.5
    amplitude_m: float = 0.5
    period_steps: int = 64

    def distance_at_step(self, step_index: int) -> float:
        phase = 2.0 * math.pi * float(step_index) / float(max(1, self.period_steps))
        return self.center_distance_m + self.amplitude_m * math.sin(phase)

    def distance_bounds_m(self) -> tuple[float, float]:
        return (
            self.center_distance_m - self.amplitude_m,
            self.center_distance_m + self.amplitude_m,
        )