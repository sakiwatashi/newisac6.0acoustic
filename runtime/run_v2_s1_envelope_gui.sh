#!/usr/bin/env bash
# GUI twin of run_v2_s1_envelope.sh — formal paired_capture_runner unchanged.
# Opens Isaac viewport via scripts/gui_formal_exec.py.
#
# Default: first available S1 cell (smoke view). Full 52-cell formal:
#   FORMAL=1 bash runtime/run_v2_s1_envelope_gui.sh
#
#   bash runtime/run_v2_s1_envelope_gui.sh
#   CELL_ID=s1_A_d0p5_sz0p05 bash runtime/run_v2_s1_envelope_gui.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ISAACSIM="$ROOT/app/python.sh"
EXEC="$ROOT/scripts/gui_formal_exec.py"
RUNNER="$ROOT/scripts/paired_capture_runner.py"
CELLS_DIR="$ROOT/docs/plan_v2/s1_cells"
BASE_OUT="${BASE_OUT:-$ROOT/runtime/outputs/v2_s1_envelope_gui}"
FORMAL="${FORMAL:-0}"
# Window must paint + stay open: formal paired_capture finishes in ~4s otherwise.
export GUI_PREVIEW_S="${GUI_PREVIEW_S:-10}"   # start wait (after cube exists)
export GUI_HOLD_S="${GUI_HOLD_S:-15}"         # end wait
export GUI_FOCUS="${GUI_FOCUS:-0.15,0.0,0.65}"   # S1 default cell target near sensor
# 4cm cube is invisible at robot-scale 2.5m camera — keep close for S1
export GUI_CAM_DIST="${GUI_CAM_DIST:-0.55}"
mkdir -p "$BASE_OUT"
LOG="$BASE_OUT/run.log"
echo "=== V2 S1 envelope GUI $(date -Is) formal=$FORMAL ===" | tee -a "$LOG"
echo "BASE_OUT=$BASE_OUT (headless formal stays at runtime/outputs/v2_s1_envelope)" | tee -a "$LOG"
echo "GUI_PREVIEW_S=$GUI_PREVIEW_S GUI_HOLD_S=$GUI_HOLD_S GUI_FOCUS=$GUI_FOCUS GUI_CAM_DIST=$GUI_CAM_DIST DISPLAY=${DISPLAY:-unset}" | tee -a "$LOG"

run_cell() {
  local J="$1"
  local cell_id
  cell_id="$(basename "$J" .json)"
  if [ -f "$BASE_OUT/$cell_id/cell_result.json" ]; then
    echo "SKIP $cell_id" | tee -a "$LOG"
    return 0
  fi
  echo "--- RUN GUI $cell_id ---" | tee -a "$LOG"
  bash "$ISAACSIM" "$EXEC" "$RUNNER" \
    --cell-json "$J" \
    --output-dir "$BASE_OUT" \
    2>&1 | tee -a "$LOG"
}

if [ "$FORMAL" = "1" ]; then
  for J in "$CELLS_DIR"/*.json; do
    [ -e "$J" ] || continue
    base="$(basename "$J")"
    [ "$base" = "generate_cells.py" ] && continue
    run_cell "$J"
  done
  python3 "$ROOT/scripts/analyze_envelope.py" --scan-dir "$BASE_OUT" 2>&1 | tee -a "$LOG"
else
  if [ -n "${CELL_JSON:-}" ]; then
    J="$CELL_JSON"
  elif [ -n "${CELL_ID:-}" ]; then
    J="$CELLS_DIR/${CELL_ID}.json"
  else
    J="$(ls "$CELLS_DIR"/*.json 2>/dev/null | head -n1 || true)"
  fi
  if [ -z "${J:-}" ] || [ ! -f "$J" ]; then
    echo "No S1 cell json found under $CELLS_DIR" >&2
    exit 1
  fi
  run_cell "$J"
  echo "Smoke done. Full 52-cell GUI: FORMAL=1 bash runtime/run_v2_s1_envelope_gui.sh" | tee -a "$LOG"
fi
echo "=== S1 GUI complete $(date -Is) ===" | tee -a "$LOG"
