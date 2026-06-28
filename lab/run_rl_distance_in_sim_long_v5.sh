#!/usr/bin/env bash
# v5 long run: shaped reward + obs norm + 500 iterations (~60 min).
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export MAX_ITERATIONS="${MAX_ITERATIONS:-500}"
export NUM_STEPS_PER_ENV="${NUM_STEPS_PER_ENV:-32}"
export SAVE_INTERVAL="${SAVE_INTERVAL:-100}"
export OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/lab_rl_distance_in_sim_long_v5}"
export LOG_SUFFIX="${LOG_SUFFIX:-_long_v5}"
export PPO_VARIANT="${PPO_VARIANT:-v5}"
export ENV_VARIANT="${ENV_VARIANT:-v5}"

exec "$(dirname "${BASH_SOURCE[0]}")/run_rl_distance_in_sim.sh"