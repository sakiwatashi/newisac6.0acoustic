"""RSL-RL PPO configuration for UR10 RTX acoustic distance smoke."""

from isaaclab.utils.configclass import configclass

from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class Ur10RtxAcousticDistancePPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 32  # one full episode rollout per iteration
    max_iterations = 200
    save_interval = 50
    experiment_name = "ur10_rtx_acoustic_distance_direct"
    empirical_normalization = False
    obs_groups = {"actor": ["policy"], "critic": ["policy"]}
    actor = RslRlMLPModelCfg(
        hidden_dims=[64, 64],
        activation="elu",
        obs_normalization=False,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=0.8),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[64, 64],
        activation="elu",
        obs_normalization=False,
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.05,
        num_learning_epochs=4,
        num_mini_batches=2,
        learning_rate=2.0e-4,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.03,
        max_grad_norm=1.0,
    )


@configclass
class Ur10RtxAcousticDistancePPORunnerCfgV4(Ur10RtxAcousticDistancePPORunnerCfg):
    """v4: empirical + per-network obs normalization for weak acoustic signal."""

    empirical_normalization = True
    actor = RslRlMLPModelCfg(
        hidden_dims=[64, 64],
        activation="elu",
        obs_normalization=True,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=0.8),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[64, 64],
        activation="elu",
        obs_normalization=True,
    )


@configclass
class Ur10RtxAcousticDistancePPORunnerCfgV5(Ur10RtxAcousticDistancePPORunnerCfgV4):
    """v5: shaped reward + longer training + higher entropy."""

    max_iterations = 500
    save_interval = 100
    actor = RslRlMLPModelCfg(
        hidden_dims=[64, 64],
        activation="elu",
        obs_normalization=True,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.08,
        num_learning_epochs=4,
        num_mini_batches=2,
        learning_rate=2.0e-4,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.03,
        max_grad_norm=1.0,
    )