"""Helpers for loading RSL-RL checkpoints with matching PPO config."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def detect_ppo_variant(checkpoint: Path) -> str:
    import torch

    payload = torch.load(str(checkpoint), map_location="cpu", weights_only=False)
    actor_state = payload.get("actor_state_dict", {})
    if any("obs_normalizer" in key for key in actor_state):
        return "v5"
    return "v3"


def make_ppo_runner_cfg(variant: str):
    from isaaclab_tasks_ext.ur10_rtx_acoustic_distance.agents.rsl_rl_ppo_cfg import (
        Ur10RtxAcousticDistancePPORunnerCfg,
        Ur10RtxAcousticDistancePPORunnerCfgV4,
        Ur10RtxAcousticDistancePPORunnerCfgV5,
    )

    if variant == "v5":
        return Ur10RtxAcousticDistancePPORunnerCfgV5()
    if variant == "v4":
        return Ur10RtxAcousticDistancePPORunnerCfgV4()
    return Ur10RtxAcousticDistancePPORunnerCfg()


def resolve_ppo_variant(checkpoint: Path, requested: str = "auto") -> str:
    if requested in ("v3", "v4", "v5"):
        return requested
    return detect_ppo_variant(checkpoint)


def build_on_policy_runner(env, variant: str, seed: int, rsl_rl_version: str):
    import importlib.metadata as metadata
    from rsl_rl.runners import OnPolicyRunner

    from isaaclab_rl.rsl_rl import handle_deprecated_rsl_rl_cfg

    agent_cfg = make_ppo_runner_cfg(variant)
    agent_cfg.seed = int(seed)
    version = rsl_rl_version or metadata.version("rsl-rl-lib")
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, version)
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    return runner, agent_cfg