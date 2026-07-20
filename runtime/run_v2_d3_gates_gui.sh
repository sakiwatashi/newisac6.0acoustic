#!/usr/bin/env bash
# GUI twin of run_v2_d3_gates.sh — d3_gates_runner.py unchanged.
#
# Default: --smoke on g1 only (quick viewport). Full four modes:
#   FORMAL=1 bash runtime/run_v2_d3_gates_gui.sh
#   FORMAL=1 bash runtime/run_v2_d3_gates_gui.sh --smoke   # formal sequence, smoke sizes
set -euo pipefail

# GUI window: wait before work / after finish (gui_formal_exec defaults)
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"
export GUI_HOLD_S="${GUI_HOLD_S:-15}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ISAACSIM="$ROOT/app/python.sh"
EXEC="$ROOT/scripts/gui_formal_exec.py"
SCRIPT="$ROOT/scripts/d3_gates_runner.py"
FORMAL="${FORMAL:-0}"
SMOKE_FLAG="--smoke"
BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_d3_gates_gui}"
for a in "$@"; do
  case "$a" in
    --smoke) SMOKE_FLAG="--smoke" ;;
    --no-smoke) SMOKE_FLAG="" ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done
if [ "$FORMAL" = "1" ] && [ -z "${BASE_OUT_SET:-}" ]; then
  if [ -n "$SMOKE_FLAG" ]; then
    BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_d3_gates_gui_smoke}"
  else
    BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_d3_gates_gui}"
  fi
fi
mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"
echo "=== V2 D3 gates GUI $(date -Is) formal=$FORMAL smoke=${SMOKE_FLAG:-no} ===" | tee -a "$LOG"

run_mode() {
  local mode="$1" result_rel="$2"
  local mode_dir="$BASE_OUT/$mode"
  local result_file="$mode_dir/$result_rel"
  if [ -f "$result_file" ] && [ -f "$mode_dir/meta.json" ]; then
    echo "[SKIP] mode=$mode" | tee -a "$LOG"
    return 0
  fi
  mkdir -p "$mode_dir"
  echo "[RUN GUI] mode=$mode" | tee -a "$LOG"
  # shellcheck disable=SC2086
  bash "$ISAACSIM" "$EXEC" "$SCRIPT" --mode "$mode" --output-dir "$BASE_OUT" $SMOKE_FLAG \
    2>&1 | tee "$mode_dir/stdout.log" | tee -a "$LOG"
}

if [ "$FORMAL" = "1" ]; then
  run_mode g1 points.csv
  run_mode g2 points.csv
  run_mode m3b_target cells.csv
  run_mode m3b_sensor cells.csv
else
  run_mode g1 points.csv
  echo "Smoke done (g1 only). Full four modes: FORMAL=1 bash $0" | tee -a "$LOG"
fi
echo "=== D3 gates GUI complete $(date -Is) ===" | tee -a "$LOG"
