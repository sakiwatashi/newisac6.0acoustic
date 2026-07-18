"""Register UR10 RTX acoustic grasp DirectRLEnv (D4 Track B)."""

import gymnasium as gym

from . import agents

gym.register(
    id="Isaac-Ur10RtxAcousticGrasp-Direct-v0",
    entry_point=(
        "isaaclab_tasks_ext.ur10_rtx_acoustic_grasp.ur10_rtx_acoustic_grasp_env:"
        "Ur10RtxAcousticGraspDirectEnv"
    ),
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": (
            "isaaclab_tasks_ext.ur10_rtx_acoustic_grasp.ur10_rtx_acoustic_grasp_env_cfg:"
            "Ur10RtxAcousticGraspEnvCfg"
        ),
        "rsl_rl_cfg_entry_point": (
            f"{agents.__name__}.rsl_rl_ppo_cfg:Ur10RtxAcousticGraspPPORunnerCfg"
        ),
    },
)
