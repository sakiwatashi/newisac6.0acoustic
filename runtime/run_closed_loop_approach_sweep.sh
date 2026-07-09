#!/usr/bin/env bash
# 實驗：閉環接近掃描 v3 — fused_distance_m（Tier-B early_energy 校正）
#
# 設計：
#   - Phase B：acoustic_only 模式，控制器純靠聲學信號（無 oracle 輔助退出）
#   - 30 episodes，trial_id 0-29（跨越完整 wrench_x 範圍）
#   - --skip-lift：FixedCuboid 目標，不執行物理抓取，只測試接近相位
#   - 在單一 Isaac Sim session 內完成（降低啟動開銷）
#
# 控制器距離估計：fused_distance_m（early_energy via DEFAULT_CALIBRATION）
#   - arm+table 場景 TABLE 主導 peak_sample_idx（背景反射 ~2 m），已改回 energy fusion
#   - peak_sample_idx 公式僅對 arm-free 場景有效（r=0.9992），作為獨立論文貢獻保留
#
# 成功判定：approach_reason 在成功集合內
#
# 用法: bash runtime/run_closed_loop_approach_sweep.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_ultrasonic_closed_loop_grasp.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/approach_sweep_v4
STAGE=/home/lab109/song/isaacsim6.0/runtime/scenes/approach_sweep_v4.usda

mkdir -p "$BASE_OUT"
mkdir -p "$(dirname "$STAGE")"
echo "=== 閉環接近掃描 v3 (fused_distance_m, acoustic_only) — $(date) ===" | tee "$BASE_OUT/run.log"
echo "controller: fused_distance_m (early_energy Tier-B fusion, DEFAULT_CALIBRATION)" | tee -a "$BASE_OUT/run.log"
echo "claim_mode: acoustic_only (無 oracle 輔助退出)" | tee -a "$BASE_OUT/run.log"
echo "episodes: 30 (trial_id 0-29)" | tee -a "$BASE_OUT/run.log"

$ISAACSIM "$SCRIPT" \
    --output-dir "$BASE_OUT" \
    --output-stage "$STAGE" \
    --overwrite \
    --episode-trial-ids 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29 \
    --control-mode closed_loop \
    --claim-mode acoustic_only \
    --skip-lift \
    --settle-steps 30 \
    --substeps-per-sample 2 \
    2>&1 | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整接近掃描結果 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import json, pathlib, math

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/approach_sweep_v4")
ep_path = base / "episodes_summary.json"
if not ep_path.exists():
    print("(無 episodes_summary.json，實驗可能未完成)")
    raise SystemExit(0)

data = json.loads(ep_path.read_text())
episodes = data.get("episodes", [])

APPROACH_SUCCESS = {
    "standoff_reached",
    "standoff_reached_ik_limit",
    "standoff_reached_search_limit",
    "standoff_reached_forward_cap",
    "standoff_reached_fusion_saturation",
    "standoff_reached_forward_cap_rescue",
    "standoff_reached_fusion_saturation_rescue",
    "tier_b_lateral_complete",
    "descend_ready",
}

approach_ok = [e for e in episodes if e.get("approach_reason", "") in APPROACH_SUCCESS]
approach_fail = [e for e in episodes if e.get("approach_reason", "") not in APPROACH_SUCCESS]
n = len(episodes)

print(f"\n=== Phase B 閉環接近 v4 (fused_distance_m/energy, acoustic_only) ===")
print(f"  成功: {len(approach_ok)}/{n} = {len(approach_ok)/n*100:.1f}%")
print(f"  失敗: {len(approach_fail)}/{n} = {len(approach_fail)/n*100:.1f}%")

# 依 reason 分組
from collections import Counter
reason_counts = Counter(e.get("approach_reason", "unknown") for e in episodes)
print(f"\n  reason 分布:")
for reason, cnt in sorted(reason_counts.items(), key=lambda x: -x[1]):
    ok = reason in APPROACH_SUCCESS
    print(f"    {'✓' if ok else '✗'} {reason}: {cnt}")

# wrench_x 分布與成功/失敗
print(f"\n  各 episode 結果:")
for e in episodes:
    ok = e.get("approach_reason", "") in APPROACH_SUCCESS
    wx = e.get("wrench_oracle_position_m", [float("nan")])[0]
    steps = e.get("approach_steps", "?")
    print(f"  {'✓' if ok else '✗'} ep={e['episode_id']:02d} trial={e['trial_id']:02d} "
          f"wx={wx:.3f}m steps={steps} reason={e.get('approach_reason','?')}")

print()
print("注意：成功 = approach_reason 在 standoff_reached/tier_b/descend_ready 集合內")
print("      oracle 距離/位置只用於評估，控制器未接收")
PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
