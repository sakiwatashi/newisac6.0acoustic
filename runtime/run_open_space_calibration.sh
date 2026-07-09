#!/usr/bin/env bash
# 開放空間校正掃描 — 移除天花板 + x_max 後牆
# 假說：sample 88 peak 來自天花板（感測器上方 2.0m）。
# 移除天花板和前向後牆後，板手應成為正前方唯一主要反射體。
# 指向性光束 az=45 el=45 保持，material=D（近無響室）。
#
# 用法: bash runtime/run_open_space_calibration.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_dynamic_approach_calibration_sweep.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/open_space_v1
SEED=20260629
MATERIAL=D
AZ_SPAN=45
EL_SPAN=45
TRACE_DEPTH=2

TRIAL_IDS=(18 20 0 4 8 12 16)

mkdir -p "$BASE_OUT"
echo "=== 開放空間校正掃描 az=${AZ_SPAN} el=${EL_SPAN} open_space=True material=${MATERIAL} — $(date) ===" | tee "$BASE_OUT/run.log"
echo "移除: ceiling（sample 88 主因）+ wall_x_max" | tee -a "$BASE_OUT/run.log"

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
        --open-space \
        --overwrite \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "trial_id=${TID} 完成" | tee -a "$BASE_OUT/run.log"
done

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 所有 trial 完成，合併並分析 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib, sys
from collections import Counter

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/open_space_v1")
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

out_path = base / "open_space_combined.csv"
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

print(f"\n=== 開放空間聲學特徵分析 ===")

features = [
    "primary_sgw_early_energy",
    "primary_sgw_ultra_early_energy",
    "primary_sgw_peak_sample_idx",
    "primary_sgw_early_peak_sample_idx",
    "ref_sgw_early_energy",
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

# 關鍵診斷 1: peak_sample_idx 分布（天花板 88 是否消失？）
print("\n=== primary_sgw_peak_sample_idx 分布（天花板 sample 88 是否消失？）===")
peak_vals = [int(float(r["primary_sgw_peak_sample_idx"]))
             for r in all_rows if sf(r.get("primary_sgw_peak_sample_idx"))]
cnt = Counter(peak_vals)
for k, v in sorted(cnt.items(), key=lambda x: -x[1])[:15]:
    dist_m = k * T_us * V / 2
    print(f"  sample={k:3d}  count={v:3d}  (≈{dist_m:.3f}m)")

# 關鍵診斷 2: mf_tof_sample_idx 分布（MF-ToF 是否移到板手範圍？）
print("\n=== mf_tof_sample_idx 分布（板手 sample 應在 10–36 範圍）===")
tof_vals = [int(float(r["mf_tof_sample_idx"]))
            for r in all_rows if sf(r.get("mf_tof_sample_idx")) and str(r.get("mf_tof_sample_idx","")).strip() not in ("-1","nan","")]
cnt2 = Counter(tof_vals)
for k, v in sorted(cnt2.items(), key=lambda x: -x[1])[:15]:
    dist_m = k * T_us * V / 2
    print(f"  sample={k:3d}  count={v:3d}  (≈{dist_m:.3f}m)")

# 關鍵診斷 3: MF-ToF vs oracle_distance 相關性
tof_pairs = [(sf(r["oracle_distance_m"]), sf(r.get("mf_tof_sample_idx")))
             for r in all_rows
             if sf(r.get("oracle_distance_m")) and sf(r.get("mf_tof_sample_idx"))
             and str(r.get("mf_tof_sample_idx","")).strip() not in ("-1","nan","")]
if tof_pairs:
    xs, ys = zip(*tof_pairs)
    r_tof = pearson_r(list(xs), list(ys))
    # mf_tof_distance_m vs oracle
    dist_pairs = [(sf(r["oracle_distance_m"]), sf(r.get("mf_tof_sample_idx")) * T_us * V / 2)
                  for r in all_rows
                  if sf(r.get("oracle_distance_m")) and sf(r.get("mf_tof_sample_idx"))
                  and str(r.get("mf_tof_sample_idx","")).strip() not in ("-1","nan","")]
    if dist_pairs:
        ox, oy = zip(*dist_pairs)
        mse = math.sqrt(sum((a-b)**2 for a,b in zip(ox,oy))/len(ox))
        print(f"\nMF-ToF → distance: Pearson r={r_tof:+.4f}  RMSE={mse:.4f}m (n={len(dist_pairs)})")
        print("  (若 RMSE < 0.05m → 可直接用 MF-ToF 測距！)")

# 關鍵診斷 4: 各 trial ultra_early_energy 序列
print("\n=== 各 trial ultra_early_energy 序列（各 trial 是否不同？）===")
for tid in sorted(set(int(float(r["trial_id"])) for r in all_rows)):
    tr = sorted([r for r in all_rows if int(float(r["trial_id"])) == tid],
                key=lambda x: -float(x["oracle_distance_m"]))
    vals = [sf(r.get("primary_sgw_ultra_early_energy")) for r in tr]
    vals_s = [f"{v:.0f}" if v else "?" for v in vals[:10]]
    d_range = [sf(r["oracle_distance_m"]) for r in tr if sf(r.get("oracle_distance_m"))]
    print(f"  trial_{tid:2d} [{min(d_range):.2f}–{max(d_range):.2f}m]: {' '.join(vals_s)}")

# 關鍵診斷 5: ultra_early_energy 距離分段單調性
print("\n=== ultra_early_energy vs 距離分段（期望：單調遞減）===")
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
