#!/usr/bin/env bash
# Optional P0 full-GMO dump (GPU). Offline audit does not require this.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
[[ -f scripts/env_host_isolated.sh ]] && source scripts/env_host_isolated.sh || true
exec ./app/python.sh scripts/p0_fixed_sensor_gmo_dump.py "$@"
