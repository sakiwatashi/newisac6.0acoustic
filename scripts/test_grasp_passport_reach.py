"""Unit tests for wrench spawn reach envelope (no Isaac Sim required)."""

from __future__ import annotations

import unittest

from grasp_passport_v1 import (
    EE_X_MAX_REACH_M,
    GRASP_STANDOFF_M,
    SEARCH_END_X_M,
    SEARCH_START_X_M,
    SENSOR_LOCAL_OFFSET_M,
    SENSOR_X_MAX_REACH_M,
    spawn_wrench_position,
    wrench_spawn_x_bounds_m,
)


class GraspPassportReachTests(unittest.TestCase):
    def test_sensor_reach_derived_from_ee(self) -> None:
        self.assertAlmostEqual(
            SENSOR_X_MAX_REACH_M,
            EE_X_MAX_REACH_M + SENSOR_LOCAL_OFFSET_M[0],
        )

    def test_search_corridor_end_includes_forward_slack(self) -> None:
        # Corridor end extends 5 cm past sensor reach ceiling (IK slack envelope).
        self.assertAlmostEqual(SEARCH_END_X_M, SENSOR_X_MAX_REACH_M + 0.05)

    def test_spawn_envelope_within_arm_reach(self) -> None:
        x_min, x_max = wrench_spawn_x_bounds_m()
        self.assertGreaterEqual(x_min, SEARCH_START_X_M + 0.12)
        self.assertLessEqual(x_max, SENSOR_X_MAX_REACH_M + GRASP_STANDOFF_M)
        self.assertLess(x_min, x_max)

    def test_spawn_samples_stay_inside_envelope(self) -> None:
        x_min, x_max = wrench_spawn_x_bounds_m()
        for trial_id in range(12):
            spawn = spawn_wrench_position(trial_id, 20260629)
            self.assertGreaterEqual(spawn.wrench_x_m, x_min)
            self.assertLessEqual(spawn.wrench_x_m, x_max)


if __name__ == "__main__":
    unittest.main()