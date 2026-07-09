#!/usr/bin/env bash
# 實驗 2：CloseRange 參數掃描
# 目標：消除近場（0.20-0.33m）的 peak 誤定位
# 預設值：closeIndirectAmpl=17.64，closeDirectAmpl=12.66
# 測試：降低 closeIndirectAmpl（間接近場放大器）到 1.0、0.5、0.1
# 也測試：closeDirectAmpl=0 極端情況
# 距離：0.15m → 0.60m，20 步（聚焦近場）
# 用法: bash runtime/run_armfree_closerange_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfree_acoustic_proximity_test.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_closerange_sweep

mkdir -p "$BASE_OUT"
echo "=== CloseRange 參數掃描實驗 — $(date) ===" | tee "$BASE_OUT/run.log"
echo "距離範圍: 0.15–0.60m (20步，聚焦近場)" | tee -a "$BASE_OUT/run.log"
echo "Cube size: 0.20m (fixed)" | tee -a "$BASE_OUT/run.log"

# 組合：(closeDirectAmpl, closeIndirectAmpl) 標籤
declare -A CONFIGS
CONFIGS["default"]=""
CONFIGS["indir_1p0"]="--close-indirect-ampl 1.0"
CONFIGS["indir_0p5"]="--close-indirect-ampl 0.5"
CONFIGS["indir_0p1"]="--close-indirect-ampl 0.1"
CONFIGS["dir_0_indir_0p1"]="--close-direct-ampl 0.0 --close-indirect-ampl 0.1"
CONFIGS["both_0"]="--close-direct-ampl 0.0 --close-indirect-ampl 0.0"

for LABEL in default indir_1p0 indir_0p5 indir_0p1 dir_0_indir_0p1 both_0; do
    EXTRA="${CONFIGS[$LABEL]}"
    OUT="$BASE_OUT/${LABEL}"
    echo "" | tee -a "$BASE_OUT/run.log"
    echo "--- config=${LABEL} extra_args='${EXTRA}' → ${OUT} ---" | tee -a "$BASE_OUT/run.log"
    $ISAACSIM "$SCRIPT" \
        --min-dist 0.15 \
        --max-dist 0.60 \
        --n-steps 20 \
        --n-settle 12 \
        --n-measure 6 \
        --cube-size 0.20 \
        --center-freq 40000 \
        --mount-spacing 0.10 \
        --az-span 90 \
        --el-span 90 \
        --output-dir "$OUT" \
        $EXTRA \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "config=${LABEL} 完成" | tee -a "$BASE_OUT/run.log"
done

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整各組參數結果 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_closerange_sweep")

def pearson_r(xs, ys):
    paired = [(x, y) for x, y in zip(xs, ys)
              if not (math.isnan(x) or math.isnan(y))]
    n = len(paired)
    if n < 2: return float("nan")
    xs2, ys2 = zip(*paired)
    mx, my = sum(xs2)/n, sum(ys2)/n
    num = sum((x-mx)*(y-my) for x,y in zip(xs2,ys2))
    den = math.sqrt(sum((x-mx)**2 for x in xs2)*sum((y-my)**2 for y in ys2))
    return num/den if den > 0 else float("nan")

ORDER = ["default", "indir_1p0", "indir_0p5", "indir_0p1", "dir_0_indir_0p1", "both_0"]

print(f"\n{'設定':>20}  {'r(peak,dist)':>13}  {'RMSE':>8}  {'有效步數':>8}  {'判定'}")
print("-" * 70)
for label in ORDER:
    csv_path = base / label / "armfree_proximity_sweep.csv"
    if not csv_path.exists():
        print(f"{label:>20}  (無資料)")
        continue
    rows = list(csv.DictReader(csv_path.open()))
    dists  = [float(r["oracle_distance_m"]) for r in rows]
    peaks  = [float(r["peak_sample_idx"])   for r in rows]
    inf_ds = [float(r["inferred_dist_m"])   for r in rows]
    valid  = [(d, i) for d, i in zip(dists, inf_ds) if not math.isnan(i)]
    r_val  = pearson_r(dists, peaks)
    rmse   = math.sqrt(sum((d-i)**2 for d,i in valid)/len(valid)) if valid else float("nan")
    flag   = "✅ 可偵測" if abs(r_val) > 0.90 else ("⚠️ 部分" if abs(r_val) > 0.60 else "❌ 不可偵測")
    print(f"{label:>20}  {r_val:>+13.4f}  {rmse:>8.4f}  {len(valid):>8}  {flag}")

PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
