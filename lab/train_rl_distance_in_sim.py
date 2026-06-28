"""In-sim RSL-RL PPO training for UR10 RTX acoustic distance (standalone entry)."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
for path in (str(LAB_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from isaaclab.app import AppLauncher

DEFAULT_OUTPUT = LAB_DIR.parent / "runtime/outputs/lab_rl_distance_in_sim_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="In-sim RSL-RL distance smoke.")
    AppLauncher.add_app_launcher_args(parser)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--num-steps-per-env", type=int, default=None)
    parser.add_argument("--save-interval", type=int, default=None)
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--ppo-variant",
        choices=("v3", "v4", "v5"),
        default="v3",
        help="v3=baseline; v4=obs norm; v5=shaped-reward long-run defaults.",
    )
    parser.add_argument(
        "--env-variant",
        choices=("v3", "v5"),
        default="v3",
        help="v3=plain -|pred-gt|; v5=energy-align + tracking shaped reward.",
    )
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
    from isaaclab_tasks_ext.ur10_rtx_acoustic_distance.agents.rsl_rl_ppo_cfg import (
        Ur10RtxAcousticDistancePPORunnerCfg,
        Ur10RtxAcousticDistancePPORunnerCfgV4,
        Ur10RtxAcousticDistancePPORunnerCfgV5,
    )
    from isaaclab_tasks_ext.ur10_rtx_acoustic_distance.ur10_rtx_acoustic_distance_env_cfg import (
        Ur10RtxAcousticDistanceEnvCfg,
        Ur10RtxAcousticDistanceEnvCfgV5,
    )

    env_cfg = (
        Ur10RtxAcousticDistanceEnvCfgV5()
        if args.env_variant == "v5"
        else Ur10RtxAcousticDistanceEnvCfg()
    )
    if args.ppo_variant == "v5":
        agent_cfg = Ur10RtxAcousticDistancePPORunnerCfgV5()
    elif args.ppo_variant == "v4":
        agent_cfg = Ur10RtxAcousticDistancePPORunnerCfgV4()
    else:
        agent_cfg = Ur10RtxAcousticDistancePPORunnerCfg()
    env_cfg.scene.num_envs = int(args.num_envs)
    if args.max_iterations is not None:
        agent_cfg.max_iterations = int(args.max_iterations)
    if args.num_steps_per_env is not None:
        agent_cfg.num_steps_per_env = int(args.num_steps_per_env)
    if args.save_interval is not None:
        agent_cfg.save_interval = int(args.save_interval)
    agent_cfg.seed = int(args.seed)
    env_cfg.seed = agent_cfg.seed

    log_root = Path("logs") / "rsl_rl" / agent_cfg.experiment_name
    log_root = log_root.resolve()
    log_dir = log_root / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    env_cfg.log_dir = str(log_dir)
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, metadata.version("rsl-rl-lib"))

    print(
        f"[INFO] Training log: {log_dir} "
        f"(env={args.env_variant}, ppo={args.ppo_variant}, "
        f"iters={agent_cfg.max_iterations}, steps_per_env={agent_cfg.num_steps_per_env}, "
        f"save_interval={agent_cfg.save_interval})",
        flush=True,
    )

    env = gym.make("Isaac-Ur10RtxAcousticDistance-Direct-v0", cfg=env_cfg)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=str(log_dir), device=agent_cfg.device)

    start = time.time()
    runner.learn(num_learning_iterations=agent_cfg.max_iterations, init_at_random_ep_len=True)
    print(f"Training time: {round(time.time() - start, 2)} s", flush=True)
    env.close()

    import shutil

    if log_dir.exists():
        shutil.copytree(log_dir, args.output_dir, dirs_exist_ok=True)
        print(f"[INFO] Synced logs to {args.output_dir}", flush=True)

    print("PASS: in-sim RSL-RL smoke complete", flush=True)
    simulation_app.close()


if __name__ == "__main__":
    main()