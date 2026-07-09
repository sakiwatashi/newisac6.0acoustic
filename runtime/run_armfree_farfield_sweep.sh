#!/usr/bin/env bash
# 實驗 1b：大 Cube 遠場重測
# 問題：0.30m/0.50m cube 在 0.20m 起測時，近場 closeRange 模型主導 → peak 非單調
# 修正：將 min_dist 移到各 cube 的「線性區」以外
#   0.30m cube：線性區從 d≈0.68m 開始 → min_dist=0.65m
#   0.50m cube：線性區從 d≈0.88m 開始 → min_dist=0.85m
# 用法: bash runtime/run_armfree_farfield_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfree_acoustic_proximity_test.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_farfield_sweep

mkdir -p "$BASE_OUT"
echo "=== 大 Cube 遠場重測 — $(date) ===" | tee "$BASE_OUT/run.log"

# 0.30m cube — 避開近場亂流，從 0.65m 開始
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- cube=0.30m  min_dist=0.65m  max_dist=2.00m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --min-dist 0.65 \
    --max-dist 2.00 \
    --n-steps 20 \
    --n-settle 12 \
    --n-measure 6 \
    --cube-size 0.30 \
    --center-freq 40000 \
    --mount-spacing 0.10 \
    --az-span 90 \
    --el-span 90 \
    --output-dir "$BASE_OUT/cube_0.30m_farfield" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "cube=0.30m farfield 完成" | tee -a "$BASE_OUT/run.log"

# 0.50m cube — 從 0.85m 開始
echo "" | tee -a "$BASE_OUT/run.log"
echo "--- cube=0.50m  min_dist=0.85m  max_dist=2.00m ---" | tee -a "$BASE_OUT/run.log"
$ISAACSIM "$SCRIPT" \
    --min-dist 0.85 \
    --max-dist 2.00 \
    --n-steps 15 \
    --n-settle 12 \
    --n-measure 6 \
    --cube-size 0.50 \
    --center-freq 40000 \
    --mount-spacing 0.10 \
    --az-span 90 \
    --el-span 90 \
    --output-dir "$BASE_OUT/cube_0.50m_farfield" \
    2>&1 | tee -a "$BASE_OUT/run.log"
echo "cube=0.50m farfield 完成" | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整遠場結果 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_farfield_sweep")

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

print(f"\n{'場景':>25}  {'r(peak,dist)':>13}  {'RMSE':>8}  {'n':>4}  {'判定'}")
print("-" * 70)
for d in sorted(base.glob("cube_*")):
    csv_path = d / "armfree_proximity_sweep.csv"
    if not csv_path.exists():
        continue
    rows = list(csv.DictReader(csv_path.open()))
    dists = [float(r["oracle_distance_m"]) for r in rows]
    peaks = [float(r["peak_sample_idx"])   for r in rows]
    inf_ds = [float(r["inferred_dist_m"])  for r in rows]
    valid = [(dv, iv) for dv, iv in zip(dists, inf_ds) if not math.isnan(iv)]
    r_val = pearson_r(dists, peaks)
    rmse  = math.sqrt(sum((dv-iv)**2 for dv,iv in valid)/len(valid)) if valid else float("nan")
    flag  = "✅ 可偵測" if abs(r_val) > 0.90 else ("⚠️ 部分" if abs(r_val) > 0.60 else "❌ 不可偵測")
    print(f"{d.name:>25}  {r_val:>+13.4f}  {rmse:>8.4f}  {len(valid):>4}  {flag}")

PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
