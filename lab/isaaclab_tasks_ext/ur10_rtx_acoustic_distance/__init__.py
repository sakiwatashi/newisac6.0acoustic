"""Register UR10 RTX acoustic distance DirectRLEnv with Gymnasium."""

import gymnasium as gym

from . import agents

gym.register(
    id="Isaac-Ur10RtxAcousticDistance-Direct-v0",
    entry_point=(
        "isaaclab_tasks_ext.ur10_rtx_acoustic_distance.ur10_rtx_acoustic_direct_env:Ur10RtxAcousticDirectEnv"
    ),
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": (
            "isaaclab_tasks_ext.ur10_rtx_acoustic_distance.ur10_rtx_acoustic_distance_env_cfg:"
            "Ur10RtxAcousticDistanceEnvCfg"
        ),
        "rsl_rl_cfg_entry_point": (
            f"{agents.__name__}.rsl_rl_ppo_cfg:Ur10RtxAcousticDistancePPORunnerCfg"
        ),
    },
)