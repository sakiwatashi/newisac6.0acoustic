#!/usr/bin/env bash
# 實驗：固定手臂 + 移動障礙物
# 核心問題：手臂 mesh 在場景中時，WPM 能否偵測障礙物距離？
#
# 測試組合：
#   - arm-home  + sphere r=0.05m  （主測試：手臂直立）
#   - arm-reach_forward + sphere r=0.05m  （壓力測試：手臂伸向+X方向）
#   - arm-home  + sphere r=0.10m  （較大目標）
#
# 與 arm-free 基準對比：
#   arm-free sphere r=0.05m → r=+0.9992（已確認）
#   arm-free sphere r=0.10m → r=+0.9997（已確認）
#
# 用法: bash runtime/run_armfixed_proximity_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfixed_sphere_proximity_test.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfixed_proximity_sweep

mkdir -p "$BASE_OUT"
echo "=== 固定手臂 + 移動障礙物實驗 — $(date) ===" | tee "$BASE_OUT/run.log"
echo "距離範圍: 0.20–1.50m (20步)" | tee -a "$BASE_OUT/run.log"
echo "arm-free 基準: sphere r=0.05m r=+0.9992, r=0.10m r=+0.9997" | tee -a "$BASE_OUT/run.log"

# 測試 1：home 姿態 + sphere r=0.05m（手臂直立，不遮擋+X軸）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- arm=home  sphere r=0.05m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --arm-pose home \
    --geometry sphere \
    --geom-radius 0.05 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/home_sphere_r0.05m" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "home+sphere_r0.05m 完成" | tee -a "$BASE_OUT/run.log"

# 測試 2：home 姿態 + sphere r=0.10m
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- arm=home  sphere r=0.10m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --arm-pose home \
    --geometry sphere \
    --geom-radius 0.10 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/home_sphere_r0.10m" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "home+sphere_r0.10m 完成" | tee -a "$BASE_OUT/run.log"

# 測試 3：reach_forward 姿態 + sphere r=0.05m（手臂伸向+X，壓力測試）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- arm=reach_forward  sphere r=0.05m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --arm-pose reach_forward \
    --geometry sphere \
    --geom-radius 0.05 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/reach_forward_sphere_r0.05m" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "reach_forward+sphere_r0.05m 完成" | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整結果（對比 arm-free 基準）===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/armfixed_proximity_sweep")

# arm-free 基準（已確認）
ARMFREE_BASELINE = {
    "sphere_r0.05m": 0.9992,
    "sphere_r0.10m": 0.9997,
}

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

ORDER = [
    ("home_sphere_r0.05m",        "arm-free sphere r=0.05m", 0.9992),
    ("home_sphere_r0.10m",        "arm-free sphere r=0.10m", 0.9997),
    ("reach_forward_sphere_r0.05m", "arm-free sphere r=0.05m", 0.9992),
]

print(f"\n{'場景':>30}  {'r(peak,dist)':>13}  {'RMSE':>8}  {'n':>4}  {'vs arm-free':>12}  {'判定'}")
print("-" * 85)
for label, baseline_label, baseline_r in ORDER:
    csv_path = base / label / "armfixed_proximity_sweep.csv"
    if not csv_path.exists():
        print(f"{label:>30}  (無資料)")
        continue
    rows = list(csv.DictReader(csv_path.open()))
    dists  = [float(r["oracle_distance_m"]) for r in rows]
    peaks  = [float(r["peak_sample_idx"])   for r in rows]
    inf_ds = [float(r["inferred_dist_m"])   for r in rows]
    valid  = [(dv, iv) for dv, iv in zip(dists, inf_ds) if not math.isnan(iv)]
    r_val  = pearson_r(dists, peaks)
    rmse   = math.sqrt(sum((dv-iv)**2 for dv,iv in valid)/len(valid)) if valid else float("nan")
    delta  = r_val - baseline_r
    flag   = "✅ 可偵測" if abs(r_val) > 0.90 else ("⚠️ 部分" if abs(r_val) > 0.60 else "❌ 被掩蓋")
    delta_str = f"{delta:+.4f}"
    print(f"{label:>30}  {r_val:>+13.4f}  {rmse:>8.4f}  {len(valid):>4}  {delta_str:>12}  {flag}")

print()
print("arm-free 基準：sphere r=0.05m r=+0.9992,  sphere r=0.10m r=+0.9997")
print("結論：")
print("  r 接近 arm-free 基準 → arm mesh 不干擾 sphere echo，raw features 可用")
print("  r 大幅低於 arm-free  → 需要差分方法（diff vs 無障礙物基準）")

PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
