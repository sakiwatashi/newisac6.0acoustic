"""Episode-level evaluation of D4 Track B acoustic grasp PPO checkpoints.

Reports oracle success_true (true_range near + gripper closed), not only
iteration last-step snapshots from training logs.

Example:
  bash lab/run_d4_ppo_eval.sh \\
    --checkpoint runtime/outputs/v2_d4_ppo_grasp_rl_tune/rsl_rl_logs/model_99.pt \\
    --episodes 30
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
REPO = LAB_DIR.parent
for path in (str(LAB_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from isaaclab.app import AppLauncher

NEAR_TOL_M = 0.05
STANDOFF_DEFAULT = 0.35


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Eval D4-B acoustic grasp PPO (episode-level).")
    AppLauncher.add_app_launcher_args(parser)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="Path to model_*.pt",
    )
    parser.add_argument("--episodes", type=int, default=30, help="Number of eval episodes.")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="Max policy steps per episode (0 = use env max_episode_length).",
    )
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write eval_summary.json here (default: beside checkpoint).",
    )
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Sample actions (default: deterministic mean).",
    )
    parser.add_argument(
        "--acoustic-only-obs",
        action="store_true",
        help="Match 8-D acoustic-only policy (no true_range in obs).",
    )
    parser.add_argument(
        "--blind-acoustic",
        action="store_true",
        help="Zero acoustic obs channels (BLIND ablation control).",
    )
    parser.set_defaults(headless=True)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    p = path.expanduser()
    if p.is_file():
        return p.resolve()
    host = (REPO / p).resolve()
    if host.is_file():
        return host
    return p.resolve()


def _policy_obs(obs):
    if hasattr(obs, "get") and "policy" in obs.keys():
        return obs["policy"]
    if isinstance(obs, dict):
        return obs.get("policy", obs.get("actor", obs))
    return obs


def main() -> None:
    args = parse_args()
    ckpt = _resolve(args.checkpoint)
    if not ckpt.is_file():
        raise FileNotFoundError(f"checkpoint not found: {args.checkpoint} -> {ckpt}")

    out_dir = args.output_dir
    if out_dir is None:
        out_dir = ckpt.parent.parent if ckpt.parent.name == "rsl_rl_logs" else ckpt.parent
    out_dir = out_dir if out_dir.is_absolute() else (REPO / out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app
    from simulation_app_ref import set_simulation_app

    set_simulation_app(simulation_app)

    import importlib.metadata as metadata

    import gymnasium as gym
    import torch
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
    env_cfg.scene.num_envs = 1
    env_cfg.seed = int(args.seed)
    acoustic_only = bool(args.acoustic_only_obs)
    # Match train: scaffold (9-D + true_range) or acoustic-only policy (8-D)
    env_cfg.obs_include_true_range = not acoustic_only
    env_cfg.observation_space = 8 if acoustic_only else 9
    env_cfg.blind_acoustic = bool(args.blind_acoustic)

    agent_cfg = Ur10RtxAcousticGraspPPORunnerCfg()
    agent_cfg.seed = int(args.seed)
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, metadata.version("rsl-rl-lib"))

    env = gym.make("Isaac-Ur10RtxAcousticGrasp-Direct-v0", cfg=env_cfg)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    print(f"[INFO] Loading {ckpt}", flush=True)
    runner.load(str(ckpt))
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    unwrapped = env.unwrapped
    standoff = float(unwrapped.cfg.standoff_m)
    thr = standoff + NEAR_TOL_M
    max_ep_len = int(unwrapped.max_episode_length)
    max_steps = int(args.max_steps) if int(args.max_steps) > 0 else max_ep_len

    print(
        f"[INFO] episodes={args.episodes} max_steps={max_steps} thr={thr:.2f}m "
        f"stochastic={args.stochastic} seed={args.seed}",
        flush=True,
    )

    episode_rows: list[dict] = []
    obs = env.get_observations()

    for ep in range(int(args.episodes)):
        # After a terminal step, RslRl/DirectRL already resets and returns next obs.
        # Only force-reset when the previous episode hit max_steps without done.
        if ep > 0 and not episode_rows[-1].get("_ended_on_done", False):
            # Avoid InferenceMode: Direct env does inplace tensor writes on reset.
            with torch.inference_mode(False):
                if hasattr(env, "reset"):
                    reset_out = env.reset()
                    obs = reset_out[0] if isinstance(reset_out, tuple) else reset_out
            if hasattr(policy, "reset"):
                try:
                    policy.reset()
                except TypeError:
                    pass

        true_hist: list[float] = []
        dhat_hist: list[float] = []
        grip_hist: list[float] = []
        rew_sum = 0.0
        steps = 0
        ever_true_near = False
        ever_true_success = False
        min_true = float("inf")
        ended_on_done = False

        for _ in range(max_steps):
            # Policy under no_grad; env.step must NOT be under InferenceMode
            # (reset/inplace tensors on episode boundary).
            with torch.no_grad():
                if args.stochastic:
                    actions = policy(obs, stochastic_output=True)
                else:
                    actions = policy(obs)
            obs, rewards, dones, extras = env.step(actions)
            if hasattr(dones, "any") and dones.any() and hasattr(policy, "reset"):
                try:
                    policy.reset(dones)
                except TypeError:
                    policy.reset()

            rew_sum += float(rewards.mean().item())
            log = extras.get("log", {}) if isinstance(extras, dict) else {}
            true_r = float(log.get("Metrics/true_range_m", float("nan")))
            d_hat = float(log.get("Metrics/d_hat_xy", float("nan")))
            grip = float(log.get("Metrics/gripper_open", float("nan")))
            if math.isfinite(true_r):
                true_hist.append(true_r)
                min_true = min(min_true, true_r)
                if true_r <= thr:
                    ever_true_near = True
            if math.isfinite(d_hat):
                dhat_hist.append(d_hat)
            if math.isfinite(grip):
                grip_hist.append(grip)
            closed = math.isfinite(grip) and grip < 0.5
            if math.isfinite(true_r) and true_r <= thr and closed:
                ever_true_success = True

            steps += 1
            if hasattr(dones, "any") and bool(dones.any()):
                ended_on_done = True
                break

        final_true = true_hist[-1] if true_hist else float("nan")
        final_dhat = dhat_hist[-1] if dhat_hist else float("nan")
        final_grip = grip_hist[-1] if grip_hist else float("nan")
        final_closed = math.isfinite(final_grip) and final_grip < 0.5
        final_true_near = math.isfinite(final_true) and final_true <= thr
        final_true_success = final_true_near and final_closed
        final_dhat_success = (
            math.isfinite(final_dhat) and final_dhat <= thr and final_closed
        )

        row = {
            "episode": ep,
            "steps": steps,
            "return_sum": rew_sum,
            "final_true_range_m": final_true,
            "final_d_hat_m": final_dhat,
            "final_gripper_open": final_grip,
            "min_true_range_m": min_true if math.isfinite(min_true) else float("nan"),
            "ever_true_near": ever_true_near,
            "ever_true_success": ever_true_success,
            "final_true_near": final_true_near,
            "final_true_success": final_true_success,
            "final_dhat_success": final_dhat_success,
            "_ended_on_done": ended_on_done,
        }
        episode_rows.append(row)
        print(
            f"[EP {ep:02d}] steps={steps:2d} true_f={final_true:.3f} min_true={row['min_true_range_m']:.3f} "
            f"closed={int(final_closed)} true_succ={int(final_true_success)} "
            f"ever_near={int(ever_true_near)} ever_succ={int(ever_true_success)} ret={rew_sum:+.1f}",
            flush=True,
        )

    n = len(episode_rows)
    def rate(key: str) -> float:
        return sum(1 for r in episode_rows if r[key]) / n if n else 0.0

    finals = [r["final_true_range_m"] for r in episode_rows if math.isfinite(r["final_true_range_m"])]
    mins = [r["min_true_range_m"] for r in episode_rows if math.isfinite(r["min_true_range_m"])]
    rets = [r["return_sum"] for r in episode_rows]

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "checkpoint": str(ckpt),
        "n_episodes": n,
        "max_steps": max_steps,
        "seed": int(args.seed),
        "stochastic": bool(args.stochastic),
        "standoff_m": standoff,
        "near_threshold_m": thr,
        "obs_include_true_range": bool(env_cfg.obs_include_true_range),
        "acoustic_only_obs": acoustic_only,
        "blind_acoustic": bool(env_cfg.blind_acoustic),
        "claim_boundary": (
            "BLIND ablation: acoustic channels zeroed. Control for acoustic policy claim."
            if bool(env_cfg.blind_acoustic)
            else (
                "Acoustic-only policy obs (no true_range). Episode-level oracle success; "
                "train reward may use true scaffold; not friction grasp."
                if acoustic_only
                else (
                    "Scaffold policy (true_range in obs). Episode-level oracle success; "
                    "not friction grasp; not pure acoustic claim."
                )
            )
        ),
        "rate_final_true_near": rate("final_true_near"),
        "rate_final_true_success": rate("final_true_success"),
        "rate_final_dhat_success": rate("final_dhat_success"),
        "rate_ever_true_near": rate("ever_true_near"),
        "rate_ever_true_success": rate("ever_true_success"),
        "mean_final_true_range_m": sum(finals) / len(finals) if finals else float("nan"),
        "mean_min_true_range_m": sum(mins) / len(mins) if mins else float("nan"),
        "mean_return": sum(rets) / len(rets) if rets else float("nan"),
        "episodes": [{k: v for k, v in r.items() if not k.startswith("_")} for r in episode_rows],
    }

    out_path = out_dir / "eval_episode_summary.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n")

    print("\n=== EPISODE-LEVEL EVAL SUMMARY ===", flush=True)
    print(f"  n={n} checkpoint={ckpt.name}", flush=True)
    print(f"  final true near:     {100*summary['rate_final_true_near']:.1f}%", flush=True)
    print(f"  final true success:  {100*summary['rate_final_true_success']:.1f}%  << main", flush=True)
    print(f"  final dhat success:  {100*summary['rate_final_dhat_success']:.1f}%", flush=True)
    print(f"  ever true near:      {100*summary['rate_ever_true_near']:.1f}%", flush=True)
    print(f"  ever true success:   {100*summary['rate_ever_true_success']:.1f}%", flush=True)
    print(f"  mean final true:     {summary['mean_final_true_range_m']:.3f} m", flush=True)
    print(f"  mean min true:       {summary['mean_min_true_range_m']:.3f} m", flush=True)
    print(f"  mean return:         {summary['mean_return']:+.2f}", flush=True)
    print(f"  wrote {out_path}", flush=True)

    env.close()
    simulation_app.close()
    print("PASS: D4-B episode eval complete", flush=True)


if __name__ == "__main__":
    main()
