#!/usr/bin/env bash
# Isaac Lab Phase 4 — UR10 RTX dynamic target smoke (headless).
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-${HOST_ROOT}/IsaacLab}"
OUTPUT_DIR="${OUTPUT_DIR:-${HOST_ROOT}/runtime/outputs/lab_dynamic_smoke_v1}"
STEPS="${STEPS:-128}"
DECIMATION="${DECIMATION:-4}"

# shellcheck source=/home/lab109/song/isaacsim6.0/scripts/env_host_isolated.sh
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

mkdir -p "${OUTPUT_DIR}"
LOG_PATH="${HOST_ROOT}/logs/lab_dynamic_smoke_v1.log"

echo "Lab Phase 4 smoke"
echo "  Isaac Lab: ${ISAACLAB_ROOT}"
echo "  Output:    ${OUTPUT_DIR}"
echo "  Steps:     ${STEPS} (decimation=${DECIMATION})"

cd "${ISAACLAB_ROOT}"
# Default headless Lab kit omits replicator + core.api; use Isaac Sim python base experience.
SIM_EXPERIENCE="${SIM_EXPERIENCE:-${APP_ROOT}/apps/isaacsim.exp.base.python.kit}"
./isaaclab.sh -p "${HOST_ROOT}/lab/ur10_rtx_acoustic_env.py" \
  --headless \
  --experience "${SIM_EXPERIENCE}" \
  --steps "${STEPS}" \
  --decimation "${DECIMATION}" \
  --output-dir "${OUTPUT_DIR}" \
  --overwrite \
  2>&1 | tee "${LOG_PATH}"
smoke_status=${PIPESTATUS[0]}

if [[ "${smoke_status}" -ne 0 ]]; then
  echo "Lab smoke failed (exit ${smoke_status}). See ${LOG_PATH}" >&2
  exit "${smoke_status}"
fi

if [[ -f "${OUTPUT_DIR}/lab_dynamic_obs_timeseries.csv" ]]; then
  "${ISAACLAB_ROOT}/isaaclab.sh" -p "${HOST_ROOT}/lab/plot_lab_smoke_results.py" \
    --output-dir "${OUTPUT_DIR}"
fi

echo "Done. CSV: ${OUTPUT_DIR}/lab_dynamic_obs_timeseries.csv"