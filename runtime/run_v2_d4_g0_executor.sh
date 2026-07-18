#!/usr/bin/env bash
# D4 g0: oracle-scaffold executor smoke (friction probe by default).
# Spec: docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md §2.3
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/runtime/outputs/v2_d4_g0_executor}"
LOG="$OUT/run.log"
mkdir -p "$OUT"
echo "=== run_v2_d4_g0_executor $(date -Is) ===" | tee -a "$LOG"
# host python only launches orchestrator; Isaac is inside
python3 "$ROOT/scripts/d4_g0_executor_smoke.py" --output-dir "$OUT" "$@" 2>&1 | tee -a "$LOG"
exit ${PIPESTATUS[0]}
