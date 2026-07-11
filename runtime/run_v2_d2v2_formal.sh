#!/usr/bin/env bash
# D2 formal three-arm experiment (2-D multilateration closed-loop approach).
# Spec: docs/plan_v2/D2V2_DESIGN_2026-07-10.md §3; runner header has criteria.
# Resume: an arm whose episodes.csv exists is skipped.
set -u
ROOT=/home/lab109/song/isaacsim6.0
ISAACSIM="$ROOT/app/python.sh"
SCRIPT="$ROOT/scripts/d2v2_formal_runner.py"
BASE_OUT="$ROOT/runtime/outputs/v2_d2v2_formal"
LOG="$BASE_OUT/run.log"
mkdir -p "$BASE_OUT"
echo "=== run_v2_d2v2_formal.sh $(date -Is) ===" | tee -a "$LOG"
for ARM in closed blind open; do
  if [ -f "$BASE_OUT/$ARM/episodes.csv" ]; then
    echo "--- $ARM: episodes.csv exists, skip (resume) ---" | tee -a "$LOG"
    continue
  fi
  echo "--- $ARM (30 episodes) $(date -Is) ---" | tee -a "$LOG"
  "$ISAACSIM" "$SCRIPT" --arm "$ARM" --output-dir "$BASE_OUT" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    echo "ABORT: $ARM exited rc=$rc; re-run this shell to resume." | tee -a "$LOG"
    exit "$rc"
  fi
done
echo "=== all arms complete $(date -Is) ===" | tee -a "$LOG"
echo "Next: python3 scripts/analyze_d2v2.py --scan-dir $BASE_OUT" | tee -a "$LOG"
