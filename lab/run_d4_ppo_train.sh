#!/usr/bin/env bash
# D4 Track B — longer PPO (default 100 iters × 32 steps).
# Blind ablation: BLIND=1 bash lab/run_d4_ppo_train.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Default: scaffold RL tune (true_range in obs/reward; no target xyz)
export OUT="${OUT:-$ROOT/runtime/outputs/v2_d4_ppo_grasp_rl_tune}"
export ITERS="${ITERS:-100}"
export STEPS="${STEPS:-48}"
export SAVE="${SAVE:-25}"
export SEED="${SEED:-20260716}"
export BLIND="${BLIND:-0}"
exec bash "$ROOT/lab/run_d4_ppo_smoke.sh"
