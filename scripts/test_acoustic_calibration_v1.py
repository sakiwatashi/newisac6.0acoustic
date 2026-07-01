"""Unit tests for acoustic_calibration_v1 (no Isaac Sim)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from acoustic_calibration_v1 import (
    build_energy_calibration_points,
    build_tof_calibration_points,
    load_tier_b_calibration,
)


class AcousticCalibrationTests(unittest.TestCase):
    def test_build_energy_points_monotonic(self) -> None:
        rows = [
            {"gmo_valid": True, "primary_sgw_early_energy": 150.0, "oracle_distance_m": 0.8},
            {"gmo_valid": True, "primary_sgw_early_energy": 130.0, "oracle_distance_m": 0.3},
            {"gmo_valid": True, "primary_sgw_early_energy": 140.0, "oracle_distance_m": 0.5},
        ]
        points = build_energy_calibration_points(rows, num_points=3)
        self.assertEqual(len(points), 3)
        self.assertGreater(points[0][0], points[-1][0])
        self.assertGreater(points[0][1], points[-1][1])

    def test_load_calibration_json_roundtrip(self) -> None:
        payload = {
            "energy_calibration": [[150.0, 0.8], [130.0, 0.3]],
            "tof_calibration": [[800000.0, 0.3], [1200000.0, 0.8]],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tier_b_calibration.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            energy, tof, meta = load_tier_b_calibration(path)
            self.assertEqual(len(energy), 2)
            self.assertEqual(len(tof), 2)
            self.assertEqual(meta["source"], "tier_b_calibration_json")

    def test_tof_points_skip_invalid(self) -> None:
        rows = [
            {
                "gmo_valid": True,
                "primary_sgw_early_energy": 130.0,
                "primary_sgw_first_time_offset_ns": 0.0,
                "oracle_distance_m": 0.3,
            },
            {
                "gmo_valid": True,
                "primary_sgw_early_energy": 140.0,
                "primary_sgw_first_time_offset_ns": 900000.0,
                "oracle_distance_m": 0.5,
            },
        ]
        points = build_tof_calibration_points(rows)
        self.assertEqual(len(points), 1)


if __name__ == "__main__":
    unittest.main()