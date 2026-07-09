#!/usr/bin/env bash
# 批次跑 ultra_early_energy + early_peak_sample_idx 校正掃描
# 使用 material-condition C (高吸音: PRA=0.70, fabric+none) 消除房間殘響
# 每個 trial 放在獨立子目錄，方便逐個確認
# 用法: bash runtime/run_ultra_early_calibration.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_dynamic_approach_calibration_sweep.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/ultra_early_calibration_v1
SEED=20260629
MATERIAL=C

# trial_id → wrench_x: 18=0.717 20=0.746 0=1.052 4=1.111 8=1.170 12=1.229 16=1.288
TRIAL_IDS=(18 20 0 4 8 12 16)

mkdir -p "$BASE_OUT"
echo "=== ultra_early_energy 校正掃描 (material=$MATERIAL) — $(date) ===" | tee "$BASE_OUT/run.log"

for TID in "${TRIAL_IDS[@]}"; do
    OUT="$BASE_OUT/trial_${TID}"
    echo ""
    echo "--- trial_id=${TID} material=${MATERIAL} → ${OUT} ---" | tee -a "$BASE_OUT/run.log"
    $ISAACSIM "$SCRIPT" \
        --trial-id "$TID" \
        --spawn-seed "$SEED" \
        --output-dir "$OUT" \
        --material-condition "$MATERIAL" \
        --overwrite \
        2>&1 | tee -a "$BASE_OUT/run.log"
    echo "trial_id=${TID} 完成" | tee -a "$BASE_OUT/run.log"
done

echo ""
echo "=== 所有 trial 完成，合併 CSV ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import csv, math, pathlib, sys

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/ultra_early_calibration_v1")
all_rows = []
for csv_path in sorted(base.glob("trial_*/dynamic_approach_calibration_sweep.csv")):
    trial_id = int(csv_path.parent.name.split("_")[1])
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            row["trial_id"] = trial_id
            all_rows.append(row)

if not all_rows:
    print("ERROR: nessun CSV trovato", file=sys.stderr)
    sys.exit(1)

out_path = base / "ultra_early_calibration_combined.csv"
fieldnames = list(all_rows[0].keys())
with out_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(all_rows)

print(f"Scritto {len(all_rows)} righe → {out_path}")

# 統計分析
def pearson_r(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx)**2 for x in xs) * sum((y - my)**2 for y in ys))
    return num / den if den > 0 else float("nan")

valid = [r for r in all_rows
         if r.get("primary_sgw_ultra_early_energy") not in (None, "", "nan")
         and r.get("oracle_distance_m") not in (None, "", "nan")]
print(f"\n有效行 (ultra_early_energy): {len(valid)}/{len(all_rows)}")

if valid:
    uee = [float(r["primary_sgw_ultra_early_energy"]) for r in valid]
    dist = [float(r["oracle_distance_m"]) for r in valid]
    r_uee = pearson_r(uee, dist)
    print(f"ultra_early_energy: min={min(uee):.4f} max={max(uee):.4f} mean={sum(uee)/len(uee):.4f}")
    print(f"ultra_early_energy Pearson r = {r_uee:.4f} (oracle_distance_m)")

    epi_vals = [r.get("primary_sgw_early_peak_sample_idx") for r in valid
                if r.get("primary_sgw_early_peak_sample_idx") not in (None, "", "nan")]
    if epi_vals:
        epi = [int(float(v)) for v in epi_vals]
        valid_epi = [r for r in valid if r.get("primary_sgw_early_peak_sample_idx") not in (None, "", "nan")]
        dist_epi = [float(r["oracle_distance_m"]) for r in valid_epi]
        r_epi = pearson_r([float(v) for v in epi_vals], dist_epi)
        from collections import Counter
        cnt = Counter(epi)
        print(f"\nearly_peak_sample_idx: range {min(epi)}–{max(epi)}, {len(cnt)} distinct values")
        print(f"early_peak_sample_idx Pearson r = {r_epi:.4f} (oracle_distance_m)")
        print(f"分布: {dict(sorted(cnt.items()))}")

    # 同框比較 early_energy vs ultra_early_energy
    ee_vals = [r.get("primary_sgw_early_energy") for r in valid
               if r.get("primary_sgw_early_energy") not in (None, "", "nan")]
    if ee_vals:
        ee = [float(v) for v in ee_vals]
        valid_ee = [r for r in valid if r.get("primary_sgw_early_energy") not in (None, "", "nan")]
        dist_ee = [float(r["oracle_distance_m"]) for r in valid_ee]
        r_ee = pearson_r(ee, dist_ee)
        print(f"\n[對比] primary_sgw_early_energy (25%) Pearson r = {r_ee:.4f}")
        print(f"[對比] ultra_early_energy     (10%) Pearson r = {r_uee:.4f}")

PYEOF

echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
