"""DirectRLEnv configuration for UR10 RTX acoustic distance estimation."""

from __future__ import annotations

from isaaclab.envs import DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import SimulationCfg
from isaaclab.utils.configclass import configclass

from geometry_passport_v1 import DEFAULT_MATERIAL_CONDITION, TICK_RATE_HZ


@configclass
class Ur10RtxAcousticDistanceEnvCfg(DirectRLEnvCfg):
    # env stepping: 4 physics substeps per policy step; 64 policy steps per episode
    decimation = 4
    episode_length_s = 1.28  # 32 * 0.01 * 4 (smoke-friendly)
    action_space = 1
    observation_space = 6
    state_space = 0
    is_finite_horizon = True
    wait_for_textures = False
    num_rerenders_on_reset = 0

    # simulation
    sim: SimulationCfg = SimulationCfg(dt=0.01, render_interval=4)

    # single-env RTX acoustic (GMO capture is slow)
    scene: InteractiveSceneCfg = InteractiveSceneCfg(
        num_envs=1,
        env_spacing=0.0,
        replicate_physics=False,
    )

    # trajectory
    period_steps: int = 64
    center_distance_m: float = 1.5
    amplitude_m: float = 0.5

    # RTX / scene
    material_condition: str = DEFAULT_MATERIAL_CONDITION
    tick_rate_hz: float = TICK_RATE_HZ
    target_settle_steps: int = 4
    substeps_per_capture: int = 2
    settle_steps: int = 16
    gmo_capture_interval: int = 2

    # action scaling: policy outputs in [-1, 1], mapped to distance bounds
    action_clip: float = 1.0

    # reward: r = -k_d*|pred-gt| - k_e*|pred-dist_energy| + k_t*move_align - k_v*(1-valid)
    rew_scale_distance: float = 1.0
    rew_scale_energy_align: float = 0.0
    rew_scale_tracking: float = 0.0
    rew_gmo_invalid_penalty: float = 0.0
    rew_alive_bonus: float = 0.0

    # energy prior: dist ≈ center + slope * (raw_E - ref) / scale  (Phase 4 r≈-0.77)
    energy_prior_ref: float = 4290.0
    energy_prior_scale: float = 50.0
    energy_prior_slope: float = -0.27

    # observation normalization (rough scales from Phase 4 smoke)
    energy_scale: float = 1.0e-4
    peak_scale: float = 1.0e-2


@configclass
class Ur10RtxAcousticDistanceEnvCfgV5(Ur10RtxAcousticDistanceEnvCfg):
    """v5: shaped reward encouraging acoustic-energy alignment and gt tracking."""

    rew_scale_distance: float = 1.0
    rew_scale_energy_align: float = 0.35
    rew_scale_tracking: float = 0.15
    rew_gmo_invalid_penalty: float = 0.25