#!/usr/bin/env bash
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ROOT="${HOST_ROOT}/app"
DOWNLOAD_DIR="${HOST_ROOT}/downloads"
ZIP_NAME="isaac-sim-standalone-6.0.0-linux-aarch64.zip"

echo "Isaac Sim 6.0 host install (isolated)"
echo "  root:      ${HOST_ROOT}"
echo "  app:       ${APP_ROOT}"
echo "  downloads: ${DOWNLOAD_DIR}"
echo

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "This script is for DGX Spark aarch64 only." >&2
  exit 1
fi

if [[ -x "${APP_ROOT}/isaac-sim.sh" ]]; then
  echo "Already installed: ${APP_ROOT}/isaac-sim.sh"
  exit 0
fi

mkdir -p "${APP_ROOT}" "${DOWNLOAD_DIR}"

ZIP_PATH="${DOWNLOAD_DIR}/${ZIP_NAME}"
if [[ ! -f "${ZIP_PATH}" ]]; then
  cat <<EOF
Missing installer zip:
  ${ZIP_PATH}

Download manually from NVIDIA Isaac Sim 6.0 Latest Release:
  https://docs.isaacsim.omniverse.nvidia.com/6.0.0/installation/download.html

Use the Linux aarch64 standalone package:
  ${ZIP_NAME}

Official quick-install notes:
  - keep ~50 GB free during download + unzip
  - installed app is ~17 GB
  - shader/runtime cache grows under ${HOST_ROOT}/runtime only
EOF
  exit 2
fi

command -v unzip >/dev/null 2>&1 || { echo "Install unzip first: sudo apt install unzip" >&2; exit 2; }

AVAIL_GB="$(df -BG "${HOST_ROOT}" | awk 'NR==2 {gsub(/G/,"",$4); print $4}')"
if [[ "${AVAIL_GB}" -lt 60 ]]; then
  echo "Warning: less than 60 GB free on ${HOST_ROOT} (available: ${AVAIL_GB}G)." >&2
fi

echo "Extracting ${ZIP_NAME} into ${APP_ROOT} ..."
unzip -q "${ZIP_PATH}" -d "${APP_ROOT}"

if [[ ! -x "${APP_ROOT}/post_install.sh" ]]; then
  # Some zips unpack into a nested folder; normalize if needed.
  nested="$(find "${APP_ROOT}" -maxdepth 1 -type f -name isaac-sim.sh | head -1 || true)"
  if [[ -z "${nested}" ]]; then
    echo "Could not find isaac-sim.sh after unzip. Check zip layout." >&2
    exit 1
  fi
fi

cd "${APP_ROOT}"
./post_install.sh

echo
echo "Install complete."
echo "Next:"
echo "  ${HOST_ROOT}/scripts/run_host_compatibility_check.sh"
echo "  ${HOST_ROOT}/scripts/run_host_acoustic_sample.sh --test"