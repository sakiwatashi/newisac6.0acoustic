#!/usr/bin/env bash
# 直接回波模式校正掃描 — 抑制 WPM 參數化房間模型
#
# 核心發現：WPM 是參數化模型，不是幾何 ray tracer。
#   closeIndirectAmpl=17.64 (間接回波) > closeDirectAmpl=12.66 (直接回波)
#   → 房間模型回波（sample 88）永遠壓制板手的直接回波
#
# 本實驗：
#   closeIndirectAmpl = 0.1  (幾乎關閉間接/房間回波)
#   closeDirectAmpl   = 30.0 (強化直接回波)
#   closeIndirectAmplBase = 0.01
#   closeDirectAmplBase   = 5.0
#   → 預期 peak_sample_idx 移動到板手距離範圍 (sample 10-36)
#   → 預期 early_energy / mf_tof 與 oracle_distance 有強相關
#
# 用法: bash runtime/run_direct_echo_calibration.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_dynamic_approach_calibration_sweep.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/direct_echo_v1
SEED=20260629
MATERIAL=D
AZ_SPAN=45
EL_SPAN=45
TRACE_DEPTH=2

TRIAL_IDS=(18 20 0 4 8 12 16)

mkdir -p "$BASE_OUT"
echo "=== 直接回波模式 closeIndirectAmpl=0.1 closeDirectAmpl=30.0 — $(date) ===" | tee "$BASE_OUT/run.log"
echo "目標: 抑制參數化房間模型，讓板手直接回波主導" | tee -a "$BASE_OUT/run.log"

for TID in "${TRIAL_IDS[@]}"; do
    OUT="$BASE_OUT/trial_${TID}"
    echo "" | tee -a "$BASE_OUT/run.log"
    echo "--- trial_id=${TID} → ${OUT} ---" | tee -a "$BASE_OUT/run.log"
    $ISAACSIM "$SCRIPT" \
        --trial-id "$TID" \
        --spawn-seed "$SEED" \
        --output-dir "$OUT" \
        --material-condition "$MATERIAL" \
        --az-span-deg "$AZ_SPAN" \
        --el-span-deg "$EL_SPAN" \
        --trace-tree-depth "$TRACE_DEPTH" \
        --close-indirect-ampl 0.1 \
        --close-direct-ampl 30.0 \
        --close-indirect-ampl-base 0.01 \
        --close-direct-ampl-base 5.0 \
        --overwrite \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "trial_id=${TID} 完成" | tee -a "$BASE_OUT/run.log"
done

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 所有 trial 完成，合併並分析 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib, sys
from collections import Counter

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/direct_echo_v1")
all_rows = []
for csv_path in sorted(base.glob("trial_*/dynamic_approach_calibration_sweep.csv")):
    trial_id = int(csv_path.parent.name.split("_")[1])
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            row["trial_id"] = trial_id
            all_rows.append(row)

if not all_rows:
    print("ERROR: 找不到 CSV", file=sys.stderr)
    sys.exit(1)

out_path = base / "direct_echo_combined.csv"
fieldnames = list(all_rows[0].keys())
with out_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(all_rows)
print(f"合併 {len(all_rows)} 筆 → {out_path}")

def sf(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except: return None

def pearson_r(xs, ys):
    n = len(xs)
    if n < 2: return float("nan")
    mx, my = sum(xs)/n, sum(ys)/n
    num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    den = math.sqrt(sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys))
    return num/den if den > 0 else float("nan")

T_us = 132.5e-6
V = 343.0

print(f"\n=== 直接回波模式聲學特徵分析 ===")

# 核心特徵相關性
features = [
    "primary_sgw_early_energy",
    "primary_sgw_ultra_early_energy",
    "primary_sgw_peak_sample_idx",
    "primary_sgw_early_peak_sample_idx",
    "waveform_early_fraction",
    "amplitude_std",
    "mf_tof_sample_idx",
]
for feat in features:
    pairs = [(sf(r["oracle_distance_m"]), sf(r.get(feat)))
             for r in all_rows
             if sf(r.get("oracle_distance_m")) and sf(r.get(feat))
             and str(r.get(feat,"")).strip() not in ("-1","nan","")]
    if pairs:
        xs, ys = zip(*pairs)
        r = pearson_r(list(xs), list(ys))
        print(f"  {feat:<42} r = {r:+.4f}  (n={len(pairs)})")

