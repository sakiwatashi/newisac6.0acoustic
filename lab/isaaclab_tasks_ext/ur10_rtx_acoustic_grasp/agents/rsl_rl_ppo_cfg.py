"""RSL-RL PPO config for D4 Track B approach + close timing.

Tuned for single-env GMO (slow rollouts): longer rollout, lower entropy,
slightly larger net so 9-D scaffold obs can learn approach from true_range.
"""

from isaaclab.utils.configclass import configclass

from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class Ur10RtxAcousticGraspPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    # 48 steps ≈ 1.92 s; enough for 0.95→0.35 m @ 4 cm/step with noise
    num_steps_per_env = 48
    max_iterations = 100
    save_interval = 25
    experiment_name = "ur10_rtx_acoustic_grasp_direct"
    empirical_normalization = True
    obs_groups = {"actor": ["policy"], "critic": ["policy"]}
    actor = RslRlMLPModelCfg(
        hidden_dims=[128, 128],
        activation="elu",
        obs_normalization=True,
        # lower init_std → less thrashing approach/retreat early
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=0.5),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[128, 128],
        activation="elu",
        obs_normalization=True,
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        # 0.05 was too high for 1-env; policy stayed random
        entropy_coef=0.01,
        num_learning_epochs=8,
        num_mini_batches=4,
        learning_rate=3.0e-4,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.02,
        max_grad_norm=1.0,
    )
