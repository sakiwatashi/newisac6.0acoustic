#!/usr/bin/env python3
"""Test script to run recalibration analysis."""

import subprocess
import sys

def test_recalibration():
    """Execute recalibration analysis."""
    result = subprocess.run(
        [sys.executable, '/home/lab109/song/isaacsim6.0/scripts/recalibrate_energy_from_dataset.py'],
        capture_output=False,
        text=True
    )
    return result.returncode == 0

if __name__ == '__main__':
    success = test_recalibration()
    sys.exit(0 if success else 1)
