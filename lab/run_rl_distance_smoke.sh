#!/usr/bin/env bash
# Phase 5 RL smoke (offline PG on Lab dynamic GMO transitions).
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/lab_rl_distance_smoke_v1}"

python3 "${HOST_ROOT}/lab/train_rl_distance_smoke.py" \
  --output-dir "${OUTPUT_DIR}" \
  --episodes "${EPISODES:-200}" \
  --overwrite

echo "Done. Summary: ${OUTPUT_DIR}/rl_distance_smoke_summary.json"