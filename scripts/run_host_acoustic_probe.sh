#!/usr/bin/env bash
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${ISAAC_ACOUSTIC_PROJECT:-/home/lab109/song/isaac_acoustic_research}"
OUTPUT_DIR="${HOST_ROOT}/runtime/outputs/probe"
OUTPUT_STAGE="${HOST_ROOT}/runtime/scenes/minimal_official_acoustic_probe_host.usda"

mkdir -p "${OUTPUT_DIR}" "${HOST_ROOT}/runtime/scenes"

exec "${SCRIPT_DIR}/run_host_python.sh" \
  "${PROJECT}/scripts/official_rtx_acoustic_runtime_probe.py" \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  "$@"