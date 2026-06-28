"""Quick smoke: instantiate DirectRLEnv and run a few steps (no RSL-RL)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
for path in (str(LAB_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import gymnasium as gym
import torch
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
parser.add_argument("--steps", type=int, default=4)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app
from simulation_app_ref import set_simulation_app

set_simulation_app(simulation_app)

import isaaclab_tasks_ext  # noqa: F401

from isaaclab_tasks_ext.ur10_rtx_acoustic_distance.ur10_rtx_acoustic_distance_env_cfg import (
    Ur10RtxAcousticDistanceEnvCfg,
)

cfg = Ur10RtxAcousticDistanceEnvCfg()
env = gym.make("Isaac-Ur10RtxAcousticDistance-Direct-v0", cfg=cfg)
obs, _ = env.reset()
policy_obs = obs["policy"][0].detach().cpu()
print(
    f"reset ok, obs shape: {obs['policy'].shape} "
    f"acoustic=[E={float(policy_obs[0]):.4f}, P={float(policy_obs[1]):.4f}, valid={float(policy_obs[2]):.0f}]",
    flush=True,
)

for i in range(int(args_cli.steps)):
    action = torch.zeros((1, 1), device=env.unwrapped.device)
    obs, reward, terminated, truncated, info = env.step(action)
    policy_obs = obs["policy"][0].detach().cpu()
    print(
        f"step {i + 1}: reward={reward.item():.4f} "
        f"acoustic=[E={float(policy_obs[0]):.4f}, P={float(policy_obs[1]):.4f}, valid={float(policy_obs[2]):.0f}] "
        f"log={info.get('log', {})}",
        flush=True,
    )

env.close()
simulation_app.close()
print("PASS: direct env smoke", flush=True)