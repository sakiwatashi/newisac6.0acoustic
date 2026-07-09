#!/usr/bin/env bash
# 差分波形校正掃描 — 用差分消除固定反射（桌面、地板），萃取純目標回波
# 使用 material-condition C (高吸音: PRA=0.70, fabric+none) 消除房間殘響
# 每個 trial 放在獨立子目錄，方便逐個確認
# 用法: bash runtime/run_differential_calibration.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_dynamic_approach_calibration_sweep.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/differential_calibration_v1
SEED=20260629
MATERIAL=C

# trial_id → wrench_x: 18=0.717 20=0.746 0=1.052 4=1.111 8=1.170 12=1.229 16=1.288
TRIAL_IDS=(18 20 0 4 8 12 16)

mkdir -p "$BASE_OUT"
echo "=== 差分波形校正掃描 (material=$MATERIAL) — $(date) ===" | tee "$BASE_OUT/run.log"

for TID in "${TRIAL_IDS[@]}"; do
    OUT="$BASE_OUT/trial_${TID}"
    echo ""
    echo "--- trial_id=${TID} material=${MATERIAL} → ${OUT} ---" | tee -a "$BASE_OUT/run.log"
    $ISAACSIM "$SCRIPT" \
        --trial-id "$TID" \
        --spawn-seed "$SEED" \
        --output-dir "$OUT" \
        --material-condition "$MATERIAL" \
        --overwrite \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "trial_id=${TID} 完成" | tee -a "$BASE_OUT/run.log"
done

echo ""
echo "=== 所有 trial 完成，合併 CSV ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib, sys
from collections import Counter

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/differential_calibration_v1")
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

out_path = base / "differential_calibration_combined.csv"
fieldnames = list(all_rows[0].keys())
with out_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(all_rows)
print(f"Scritto {len(all_rows)} righe → {out_path}")

def pearson_r(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs)/n, sum(ys)/n
    num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    den = math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
    return num/den if den > 0 else float("nan")

def analyze_col(col, all_rows, label):
    valid = [(float(r[col]), float(r["oracle_distance_m"]))
             for r in all_rows
             if r.get(col) not in (None,"","nan","-1") and r.get("oracle_distance_m") not in (None,"","nan")]
    if not valid:
        print(f"  {label}: 無有效資料")
        return
    xs, ys = zip(*valid)
    r = pearson_r(list(xs), list(ys))
    print(f"  {label}: n={len(valid)} min={min(xs):.3f} max={max(xs):.3f} Pearson_r={r:.4f}")

print("\n=== 差分特徵 vs oracle_distance_m ===")
analyze_col("diff_early_energy",       all_rows, "diff_early_energy      (25%)")
analyze_col("diff_ultra_early_energy", all_rows, "diff_ultra_early_energy(10%)")
analyze_col("diff_peak_sample_idx",    all_rows, "diff_peak_sample_idx        ")
analyze_col("diff_early_peak_sample_idx", all_rows, "diff_early_peak_sample_idx  ")

print("\n=== 原始特徵對比 ===")
analyze_col("primary_sgw_early_energy",       all_rows, "raw_early_energy       (25%)")
analyze_col("primary_sgw_ultra_early_energy", all_rows, "raw_ultra_early_energy (10%)")

# distribution of diff_peak_sample_idx
dpi = [int(float(r["diff_peak_sample_idx"])) for r in all_rows
       if r.get("diff_peak_sample_idx") not in (None,"","nan","-1")]
if dpi:
    cnt = Counter(dpi)
    print(f"\ndiff_peak_sample_idx 分布: {dict(sorted(cnt.items()))}")

PYEOF

echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
