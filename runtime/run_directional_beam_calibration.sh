#!/usr/bin/env bash
# 指向性光束校正掃描 — azSpanDeg=45, elSpanDeg=45 (模擬 CH201 ±22.5° 指向性)
# traceTreeDepth=2：保留預設值 (depth=1 觸發 WPM CUDA abort)
# 目的：確認縮小波束後，primary_sgw 是否從後牆(sample≈88)轉移到板手，
#       且各 trial (不同板手位置) 的能量序列是否出現差異。
#
# 用法: bash runtime/run_directional_beam_calibration.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_dynamic_approach_calibration_sweep.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/directional_beam_v1
SEED=20260629
MATERIAL=D          # fur_hair 牆壁 (近無響室)，排除房間殘響
AZ_SPAN=45
EL_SPAN=45
TRACE_DEPTH=2       # 預設值 (depth=1 觸發 WPM CUDA assert)

# 與先前相同的 7 個 trial
TRIAL_IDS=(18 20 0 4 8 12 16)

mkdir -p "$BASE_OUT"
echo "=== 指向性光束校正掃描 az=${AZ_SPAN} el=${EL_SPAN} depth=${TRACE_DEPTH} material=${MATERIAL} — $(date) ===" | tee "$BASE_OUT/run.log"
echo "設定: fur_hair 牆壁 + retroreflective aluminum 板手 + 指向性波束 ±22.5°" | tee -a "$BASE_OUT/run.log"

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
        --overwrite \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "trial_id=${TID} 完成" | tee -a "$BASE_OUT/run.log"
done

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 所有 trial 完成，合併並分析 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib, sys
from collections import Counter

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/directional_beam_v1")
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

out_path = base / "directional_beam_combined.csv"
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

print(f"\n=== 指向性波束聲學特徵分析 ===")

# --- 核心特徵相關性 ---
features = [
    "primary_sgw_early_energy",
    "primary_sgw_ultra_early_energy",
    "primary_sgw_peak_sample_idx",
    "primary_sgw_early_peak_sample_idx",
    "ref_sgw_early_energy",
    "waveform_early_fraction",
    "amplitude_std",
    "num_signal_ways",
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

# --- 關鍵診斷 1: peak_sample_idx 分布 ---
# 若 primary_sgw 仍是後牆 → sample≈88；若切換到板手 → sample < 10
print("\n=== primary_sgw_peak_sample_idx 分布（後牆=88? 板手=<10?）===")
peak_vals = [int(float(r["primary_sgw_peak_sample_idx"]))
             for r in all_rows if sf(r.get("primary_sgw_peak_sample_idx"))]
cnt = Counter(peak_vals)
for k, v in sorted(cnt.items(), key=lambda x: -x[1])[:15]:
    dist_approx = k * 0.1325 * 343 / 2
    print(f"  sample={k:3d}  count={v:3d}  (≈{dist_approx:.2f}m)")

# --- 關鍵診斷 2: 各 trial ultra_early_energy 序列是否出現差異 ---
# 若全域相同 → 仍測到手臂/牆壁；若每個 trial 不同 → 開始看到板手
print("\n=== 各 trial ultra_early_energy 序列（不同=好消息!）===")
for tid in sorted(set(int(float(r["trial_id"])) for r in all_rows)):
    tr = sorted([r for r in all_rows if int(float(r["trial_id"])) == tid],
                key=lambda x: -float(x["oracle_distance_m"]))
    vals = [sf(r.get("primary_sgw_ultra_early_energy")) for r in tr]
    vals = [f"{v:.0f}" if v else "?" for v in vals[:10]]
    d_range = [sf(r["oracle_distance_m"]) for r in tr if sf(r.get("oracle_distance_m"))]
    print(f"  trial_{tid:2d} [{min(d_range):.2f}–{max(d_range):.2f}m]: {' '.join(vals)}")

# --- 關鍵診斷 3: 距離分段能量單調性 ---
print("\n=== ultra_early_energy vs 距離分段（是否比先前更單調？）===")
pairs_ue = sorted([(sf(r["oracle_distance_m"]), sf(r["primary_sgw_ultra_early_energy"]))
                   for r in all_rows if sf(r.get("oracle_distance_m")) and sf(r.get("primary_sgw_ultra_early_energy"))])
bins = [(0.20,0.30),(0.30,0.35),(0.35,0.40),(0.40,0.45),(0.45,0.50),(0.50,0.60),(0.60,0.70),(0.70,0.82)]
for lo, hi in bins:
    sub = [e for d,e in pairs_ue if lo<=d<hi]
    if sub:
        mu = sum(sub)/len(sub)
        std = math.sqrt(sum((x-mu)**2 for x in sub)/len(sub))
        print(f"  [{lo:.2f},{hi:.2f})  mean={mu:6.2f}  std={std:5.2f}  n={len(sub)}")

# --- 關鍵診斷 4: num_signal_ways 分布 ---
print("\n=== num_signal_ways 分布（是否仍固定=2？或出現 1?）===")
nw_cnt = Counter(int(float(r["num_signal_ways"])) for r in all_rows if sf(r.get("num_signal_ways")))
for k, v in sorted(nw_cnt.items()):
    print(f"  num_signal_ways={k}  count={v}")

PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
