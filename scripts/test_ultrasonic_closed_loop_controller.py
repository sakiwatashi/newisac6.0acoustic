"""Unit tests for ultrasonic_closed_loop_controller (no Isaac Sim required)."""

from __future__ import annotations

import math
import unittest

from grasp_passport_v1 import DEFAULT_CALIBRATION, DEFAULT_TOF_CALIBRATION, ACOUSTIC_FUSION_ENERGY_WEIGHT
from rtx_acoustic_factory import build_acoustic_features
from ultrasonic_closed_loop_controller import (
    ControllerConfig,
    ControllerState,
    DistanceCalibration,
    FailReason,
    UltrasonicClosedLoopController,
)


def _features(
    *,
    early_energy: float,
    rx_balance: float = 0.0,
    gmo_valid: bool = True,
) -> object:
    return build_acoustic_features(
        gmo_valid=gmo_valid,
        early_energy=early_energy,
        ref_early_energy=early_energy * 0.9,
        tof_ns=0.8e6,
        ref_tof_ns=0.82e6,
        peak_amplitude=10.0,
        ref_peak_amplitude=9.0,
        amplitude_mean=5.0,
        amplitude_std=1.0,
        all_sgw_peak_mean=9.0,
        all_sgw_peak_std=0.5,
        num_signal_ways=2,
        rx_early_energy_0=early_energy,
        rx_early_energy_1=early_energy * (1.0 - rx_balance),
        rx_tof_ns_0=0.8e6,
        rx_tof_ns_1=0.81e6,
        rx_energy_balance=rx_balance,
        rx_tof_delta_ns=1e4,
        waveform_early_fraction=0.4,
        energy_calibration=DEFAULT_CALIBRATION,
        tof_calibration=DEFAULT_TOF_CALIBRATION,
        fusion_energy_weight=ACOUSTIC_FUSION_ENERGY_WEIGHT,
    )


class UltrasonicClosedLoopControllerTests(unittest.TestCase):
    def test_calibration_interpolation(self) -> None:
        cal = DistanceCalibration()
        d = cal.estimate_distance_m(22.0)
        self.assertTrue(math.isfinite(d))
        # 22 * 132.5e-6 * 343.0 / 2 = 0.4999...
        self.assertAlmostEqual(d, 22.0 * 132.5e-6 * 343.0 / 2.0, places=9)
        self.assertGreater(d, 0.45)
        self.assertLess(d, 0.55)
        self.assertTrue(math.isnan(cal.estimate_distance_m(float("nan"))))
        self.assertTrue(math.isnan(cal.estimate_distance_m(-1.0)))

    def test_reaches_descend_when_fused_distance_close(self) -> None:
        ctrl = UltrasonicClosedLoopController(
            config=ControllerConfig(
                grasp_standoff_m=0.55,
                max_approach_steps=10,
                search_end_x_m=2.0,
                min_approach_samples_before_standoff=1,
                enable_grasp_phase=True,
                lateral_rx_balance_tolerance=0.05,
                final_approach_standoff_m=0.30,
            ),
        )
        ctrl.reset()
        ctrl.observe(
            features=_features(early_energy=110.0, rx_balance=0.01),
            sensor_x_m=0.60,
            oracle_distance_m=0.14,
        )
        ctrl.observe(
            features=_features(early_energy=102.0, rx_balance=0.01),
            sensor_x_m=0.60,
            oracle_distance_m=0.14,
        )
        state = ctrl.observe(
            features=_features(early_energy=98.0, rx_balance=0.01),
            sensor_x_m=0.60,
            oracle_distance_m=0.14,
        )
        self.assertEqual(state, ControllerState.DESCEND)
        self.assertTrue(ctrl.is_terminal())

    def test_steps_forward_when_far(self) -> None:
        ctrl = UltrasonicClosedLoopController(
            config=ControllerConfig(grasp_standoff_m=0.15, max_approach_steps=5, search_end_x_m=2.0),
        )
        ctrl.reset()
        ctrl.observe(
            features=_features(early_energy=155.0),
            sensor_x_m=0.60,
            oracle_distance_m=2.5,
        )
        self.assertTrue(ctrl.should_step_forward())
        self.assertAlmostEqual(ctrl.step_forward_delta_x_m(), 0.04)

    def test_fails_at_search_limit_without_close_fused_distance(self) -> None:
        ctrl = UltrasonicClosedLoopController(
            config=ControllerConfig(grasp_standoff_m=0.10, max_approach_steps=50, search_end_x_m=0.70),
        )
        ctrl.reset()
        ctrl.observe(
            features=_features(early_energy=155.0),
            sensor_x_m=0.72,
            oracle_distance_m=1.5,
        )
        ctrl.observe(
            features=_features(early_energy=155.0),
            sensor_x_m=0.72,
            oracle_distance_m=1.5,
        )
        self.assertEqual(ctrl.telemetry.state, ControllerState.FAIL)
        self.assertEqual(ctrl.telemetry.fail_reason, FailReason.SEARCH_LIMIT)

    def test_fails_without_gmo(self) -> None:
        ctrl = UltrasonicClosedLoopController()
        ctrl.reset()
        state = ctrl.observe(
            features=_features(early_energy=math.nan, gmo_valid=False),
            sensor_x_m=0.6,
        )
        self.assertEqual(state, ControllerState.FAIL)
        self.assertEqual(ctrl.telemetry.fail_reason, FailReason.NO_GMO)

    def test_lateral_step_when_rx_imbalanced(self) -> None:
        ctrl = UltrasonicClosedLoopController(
            config=ControllerConfig(
                enable_grasp_phase=True,
                min_approach_samples_before_standoff=0,
                grasp_standoff_m=0.40,
                lateral_rx_balance_tolerance=0.05,
                max_approach_steps=5,
            ),
        )
        ctrl.reset()
        ctrl.observe(
            features=_features(early_energy=100.0, rx_balance=0.30),
            sensor_x_m=0.8,
        )
        self.assertTrue(ctrl.should_step_lateral_y())
        self.assertLess(ctrl.step_lateral_delta_y_m(), 0.0)


if __name__ == "__main__":
    unittest.main()