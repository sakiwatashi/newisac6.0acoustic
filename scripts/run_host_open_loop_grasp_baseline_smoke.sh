#!/usr/bin/env bash
# Open-loop baseline: oracle wrench pose -> grasp (control group).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=run_host_repeat_common.sh
source "${SCRIPT_DIR}/run_host_repeat_common.sh"

BASE_OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/open_loop_grasp_baseline_smoke_v1}"
BASE_OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/open_loop_grasp_baseline_smoke_v1.usda}"
TRIAL_ID="${TRIAL_ID:-9}"
SPAWN_SEED="${SPAWN_SEED:-20260629}"
GUI="${GUI:-0}"
PRE_START_WAIT_SECONDS="${PRE_START_WAIT_SECONDS:-15}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-120}"
# Match closed-loop smoke: default to contact-only stable proxy unless GUI_LIFT=1.
GUI_LIFT="${GUI_LIFT:-0}"
if [[ "${GUI}" == "1" && "${GUI_LIFT}" == "1" ]]; then
  GRASP_SKIP_LIFT=0
else
  GRASP_SKIP_LIFT=1
fi
GRASP_KINEMATIC_CLOSE="${GRASP_KINEMATIC_CLOSE:-1}"
GRASP_FINGER_PHYSICS_CONTROL="${GRASP_FINGER_PHYSICS_CONTROL:-0}"
export GRASP_SKIP_LIFT GRASP_KINEMATIC_CLOSE GRASP_FINGER_PHYSICS_CONTROL
STOP_ON_FAIL="${STOP_ON_FAIL:-0}"
REPEAT_COUNT="$(run_host_resolve_repeat_count "${GUI}")"

mkdir -p "${BASE_OUTPUT_DIR}"

echo "Open-loop grasp smoke: trial=${TRIAL_ID} seed=${SPAWN_SEED} repeats=${REPEAT_COUNT} gui=${GUI} grasp_skip_lift=${GRASP_SKIP_LIFT}"

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
  fi
  mkdir -p "${OUTPUT_DIR}" "$(dirname "${OUTPUT_STAGE}")"

  ARGS=(
    "${SCRIPT_DIR}/official_asset_ur10_ultrasonic_closed_loop_grasp.py"
    --overwrite
    --output-dir "${OUTPUT_DIR}"
    --output-stage "${OUTPUT_STAGE}"
    --trial-id "${TRIAL_ID}"
    --spawn-seed "${SPAWN_SEED}"
    --control-mode open_loop_baseline
  )

  if [[ "${GRASP_SKIP_LIFT}" == "1" ]]; then
  ARGS+=(--skip-lift)
else
  ARGS+=(--enable-lift)
fi

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
    "ultrasonic_closed_loop_grasp_summary.json" \
    "open_loop_grasp_baseline"
fi

if [[ "${fail_count}" -gt 0 ]]; then
  echo "Completed with ${fail_count} failed run(s) out of ${REPEAT_COUNT}"
  exit 1
fi