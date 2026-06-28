"""Phase 5 RL smoke — policy-gradient distance estimation on Lab dynamic GMO rows.

Uses recorded Lab smoke transitions (no full sim relaunch) to demonstrate
an RL training loop with reward r = -|action - d_gt|.

Full in-sim RSL-RL + DirectRLEnv is deferred (see ISAAC_LAB_PHASE5_RL_PLAN.md).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ISAACSIM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAB_CSV = ISAACSIM_ROOT / "runtime/outputs/lab_dynamic_smoke_v1/lab_dynamic_obs_timeseries.csv"
DEFAULT_SL_SUMMARY = ISAACSIM_ROOT / "runtime/outputs/lab_sl_distance_v1/sl_distance_summary.json"
DEFAULT_OUTPUT_DIR = ISAACSIM_ROOT / "runtime/outputs/lab_rl_distance_smoke_v1"


@dataclass
class Transition:
    step_index: int
    early_energy: float
    distance_gt: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RL smoke: PG distance policy on Lab GMO rows.")
    parser.add_argument("--lab-csv", type=Path, default=DEFAULT_LAB_CSV)
    parser.add_argument("--sl-summary", type=Path, default=DEFAULT_SL_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--episodes", type=int, default=200)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--explore-std", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_transitions(csv_path: Path) -> list[Transition]:
    rows: list[Transition] = []
    with csv_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("gmo_captured", "")).lower() not in {"true", "1"}:
                continue
            if str(row.get("gmo_valid", "")).lower() not in {"true", "1"}:
                continue
            energy = float(row["primary_sgw_early_energy"])
            gt = float(row["target_distance_m_gt"])
            if not (math.isfinite(energy) and math.isfinite(gt)):
                continue
            rows.append(Transition(int(float(row["step_index"])), energy, gt))
    if len(rows) < 5:
        raise SystemExit(f"Too few GMO transitions in {csv_path}")
    return rows


def sl_init(energy: np.ndarray, gt: np.ndarray) -> tuple[float, float]:
    slope = float(np.cov(energy, gt, bias=True)[0, 1] / (np.var(energy) + 1e-9))
    intercept = float(np.mean(gt) - slope * np.mean(energy))
    return slope, intercept


class LinearGaussianPolicy:
    def __init__(self, w: float, b: float, log_std: float):
        self.w = w
        self.b = b
        self.log_std = log_std

    @property
    def std(self) -> float:
        return float(math.exp(self.log_std))

    def mean(self, energy: float) -> float:
        return self.w * energy + self.b

    def sample_action(self, energy: float, rng: np.random.Generator) -> tuple[float, float]:
        mean = self.mean(energy)
        action = float(rng.normal(mean, self.std))
        log_prob = -0.5 * ((action - mean) / self.std) ** 2 - self.log_std - 0.5 * math.log(2 * math.pi)
        return action, log_prob

    def update(
        self,
        energies: list[float],
        actions: list[float],
        rewards: list[float],
        log_probs: list[float],
        lr: float,
        baseline: float,
    ) -> float:
        advantages = [r - baseline for r in rewards]
        adv = np.asarray(advantages, dtype=float)
        adv = np.clip(adv, -1.0, 1.0)

        grad_w = 0.0
        grad_b = 0.0
        std2 = max(self.std**2, 1e-6)
        for energy, action, advantage, _lp in zip(energies, actions, adv, log_probs):
            mean = self.mean(energy)
            grad_mean = advantage * (action - mean) / std2
            grad_w += grad_mean * energy
            grad_b += grad_mean

        n = float(len(energies))
        self.w += lr * grad_w / n
        self.b += lr * grad_b / n
        self.w = float(np.clip(self.w, -1.0, 0.5))
        self.b = float(np.clip(self.b, 0.5, 3.0))
        return float(np.mean(rewards))


def evaluate(
    policy: LinearGaussianPolicy,
    transitions: list[Transition],
    energy_mean: float,
    energy_std: float,
) -> dict[str, float]:
    preds = np.array([policy.mean((t.early_energy - energy_mean) / energy_std) for t in transitions])
    gt = np.array([t.distance_gt for t in transitions])
    err = preds - gt
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    if np.std(preds) > 0 and np.std(gt) > 0:
        r = float(np.corrcoef(preds, gt)[0, 1])
    else:
        r = float("nan")
    return {"mae_m": mae, "rmse_m": rmse, "pearson_r": r, "n": len(transitions)}


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "rl_distance_smoke_summary.json"
    if summary_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {summary_path}")

    rng = np.random.default_rng(args.seed)
    transitions = load_transitions(args.lab_csv)
    energy = np.array([t.early_energy for t in transitions])
    gt = np.array([t.distance_gt for t in transitions])
    energy_mean = float(np.mean(energy))
    energy_std = float(np.std(energy) + 1e-9)
    energy_norm = (energy - energy_mean) / energy_std
    w0, b0 = sl_init(energy_norm, gt)
    policy = LinearGaussianPolicy(w0, b0, math.log(args.explore_std))

    episode_rewards: list[float] = []
    episode_mae: list[float] = []

    for ep in range(args.episodes):
        order = rng.permutation(len(transitions))
        ep_trans = [transitions[i] for i in order]
        energies: list[float] = []
        actions: list[float] = []
        rewards: list[float] = []
        log_probs: list[float] = []

        for tr in ep_trans:
            e_norm = (tr.early_energy - energy_mean) / energy_std
            action, lp = policy.sample_action(e_norm, rng)
            action = float(np.clip(action, 0.8, 2.2))
            reward = -abs(action - tr.distance_gt)
            energies.append(e_norm)
            actions.append(action)
            rewards.append(reward)
            log_probs.append(lp)

        baseline = float(np.mean(rewards))
        mean_reward = policy.update(energies, actions, rewards, log_probs, args.lr, baseline)
        episode_rewards.append(mean_reward)
        episode_mae.append(evaluate(policy, transitions, energy_mean, energy_std)["mae_m"])

    final_metrics = evaluate(policy, transitions, energy_mean, energy_std)
    sl_baseline_r = float(np.corrcoef(energy, gt)[0, 1]) if np.std(energy) > 0 else float("nan")

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(episode_rewards, label="mean episode reward", color="#1f77b4")
    ax.set_xlabel("episode")
    ax.set_ylabel("reward (-MAE proxy)")
    ax.set_title("RL smoke: REINFORCE on Lab dynamic GMO rows")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    reward_path = args.output_dir / "rl_reward_curve.png"
    fig.savefig(reward_path, dpi=150)
    plt.close(fig)

    preds = [policy.mean((t.early_energy - energy_mean) / energy_std) for t in transitions]
    fig2, ax2 = plt.subplots(figsize=(6, 5))
    gts = [t.distance_gt for t in transitions]
    ax2.scatter(gts, preds, color="#9467bd", alpha=0.85)
    lo, hi = min(gts + preds), max(gts + preds)
    ax2.plot([lo, hi], [lo, hi], "k--")
    ax2.set_title(f"RL policy after {args.episodes} ep\nMAE={final_metrics['mae_m']:.3f} r={final_metrics['pearson_r']:.3f}")
    ax2.set_xlabel("GT distance (m)")
    ax2.set_ylabel("Policy mean (m)")
    fig2.tight_layout()
    pred_path = args.output_dir / "rl_pred_vs_gt.png"
    fig2.savefig(pred_path, dpi=150)
    plt.close(fig2)

    passed = final_metrics["pearson_r"] >= 0.35 and final_metrics["mae_m"] <= 0.55

    summary = {
        "pass": passed,
        "claim_boundary": "offline_pg_smoke_on_lab_transitions; not in-sim RSL-RL",
        "algorithm": "REINFORCE_linear_gaussian_policy",
        "lab_csv": str(args.lab_csv),
        "n_transitions": len(transitions),
        "episodes": args.episodes,
        "init_weights": {"w": w0, "b": b0},
        "final_weights": {"w": policy.w, "b": policy.b, "std": policy.std},
        "final_metrics": final_metrics,
        "sl_feature_vs_gt_pearson_r": sl_baseline_r,
        "final_episode_reward": episode_rewards[-1] if episode_rewards else None,
        "figures": {"rl_reward_curve": str(reward_path), "rl_pred_vs_gt": str(pred_path)},
        "next_step": "In-sim RSL-RL DirectRLEnv per ISAAC_LAB_PHASE5_RL_PLAN.md task A",
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with (args.output_dir / "rl_episode_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["episode", "mean_reward", "eval_mae_m"])
        writer.writeheader()
        for i, (rew, mae) in enumerate(zip(episode_rewards, episode_mae)):
            writer.writerow({"episode": i, "mean_reward": rew, "eval_mae_m": mae})

    print(f"Transitions: {len(transitions)}")
    print(f"Final: MAE={final_metrics['mae_m']:.4f} r={final_metrics['pearson_r']:.4f}")
    print(f"Weights: w={policy.w:.6f} b={policy.b:.4f} std={policy.std:.4f}")
    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()