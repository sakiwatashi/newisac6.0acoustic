#!/usr/bin/env bash
# Phase C smoke: ultrasonic closed-loop grasp + lift.
# One Sim window; use EPISODES or EPISODE_TRIAL_IDS for in-session repeats (not separate launches).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BASE_OUTPUT_DIR="${OUTPUT_DIR:-${ISAACSIM_ROOT}/runtime/outputs/ur10e_robotiq_ultrasonic_grasp_smoke_v1}"
OUTPUT_STAGE="${OUTPUT_STAGE:-${ISAACSIM_ROOT}/runtime/scenes/ur10e_robotiq_ultrasonic_grasp_smoke_v1.usda}"
TRIAL_ID="${TRIAL_ID:-9}"
SPAWN_SEED="${SPAWN_SEED:-20260629}"
GUI="${GUI:-0}"
PRE_START_WAIT_SECONDS="${PRE_START_WAIT_SECONDS:-15}"
KEEP_OPEN_SECONDS="${KEEP_OPEN_SECONDS:-120}"
CONTROL_MODE="${CONTROL_MODE:-closed_loop}"
CLAIM_MODE="${CLAIM_MODE:-scaffold}"
# GRASP_SKIP_LIFT=1 (default): contact-only success, FixedCuboid in GUI (block stays on table).
# GRASP_SKIP_LIFT=0: physics lift — DynamicCuboid + weld-to-ee in GUI (set GUI_LIFT=1).
GUI_LIFT="${GUI_LIFT:-0}"
if [[ "${GUI}" == "1" && "${GUI_LIFT}" == "1" ]]; then
  GRASP_SKIP_LIFT=0
else
  GRASP_SKIP_LIFT=1
fi
GRASP_KINEMATIC_CLOSE="${GRASP_KINEMATIC_CLOSE:-1}"
GRASP_FINGER_PHYSICS_CONTROL="${GRASP_FINGER_PHYSICS_CONTROL:-0}"
export GRASP_SKIP_LIFT GRASP_KINEMATIC_CLOSE GRASP_FINGER_PHYSICS_CONTROL
EPISODES="${EPISODES:-}"
EPISODE_TRIAL_IDS="${EPISODE_TRIAL_IDS:-}"
EPISODE_PAUSE_SECONDS="${EPISODE_PAUSE_SECONDS:-}"
GUI_SETTLE_SCALE="${GUI_SETTLE_SCALE:-}"

if [[ "${GUI}" == "1" ]]; then
  EPISODES="${EPISODES:-1}"
  EPISODE_PAUSE_SECONDS="${EPISODE_PAUSE_SECONDS:-25}"
  GUI_SETTLE_SCALE="${GUI_SETTLE_SCALE:-1}"
fi
EPISODES="${EPISODES:-1}"
EPISODE_PAUSE_SECONDS="${EPISODE_PAUSE_SECONDS:-0}"
GUI_SETTLE_SCALE="${GUI_SETTLE_SCALE:-1}"

mkdir -p "${BASE_OUTPUT_DIR}"

echo "Phase C grasp smoke: trial=${TRIAL_ID} seed=${SPAWN_SEED} mode=${CONTROL_MODE} claim_mode=${CLAIM_MODE}"
echo "  gui=${GUI} gui_lift=${GUI_LIFT} grasp_skip_lift=${GRASP_SKIP_LIFT} episodes=${EPISODES} pause=${EPISODE_PAUSE_SECONDS}s"

ARGS=(
  "${SCRIPT_DIR}/official_asset_ur10_ultrasonic_closed_loop_grasp.py"
  --overwrite
  --output-dir "${BASE_OUTPUT_DIR}"
  --output-stage "${OUTPUT_STAGE}"
  --trial-id "${TRIAL_ID}"
  --spawn-seed "${SPAWN_SEED}"
  --control-mode "${CONTROL_MODE}"
  --claim-mode "${CLAIM_MODE}"
  --episode-count "${EPISODES}"
  --episode-pause-seconds "${EPISODE_PAUSE_SECONDS}"
  --gui-settle-scale "${GUI_SETTLE_SCALE}"
)

if [[ -n "${EPISODE_TRIAL_IDS}" ]]; then
  ARGS+=(--episode-trial-ids "${EPISODE_TRIAL_IDS}")
fi

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

"${SCRIPT_DIR}/run_host_python.sh" "${ARGS[@]}"