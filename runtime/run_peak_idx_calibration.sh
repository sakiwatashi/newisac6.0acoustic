#!/usr/bin/env bash
# 批次跑 peak_sample_idx 校正掃描
# 每個 trial 放在獨立子目錄，方便逐個確認
# 用法: bash runtime/run_peak_idx_calibration.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_dynamic_approach_calibration_sweep.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/peak_idx_calibration_v1
SEED=20260629

# trial_id → wrench_x: 18=0.717 20=0.746 0=1.052 4=1.111 8=1.170 12=1.229 16=1.288
TRIAL_IDS=(18 20 0 4 8 12 16)

mkdir -p "$BASE_OUT"
echo "=== peak_sample_idx 校正掃描 — $(date) ===" | tee "$BASE_OUT/run.log"

for TID in "${TRIAL_IDS[@]}"; do
    OUT="$BASE_OUT/trial_${TID}"
    echo ""
    echo "--- trial_id=${TID} → ${OUT} ---" | tee -a "$BASE_OUT/run.log"
    $ISAACSIM "$SCRIPT" \
        --trial-id "$TID" \
        --spawn-seed "$SEED" \
        --output-dir "$OUT" \
        --overwrite \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "trial_id=${TID} 完成" | tee -a "$BASE_OUT/run.log"
done

echo ""
echo "=== 所有 trial 完成，合併 CSV ===" | tee -a "$BASE_OUT/run.log"

# 合併所有 sweep CSV
python3 - <<'PYEOF'
import csv, pathlib, sys

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/peak_idx_calibration_v1")
all_rows = []
for csv_path in sorted(base.glob("trial_*/dynamic_approach_calibration_sweep.csv")):
    trial_id = int(csv_path.parent.name.split("_")[1])
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            row["trial_id"] = trial_id
            all_rows.append(row)

if not all_rows:
    print("ERROR: nessun CSV trovato", file=sys.stderr)
    sys.exit(1)

out_path = base / "peak_idx_calibration_combined.csv"
fieldnames = list(all_rows[0].keys())
with out_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(all_rows)

print(f"Scritto {len(all_rows)} righe → {out_path}")

# Statistiche rapide
import math
valid = [r for r in all_rows
         if r.get("primary_sgw_peak_sample_idx") not in (None, "", "nan")
         and r.get("oracle_distance_m") not in (None, "", "nan")]
print(f"Righe con peak_sample_idx valido: {len(valid)}/{len(all_rows)}")
if valid:
    idxs = [int(float(r["primary_sgw_peak_sample_idx"])) for r in valid]
    dists = [float(r["oracle_distance_m"]) for r in valid]
    print(f"peak_sample_idx range: {min(idxs)} – {max(idxs)}")
    print(f"oracle_distance_m range: {min(dists):.3f} – {max(dists):.3f} m")
PYEOF

echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
