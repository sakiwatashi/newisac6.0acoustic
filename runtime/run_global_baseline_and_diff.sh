#!/usr/bin/env bash
# 全局基準差分掃描 — 先錄製乾淨基準波形，再用全局差分消除固定反射
# 先跑一次 baseline 掃描（無扳手），再跑 7 個 trial，每個 trial 使用同一基準
# 用法: bash runtime/run_global_baseline_and_diff.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_dynamic_approach_calibration_sweep.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/global_baseline_diff_v1
SEED=20260629
MATERIAL=C
BASELINE_TRIAL_ID=16
BASELINE_NPY=$BASE_OUT/baseline/baseline_waveforms.npy

# trial_id → wrench_x: 18=0.717 20=0.746 0=1.052 4=1.111 8=1.170 12=1.229 16=1.288
TRIAL_IDS=(18 20 0 4 8 12 16)

mkdir -p "$BASE_OUT"
echo "=== 全局基準差分掃描 (material=$MATERIAL) — $(date) ===" | tee "$BASE_OUT/run.log"

# ── 步驟 1: 基準掃描（無扳手，記錄乾淨房間波形）──────────────────────────────
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- [BASELINE] trial_id=${BASELINE_TRIAL_ID} baseline-mode → ${BASE_OUT}/baseline ---" | tee -a "$BASE_OUT/run.log"
mkdir -p "$BASE_OUT/baseline"
$ISAACSIM "$SCRIPT" \
    --trial-id "$BASELINE_TRIAL_ID" \
    --spawn-seed "$SEED" \
    --output-dir "$BASE_OUT/baseline" \
    --material-condition "$MATERIAL" \
    --baseline-mode \
    --save-baseline-npy "$BASELINE_NPY" \
    --overwrite \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "[BASELINE] 完成 → $BASELINE_NPY" | tee -a "$BASE_OUT/run.log"

# ── 步驟 2: 正式掃描（7 個 trial，使用全局基準差分）──────────────────────────
echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 開始正式掃描（使用 baseline-npy: $BASELINE_NPY）===" | tee -a "$BASE_OUT/run.log"

for TID in "${TRIAL_IDS[@]}"; do
    OUT="$BASE_OUT/trial_${TID}"
    echo "" | tee -a "$BASE_OUT/run.log"
    echo "--- trial_id=${TID} material=${MATERIAL} → ${OUT} ---" | tee -a "$BASE_OUT/run.log"
    $ISAACSIM "$SCRIPT" \
        --trial-id "$TID" \
        --spawn-seed "$SEED" \
        --output-dir "$OUT" \
        --material-condition "$MATERIAL" \
        --baseline-npy "$BASELINE_NPY" \
        --overwrite \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "trial_id=${TID} 完成" | tee -a "$BASE_OUT/run.log"
done

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 所有 trial 完成，合併 CSV ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib, sys
from collections import Counter

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/global_baseline_diff_v1")
all_rows = []
for csv_path in sorted(base.glob("trial_*/dynamic_approach_calibration_sweep.csv")):
    trial_id = int(csv_path.parent.name.split("_")[1])
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            row["trial_id"] = trial_id
            all_rows.append(row)

if not all_rows:
    print("ERROR: no CSV found", file=sys.stderr)
    sys.exit(1)

out_path = base / "global_baseline_diff_combined.csv"
fieldnames = list(all_rows[0].keys())
with out_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(all_rows)
print(f"Scritto {len(all_rows)} righe → {out_path}")

def pearson_r(xs, ys):
    n = len(xs)
    if n < 2: return float("nan")
    mx, my = sum(xs)/n, sum(ys)/n
    num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    den = math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
    return num/den if den > 0 else float("nan")

def analyze(col, rows, label):
    valid = [(float(r[col]), float(r["oracle_distance_m"]))
             for r in rows
             if r.get(col) not in (None,"","nan","-1") and r.get("oracle_distance_m") not in (None,"","nan")]
    if not valid:
        print(f"  {label}: 無資料"); return
    xs, ys = zip(*valid)
    print(f"  {label}: n={len(valid)} r={pearson_r(list(xs),list(ys)):.4f}")

print("\n=== 全局差分特徵 ===")
analyze("global_diff_early_energy",          all_rows, "global_diff_early(25%)     ")
analyze("global_diff_ultra_early_energy",    all_rows, "global_diff_ultra_early(10%)")
analyze("global_diff_early_peak_sample_idx", all_rows, "global_diff_early_peak_idx  ")
print("\n=== 原始對比 ===")
analyze("primary_sgw_early_energy",          all_rows, "raw_early(25%)              ")
analyze("primary_sgw_ultra_early_energy",    all_rows, "raw_ultra_early(10%)        ")
PYEOF

echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
