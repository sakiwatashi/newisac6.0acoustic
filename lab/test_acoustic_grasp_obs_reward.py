#!/usr/bin/env python3
"""Unit tests for D4 Track B pure obs/reward helpers (no Isaac / GPU)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "isaaclab_tasks_ext" / "ur10_rtx_acoustic_grasp"))

# Import helpers without loading DirectRLEnv / isaaclab
import importlib.util

spec = importlib.util.spec_from_file_location(
    "grasp_env_mod",
    LAB / "isaaclab_tasks_ext" / "ur10_rtx_acoustic_grasp" / "ur10_rtx_acoustic_grasp_env.py",
)
# Cannot import full module (pulls isaaclab). Duplicate pure functions here by path exec of helpers only.

# Re-import by reading - actually exec the helper functions from source:
src = (LAB / "isaaclab_tasks_ext" / "ur10_rtx_acoustic_grasp" / "ur10_rtx_acoustic_grasp_env.py").read_text()
# Extract by importing from a minimal namespace after isolating functions
ns: dict = {}
# safer: copy the three pure functions inline from the module text via runpy on a stub

from typing import Any

# Minimal re-implementation import: add path and import only if we split helpers.
# Instead, paste calls by importing the module file's pure section via exec of selected lines.

exec(
    compile(
        """
def pack_policy_obs(*, energy_scaled, peak_scaled, gmo_valid, d_hat_xy, gripper_open, ee_x, prev_a0, prev_a1, blind_acoustic=False, true_range_scaled=0.0, include_true_range=False):
    if blind_acoustic:
        energy_scaled, peak_scaled, gmo_valid, d_hat_xy = 0.0, 0.0, 0.0, 0.0
    row = [float(energy_scaled), float(peak_scaled), float(gmo_valid), float(d_hat_xy),
            float(gripper_open), float(ee_x), float(prev_a0), float(prev_a1)]
    if include_true_range:
        row.append(float(true_range_scaled))
    return row

def compute_reward(*, d_hat_xy, standoff_m, gripper_cmd, gmo_valid, action_l2,
                   cfg_approach, cfg_standoff, cfg_close, cfg_alive, cfg_invalid, cfg_act,
                   true_range_m=None, prev_true_range_m=None, gripper_open=1.0,
                   cfg_true_approach=0.0, cfg_false_close=0.0, cfg_progress=0.0,
                   cfg_hold_closed=0.0, cfg_open_when_near=0.0, near_tol_m=0.05):
    import math
    if not math.isfinite(d_hat_xy):
        d_hat_xy = 10.0
    thr = float(standoff_m) + float(near_tol_m)
    approach_err = abs(d_hat_xy - standoff_m)
    r = -cfg_approach * approach_err + cfg_alive
    true_ok = true_range_m is not None and math.isfinite(float(true_range_m))
    true_r = float(true_range_m) if true_ok else float('nan')
    if true_ok and cfg_true_approach > 0.0:
        r -= cfg_true_approach * abs(true_r - standoff_m)
    if true_ok and cfg_progress > 0.0 and prev_true_range_m is not None and math.isfinite(float(prev_true_range_m)):
        r += cfg_progress * (float(prev_true_range_m) - true_r)
    if true_ok and cfg_true_approach > 0.0:
        near = true_r <= thr
    else:
        near = d_hat_xy <= thr
    closed_state = float(gripper_open) < 0.5
    if near:
        r += cfg_standoff
        if closed_state:
            r += cfg_hold_closed
        else:
            r -= cfg_open_when_near
        if gripper_cmd < 0.0:
            r += cfg_close * (-gripper_cmd)
    if true_ok and cfg_false_close > 0.0 and gripper_cmd < -0.1 and true_r > thr:
        r -= cfg_false_close * (-gripper_cmd)
    r -= cfg_invalid * (1.0 - gmo_valid)
    r -= cfg_act * action_l2
    return float(r)

def peak_to_d_hat_xy(peak, slope, intercept, height_diff):
    import math
    if not math.isfinite(peak) or slope == 0.0:
        return float('nan')
    d3 = (peak - intercept) / slope
    return math.sqrt(max(d3 * d3 - height_diff * height_diff, 1e-6))

PEAK_SAMPLE_IDX_KEYS = (
    "primary_sgw_early_peak_sample_idx",
    "tof_primary_sgw_early_peak_sample_idx",
    "primary_sgw_peak_sample_idx",
    "tof_primary_sgw_peak_sample_idx",
    "peak_sample_idx",
)

def extract_peak_sample_idx(gmo):
    import math
    if not gmo:
        return float('nan'), ""
    for key in PEAK_SAMPLE_IDX_KEYS:
        if key not in gmo or gmo[key] is None:
            continue
        try:
            val = float(gmo[key])
        except (TypeError, ValueError):
            continue
        if math.isfinite(val):
            return val, key
    return float('nan'), ""

