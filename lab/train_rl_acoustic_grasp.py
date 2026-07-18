"""In-sim RSL-RL PPO for D4 Track B: acoustic approach + gripper (no object xyz).

Usage (via app/python or Lab launcher pattern matching distance train):
  ./isaaclab.sh -p lab/train_rl_acoustic_grasp.py --headless \\
      --max-iterations 5 --num-steps-per-env 16 \\
      --output-dir runtime/outputs/v2_d4_ppo_grasp_smoke

Or with Isaac Sim python after path setup — prefer shell wrapper:
  bash lab/run_d4_ppo_smoke.sh
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
REPO = LAB_DIR.parent
for path in (str(LAB_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from isaaclab.app import AppLauncher

DEFAULT_OUTPUT = REPO / "runtime/outputs/v2_d4_ppo_grasp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="D4 Track B: acoustic grasp PPO.")
    AppLauncher.add_app_launcher_args(parser)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--num-steps-per-env", type=int, default=None)
    parser.add_argument("--save-interval", type=int, default=None)
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=20260716)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Optional RSL-RL model_*.pt to resume (actor/critic/optimizer).",
    )
    parser.add_argument(
        "--resume-iteration",
        action="store_true",
        help="If set with --checkpoint, continue iteration counter from ckpt (default: restart at 0).",
    )
    parser.add_argument(
        "--blind-acoustic",
        action="store_true",
        help="Zero acoustic obs channels (ablation control policy).",
    )
    parser.add_argument(
        "--acoustic-only-obs",
        action="store_true",
        help=(
            "Policy obs without true_range (8-D). Reward may still use true_range "
            "scaffold. Cannot load 9-D scaffold checkpoints."
        ),
    )
    parser.add_argument(
        "--close-finetune",
        action="store_true",
        help=(
            "Boost near-close / hold-closed rewards and ease false-close penalty "
            "(for resume from an approach-only policy)."
        ),
    )
    parser.add_argument(
        "--no-true-reward",
        action="store_true",
        help=(
            "Pure acoustic REWARD: disable true_range in reward (d_hat progress/near only). "
            "Eval metrics still use oracle true success."
        ),
    )
    parser.set_defaults(headless=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app
    from simulation_app_ref import set_simulation_app

    set_simulation_app(simulation_app)

    import importlib.metadata as metadata

    import gymnasium as gym
    from rsl_rl.runners import OnPolicyRunner

    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg

    import isaaclab_tasks_ext  # noqa: F401
    from isaaclab_tasks_ext.ur10_rtx_acoustic_grasp.agents.rsl_rl_ppo_cfg import (
        Ur10RtxAcousticGraspPPORunnerCfg,
    )
    from isaaclab_tasks_ext.ur10_rtx_acoustic_grasp.ur10_rtx_acoustic_grasp_env_cfg import (
        Ur10RtxAcousticGraspEnvCfg,
    )

    env_cfg = Ur10RtxAcousticGraspEnvCfg()
    env_cfg.blind_acoustic = bool(args.blind_acoustic)
    # Acoustic-only policy obs: drop true_range channel (8-D). Reward still uses true.
    acoustic_only = bool(args.acoustic_only_obs)
    env_cfg.obs_include_true_range = not acoustic_only
    env_cfg.observation_space = 8 if acoustic_only else 9
    if acoustic_only:
        # Slightly trust acoustic d_hat more when true is not in obs.
        env_cfg.rew_approach = max(float(env_cfg.rew_approach), 0.35)
    close_ft = bool(args.close_finetune)
    if close_ft:
        # Approach policies often freeze open; amplify close timing credit.
        env_cfg.rew_close_near = 2.5
        env_cfg.rew_hold_closed = 3.0
        env_cfg.rew_open_when_near = 2.0
        env_cfg.rew_false_close = 0.25  # allow exploration of close earlier
        env_cfg.rew_progress = 1.0  # de-emphasize pure approach once near
        env_cfg.early_stop_on_success = True
    pure_reward = bool(args.no_true_reward)
    if pure_reward:
        # Step-③: no true in reward — only d_hat / peak-based shaping.
        env_cfg.reward_use_true_range = False
        env_cfg.rew_true_approach = 0.0
        env_cfg.rew_approach = max(float(env_cfg.rew_approach), 1.5)
        env_cfg.rew_progress = max(float(env_cfg.rew_progress), 2.0)
        env_cfg.rew_standoff_bonus = max(float(env_cfg.rew_standoff_bonus), 1.0)
        env_cfg.rew_close_near = max(float(env_cfg.rew_close_near), 2.0)
        env_cfg.rew_hold_closed = max(float(env_cfg.rew_hold_closed), 2.5)
        env_cfg.rew_open_when_near = max(float(env_cfg.rew_open_when_near), 1.5)
        env_cfg.rew_false_close = max(float(env_cfg.rew_false_close), 0.5)
        env_cfg.early_stop_on_success = True
        # Pure-reward claim pairs with acoustic-only obs by default.
        if not acoustic_only:
            env_cfg.obs_include_true_range = False
            env_cfg.observation_space = 8
            acoustic_only = True
    env_cfg.scene.num_envs = int(args.num_envs)
    agent_cfg = Ur10RtxAcousticGraspPPORunnerCfg()
    if args.max_iterations is not None:
        agent_cfg.max_iterations = int(args.max_iterations)
    if args.num_steps_per_env is not None:
        agent_cfg.num_steps_per_env = int(args.num_steps_per_env)
    if args.save_interval is not None:
        agent_cfg.save_interval = int(args.save_interval)
    if close_ft:
        # Slightly more exploration so close actions appear in rollouts.
        agent_cfg.algorithm.entropy_coef = max(float(agent_cfg.algorithm.entropy_coef), 0.02)
        if hasattr(agent_cfg.actor, "distribution_cfg") and agent_cfg.actor.distribution_cfg is not None:
            try:
                agent_cfg.actor.distribution_cfg.init_std = max(
                    float(agent_cfg.actor.distribution_cfg.init_std), 0.55
                )
            except Exception:
                pass
    agent_cfg.seed = int(args.seed)
    env_cfg.seed = agent_cfg.seed

    log_root = Path("logs") / "rsl_rl" / agent_cfg.experiment_name
    log_root = log_root.resolve()
    log_dir = log_root / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    env_cfg.log_dir = str(log_dir)
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, metadata.version("rsl-rl-lib"))

    resume_ckpt: Path | None = None
    if args.checkpoint is not None:
        resume_ckpt = args.checkpoint.expanduser()
        if not resume_ckpt.is_absolute():
            resume_ckpt = (REPO / resume_ckpt).resolve()
        if not resume_ckpt.is_file():
            raise FileNotFoundError(f"--checkpoint not found: {resume_ckpt}")

    if pure_reward:
        obs_policy = (
            "energy,peak,gmo_valid,d_hat,gripper,ee_x,prev_a "
            "— NO true_range in obs; pure acoustic REWARD (d_hat only)"
        )
        claim = (
            "Pure acoustic train: no true_range in obs or reward. Eval still reports "
            "oracle success_true. Not a friction grasp claim."
        )
    elif acoustic_only:
        obs_policy = (
            "energy,peak,gmo_valid,d_hat,gripper,ee_x,prev_a "
            "— NO true_range, NO target xyz (acoustic-only policy obs)"
        )
        claim = (
            "Acoustic-only policy obs (no true_range, no xyz). Train reward may still "
            "use true_range as scaffold. Eval: success_true_near_and_closed. "
            "Not a friction grasp claim."
        )
    else:
        obs_policy = (
            "energy,peak,gmo_valid,d_hat,gripper,ee_x,prev_a,[true_range scaffold] "
            "— NO target xyz"
        )
        claim = (
            "NO target xyz. true_range scalar may enter obs/reward as TRAIN SCAFFOLD "
            "only; acoustic-only claim requires obs_include_true_range=False + retrain. "
            "Eval metric: success_true_near_and_closed. Not a friction grasp claim."
        )

    run_meta = {
        "track": "D4_B_ppo",
        "task": "Isaac-Ur10RtxAcousticGrasp-Direct-v0",
        "blind_acoustic": bool(args.blind_acoustic),
        "acoustic_only_obs": acoustic_only,
        "close_finetune": close_ft,
        "no_true_reward": pure_reward,
        "reward_use_true_range": bool(getattr(env_cfg, "reward_use_true_range", True)),
        "obs_include_true_range": bool(env_cfg.obs_include_true_range),
        "observation_space": int(env_cfg.observation_space),
        "max_iterations": agent_cfg.max_iterations,
        "num_steps_per_env": agent_cfg.num_steps_per_env,
        "seed": agent_cfg.seed,
        "checkpoint": str(resume_ckpt) if resume_ckpt else None,
        "resume_iteration": bool(args.resume_iteration),
        "rew_close_near": float(env_cfg.rew_close_near),
        "rew_hold_closed": float(env_cfg.rew_hold_closed),
        "rew_open_when_near": float(env_cfg.rew_open_when_near),
        "rew_false_close": float(env_cfg.rew_false_close),
        "obs_policy": obs_policy,
        "action": "Δrange (via target move) + gripper open/close",
        "claim_boundary": claim,
    }
    with (args.output_dir / "train_meta.json").open("w") as f:
        json.dump(run_meta, f, indent=2)

    print(
        f"[INFO] D4-B train log={log_dir} iters={agent_cfg.max_iterations} "
        f"steps/env={agent_cfg.num_steps_per_env} blind={args.blind_acoustic}",
        flush=True,
    )
    if resume_ckpt is not None:
        print(f"[INFO] resume checkpoint={resume_ckpt} resume_iter={args.resume_iteration}", flush=True)
    print(f"[INFO] meta={run_meta}", flush=True)

    env = gym.make("Isaac-Ur10RtxAcousticGrasp-Direct-v0", cfg=env_cfg)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=str(log_dir), device=agent_cfg.device)

    if resume_ckpt is not None:
        # Default: load weights/optimizer but restart iteration counter (clean model_0..N names).
        load_cfg = {
            "actor": True,
            "critic": True,
            "optimizer": True,
            "iteration": bool(args.resume_iteration),
            "rnd": True,
        }
        runner.load(str(resume_ckpt), load_cfg=load_cfg)
        print(
            f"[INFO] Loaded ckpt; current_learning_iteration={runner.current_learning_iteration}",
            flush=True,
        )

    start = time.time()
    runner.learn(num_learning_iterations=agent_cfg.max_iterations, init_at_random_ep_len=True)
    elapsed = round(time.time() - start, 2)
    print(f"Training time: {elapsed} s", flush=True)
    env.close()

    import shutil

    if log_dir.exists():
        shutil.copytree(log_dir, args.output_dir / "rsl_rl_logs", dirs_exist_ok=True)
        print(f"[INFO] Synced logs to {args.output_dir / 'rsl_rl_logs'}", flush=True)

    summary = {
        **run_meta,
        "training_time_s": elapsed,
        "log_dir": str(log_dir),
        "output_dir": str(args.output_dir),
        "status": "PASS",
    }
    with (args.output_dir / "train_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print("PASS: D4 Track B acoustic grasp PPO complete", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    simulation_app.close()


if __name__ == "__main__":
    main()
