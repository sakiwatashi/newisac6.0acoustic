#!/usr/bin/env bash
# D4 same-scene overnight: B policy approach+close inside d3 physics scene → weld/lift.
# Does NOT write into v2_d3_grasp_r3 or v2_d4_sm_grasp_n30.
#
#   bash runtime/run_v2_d4_same_scene_policy.sh              # n=90 long (default)
#   N_EP=5 bash runtime/run_v2_d4_same_scene_policy.sh       # short smoke
#   bash runtime/run_v2_d4_same_scene_policy.sh --smoke
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/runtime/outputs/v2_d4_same_scene_policy_n90}"
CKPT="${CHECKPOINT:-$ROOT/runtime/outputs/v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt}"
N_EP="${N_EP:-90}"
SEED="${SEED:-20260718}"
PY="${PY:-$ROOT/app/python.sh}"
SMOKE=0
for a in "$@"; do
  case "$a" in
    --smoke) SMOKE=1; N_EP=2; OUT="${OUT}_smoke" ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done
# refuse canonical dirs
case "$OUT" in
  *v2_d3_grasp_r3*|*v2_d4_sm_grasp_n30*)
    echo "ABORT: refuse output dir that collides with canon: $OUT" >&2
    exit 2
    ;;
esac
mkdir -p "$OUT"
LOG="$OUT/run.log"
echo "=== D4 same-scene policy $(date -Is) n=$N_EP seed=$SEED ===" | tee "$LOG"
echo "  OUT=$OUT" | tee -a "$LOG"
echo "  CKPT=$CKPT" | tee -a "$LOG"
echo "  claim: B policy approach+close in d3 scene; A weld/lift; not pure-reward" | tee -a "$LOG"

# r3 guard
if [[ -d "$ROOT/runtime/outputs/v2_d3_grasp_r3" ]]; then
  echo "  (D3 r3 present — will not touch)" | tee -a "$LOG"
fi

EXTRA=()
if [ "$SMOKE" -eq 1 ]; then EXTRA+=(--smoke); fi

bash "$PY" "$ROOT/scripts/d3_grasp_runner.py" \
  --mode closed \
  --output-dir "$OUT" \
  --n-episodes "$N_EP" \
  --seed "$SEED" \
  --standoff 0.35 \
  --step 0.05 \
  --max-steps "${MAX_STEPS:-60}" \
  --sensor-offset 0.25 \
  --target-x-min 1.00 \
  --target-x-max 1.15 \
  --weld-on-stall \
  --lift-up-step 0.002 \
  --policy-checkpoint "$CKPT" \
  --policy-max-step 0.05 \
  --policy-close-slack 0.10 \
  "${EXTRA[@]}" \
  2>&1 | tee -a "$LOG"

rc=${PIPESTATUS[0]}
echo "=== runner exit $rc $(date -Is) ===" | tee -a "$LOG"

# Offline summary (no GPU). d3 writes under OUT/closed/ when mode=closed.
python3 - <<PY 2>&1 | tee -a "$LOG"
import csv, json, math, pathlib, statistics
out = pathlib.Path("$OUT")
cands = [out / "episodes.csv", out / "closed" / "episodes.csv"]
ep = next((p for p in cands if p.is_file()), None)
if ep is None:
    # last resort
    found = list(out.glob("**/episodes.csv"))
    ep = found[0] if found else None
if ep is None or not ep.is_file():
    print("NO episodes.csv — fail", out)
    raise SystemExit(1)
print("using", ep)
rows = list(csv.DictReader(ep.open()))
n = len(rows)

def b(k):
    return [r.get(k, "").strip().lower() in ("1", "true", "yes") for r in rows]

def f(k):
    outv = []
    for r in rows:
        try:
            outv.append(float(r[k]))
        except Exception:
            outv.append(float("nan"))
    return outv

aligned = b("aligned")
lift = b("grasp_lift_success")
weld = b("weld_applied")
contact = b("contact_detected")
reasons = {}
for r in rows:
    reasons[r.get("reason", "?")] = reasons.get(r.get("reason", "?"), 0) + 1
n_al = sum(aligned)
lift_given = (sum(1 for a, L in zip(aligned, lift) if a and L) / n_al) if n_al else float("nan")
errs = [abs(x) for x in f("align_error_x") if math.isfinite(x)]
summary = {
    "track": "D4_same_scene_policy",
    "n": n,
    "rate_aligned": n_al / n if n else 0,
    "rate_lift": sum(lift) / n if n else 0,
    "rate_weld": sum(weld) / n if n else 0,
    "rate_contact": sum(contact) / n if n else 0,
    "rate_lift_given_align": lift_given,
    "mean_abs_align_err_m": statistics.mean(errs) if errs else float("nan"),
    "stop_reasons": reasons,
    "claim_boundary": (
        "Same-scene: policy approach+close + A weld/lift. "
        "Domain gap: B trained fixed-TCP coplanar; A is desk geometry. "
        "Not pure acoustic reward; not friction-only."
    ),
    "checkpoint": "$CKPT",
    "status": "PASS" if n > 0 else "FAIL",
}
(out / "same_scene_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
print(f"wrote {out / 'same_scene_summary.json'}")
PY

exit "$rc"