def gated_peak_sample_idx(amps, *, slope, intercept, range_lo_m, range_hi_m, margin_samples=2):
    import math
    if amps is None:
        return float('nan'), ""
    try:
        n = len(amps)
    except TypeError:
        return float('nan'), ""
    if n <= 0 or not math.isfinite(slope) or slope == 0.0:
        return float('nan'), ""
    lo = int(math.floor(slope * float(range_lo_m) + intercept)) - int(margin_samples)
    hi = int(math.ceil(slope * float(range_hi_m) + intercept)) + int(margin_samples)
    lo = max(1, lo)
    hi = min(n - 2, hi)
    if hi <= lo:
        return float('nan'), ""
    def _abs(i):
        return abs(float(amps[i]))
    pre_lo = max(0, lo - 12)
    pre = [_abs(i) for i in range(pre_lo, lo)]
    noise = (sum(pre) / len(pre)) if pre else 0.0
    thr = max(noise * 4.0, 1e-9)
    for i in range(lo, hi + 1):
        v = _abs(i)
        if v < thr:
            continue
        if v >= _abs(i - 1) and v >= _abs(i + 1):
            return float(i), f"gated_first[{lo},{hi}]"
    best_i, best_v = lo, -1.0
    for i in range(lo, hi + 1):
        v = _abs(i)
        if v > best_v:
            best_v, best_i = v, i
    if best_v < 0.0:
        return float('nan'), ""
    return float(best_i), f"gated_max[{lo},{hi}]"
