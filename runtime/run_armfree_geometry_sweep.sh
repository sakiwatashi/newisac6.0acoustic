#!/usr/bin/env bash
# 實驗 2b：多目標幾何掃描
# 目標：比較 Cube / Sphere / Cylinder 的聲學可偵測性
# 背景：真實場景的障礙物（人手、工具）是非 Cube 幾何
#   - sphere r=0.05m：人手尺寸
#   - sphere r=0.10m：拳頭/工具尺寸
#   - cylinder r=0.05m h=0.20m (axis=Y)：前臂剖面
#   - cube edge=0.10m（基準對照）
# 距離：0.20m → 1.50m，20 步
# 用法: bash runtime/run_armfree_geometry_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfree_acoustic_proximity_test.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_geometry_sweep

mkdir -p "$BASE_OUT"
echo "=== 多目標幾何掃描實驗 — $(date) ===" | tee "$BASE_OUT/run.log"
echo "距離範圍: 0.20–1.50m (20步)" | tee -a "$BASE_OUT/run.log"

# 基準：cube 0.10m（上個實驗已知 r≈0.999）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- geometry=cube  size=0.10m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --geometry cube \
    --cube-size 0.10 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 12 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/cube_0.10m" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "cube_0.10m 完成" | tee -a "$BASE_OUT/run.log"

# Sphere r=0.05m（人手大小）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- geometry=sphere  r=0.05m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --geometry sphere \
    --geom-radius 0.05 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 12 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/sphere_r0.05m" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "sphere_r0.05m 完成" | tee -a "$BASE_OUT/run.log"

# Sphere r=0.10m（拳頭/工具）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- geometry=sphere  r=0.10m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --geometry sphere \
    --geom-radius 0.10 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 12 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/sphere_r0.10m" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "sphere_r0.10m 完成" | tee -a "$BASE_OUT/run.log"

# Cylinder r=0.05m h=0.20m（前臂剖面，垂直於 +X）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- geometry=cylinder  r=0.05m  h=0.20m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --geometry cylinder \
    --geom-radius 0.05 \
    --cylinder-height 0.20 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 12 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/cylinder_r0.05m_h0.20m" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "cylinder_r0.05m_h0.20m 完成" | tee -a "$BASE_OUT/run.log"

# Cylinder r=0.05m h=0.30m（較長前臂）
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- geometry=cylinder  r=0.05m  h=0.30m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --geometry cylinder \
    --geom-radius 0.05 \
    --cylinder-height 0.30 \
    --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
    --n-settle 12 --n-measure 6 \
    --center-freq 40000 --mount-spacing 0.10 \
    --az-span 90 --el-span 90 \
    --output-dir "$BASE_OUT/cylinder_r0.05m_h0.30m" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "cylinder_r0.05m_h0.30m 完成" | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整各幾何體結果 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_geometry_sweep")

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

ORDER = ["cube_0.10m", "sphere_r0.05m", "sphere_r0.10m",
         "cylinder_r0.05m_h0.20m", "cylinder_r0.05m_h0.30m"]

print(f"\n{'幾何體':>28}  {'r(peak,dist)':>13}  {'RMSE':>8}  {'n':>4}  {'判定'}")
print("-" * 75)
for label in ORDER:
    csv_path = base / label / "armfree_proximity_sweep.csv"
    if not csv_path.exists():
        print(f"{label:>28}  (無資料)")
        continue
    rows = list(csv.DictReader(csv_path.open()))
    dists  = [float(r["oracle_distance_m"]) for r in rows]
    peaks  = [float(r["peak_sample_idx"])   for r in rows]
    inf_ds = [float(r["inferred_dist_m"])   for r in rows]
    valid  = [(dv, iv) for dv, iv in zip(dists, inf_ds) if not math.isnan(iv)]
    r_val  = pearson_r(dists, peaks)
    rmse   = math.sqrt(sum((dv-iv)**2 for dv,iv in valid)/len(valid)) if valid else float("nan")
    flag   = "✅ 可偵測" if abs(r_val) > 0.90 else ("⚠️ 部分" if abs(r_val) > 0.60 else "❌ 不可偵測")
    print(f"{label:>28}  {r_val:>+13.4f}  {rmse:>8.4f}  {len(valid):>4}  {flag}")

PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
