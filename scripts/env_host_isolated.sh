#!/usr/bin/env bash
# Source this file before any host Isaac Sim command.
# Keeps cache/config/data under isaacsim6.0/runtime and away from ~/.cache/ov.

set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ROOT="${HOST_ROOT}/app"
RUNTIME_ROOT="${HOST_ROOT}/runtime"

export HOST_ROOT APP_ROOT RUNTIME_ROOT

# Do not write Omniverse state into the default home directories.
export XDG_CACHE_HOME="${RUNTIME_ROOT}/xdg-cache"
export XDG_CONFIG_HOME="${RUNTIME_ROOT}/xdg-config"
export XDG_DATA_HOME="${RUNTIME_ROOT}/xdg-data"

# Isaac / Kit license and privacy (host-only session).
export OMNI_KIT_ACCEPT_EULA="${OMNI_KIT_ACCEPT_EULA:-YES}"
export PRIVACY_CONSENT="${PRIVACY_CONSENT:-Y}"

# Optional CPU pinning for acoustic probes; does not affect other users by default.
export CPUSET="${CPUSET:-15-19}"

# Keep project paths explicit for wrappers.
export ISAAC_ACOUSTIC_PROJECT="/home/lab109/song/isaac_acoustic_research"

if [[ ! -x "${APP_ROOT}/python.sh" ]]; then
  echo "Host Isaac Sim not installed yet: missing ${APP_ROOT}/python.sh" >&2
  echo "Run: ${HOST_ROOT}/scripts/install_host_isaacsim.sh" >&2
  return 1 2>/dev/null || exit 1
fi