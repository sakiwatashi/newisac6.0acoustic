"""DirectRLEnv config: acoustic obs + approach/gripper actions (D4 Track B).

Observation MUST NOT include object xyz (D4-5). Enforced in env + unit tests.
"""
from __future__ import annotations

from isaaclab.envs import DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import SimulationCfg
from isaaclab.utils.configclass import configclass

from geometry_passport_v1 import DEFAULT_MATERIAL_CONDITION, TICK_RATE_HZ


@configclass
class Ur10RtxAcousticGraspEnvCfg(DirectRLEnvCfg):
    """Phase-1 grasp env: 1-DOF corridor approach + gripper open/close.

    action[0] = forward speed in [-1,1] mapped to Δx step
    action[1] = gripper cmd in [-1,1] (negative → close)

    obs (8,):
      0 energy_scaled
      1 peak_scaled
      2 gmo_valid
      3 d_hat_xy_scaled (from peak+calib if available, else 0)
      4 gripper_open (1 open, 0 closed proxy)
      5 ee_x_scaled (proprio only — NOT target)
      6 prev_action_0
      7 prev_action_1
    """

    decimation = 4
    # 48 policy steps @ dt=0.01 * decimation=4 → 1.92 s; match PPO num_steps_per_env
    episode_length_s = 1.92
    action_space = 2
    # 8 acoustic/proprio + optional true_range scaffold (see obs_include_true_range)
    observation_space = 9
    state_space = 0
    is_finite_horizon = True
    wait_for_textures = False
    num_rerenders_on_reset = 0

    sim: SimulationCfg = SimulationCfg(dt=0.01, render_interval=4)
    scene: InteractiveSceneCfg = InteractiveSceneCfg(
        num_envs=1,
        env_spacing=0.0,
        replicate_physics=False,
    )

    material_condition: str = DEFAULT_MATERIAL_CONDITION
    tick_rate_hz: float = TICK_RATE_HZ
    settle_steps: int = 16
    substeps_per_capture: int = 2
    # Capture every policy step after approach move (GMO is the acoustic channel)
    gmo_capture_interval: int = 1
    # 2 frames: faster RL iterations; peak still multi-frame averaged
    gmo_avg_frames: int = 2
    target_settle_steps: int = 3

    # geometry / task — action[0] moves sensor-to-target distance (NOT oracle in obs)
    # standoff must be strictly inside [range_min, range_max] so true_near is reachable.
    standoff_m: float = 0.35
    max_forward_step_m: float = 0.05  # |action[0]|=1 → ±5 cm (faster approach)
    range_min_m: float = 0.30
    range_max_m: float = 1.05
    reset_range_min_m: float = 0.55
    reset_range_max_m: float = 0.95
    # Fixed-TCP boresight scene: target coplanar with sensor → h≈0 (not D3 desk 0.19–0.20).
    height_diff_m: float = 0.0
    # calib path relative to repo (loaded at runtime if present)
    bar_calib_json: str = "runtime/outputs/v2_d3_gates/bar_calibration.json"

    energy_scale: float = 1.0e-4
    # peak channel is ToF sample index (~20–70 over corridor), not amplitude
    peak_scale: float = 1.0e-2
    d_hat_scale: float = 1.0  # meters already small

    # rewards — true_* terms are TRAIN SCAFFOLD (obs may include true_range scalar)
    rew_approach: float = 0.1          # weak acoustic aux (d_hat noisy)
    rew_true_approach: float = 1.5     # main: |true - standoff|
    rew_progress: float = 2.0          # bonus per meter true_range decreased
    rew_standoff_bonus: float = 1.0    # bonus when true near
    rew_close_near: float = 1.2        # close command when true near
    rew_hold_closed: float = 1.5       # per-step keep closed at standoff
    rew_open_when_near: float = 0.8    # per-step penalty if near but open
    rew_false_close: float = 0.8       # penalize close when true still far
    rew_alive: float = 0.01
    rew_gmo_invalid: float = 0.05
    rew_action_l2: float = 0.002
    # End episode when true near + closed (aligns train with final success)
    early_stop_on_success: bool = True

    # blind ablation: zero acoustic channels in obs
    blind_acoustic: bool = False
    # Train scaffold: append true_range (m) as last obs dim for credit assignment.
    # Does NOT add target xyz. Set False for acoustic-only policy experiments.
    obs_include_true_range: bool = True
    # Train scaffold in REWARD (true approach/progress/false_close). Set False for
    # pure acoustic reward experiments (d_hat only). Eval metrics still log true success.
    reward_use_true_range: bool = True


# Forbidden observation name fragments (static contract for tests / reviewers)
FORBIDDEN_OBS_KEYS = (
    "target_x",
    "target_y",
    "target_z",
    "object_position",
    "object_pose",
    "bar_x",
    "oracle",
)
