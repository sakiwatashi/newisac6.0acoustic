#!/usr/bin/env bash
# 實驗：背景場景魯棒性測試
# 核心問題：有地板和牆壁的情況下，WPM 還能偵測球體距離嗎？
#
# 測試條件：
#   - no_bg        : 無背景（基準，應與 arm-free 基準一致 r≈0.9992）
#   - floor_only   : 只有地板（y=-0.50m）
#   - floor_wall   : 地板 + 後牆（x=2.00m）
#   - floor_wall_close : 地板 + 近後牆（x=1.60m，牆比目標最大距離 1.50m 稍遠）
#
# arm-free 基準：sphere r=0.05m → r=+0.9992（已確認）
#
# 用法: bash runtime/run_armfree_background_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfree_background_proximity_test.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_background_sweep

mkdir -p "$BASE_OUT"
echo "=== 背景場景魯棒性實驗 — $(date) ===" | tee "$BASE_OUT/run.log"
echo "距離範圍: 0.20–1.50m (20步)  sphere r=0.05m" | tee -a "$BASE_OUT/run.log"
echo "arm-free 基準: r=+0.9992" | tee -a "$BASE_OUT/run.log"

# 條件 1：無背景（基準）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- 條件1: no_bg (無背景) ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --no-floor --no-wall \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/no_bg" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "no_bg 完成" | tee -a "$BASE_OUT/run.log"

# 條件 2：只有地板（y=-0.50m）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- 條件2: floor_only (地板 y=-0.50m) ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --no-wall \
    --floor-y -0.50 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/floor_only" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "floor_only 完成" | tee -a "$BASE_OUT/run.log"

# 條件 3：地板 + 後牆（x=2.00m）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- 條件3: floor_wall (地板 + 後牆 x=2.00m) ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --floor-y -0.50 \
    --wall-x 2.00 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/floor_wall" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "floor_wall 完成" | tee -a "$BASE_OUT/run.log"

# 條件 4：地板 + 近後牆（x=1.60m，緊逼目標最大距離）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- 條件4: floor_wall_close (地板 + 近後牆 x=1.60m) ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --floor-y -0.50 \
    --wall-x 1.60 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/floor_wall_close" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "floor_wall_close 完成" | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整結果 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_background_sweep")

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
    ("no_bg",            "無背景（基準）"),
    ("floor_only",       "地板 y=-0.50m"),
    ("floor_wall",       "地板 + 後牆 x=2.00m"),
    ("floor_wall_close", "地板 + 後牆 x=1.60m"),
]

BASELINE_R = 0.9992

print(f"\n{'場景':>28}  {'r(peak,dist)':>13}  {'RMSE':>8}  {'bias':>8}  {'n':>4}  {'vs基準':>8}  {'判定'}")
print("-" * 90)
for label, desc in ORDER:
    csv_path = base / label / "armfree_bg_proximity_sweep.csv"
    if not csv_path.exists():
        print(f"{desc:>28}  (無資料)")
        continue
    rows = list(csv.DictReader(csv_path.open()))
    dists  = [float(r["oracle_distance_m"]) for r in rows]
    peaks  = [float(r["peak_sample_idx"])   for r in rows]
    inf_ds = [float(r["inferred_dist_m"])   for r in rows]
    valid  = [(dv, iv) for dv, iv in zip(dists, inf_ds) if not math.isnan(iv)]
    r_val  = pearson_r(dists, peaks)
    rmse   = math.sqrt(sum((dv-iv)**2 for dv,iv in valid)/len(valid)) if valid else float("nan")
    bias   = sum(iv-dv for dv,iv in valid)/len(valid) if valid else float("nan")
    delta  = r_val - BASELINE_R
    flag   = "✅ 可偵測" if abs(r_val) > 0.90 else ("⚠️ 部分" if abs(r_val) > 0.60 else "❌ 被掩蓋")
    print(f"{desc:>28}  {r_val:>+13.4f}  {rmse:>8.4f}  {bias:>+8.4f}  {len(valid):>4}  {delta:>+8.4f}  {flag}")

print()
print("arm-free 基準（無背景）: r=+0.9992")
print("判定標準: r>0.90→可偵測, r>0.60→部分, r<0.60→被背景掩蓋")
print()
print("結論說明：")
print("  地板/牆壁回聲路徑：")
print("  - 地板 (y=-0.50m) 最近回聲路徑 ≈ 2×0.5m=1.0m → 等效 sample≈38")
print("    → 與 dist>0.5m 目標 peak 重疊！")
print("  - 後牆 (x=2.00m) 回聲路徑 = 2×2.0m=4.0m → 等效 sample≈151 (超出窗口)")
print("    → 後牆不干擾（到達太晚）")
PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
