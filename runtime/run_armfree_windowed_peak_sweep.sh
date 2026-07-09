#!/usr/bin/env bash
# 實驗：早期窗口峰值 vs 全窗口峰值（背景魯棒性修復驗證）
#
# 核心假設：牆壁回聲（sample 116 for x=2.0m）比球體回聲（sample 8–79）晚到。
# 若用早期窗口（只看 sample 0–89），可跳過牆壁回聲，恢復對目標的追蹤。
#
# 測試：
#   1. 無背景 + 全窗口（基準）
#   2. 地板+後牆 x=2.0m + 全窗口（已知 r=-0.38，失敗）
#   3. 地板+後牆 x=2.0m + 早期窗口 90（預測恢復 r>0.90）
#   4. 地板+後牆 x=1.6m + 早期窗口 85（牆在 sample~91，窗口截在 85）
#
# 用法: bash runtime/run_armfree_windowed_peak_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfree_windowed_peak_proximity_test.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_windowed_peak_sweep

mkdir -p "$BASE_OUT"
echo "=== 早期窗口峰值實驗 — $(date) ===" | tee "$BASE_OUT/run.log"

# 條件 1：無背景 + 全窗口（基準，驗證腳本正確）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- 條件1: 無背景 + 全窗口 ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --no-floor --no-wall \
    --window-size 90 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --output-dir "$BASE_OUT/no_bg_full" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "完成" | tee -a "$BASE_OUT/run.log"

# 條件 2：地板+後牆 x=2.0m + 全窗口（預期失敗）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- 條件2: 地板+後牆 x=2.0m + 全窗口 ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --floor-y -0.50 --wall-x 2.00 \
    --window-size 320 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --output-dir "$BASE_OUT/floor_wall200_full" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "完成" | tee -a "$BASE_OUT/run.log"

# 條件 3：地板+後牆 x=2.0m + 早期窗口 90（預測修復）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- 條件3: 地板+後牆 x=2.0m + 早期窗口 win=90 ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --floor-y -0.50 --wall-x 2.00 \
    --window-size 90 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --output-dir "$BASE_OUT/floor_wall200_win090" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "完成" | tee -a "$BASE_OUT/run.log"

# 條件 4：地板+後牆 x=1.6m + 早期窗口 85（牆在 sample~91，窗口截在 85）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- 條件4: 地板+後牆 x=1.6m + 早期窗口 win=85 ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --floor-y -0.50 --wall-x 1.60 \
    --window-size 85 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 15 --n-measure 6 \
    --output-dir "$BASE_OUT/floor_wall160_win085" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "完成" | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整：全窗口 vs 早期窗口 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_windowed_peak_sweep")

def pearson_r(xs, ys):
    paired = [(x, y) for x, y in zip(xs, ys) if not (math.isnan(x) or math.isnan(y))]
    n = len(paired)
    if n < 2: return float("nan")
    xs2, ys2 = zip(*paired)
    mx, my = sum(xs2)/n, sum(ys2)/n
    num = sum((x-mx)*(y-my) for x,y in zip(xs2,ys2))
    den = math.sqrt(sum((x-mx)**2 for x in xs2)*sum((y-my)**2 for y in ys2))
    return num/den if den > 0 else float("nan")

CASES = [
    ("no_bg_full",          "無背景",         "全窗口"),
    ("floor_wall200_full",  "地板+牆x=2.0m",  "全窗口 win=320"),
    ("floor_wall200_win090","地板+牆x=2.0m",  "早期窗口 win=90"),
    ("floor_wall160_win085","地板+牆x=1.6m",  "早期窗口 win=85"),
]

print(f"\n{'場景':>18}  {'方法':>18}  {'r_full':>8}  {'r_win':>8}  {'判定'}")
print("-" * 72)
for label, scene, method in CASES:
    csv_path = base / label / "armfree_winpeak_sweep.csv"
    if not csv_path.exists():
        print(f"{scene:>18}  {method:>18}  (無資料)")
        continue
    rows = list(csv.DictReader(csv_path.open()))
    dists  = [float(r["oracle_distance_m"])  for r in rows]
    peaks  = [float(r["peak_sample_idx"])    for r in rows]
    wpks   = [float(r["win_peak_idx"])       for r in rows]
    r_f = pearson_r(dists, peaks)
    r_w = pearson_r(dists, wpks)
    flag_f = "✅" if abs(r_f) > 0.90 else ("⚠️" if abs(r_f) > 0.60 else "❌")
    flag_w = "✅" if abs(r_w) > 0.90 else ("⚠️" if abs(r_w) > 0.60 else "❌")
    print(f"{scene:>18}  {method:>18}  {r_f:>+8.4f}{flag_f}  {r_w:>+8.4f}{flag_w}")

print()
print("結論：")
print("  r_full = 全窗口 argmax 的相關係數（牆壁存在時失效）")
print("  r_win  = 早期窗口 argmax 的相關係數（預期修復牆壁干擾）")
print("  ★ 若 r_win >> r_full：早期窗口截止法有效消除背景干擾")
PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
