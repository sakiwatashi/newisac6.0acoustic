#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/ur10_official_asset_smoke}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${HOST_ROOT}/runtime/scenes/ur10_official_asset_ee_acoustic_smoke.usda}"
END_EFFECTOR_FRAME="${END_EFFECTOR_FRAME:-ee_link}"

exec "${SCRIPT_DIR}/run_host_python.sh" \
  "${SCRIPT_DIR}/official_asset_ur10_ee_acoustic_smoke.py" \
  --overwrite \
  --gui \
  --end-effector-frame "${END_EFFECTOR_FRAME}" \
  --output-dir "${OUTPUT_DIR}" \
  --output-stage "${OUTPUT_STAGE}" \
  --frames "${FRAMES:-80}" \
  --progress-interval "${PROGRESS_INTERVAL:-10}" \
  --max-runtime-seconds "${MAX_RUNTIME_SECONDS:-300}" \
  "$@"
