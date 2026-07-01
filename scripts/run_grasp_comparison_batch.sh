#!/usr/bin/env bash
# Phase C batch: closed-loop vs open-loop baseline across trials.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACSIM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BATCH_ID="${BATCH_ID:-grasp_comparison_v1}"
TRIAL_START="${TRIAL_START:-0}"
TRIAL_COUNT="${TRIAL_COUNT:-3}"
SPAWN_SEED="${SPAWN_SEED:-20260629}"
GUI="${GUI:-0}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ISAACSIM_ROOT}/runtime/outputs/${BATCH_ID}}"
SCENE_ROOT="${SCENE_ROOT:-${ISAACSIM_ROOT}/runtime/scenes/${BATCH_ID}}"

mkdir -p "${OUTPUT_ROOT}" "${SCENE_ROOT}"

closed_pass=0
closed_fail=0
open_pass=0
open_fail=0
closed_grasp_success=0
open_grasp_success=0

echo "Grasp comparison batch: ${BATCH_ID}"
echo "Trials: ${TRIAL_START}..$((TRIAL_START + TRIAL_COUNT - 1)) seed=${SPAWN_SEED}"
echo "Output root: ${OUTPUT_ROOT}"

for trial_id in $(seq "${TRIAL_START}" $((TRIAL_START + TRIAL_COUNT - 1))); do
  echo "--- trial=${trial_id} closed_loop ---"
  closed_dir="${OUTPUT_ROOT}/closed_loop_trial_${trial_id}"
  closed_stage="${SCENE_ROOT}/closed_loop_trial_${trial_id}.usda"
  if GUI="${GUI}" CLAIM_MODE="${CLAIM_MODE:-scaffold}" TRIAL_ID="${trial_id}" SPAWN_SEED="${SPAWN_SEED}" \
    OUTPUT_DIR="${closed_dir}" OUTPUT_STAGE="${closed_stage}" \
    bash "${SCRIPT_DIR}/run_host_ultrasonic_closed_loop_grasp_smoke.sh"; then
    closed_pass=$((closed_pass + 1))
    echo "PASS closed_loop trial=${trial_id}"
  else
    closed_fail=$((closed_fail + 1))
    echo "FAIL closed_loop trial=${trial_id}"
  fi

  echo "--- trial=${trial_id} open_loop_baseline ---"
  open_dir="${OUTPUT_ROOT}/open_loop_trial_${trial_id}"
  open_stage="${SCENE_ROOT}/open_loop_trial_${trial_id}.usda"
  if GUI="${GUI}" TRIAL_ID="${trial_id}" SPAWN_SEED="${SPAWN_SEED}" \
    OUTPUT_DIR="${open_dir}" OUTPUT_STAGE="${open_stage}" \
    bash "${SCRIPT_DIR}/run_host_open_loop_grasp_baseline_smoke.sh"; then
    open_pass=$((open_pass + 1))
    echo "PASS open_loop_baseline trial=${trial_id}"
  else
    open_fail=$((open_fail + 1))
    echo "FAIL open_loop_baseline trial=${trial_id}"
  fi
done

summary_json="${OUTPUT_ROOT}/grasp_comparison_summary.json"
summary_txt="${OUTPUT_ROOT}/grasp_comparison_summary.txt"

python3 - "${OUTPUT_ROOT}" "${BATCH_ID}" "${SPAWN_SEED}" "${TRIAL_START}" "${TRIAL_COUNT}" \
  "${closed_pass}" "${closed_fail}" "${open_pass}" "${open_fail}" <<'PY'
import json
import sys
from pathlib import Path

output_root = Path(sys.argv[1])
batch_id = sys.argv[2]
spawn_seed = int(sys.argv[3])
trial_start = int(sys.argv[4])
trial_count = int(sys.argv[5])
closed_pass = int(sys.argv[6])
closed_fail = int(sys.argv[7])
open_pass = int(sys.argv[8])
open_fail = int(sys.argv[9])

