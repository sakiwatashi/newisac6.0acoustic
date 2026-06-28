"""Play a trained in-sim RSL-RL checkpoint with optional GUI viewport."""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
for path in (str(LAB_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from isaaclab.app import AppLauncher

DEFAULT_OUTPUT = LAB_DIR.parent / "runtime/outputs/lab_rl_distance_in_sim_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play in-sim RSL-RL distance checkpoint.")
    AppLauncher.add_app_launcher_args(parser)
    parser.add_argument("--checkpoint", type=Path, required=True, help="Path to model_*.pt checkpoint.")
    parser.add_argument("--steps", type=int, default=128, help="Policy steps to run (0 = until closed).")
    parser.add_argument("--real-time", action="store_true", help="Sleep to approximate real-time stepping.")
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Sample actions from the policy distribution instead of deterministic mean.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--ppo-variant",
        choices=("auto", "v3", "v4", "v5"),
        default="auto",
        help="Match checkpoint architecture (auto detects obs_normalizer).",
    )
    return parser.parse_args()


def _resolve_checkpoint(path: Path) -> Path:
    candidate = path.expanduser()
    if candidate.is_file():
        return candidate.resolve()
    host_relative = (LAB_DIR.parent / candidate).resolve()
    if host_relative.is_file():
        return host_relative
    return candidate.resolve()


def pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return math.nan
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return math.nan
    return num / (den_x * den_y)


def _policy_obs_tensor(obs):
    if hasattr(obs, "get"):
        if "policy" in obs.keys():
            return obs["policy"]
        if "actor" in obs.keys():
            return obs["actor"]
    if isinstance(obs, dict):
        return obs.get("policy", obs.get("actor", obs))
    return obs


def _acoustic_obs_summary(obs_tensor) -> tuple[float, float, float]:
    tensor = obs_tensor
    if hasattr(tensor, "detach"):
        tensor = tensor.detach()
    if hasattr(tensor, "cpu"):
        tensor = tensor.cpu()
    if hasattr(tensor, "squeeze"):
        flat = tensor.squeeze()
    else:
        flat = tensor
    return float(flat[0]), float(flat[1]), float(flat[2])


def _print_correlation_summary(
    *,
    checkpoint: Path,
    stochastic: bool,
    gt: list[float],
    pred: list[float],
    raw_energy: list[float],
    raw_peak: list[float],
    scaled_energy: list[float],
    scaled_peak: list[float],
) -> None:
    n = len(gt)
    if n == 0:
        print("[SUMMARY] No steps recorded.", flush=True)
        return

    mae = sum(abs(p - g) for p, g in zip(pred, gt)) / n
    print(
        f"\n[SUMMARY] checkpoint={checkpoint.name} mode={'stochastic' if stochastic else 'deterministic'} n={n}",
        flush=True,
    )
    print(f"  pred: mean={sum(pred)/n:.3f}m std={math.sqrt(sum((p-sum(pred)/n)**2 for p in pred)/max(1,n-1)):.4f}m", flush=True)
    print(f"  gt:   mean={sum(gt)/n:.3f}m std={math.sqrt(sum((g-sum(gt)/n)**2 for g in gt)/max(1,n-1)):.4f}m", flush=True)
    print(f"  MAE(pred, gt)={mae:.4f}m", flush=True)
    print(f"  pearson(gt, pred)={pearson_r(gt, pred):.4f}", flush=True)
    print(f"  pearson(gt, raw_E)={pearson_r(gt, raw_energy):.4f}", flush=True)
    print(f"  pearson(gt, raw_P)={pearson_r(gt, raw_peak):.4f}", flush=True)
    print(f"  pearson(gt, scaled_E)={pearson_r(gt, scaled_energy):.4f}", flush=True)
    print(f"  pearson(gt, scaled_P)={pearson_r(gt, scaled_peak):.4f}", flush=True)
    if raw_energy:
        e_mean = sum(raw_energy) / n
        e_range = max(raw_energy) - min(raw_energy)
        p_mean = sum(raw_peak) / n
        p_range = max(raw_peak) - min(raw_peak)
        gt_range = max(gt) - min(gt)
        print(
            f"  raw_E: mean={e_mean:.1f} range={e_range:.1f} ({100*e_range/max(e_mean,1e-9):.2f}% of mean)",
            flush=True,
        )
        print(
            f"  raw_P: mean={p_mean:.2f} range={p_range:.2f} ({100*p_range/max(p_mean,1e-9):.2f}% of mean)",
            flush=True,
        )
        print(f"  gt range={gt_range:.3f}m ({100*gt_range/max(sum(gt)/n,1e-9):.1f}% of mean)", flush=True)


