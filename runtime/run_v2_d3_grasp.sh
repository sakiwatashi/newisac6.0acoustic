#!/usr/bin/env bash
# D3 end-to-end grasp: g3 oracle-scaffold gate -> ABORT check -> three formal
# arms (closed / blind / open, 30 episodes each, same seed => paired targets).
#
# Spec: docs/plan_v2/d3/plan.md 步 3-4; runner: scripts/d3_grasp_runner.py
# (module docstring has the full design + pre-registered criteria text).
#
#   bash runtime/run_v2_d3_grasp.sh                # g3 gate, then three arms
#   bash runtime/run_v2_d3_grasp.sh --gates-only   # g3 gate only (plan.md 步 4)
#
# Resume: an arm whose episodes.csv already exists is skipped (delete the
# mode directory to force a re-run). g3 always re-runs unless --skip-g3.
set -u

ROOT=/home/lab109/song/isaacsim6.0
ISAACSIM="$ROOT/app/python.sh"
SCRIPT="$ROOT/scripts/d3_grasp_runner.py"
BASE_OUT="$ROOT/runtime/outputs/v2_d3_grasp"
LOG="$BASE_OUT/run.log"
G3_MIN_SUCCESS=8

GATES_ONLY=0
SKIP_G3=0
for a in "$@"; do
  case "$a" in
    --gates-only) GATES_ONLY=1 ;;
    --skip-g3)    SKIP_G3=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

mkdir -p "$BASE_OUT"
echo "=== run_v2_d3_grasp.sh $(date -Is) gates_only=$GATES_ONLY skip_g3=$SKIP_G3 ===" | tee -a "$LOG"

if [ "$SKIP_G3" -eq 0 ]; then
  echo "--- g3 (oracle scaffold, quarantined under gates/g3_scaffold) ---" | tee -a "$LOG"
  "$ISAACSIM" "$SCRIPT" --mode g3 --output-dir "$BASE_OUT" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    echo "ABORT: g3 runner exited rc=$rc. Diagnose via $LOG (common causes:" | tee -a "$LOG"
    echo "  finger prim discovery failure -> runner prints the gripper subtree;" | tee -a "$LOG"
    echo "  missing bar_calibration.json -> run gates adjudication first)." | tee -a "$LOG"
    exit "$rc"
  fi
  G3_JSON="$BASE_OUT/gates/g3_scaffold/g3_summary.json"
  # AMENDED gate (decisions.md D-12, 2026-07-10, before any formal run):
  # maneuver validity -- complete sequence, zero posture violations, zero
  # physics NaN, pre-close bar disturbance < 5 mm. Lift success RECORDED only.
  G3_OK=$(python3 - "$G3_JSON" <<'PYEOF'
import json, math, sys
s = json.load(open(sys.argv[1]))
trials = s.get("trials", [])
viol = sum(t.get("posture_violations_advance", 0) + t.get("posture_violations_lift", 0) for t in trials)
nan = sum(1 for t in trials if t.get("physics_nan"))
incomplete = sum(1 for t in trials if t.get("reason") != "completed")
disturbed = 0
for t in trials:
    pre = t.get("bar_pre_grasp")
    bx = t.get("bar_x_true")
    if pre and bx is not None:
        d = math.sqrt((pre[0]-bx)**2 + pre[1]**2 + (pre[2]-0.46)**2)
        if d > 0.005:
            disturbed += 1
ok = viol == 0 and nan == 0 and incomplete == 0 and disturbed == 0 and len(trials) >= 10
print(f"g3 maneuver: n={len(trials)} incomplete={incomplete} posture_viol={viol} "
      f"physics_nan={nan} bar_disturbed_pre_close={disturbed} "
      f"(lift_success={s.get('n_success')}/{s.get('n_trials')}, RECORDED not gated) "
      f"-> {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
PYEOF
)
  rc=$?
  echo "$G3_OK" | tee -a "$LOG"
  if [ "$rc" -ne 0 ]; then
    echo "ABORT: g3 maneuver gate FAILED (D-12 amended criterion). Formal arms NOT" | tee -a "$LOG"
    echo "started. Diagnose via $G3_JSON." | tee -a "$LOG"
    exit 3
  fi
fi

if [ "$GATES_ONLY" -eq 1 ]; then
  echo "--gates-only: stopping after g3 (lock TOL_ALIGN_X_M from its offset sweep" | tee -a "$LOG"
  echo "before starting the formal arms; plan.md 步 4)." | tee -a "$LOG"
  exit 0
fi

for ARM in closed blind open; do
  if [ -f "$BASE_OUT/$ARM/episodes.csv" ]; then
    echo "--- $ARM: episodes.csv exists, skipping (resume semantics) ---" | tee -a "$LOG"
    continue
  fi
  echo "--- $ARM (30 episodes) $(date -Is) ---" | tee -a "$LOG"
  "$ISAACSIM" "$SCRIPT" --mode "$ARM" --output-dir "$BASE_OUT" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    echo "ABORT: $ARM runner exited rc=$rc; later arms not started. Re-running this" | tee -a "$LOG"
    echo "shell resumes from the first arm without an episodes.csv." | tee -a "$LOG"
    exit "$rc"
  fi
done

echo "=== all requested modes complete $(date -Is) ===" | tee -a "$LOG"
echo "Next: python3 scripts/analyze_d3_grasp.py --scan-dir $BASE_OUT (plan.md 步 5-6)" | tee -a "$LOG"