def load_trial(mode_dir: str, trial_id: int) -> dict:
    summary_path = output_root / f"{mode_dir}_trial_{trial_id}" / "ultrasonic_closed_loop_grasp_summary.json"
    if not summary_path.exists():
        return {"trial_id": trial_id, "missing": True}
    with summary_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return {
        "trial_id": trial_id,
        "success": data.get("success"),
        "mode": data.get("mode"),
        "approach_reason": data.get("approach_reason"),
        "terminal_reason": data.get("terminal_reason"),
        "approach_steps": data.get("approach_steps"),
        "runtime_s": data.get("runtime_s"),
        "final_oracle_distance_m": data.get("final_oracle_distance_m"),
    }

trials = []
closed_grasp_success = 0
open_grasp_success = 0
for trial_id in range(trial_start, trial_start + trial_count):
    closed_row = load_trial("closed_loop", trial_id)
    open_row = load_trial("open_loop", trial_id)
    if closed_row.get("success"):
        closed_grasp_success += 1
    if open_row.get("success"):
        open_grasp_success += 1
    trials.append({
        "trial_id": trial_id,
        "closed_loop": closed_row,
        "open_loop_baseline": open_row,
    })

payload = {
    "batch_id": batch_id,
    "spawn_seed": spawn_seed,
    "trial_start": trial_start,
    "trial_count": trial_count,
    "closed_loop": {"pass": closed_pass, "fail": closed_fail, "grasp_success": closed_grasp_success},
    "open_loop_baseline": {"pass": open_pass, "fail": open_fail, "grasp_success": open_grasp_success},
    "trials": trials,
}

summary_json = output_root / "grasp_comparison_summary.json"
summary_txt = output_root / "grasp_comparison_summary.txt"
with summary_json.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)

lines = [
    f"batch_id={batch_id}",
    f"spawn_seed={spawn_seed}",
    f"trials={trial_start}..{trial_start + trial_count - 1}",
    f"closed_loop_pass={closed_pass}",
    f"closed_loop_fail={closed_fail}",
    f"open_loop_pass={open_pass}",
    f"open_loop_fail={open_fail}",
    f"closed_loop_grasp_success={closed_grasp_success}",
    f"open_loop_grasp_success={open_grasp_success}",
    "",
    "trial_id | closed_success | closed_terminal | open_success | open_terminal | open_mode",
]
for row in trials:
    cl = row["closed_loop"]
    ol = row["open_loop_baseline"]
    lines.append(
        f"{row['trial_id']:8d} | {str(cl.get('success')):14} | {str(cl.get('terminal_reason')):15} | "
        f"{str(ol.get('success')):12} | {str(ol.get('terminal_reason')):13} | {ol.get('mode')}"
    )
summary_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {summary_json}")
print(f"Wrote {summary_txt}")
PY

echo "Batch complete:"
echo "  closed_loop: pass=${closed_pass} fail=${closed_fail}"
echo "  open_loop_baseline: pass=${open_pass} fail=${open_fail}"
eval "$(python3 - "${OUTPUT_ROOT}" "${TRIAL_START}" "${TRIAL_COUNT}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
start, count = int(sys.argv[2]), int(sys.argv[3])
def ok(mode, tid):
    p = root / f"{mode}_trial_{tid}" / "ultrasonic_closed_loop_grasp_summary.json"
    return p.exists() and json.loads(p.read_text()).get("success")
c = sum(ok("closed_loop", t) for t in range(start, start+count))
o = sum(ok("open_loop", t) for t in range(start, start+count))
print(f"echo \"  closed_loop_grasp_success={c}/{count}\"")
print(f"echo \"  open_loop_grasp_success={o}/{count}\"")
PY
)"
echo "Wrote ${summary_json}"
echo "Wrote ${summary_txt}"

if [[ "${closed_fail}" -gt 0 || "${open_fail}" -gt 0 ]]; then
  exit 1
fi