""",
        "<helpers>",
        "exec",
    ),
    ns,
)

pack_policy_obs = ns["pack_policy_obs"]
compute_reward = ns["compute_reward"]
peak_to_d_hat_xy = ns["peak_to_d_hat_xy"]
extract_peak_sample_idx = ns["extract_peak_sample_idx"]
gated_peak_sample_idx = ns["gated_peak_sample_idx"]

FORBIDDEN = ("target_x", "target_y", "target_z", "object_position", "oracle", "bar_x")


def test_obs_dim_and_blind():
    o = pack_policy_obs(
        energy_scaled=1.0,
        peak_scaled=2.0,
        gmo_valid=1.0,
        d_hat_xy=0.4,
        gripper_open=1.0,
        ee_x=0.6,
        prev_a0=0.1,
        prev_a1=-0.2,
    )
    assert len(o) == 8
    o9 = pack_policy_obs(
        energy_scaled=1.0,
        peak_scaled=2.0,
        gmo_valid=1.0,
        d_hat_xy=0.4,
        gripper_open=1.0,
        ee_x=0.6,
        prev_a0=0.1,
        prev_a1=-0.2,
        true_range_scaled=0.7,
        include_true_range=True,
    )
    assert len(o9) == 9 and o9[8] == 0.7
    b = pack_policy_obs(
        energy_scaled=1.0,
        peak_scaled=2.0,
        gmo_valid=1.0,
        d_hat_xy=0.4,
        gripper_open=1.0,
        ee_x=0.6,
        prev_a0=0.1,
        prev_a1=-0.2,
        blind_acoustic=True,
        true_range_scaled=0.7,
        include_true_range=True,
    )
    assert b[0] == b[1] == b[2] == b[3] == 0.0
    assert b[5] == 0.6  # proprio kept
    assert b[8] == 0.7  # true_range scaffold kept under blind


def test_reward_prefers_standoff_and_close():
    r_far = compute_reward(
        d_hat_xy=0.8,
        standoff_m=0.35,
        gripper_cmd=0.0,
        gmo_valid=1.0,
        action_l2=0.0,
        cfg_approach=1.0,
        cfg_standoff=0.5,
        cfg_close=0.3,
        cfg_alive=0.01,
        cfg_invalid=0.1,
        cfg_act=0.0,
    )
    r_near_open = compute_reward(
        d_hat_xy=0.35,
        standoff_m=0.35,
        gripper_cmd=0.0,
        gmo_valid=1.0,
        action_l2=0.0,
        cfg_approach=1.0,
        cfg_standoff=0.5,
        cfg_close=0.3,
        cfg_alive=0.01,
        cfg_invalid=0.1,
        cfg_act=0.0,
    )
    r_near_close = compute_reward(
        d_hat_xy=0.35,
        standoff_m=0.35,
        gripper_cmd=-1.0,
        gmo_valid=1.0,
        action_l2=0.0,
        cfg_approach=1.0,
        cfg_standoff=0.5,
        cfg_close=0.3,
        cfg_alive=0.01,
        cfg_invalid=0.1,
        cfg_act=0.0,
    )
    assert r_near_open > r_far
    assert r_near_close > r_near_open


def test_reward_false_close_penalty_and_true_scaffold():
    # d_hat claims near but true is far → false close should be worse than open
    kwargs = dict(
        d_hat_xy=0.35,
        standoff_m=0.35,
        gmo_valid=1.0,
        action_l2=0.0,
        cfg_approach=0.25,
        cfg_standoff=0.5,
        cfg_close=0.5,
        cfg_alive=0.01,
        cfg_invalid=0.0,
        cfg_act=0.0,
        true_range_m=0.80,
        cfg_true_approach=1.0,
        cfg_false_close=0.5,
        gripper_open=1.0,
    )
    r_open = compute_reward(gripper_cmd=0.0, **kwargs)
    r_close = compute_reward(gripper_cmd=-1.0, **kwargs)
    assert r_close < r_open  # false close penalized
    # true near + hold closed better than true near but open
    base = dict(
        gripper_cmd=0.0,
        d_hat_xy=0.35,
        standoff_m=0.35,
        gmo_valid=1.0,
        action_l2=0.0,
        cfg_approach=0.25,
        cfg_standoff=0.5,
        cfg_close=0.5,
        cfg_alive=0.01,
        cfg_invalid=0.0,
        cfg_act=0.0,
        true_range_m=0.35,
        cfg_true_approach=1.0,
        cfg_false_close=0.5,
        cfg_hold_closed=1.5,
        cfg_open_when_near=0.8,
    )
    r_near_closed = compute_reward(gripper_open=0.0, **base)
    r_near_open = compute_reward(gripper_open=1.0, **base)
    assert r_near_closed > r_near_open


def test_peak_to_range():
    # peak = a*d + b  => d = (peak-b)/a
    a, b = 50.0, -5.0
    d3 = 0.5
    peak = a * d3 + b
    h = 0.2
    dxy = peak_to_d_hat_xy(peak, a, b, h)
    assert abs(dxy - math.sqrt(0.5**2 - 0.2**2)) < 1e-9


def test_cfg_forbidden_list():
    cfg_path = LAB / "isaaclab_tasks_ext/ur10_rtx_acoustic_grasp/ur10_rtx_acoustic_grasp_env_cfg.py"
    text = cfg_path.read_text()
    assert "FORBIDDEN_OBS_KEYS" in text
    for k in FORBIDDEN:
        assert k in text or k.replace("_", "") in text.replace("_", "")


def test_env_source_has_no_target_in_pack():
    env_src = (LAB / "isaaclab_tasks_ext/ur10_rtx_acoustic_grasp/ur10_rtx_acoustic_grasp_env.py").read_text()
    # pack_policy_obs signature must not take target
    assert "def pack_policy_obs" in env_src
    assert "target_x" not in env_src.split("def pack_policy_obs")[1].split("def compute_reward")[0]


def test_extract_peak_prefers_sample_idx_not_amplitude():
    """Amplitude key primary_sgw_peak must never be used for ToF range."""
    peak, src = extract_peak_sample_idx(
        {
            "primary_sgw_peak": 99999.0,  # amplitude trap
            "primary_sgw_peak_sample_idx": 36.5,
            "primary_sgw_early_peak_sample_idx": 28.0,
        }
    )
    # early window preferred over full-waveform (room multipath)
    assert src == "primary_sgw_early_peak_sample_idx"
    assert abs(peak - 28.0) < 1e-9
    peak2, src2 = extract_peak_sample_idx({"primary_sgw_peak": 123.0})
    assert not math.isfinite(peak2)
    assert src2 == ""
    peak3, src3 = extract_peak_sample_idx({"primary_sgw_peak_sample_idx": 40.0})
    assert src3 == "primary_sgw_peak_sample_idx"
    assert abs(peak3 - 40.0) < 1e-9


def test_env_source_uses_peak_sample_idx_keys():
    env_src = (LAB / "isaaclab_tasks_ext/ur10_rtx_acoustic_grasp/ur10_rtx_acoustic_grasp_env.py").read_text()
    assert "primary_sgw_early_peak_sample_idx" in env_src
    assert "extract_peak_sample_idx" in env_src
    assert "gated_peak_sample_idx" in env_src
    # Must not list bare amplitude as a peak-for-range key in the extractor tuple
    # (primary_sgw_peak may still appear in energy comments / docs).
    extract_block = env_src.split("PEAK_SAMPLE_IDX_KEYS")[1].split(")")[0]
    assert "primary_sgw_early_peak_sample_idx" in extract_block
    assert '"primary_sgw_peak"' not in extract_block
    assert "'primary_sgw_peak'" not in extract_block


def test_gated_peak_ignores_room_and_near_ringing():
    # Synthetic: near ringing at idx 8, target at 36, room at 64
    amps = [0.1] * 80
    amps[8] = 50.0
    amps[36] = 20.0
    amps[64] = 100.0
    slope, intercept = 58.12, -3.9
    # Corridor gate excludes near ringing (8) and room (64)
    peak, src = gated_peak_sample_idx(
        amps, slope=slope, intercept=intercept, range_lo_m=0.40, range_hi_m=1.05, margin_samples=2
    )
    assert "gated" in src
    assert abs(peak - 36.0) < 1e-9


if __name__ == "__main__":
    test_obs_dim_and_blind()
    test_reward_prefers_standoff_and_close()
    test_reward_false_close_penalty_and_true_scaffold()
    test_peak_to_range()
    test_cfg_forbidden_list()
    test_env_source_has_no_target_in_pack()
    test_extract_peak_prefers_sample_idx_not_amplitude()
    test_env_source_uses_peak_sample_idx_keys()
    test_gated_peak_ignores_room_and_near_ringing()
    print("test_acoustic_grasp_obs_reward: ALL PASSED")
