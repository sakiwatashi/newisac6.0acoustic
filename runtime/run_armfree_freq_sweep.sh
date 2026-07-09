#!/usr/bin/env bash
# 實驗：中心頻率掃描
# 核心問題：WPM 的聲學偵測性能如何隨頻率變化？
#
# 測試頻率：20kHz / 30kHz / 40kHz（基準）/ 60kHz / 80kHz / 100kHz
# 目標：sphere r=0.05m，距離 0.20–1.50m（20 步）
# 其他參數固定（az=90°, el=90°, spacing=0.10m）
#
# 注意：inferred_dist_m 由 T_US=132.5µs（40kHz 校正值）計算，
#       在非 40kHz 下可能有系統偏移，但 Pearson r 不受影響（scale-invariant）。
#
# 用法: bash runtime/run_armfree_freq_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfree_acoustic_proximity_test.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_freq_sweep

mkdir -p "$BASE_OUT"
echo "=== 中心頻率掃描實驗 — $(date) ===" | tee "$BASE_OUT/run.log"
echo "目標：sphere r=0.05m  距離 0.20–1.50m  20 步" | tee -a "$BASE_OUT/run.log"
echo "40kHz 基準: r=+0.9992" | tee -a "$BASE_OUT/run.log"

for FREQ in 20000 30000 40000 60000 80000 100000; do
    echo "" | tee -a "$BASE_OUT/run.log"
    echo "--- center_freq=${FREQ}Hz ---" | tee -a "$BASE_OUT/run.log"
    $ISAACSIM "$SCRIPT" \
        --geometry sphere \
        --geom-radius 0.05 \
        --center-freq "$FREQ" \
        --mount-spacing 0.10 \
        --az-span 90 --el-span 90 \
        --min-dist 0.20 --max-dist 1.50 --n-steps 20 \
        --n-settle 15 --n-measure 6 \
        --output-dir "$BASE_OUT/freq_${FREQ}hz" \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "freq=${FREQ}Hz 完成" | tee -a "$BASE_OUT/run.log"
done

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整頻率掃描結果 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_freq_sweep")

V_SOUND = 343.0

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

FREQS = [20000, 30000, 40000, 60000, 80000, 100000]

print(f"\n{'頻率':>10}  {'波長mm':>8}  {'r(peak,dist)':>13}  {'n_spsgw':>8}  "
      f"{'n有效':>6}  {'peak_seq(前5)':>25}  {'判定'}")
print("-" * 100)

for freq in FREQS:
    csv_path = base / f"freq_{freq}hz" / "armfree_proximity_sweep.csv"
    if not csv_path.exists():
        print(f"{freq:>10}  (無資料)")
        continue
    rows = list(csv.DictReader(csv_path.open()))
    dists   = [float(r["oracle_distance_m"])  for r in rows]
    peaks   = [float(r["peak_sample_idx"])    for r in rows]
    spsgws  = [float(r.get("n_samples_per_sgw", "nan")) for r in rows]
    valid   = [(d, p) for d, p in zip(dists, peaks) if not math.isnan(p)]

    r_val  = pearson_r(dists, peaks)
    wl_mm  = V_SOUND / freq * 1000.0
    spsgw  = spsgws[0] if spsgws else float("nan")
    pk_seq = ", ".join(f"{p:.0f}" for _, p in valid[:5])
    flag   = "✅" if abs(r_val) > 0.90 else ("⚠️" if abs(r_val) > 0.60 else "❌")

    print(f"{freq:>10}  {wl_mm:>8.2f}  {r_val:>+13.4f}  {spsgw:>8.0f}  "
          f"{len(valid):>6}  {pk_seq:>25}  {flag}")

print()
print("注意：inferred_dist_m 以 T_US=132.5µs（40kHz 校正）計算")
print("      各頻率的 peak 位置（sample 序號）才是直接可比較的量")
print()
print("物理說明：")
print("  WPM = ray tracer，頻率主要影響：")
print("  1) 波長（λ=V/f）→ 繞射程度")
print("  2) 近場模型（closeRange 參數，已知在 WPM 中無法調整）")
print("  3) 高頻（>60kHz）空氣衰減增大，遠場振幅可能降低")
print()
print("  若 r ≈ 0.9992 across all frequencies：WPM ray tracer 幾何獨立於頻率")
print("  若 r 隨頻率降低：高頻衰減使遠距離（>1m）信噪比下降")
PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
