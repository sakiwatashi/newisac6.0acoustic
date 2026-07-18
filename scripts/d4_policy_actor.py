"""Lightweight Track-B actor for same-scene d3 hookup (no rsl_rl / Isaac Lab).

Loads RSL-RL ``model_*.pt`` actor MLP + EmpiricalNormalization stats and
returns deterministic mean actions for 8-D acoustic grasp obs.

Obs layout (must match ur10_rtx_acoustic_grasp pack_policy_obs, 8-D):
  energy_scaled, peak_scaled, gmo_valid, d_hat_xy, gripper_open, ee_x, prev_a0, prev_a1
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
import torch.nn as nn


ENERGY_SCALE = 1.0e-4
PEAK_SCALE = 1.0e-2
D_HAT_SCALE = 1.0


class ActorMLP(nn.Module):
    def __init__(self, obs_dim: int = 8, hidden: int = 128, act_dim: int = 2):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(obs_dim, hidden),
            nn.ELU(),
            nn.Linear(hidden, hidden),
            nn.ELU(),
            nn.Linear(hidden, act_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.mlp(x)


class D4PolicyActor:
    """Deterministic actor for closed-loop approach/close timing."""

    def __init__(self, checkpoint: Path | str, device: str = "cpu"):
        path = Path(checkpoint).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"policy checkpoint not found: {path}")
        ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
        if not isinstance(ckpt, dict) or "actor_state_dict" not in ckpt:
            raise ValueError(f"unexpected checkpoint format: {path}")
        sd = ckpt["actor_state_dict"]

        self.device = torch.device(device)
        self.obs_mean = sd["obs_normalizer._mean"].to(self.device).float()
        self.obs_std = sd["obs_normalizer._std"].to(self.device).float().clamp_min(1e-6)
        w0 = sd["mlp.0.weight"]
        obs_dim = int(w0.shape[1])
        hidden = int(w0.shape[0])
        act_dim = int(sd["mlp.4.weight"].shape[0])
        self.actor = ActorMLP(obs_dim=obs_dim, hidden=hidden, act_dim=act_dim).to(self.device)
        # remap flat keys → Sequential
        mapped = {
            "mlp.0.weight": sd["mlp.0.weight"],
            "mlp.0.bias": sd["mlp.0.bias"],
            "mlp.2.weight": sd["mlp.2.weight"],
            "mlp.2.bias": sd["mlp.2.bias"],
            "mlp.4.weight": sd["mlp.4.weight"],
            "mlp.4.bias": sd["mlp.4.bias"],
        }
        self.actor.load_state_dict(mapped, strict=True)
        self.actor.eval()
        self.obs_dim = obs_dim
        self.checkpoint = str(path)
        self.train_iter = int(ckpt.get("iter", -1))

    def normalize(self, obs: np.ndarray | torch.Tensor) -> torch.Tensor:
        x = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        if x.ndim == 1:
            x = x.unsqueeze(0)
        # EmpiricalNormalization: (x - mean) / std
        return (x - self.obs_mean) / self.obs_std

    @torch.no_grad()
    def act(self, obs: Sequence[float] | np.ndarray) -> tuple[float, float]:
        x = self.normalize(np.asarray(obs, dtype=np.float32))
        mean = self.actor(x)
        a0 = float(mean[0, 0].item())
        a1 = float(mean[0, 1].item())
        # match env clamp
        a0 = float(max(-1.0, min(1.0, a0)))
        a1 = float(max(-1.0, min(1.0, a1)))
        return a0, a1


def pack_obs8(
    *,
    early_energy: float,
    peak_sample_idx: float,
    gmo_valid: float,
    d_hat_xy: float,
    gripper_open: float,
    ee_x: float,
    prev_a0: float,
    prev_a1: float,
    blind: bool = False,
) -> list[float]:
    if blind:
        early_energy, peak_sample_idx, gmo_valid, d_hat_xy = 0.0, 0.0, 0.0, 0.0
    e = float(early_energy) if math.isfinite(early_energy) else 0.0
    p = float(peak_sample_idx) if math.isfinite(peak_sample_idx) else 0.0
    d = float(d_hat_xy) if math.isfinite(d_hat_xy) else 10.0
    return [
        e * ENERGY_SCALE,
        p * PEAK_SCALE,
        float(gmo_valid),
        d * D_HAT_SCALE,
        float(gripper_open),
        float(ee_x),
        float(prev_a0),
        float(prev_a1),
    ]


def gated_peak_sample_idx(
    amps: np.ndarray | None,
    *,
    slope: float,
    intercept: float,
    range_lo_m: float = 0.32,
    range_hi_m: float = 1.05,
    margin_samples: int = 2,
) -> tuple[float, str]:
    """First local max inside distance gate (sample-index peak)."""
    if amps is None or len(amps) == 0 or not math.isfinite(slope) or slope == 0.0:
        return float("nan"), "empty"
    wf = np.asarray(amps, dtype=float).reshape(-1)
    if wf.size < 3:
        return float("nan"), "short"

    def idx_for_range(r: float) -> float:
        return r * slope + intercept

    lo = max(0, int(math.floor(idx_for_range(range_lo_m))) - margin_samples)
    hi = min(wf.size - 1, int(math.ceil(idx_for_range(range_hi_m))) + margin_samples)
    if hi <= lo + 1:
        return float("nan"), "gate_empty"
    seg = wf[lo : hi + 1]
    # first local max
    for i in range(1, seg.size - 1):
        if seg[i] >= seg[i - 1] and seg[i] >= seg[i + 1] and seg[i] > 0:
            return float(lo + i), "gated_local_max"
    j = int(np.argmax(seg))
    return float(lo + j), "gated_argmax"


def peak_to_d_hat_xy(peak: float, slope: float, intercept: float, height_diff: float = 0.0) -> float:
    if not math.isfinite(peak) or slope == 0.0:
        return float("nan")
    d3d = (peak - intercept) / slope
    if not math.isfinite(d3d):
        return float("nan")
    return math.sqrt(max(d3d * d3d - height_diff * height_diff, 1e-6))