# 診斷 1: peak_sample_idx 是否移到板手範圍
print("\n=== primary_sgw_peak_sample_idx 分布（板手 sample 應在 10–36）===")
peak_vals = [int(float(r["primary_sgw_peak_sample_idx"]))
             for r in all_rows if sf(r.get("primary_sgw_peak_sample_idx"))]
cnt = Counter(peak_vals)
for k, v in sorted(cnt.items(), key=lambda x: -x[1])[:15]:
    dist_m = k * T_us * V / 2
    print(f"  sample={k:3d}  count={v:3d}  ({dist_m:.3f}m)")

# 診斷 2: mf_tof_sample_idx
print("\n=== mf_tof_sample_idx 分布 ===")
tof_vals = [int(float(r["mf_tof_sample_idx"]))
            for r in all_rows if sf(r.get("mf_tof_sample_idx"))
            and str(r.get("mf_tof_sample_idx","")).strip() not in ("-1","nan","")]
cnt2 = Counter(tof_vals)
for k, v in sorted(cnt2.items(), key=lambda x: -x[1])[:15]:
    dist_m = k * T_us * V / 2
    print(f"  sample={k:3d}  count={v:3d}  ({dist_m:.3f}m)")

# 診斷 3: MF-ToF vs oracle_distance
tof_pairs = [(sf(r["oracle_distance_m"]), sf(r.get("mf_tof_sample_idx")) * T_us * V / 2)
             for r in all_rows
             if sf(r.get("oracle_distance_m")) and sf(r.get("mf_tof_sample_idx"))
             and str(r.get("mf_tof_sample_idx","")).strip() not in ("-1","nan","")]
if tof_pairs:
    ox, oy = zip(*tof_pairs)
    r_tof = pearson_r(list(ox), list(oy))
    rmse = math.sqrt(sum((a-b)**2 for a,b in zip(ox,oy))/len(ox))
    print(f"\nMF-ToF distance vs oracle_distance: r={r_tof:+.4f}  RMSE={rmse:.4f}m (n={len(tof_pairs)})")
    if abs(r_tof) > 0.8:
        print("  ★★★ 強相關！可用 MF-ToF 做距離估計 ★★★")

# 診斷 4: 各 trial energy 序列（是否不同且單調？）
print("\n=== 各 trial ultra_early_energy 序列 ===")
for tid in sorted(set(int(float(r["trial_id"])) for r in all_rows)):
    tr = sorted([r for r in all_rows if int(float(r["trial_id"])) == tid],
                key=lambda x: -float(x["oracle_distance_m"]))
    vals = [sf(r.get("primary_sgw_ultra_early_energy")) for r in tr]
    vals_s = [f"{v:.0f}" if v else "?" for v in vals[:10]]
    d_range = [sf(r["oracle_distance_m"]) for r in tr if sf(r.get("oracle_distance_m"))]
    print(f"  trial_{tid:2d} [{min(d_range):.2f}–{max(d_range):.2f}m]: {' '.join(vals_s)}")

# 診斷 5: 距離分段單調性
print("\n=== ultra_early_energy 距離分段（是否單調遞減？）===")
pairs_ue = sorted([(sf(r["oracle_distance_m"]), sf(r["primary_sgw_ultra_early_energy"]))
                   for r in all_rows if sf(r.get("oracle_distance_m")) and sf(r.get("primary_sgw_ultra_early_energy"))])
bins = [(0.20,0.30),(0.30,0.35),(0.35,0.40),(0.40,0.45),(0.45,0.50),(0.50,0.60),(0.60,0.70),(0.70,0.82)]
for lo, hi in bins:
    sub = [e for d,e in pairs_ue if lo<=d<hi]
    if sub:
        mu = sum(sub)/len(sub)
        std = math.sqrt(sum((x-mu)**2 for x in sub)/len(sub))
        print(f"  [{lo:.2f},{hi:.2f})  mean={mu:6.2f}  std={std:5.2f}  n={len(sub)}")

PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
