#!/usr/bin/env bash
# 實驗 1：Cube 尺寸掃描
# 目標：找出 WPM 最小可偵測目標尺寸
# 測試尺寸：0.05m / 0.10m / 0.20m（參考） / 0.30m / 0.50m
# 距離：0.20m → 1.50m，20 步
# 用法: bash runtime/run_armfree_cube_size_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfree_acoustic_proximity_test.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_cube_size_sweep

mkdir -p "$BASE_OUT"
echo "=== Cube 尺寸掃描實驗 — $(date) ===" | tee "$BASE_OUT/run.log"
echo "距離範圍: 0.20–1.50m (20步)" | tee -a "$BASE_OUT/run.log"

for SIZE in 0.05 0.10 0.20 0.30 0.50; do
    OUT="$BASE_OUT/cube_${SIZE}m"
    echo "" | tee -a "$BASE_OUT/run.log"
    echo "--- Cube size=${SIZE}m → ${OUT} ---" | tee -a "$BASE_OUT/run.log"
    $ISAACSIM "$SCRIPT" \
        --min-dist 0.20 \
        --max-dist 1.50 \
        --n-steps 20 \
        --n-settle 12 \
        --n-measure 6 \
        --cube-size "$SIZE" \
        --center-freq 40000 \
        --mount-spacing 0.10 \
        --az-span 90 \
        --el-span 90 \
        --output-dir "$OUT" \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "cube_size=${SIZE}m 完成" | tee -a "$BASE_OUT/run.log"
done

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整各尺寸結果 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_cube_size_sweep")

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

print(f"\n{'尺寸':>8}  {'r(peak,dist)':>13}  {'RMSE':>8}  {'有效步數':>8}  {'判定'}")
print("-" * 60)
for size_dir in sorted(base.glob("cube_*m")):
    csv_path = size_dir / "armfree_proximity_sweep.csv"
    if not csv_path.exists():
        continue
    rows = list(csv.DictReader(csv_path.open()))
    dists  = [float(r["oracle_distance_m"]) for r in rows]
    peaks  = [float(r["peak_sample_idx"]) for r in rows]
    inf_ds = [float(r["inferred_dist_m"]) for r in rows]
    valid  = [(d, i) for d, i in zip(dists, inf_ds)
              if not math.isnan(i)]
    r_val  = pearson_r(dists, peaks)
    rmse   = math.sqrt(sum((d-i)**2 for d,i in valid)/len(valid)) if valid else float("nan")
    label  = size_dir.name.replace("cube_", "").replace("m", "")
    flag   = "✅ 可偵測" if abs(r_val) > 0.90 else ("⚠️ 部分" if abs(r_val) > 0.60 else "❌ 不可偵測")
    print(f"{label:>8}m  {r_val:>+13.4f}  {rmse:>8.4f}  {len(valid):>8}  {flag}")

PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
