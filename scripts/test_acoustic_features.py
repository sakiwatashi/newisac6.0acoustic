"""Unit tests for Tier-B RTX acoustic feature extraction (no Isaac Sim)."""

from __future__ import annotations

import math
import unittest

from grasp_passport_v1 import DEFAULT_CALIBRATION, DEFAULT_TOF_CALIBRATION, ACOUSTIC_FUSION_ENERGY_WEIGHT
from rtx_acoustic_factory import (
    build_acoustic_features,
    estimate_distance_from_energy,
    estimate_distance_from_tof,
    fuse_distance_estimates,
)


class AcousticFeatureTests(unittest.TestCase):
    def test_energy_distance_interpolation(self) -> None:
        d = estimate_distance_from_energy(140.0, DEFAULT_CALIBRATION)
        self.assertTrue(math.isfinite(d))
        self.assertAlmostEqual(d, 0.50, delta=0.05)

    def test_tof_distance_monotonic(self) -> None:
        near = estimate_distance_from_tof(0.6e6, DEFAULT_TOF_CALIBRATION)
        far = estimate_distance_from_tof(1.2e6, DEFAULT_TOF_CALIBRATION)
        self.assertTrue(math.isfinite(near))
        self.assertTrue(math.isfinite(far))
        self.assertLess(near, far)

    def test_fused_distance_prefers_both_channels(self) -> None:
        fused = fuse_distance_estimates(0.40, 0.50, energy_weight=0.5)
        self.assertAlmostEqual(fused, 0.45, places=3)

    def test_alignment_score_penalizes_rx_imbalance(self) -> None:
        balanced = build_acoustic_features(
            gmo_valid=True,
            early_energy=120.0,
            ref_early_energy=100.0,
            tof_ns=0.8e6,
            ref_tof_ns=0.82e6,
            peak_amplitude=10.0,
            ref_peak_amplitude=9.0,
            amplitude_mean=5.0,
            amplitude_std=1.0,
            all_sgw_peak_mean=9.0,
            all_sgw_peak_std=0.5,
            num_signal_ways=2,
            rx_early_energy_0=110.0,
            rx_early_energy_1=108.0,
            rx_tof_ns_0=0.8e6,
            rx_tof_ns_1=0.81e6,
            rx_energy_balance=0.01,
            rx_tof_delta_ns=1e4,
            waveform_early_fraction=0.4,
            energy_calibration=DEFAULT_CALIBRATION,
            tof_calibration=DEFAULT_TOF_CALIBRATION,
            fusion_energy_weight=ACOUSTIC_FUSION_ENERGY_WEIGHT,
        )
        imbalanced = build_acoustic_features(
            gmo_valid=True,
            early_energy=120.0,
            ref_early_energy=100.0,
            tof_ns=0.8e6,
            ref_tof_ns=0.82e6,
            peak_amplitude=10.0,
            ref_peak_amplitude=9.0,
            amplitude_mean=5.0,
            amplitude_std=1.0,
            all_sgw_peak_mean=9.0,
            all_sgw_peak_std=0.5,
            num_signal_ways=2,
            rx_early_energy_0=150.0,
            rx_early_energy_1=60.0,
            rx_tof_ns_0=0.8e6,
            rx_tof_ns_1=0.81e6,
            rx_energy_balance=0.43,
            rx_tof_delta_ns=1e4,
            waveform_early_fraction=0.4,
            energy_calibration=DEFAULT_CALIBRATION,
            tof_calibration=DEFAULT_TOF_CALIBRATION,
            fusion_energy_weight=ACOUSTIC_FUSION_ENERGY_WEIGHT,
        )
        self.assertGreater(balanced.alignment_score, imbalanced.alignment_score)


if __name__ == "__main__":
    unittest.main()