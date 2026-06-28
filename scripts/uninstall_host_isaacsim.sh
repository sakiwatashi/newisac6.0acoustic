#!/usr/bin/env bash
set -euo pipefail

HOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "This removes ONLY host-isolated Isaac Sim files under:"
echo "  ${HOST_ROOT}/app"
echo "  ${HOST_ROOT}/downloads"
echo "  ${HOST_ROOT}/runtime"
echo "  ${HOST_ROOT}/logs"
echo
echo "It will NOT touch:"
echo "  /home/lab109/song/isaac-sim-docker"
echo "  /home/lab109/docker/isaac-sim"
echo "  /home/lab109/song/isaac_acoustic_research"
echo "  system NVIDIA driver"
echo
read -r -p "Type REMOVE to continue: " confirm
if [[ "${confirm}" != "REMOVE" ]]; then
  echo "Cancelled."
  exit 1
fi

rm -rf "${HOST_ROOT}/app"/* "${HOST_ROOT}/runtime"/* "${HOST_ROOT}/logs"/*
echo "Host Isaac Sim isolated install removed."