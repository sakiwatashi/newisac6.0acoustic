"""D4 shared constants and helpers (Track A state machine + metrics).

No Isaac / GPU import. Safe for offline analyzers and unit tests.

Spec: docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md
"""
from __future__ import annotations

import json
import math
import pathlib
from enum import IntEnum

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pre-registered (D4-3); lock changes only via d4/decisions.md + new output dir
TOL_ALIGN_X_M = 0.02
GRASP_SUCCESS_Z_GAIN_M = 0.05
STANDOFF_M = 0.35
APPROACH_STEP_M = 0.05
LIFT_HEIGHT_M = 0.10
# D4 change vs D3: smaller continuous lift steps (reduce teleport impulse)
LIFT_UP_STEP_M = 0.002
LIFT_SETTLE_STEPS = 8
HOLD_FRAMES = 60
NEAR_FIELD_NO_ACOUSTIC_M = 0.32

BAR_CALIB_JSON = REPO_ROOT / "runtime" / "outputs" / "v2_d3_gates" / "bar_calibration.json"
V_SOUND = 343.0


class SmState(IntEnum):
    """Track A state machine (order = episode progress)."""

    REST = 0
    ACOUSTIC_APPROACH = 1
    ACOUSTIC_ALIGN_STOP = 2
    DESCEND = 3
    CLOSE = 4
    LIFT = 5
    HOLD = 6
    DONE = 7
    FAILED = 8


SM_STATE_NAMES = {s: s.name for s in SmState}


def load_bar_calibration(path: pathlib.Path | None = None) -> dict:
    path = path or BAR_CALIB_JSON
    if not path.exists():
        raise FileNotFoundError(
            f"bar calibration missing: {path} — run D3.0 gates first "
            "(runtime/outputs/v2_d3_gates/bar_calibration.json)"
        )
    with path.open() as f:
        cal = json.load(f)
    for key in ("slope_smp_per_m", "intercept_smp"):
        if key not in cal or not math.isfinite(float(cal[key])):
            raise ValueError(f"calibration missing/invalid {key}: {path}")
    return cal


def peak_to_range_3d(peak_idx: float, slope: float, intercept: float) -> float:
    if not math.isfinite(peak_idx) or slope == 0.0:
        return float("nan")
    return (peak_idx - intercept) / slope


def range_3d_to_horiz(d3d: float, height_diff_m: float) -> float:
    if not math.isfinite(d3d):
        return float("inf")
    return math.sqrt(max(d3d * d3d - height_diff_m * height_diff_m, 1e-6))


def is_aligned(grasp_x: float, target_x: float, tol_m: float = TOL_ALIGN_X_M) -> bool:
    if not (math.isfinite(grasp_x) and math.isfinite(target_x)):
        return False
    return abs(grasp_x - target_x) <= tol_m


def lift_success(z_gain_m: float, threshold_m: float = GRASP_SUCCESS_Z_GAIN_M) -> bool:
    return math.isfinite(z_gain_m) and z_gain_m >= threshold_m


# ── pure stats (analyzer / self-test) ─────────────────────────────────────────
def pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact_one_sided(a: int, b: int, c: int, d: int) -> float:
    """P(X >= a) for table [[a,b],[c,d]], one-sided closed>blind."""
    row1, col1, n = a + b, a + c, a + b + c + d
    if n == 0:
        return 1.0
    hi = min(row1, col1)
    denom = log_comb(n, col1)
    p = 0.0
    for x in range(a, hi + 1):
        p += math.exp(log_comb(row1, x) + log_comb(n - row1, col1 - x) - denom)
    return min(1.0, p)
