#!/usr/bin/env bash
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/home/lab109/song/isaacsim6.0/scripts/env_host_isolated.sh
source "${HOST_ROOT}/scripts/env_host_isolated.sh"

cd "${APP_ROOT}"
exec ./isaac-sim.compatibility_check.sh \
  --portable --portable-root="${RUNTIME_ROOT}/portable" \
  --/app/quitAfter=10 \
  "$@"