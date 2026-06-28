#!/usr/bin/env bash
# Long in-sim RSL-RL run v4: obs normalization for weak acoustic signal.
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export MAX_ITERATIONS="${MAX_ITERATIONS:-200}"
export NUM_STEPS_PER_ENV="${NUM_STEPS_PER_ENV:-32}"
export SAVE_INTERVAL="${SAVE_INTERVAL:-50}"
export OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/lab_rl_distance_in_sim_long_v4}"
export LOG_SUFFIX="${LOG_SUFFIX:-_long_v4}"
export PPO_VARIANT="${PPO_VARIANT:-v4}"

exec "$(dirname "${BASH_SOURCE[0]}")/run_rl_distance_in_sim.sh"