def main() -> None:
    args = parse_args()
    checkpoint = _resolve_checkpoint(args.checkpoint)
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint} (resolved: {checkpoint})")
    args.checkpoint = checkpoint

    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app
    from simulation_app_ref import set_simulation_app

    set_simulation_app(simulation_app)

    import importlib.metadata as metadata

    import gymnasium as gym
    import torch

    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

    import isaaclab_tasks_ext  # noqa: F401
    from isaaclab_tasks_ext.ur10_rtx_acoustic_distance.ur10_rtx_acoustic_distance_env_cfg import (
        Ur10RtxAcousticDistanceEnvCfg,
    )
    from rl_checkpoint_utils import build_on_policy_runner, make_ppo_runner_cfg, resolve_ppo_variant

    variant = resolve_ppo_variant(args.checkpoint, requested=args.ppo_variant)
    agent_cfg = make_ppo_runner_cfg(variant)
    print(f"[INFO] PPO variant={variant}", flush=True)

    env_cfg = Ur10RtxAcousticDistanceEnvCfg()
    env_cfg.seed = int(args.seed)

    env = gym.make("Isaac-Ur10RtxAcousticDistance-Direct-v0", cfg=env_cfg)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    runner, _ = build_on_policy_runner(
        env, variant, seed=int(args.seed), rsl_rl_version=metadata.version("rsl-rl-lib")
    )
    print(f"[INFO] Loading checkpoint: {args.checkpoint}", flush=True)
    runner.load(str(args.checkpoint))

    policy = runner.get_inference_policy(device=env.unwrapped.device)
    dt = env.unwrapped.step_dt
    obs = env.get_observations()

    print(
        f"[INFO] Playing {args.steps or 'until window closed'} steps "
        f"(dt={dt:.3f}s, real_time={args.real_time}, stochastic={args.stochastic})",
        flush=True,
    )

    gt_hist: list[float] = []
    pred_hist: list[float] = []
    raw_e_hist: list[float] = []
    raw_p_hist: list[float] = []
    scaled_e_hist: list[float] = []
    scaled_p_hist: list[float] = []

    step = 0
    try:
        while args.steps <= 0 or step < int(args.steps):
            if not simulation_app.is_running():
                break
            start = time.time()
            with torch.inference_mode():
                if args.stochastic:
                    actions = policy(obs, stochastic_output=True)
                else:
                    actions = policy(obs)
                obs, rewards, dones, extras = env.step(actions)
                if dones.any():
                    policy.reset(dones)

            reward = float(rewards.mean().item())
            log = extras.get("log", {}) if isinstance(extras, dict) else {}
            gt = float(log.get("Metrics/gt_distance_m", float("nan")))
            pred = float(log.get("Metrics/pred_distance_m", float("nan")))
            raw_e = float(log.get("Metrics/raw_early_energy", float("nan")))
            raw_p = float(log.get("Metrics/raw_peak", float("nan")))
            scaled_e, scaled_p, gmo_valid = _acoustic_obs_summary(_policy_obs_tensor(obs))

            if math.isfinite(gt):
                gt_hist.append(gt)
            if math.isfinite(pred):
                pred_hist.append(pred)
            if math.isfinite(raw_e):
                raw_e_hist.append(raw_e)
            if math.isfinite(raw_p):
                raw_p_hist.append(raw_p)
            if math.isfinite(scaled_e):
                scaled_e_hist.append(scaled_e)
            if math.isfinite(scaled_p):
                scaled_p_hist.append(scaled_p)

            if step % 8 == 0 or step < 4:
                print(
                    f"step {step + 1}: reward={reward:.4f} "
                    f"gt={gt:.3f}m pred={pred:.3f}m "
                    f"obs=[E={scaled_e:.4f}, P={scaled_p:.4f}, valid={gmo_valid:.0f}] "
                    f"raw=[E={raw_e:.1f}, P={raw_p:.2f}]",
                    flush=True,
                )
            step += 1
            if args.real_time:
                time.sleep(max(0.0, dt - (time.time() - start)))
    except KeyboardInterrupt:
        print("[INFO] Interrupted.", flush=True)

    _print_correlation_summary(
        checkpoint=args.checkpoint,
        stochastic=args.stochastic,
        gt=gt_hist,
        pred=pred_hist,
        raw_energy=raw_e_hist,
        raw_peak=raw_p_hist,
        scaled_energy=scaled_e_hist,
        scaled_peak=scaled_p_hist,
    )

    env.close()
    print(f"PASS: played {step} steps", flush=True)
    simulation_app.close()


if __name__ == "__main__":
    main()