#!/usr/bin/env bash
# Phase B smoke: ultrasonic closed-loop approach (no gripper yet).
# Set REPEAT_COUNT=N (or GUI=1 defaults to 5) to run multiple trials in one command.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=run_host_repeat_common.sh
source "${SCRIPT_DIR}/run_host_repeat_common.sh"

BASE_OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10e_robotiq_ultrasonic_approach_smoke_v1}"
BASE_OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10e_robotiq_ultrasonic_approach_smoke_v1.usda}"
TRIAL_ID="${TRIAL_ID:-9}"
SPAWN_SEED="${SPAWN_SEED:-20260629}"
GUI="${GUI:-1}"
PRE_START_WAIT_SECONDS="${PRE_START_WAIT_SECONDS:-15}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-120}"
STOP_ON_FAIL="${STOP_ON_FAIL:-0}"
REPEAT_COUNT="$(run_host_resolve_repeat_count "${GUI}")"

mkdir -p "${BASE_OUTPUT_DIR}"

echo "Phase B approach smoke: trial=${TRIAL_ID} seed=${SPAWN_SEED} repeats=${REPEAT_COUNT} gui=${GUI}"

fail_count=0
for run_idx in $(seq 1 "${REPEAT_COUNT}"); do
  if [[ "${REPEAT_COUNT}" -gt 1 ]]; then
    RUN_TAG="$(printf 'run_%03d' "${run_idx}")"
    OUTPUT_DIR="${BASE_OUTPUT_DIR}/${RUN_TAG}"
    OUTPUT_STAGE="${BASE_OUTPUT_DIR}/scenes/${RUN_TAG}.usda"
    echo "=== repeat ${run_idx}/${REPEAT_COUNT} -> ${OUTPUT_DIR} ==="
  else
    OUTPUT_DIR="${BASE_OUTPUT_DIR}"
    OUTPUT_STAGE="${BASE_OUTPUT_STAGE}"
    echo "=== single run -> ${OUTPUT_DIR} ==="
  fi
  mkdir -p "${OUTPUT_DIR}" "$(dirname "${OUTPUT_STAGE}")"

  ARGS=(
    "${SCRIPT_DIR}/official_asset_ur10_ultrasonic_closed_loop_approach.py"
    --overwrite
    --output-dir "${OUTPUT_DIR}"
    --output-stage "${OUTPUT_STAGE}"
    --trial-id "${TRIAL_ID}"
    --spawn-seed "${SPAWN_SEED}"
    --settle-steps 30
    --substeps-per-sample 2
  )

  if [[ "${GUI}" == "1" ]]; then
    ARGS+=(
      --gui
      --keep-open-seconds "${KEEP_OPEN_SECONDS}"
      --gui-pre-start-wait-seconds "${PRE_START_WAIT_SECONDS}"
    )
  fi

  if "${SCRIPT_DIR}/run_host_python.sh" "${ARGS[@]}"; then
    echo "PASS run ${run_idx}/${REPEAT_COUNT}"
  else
    fail_count=$((fail_count + 1))
    echo "FAIL run ${run_idx}/${REPEAT_COUNT}"
    if [[ "${STOP_ON_FAIL}" == "1" ]]; then
      break
    fi
  fi
done

if [[ "${REPEAT_COUNT}" -gt 1 ]]; then
  run_host_repeat_aggregate_summaries \
    "${BASE_OUTPUT_DIR}" \
    "${REPEAT_COUNT}" \
    "ultrasonic_closed_loop_approach_summary.json" \
    "phase_b_ultrasonic_approach"
fi

if [[ "${fail_count}" -gt 0 ]]; then
  echo "Completed with ${fail_count} failed run(s) out of ${REPEAT_COUNT}"
  exit 1
fi