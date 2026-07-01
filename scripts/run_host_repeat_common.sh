#!/usr/bin/env bash
# Shared repeat-run helpers for smoke/batch runners (source, do not execute).
set -euo pipefail

run_host_resolve_repeat_count() {
  local gui="${1:-0}"
  if [[ -n "${REPEAT_COUNT:-}" ]]; then
    echo "${REPEAT_COUNT}"
    return 0
  fi
  # Default: one Sim launch. Use EPISODES in Python scripts for in-session repeats.
  echo "1"
}

run_host_repeat_aggregate_summaries() {
  local base_output_dir="$1"
  local repeat_count="$2"
  local summary_filename="$3"
  local experiment_label="$4"

  python3 - "${base_output_dir}" "${repeat_count}" "${summary_filename}" "${experiment_label}" <<'PY'
import json
import sys
from pathlib import Path

base_output_dir = Path(sys.argv[1])
repeat_count = int(sys.argv[2])
summary_filename = sys.argv[3]
experiment_label = sys.argv[4]

runs: list[dict] = []
success_count = 0
for run_idx in range(1, repeat_count + 1):
    if repeat_count > 1:
        run_dir = base_output_dir / f"run_{run_idx:03d}"
    else:
        run_dir = base_output_dir
    summary_path = run_dir / summary_filename
    row: dict = {"run_index": run_idx, "output_dir": str(run_dir), "missing": not summary_path.exists()}
    if summary_path.exists():
        with summary_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        row.update(
            {
                "success": data.get("success"),
                "terminal_reason": data.get("terminal_reason"),
                "approach_reason": data.get("approach_reason"),
                "trial_id": data.get("trial_id"),
                "runtime_s": data.get("runtime_s"),
            }
        )
        if row.get("success"):
            success_count += 1
    runs.append(row)

payload = {
    "experiment": experiment_label,
    "repeat_count": repeat_count,
    "success_count": success_count,
    "success_rate": (success_count / repeat_count) if repeat_count else 0.0,
    "runs": runs,
}
out_json = base_output_dir / "repeat_run_summary.json"
out_txt = base_output_dir / "repeat_run_summary.txt"
with out_json.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)

lines = [
    f"experiment={experiment_label}",
    f"repeat_count={repeat_count}",
    f"success_count={success_count}",
    f"success_rate={success_count}/{repeat_count}",
    "",
    "run | success | terminal_reason",
]
for row in runs:
    lines.append(
        f"{row['run_index']:3d} | {str(row.get('success')):7} | {row.get('terminal_reason', 'missing')}"
    )
out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {out_json}")
print(f"Wrote {out_txt}")
print(f"Repeat summary: {success_count}/{repeat_count} success")
PY
}