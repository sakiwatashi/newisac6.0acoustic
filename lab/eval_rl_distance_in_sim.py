"""Headless evaluation of one or more RSL-RL checkpoints (deterministic + stochastic)."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
for path in (str(LAB_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from isaaclab.app import AppLauncher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate in-sim RSL-RL distance checkpoints.")
    AppLauncher.add_app_launcher_args(parser)
    parser.add_argument(
        "--checkpoints",
        type=Path,
        nargs="+",
        required=True,
        help="One or more model_*.pt paths.",
    )
    parser.add_argument("--steps", type=int, default=64, help="Policy steps per checkpoint/mode.")
    parser.add_argument("--seed", type=int, default=42)
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


def _run_episode(env, policy, obs, steps: int, stochastic: bool) -> dict[str, list[float]]:
    import torch

    gt_hist: list[float] = []
    pred_hist: list[float] = []
    raw_e_hist: list[float] = []
    raw_p_hist: list[float] = []

    for _ in range(steps):
        with torch.inference_mode():
            if stochastic:
                actions = policy(obs, stochastic_output=True)
            else:
                actions = policy(obs)
            obs, _rewards, dones, extras = env.step(actions)
            if dones.any():
                policy.reset(dones)

        log = extras.get("log", {}) if isinstance(extras, dict) else {}
        for key, hist in (
            ("Metrics/gt_distance_m", gt_hist),
            ("Metrics/pred_distance_m", pred_hist),
            ("Metrics/raw_early_energy", raw_e_hist),
            ("Metrics/raw_peak", raw_p_hist),
        ):
            val = float(log.get(key, float("nan")))
            if math.isfinite(val):
                hist.append(val)

    return {
        "gt": gt_hist,
        "pred": pred_hist,
        "raw_e": raw_e_hist,
        "raw_p": raw_p_hist,
    }


def _summarize(hist: dict[str, list[float]]) -> dict[str, float]:
    gt = hist["gt"]
    pred = hist["pred"]
    raw_e = hist["raw_e"]
    raw_p = hist["raw_p"]
    n = len(gt)
    if n == 0:
        return {"n": 0.0}

    mae = sum(abs(p - g) for p, g in zip(pred, gt)) / n
    pred_mean = sum(pred) / len(pred) if pred else math.nan
    pred_std = math.sqrt(sum((p - pred_mean) ** 2 for p in pred) / max(1, len(pred) - 1)) if pred else math.nan

    out = {
        "n": float(n),
        "mae_m": mae,
        "pearson_gt_pred": pearson_r(gt, pred),
        "pearson_gt_raw_e": pearson_r(gt, raw_e),
        "pearson_gt_raw_p": pearson_r(gt, raw_p),
        "pred_mean_m": pred_mean,
        "pred_std_m": pred_std,
        "gt_mean_m": sum(gt) / n,
        "gt_std_m": math.sqrt(sum((g - sum(gt) / n) ** 2 for g in gt) / max(1, n - 1)),
    }
    if raw_e:
        e_mean = sum(raw_e) / len(raw_e)
        out["raw_e_range_pct"] = 100.0 * (max(raw_e) - min(raw_e)) / max(e_mean, 1e-9)
    if raw_p:
        p_mean = sum(raw_p) / len(raw_p)
        out["raw_p_range_pct"] = 100.0 * (max(raw_p) - min(raw_p)) / max(p_mean, 1e-9)
    return out


def main() -> None:
    args = parse_args()
    checkpoints = [_resolve_checkpoint(p) for p in args.checkpoints]
    for ckpt in checkpoints:
        if not ckpt.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {ckpt}")

    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app
    from simulation_app_ref import set_simulation_app

    set_simulation_app(simulation_app)

    import importlib.metadata as metadata

    import gymnasium as gym

    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

    import isaaclab_tasks_ext  # noqa: F401
    from isaaclab_tasks_ext.ur10_rtx_acoustic_distance.ur10_rtx_acoustic_distance_env_cfg import (
        Ur10RtxAcousticDistanceEnvCfg,
    )
    from rl_checkpoint_utils import build_on_policy_runner, resolve_ppo_variant

    env_cfg = Ur10RtxAcousticDistanceEnvCfg()
    env_cfg.seed = int(args.seed)
    rsl_rl_version = metadata.version("rsl-rl-lib")

    env = gym.make("Isaac-Ur10RtxAcousticDistance-Direct-v0", cfg=env_cfg)
    # Wrapper clip_actions is identical across v3/v4.
    env = RslRlVecEnvWrapper(env, clip_actions=1.0)

    print(f"[INFO] Evaluating {len(checkpoints)} checkpoint(s), {args.steps} steps each", flush=True)
    results: list[dict] = []
    runner = None
    current_variant: str | None = None

    for ckpt in checkpoints:
        variant = resolve_ppo_variant(ckpt)
        if runner is None or variant != current_variant:
            runner, _agent_cfg = build_on_policy_runner(
                env, variant, seed=int(args.seed), rsl_rl_version=rsl_rl_version
            )
            current_variant = variant
            print(f"[INFO] Using PPO variant={variant} for {ckpt.name}", flush=True)

        for stochastic in (False, True):
            mode = "stochastic" if stochastic else "deterministic"
            print(f"\n[EVAL] {ckpt.name} ({variant}) mode={mode}", flush=True)
            runner.load(str(ckpt))
            policy = runner.get_inference_policy(device=env.unwrapped.device)
            obs = env.get_observations()
            hist = _run_episode(env, policy, obs, int(args.steps), stochastic=stochastic)
            summary = _summarize(hist)
            results.append({"checkpoint": ckpt.name, "mode": mode, **summary})
            print(
                f"  n={int(summary['n'])} MAE={summary.get('mae_m', float('nan')):.4f}m "
                f"r(gt,pred)={summary.get('pearson_gt_pred', float('nan')):.4f} "
                f"r(gt,E)={summary.get('pearson_gt_raw_e', float('nan')):.4f} "
                f"r(gt,P)={summary.get('pearson_gt_raw_p', float('nan')):.4f} "
                f"pred={summary.get('pred_mean_m', float('nan')):.3f}±{summary.get('pred_std_m', float('nan')):.4f}m "
                f"E_range={summary.get('raw_e_range_pct', float('nan')):.2f}%",
                flush=True,
            )

    print("\n[COMPARE] sorted by MAE (deterministic first):", flush=True)
    det = [r for r in results if r["mode"] == "deterministic"]
    for r in sorted(det, key=lambda x: x.get("mae_m", 999.0)):
        print(
            f"  {r['checkpoint']:14s} MAE={r.get('mae_m', float('nan')):.4f}m "
            f"r(pred)={r.get('pearson_gt_pred', float('nan')):.4f} "
            f"r(E)={r.get('pearson_gt_raw_e', float('nan')):.4f} "
            f"pred_std={r.get('pred_std_m', float('nan')):.4f}m",
            flush=True,
        )

    env.close()
    simulation_app.close()
    print("PASS: eval complete", flush=True)


if __name__ == "__main__":
    main()