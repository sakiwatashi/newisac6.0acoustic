#!/usr/bin/env bash
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/lab109/song/isaacsim6.0/scripts/env_host_isolated.sh
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

exec "${SCRIPT_DIR}/run_host_python.sh" \
  "${APP_ROOT}/standalone_examples/api/isaacsim.sensors.experimental.rtx/create_acoustic_basic.py" \
  "$@"