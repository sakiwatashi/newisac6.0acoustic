#!/usr/bin/env bash
# 實驗：閉環抓取掃描 v4 — fused_distance_m (Tier-B energy) + Robotiq 2F-85 finger joints
#
# 設計：
#   - Phase C：完整接近 + Robotiq 2F-85 finger joints 抓取 + 物理升舉
#   - acoustic_only 模式（無 oracle 輔助）
#   - 控制器距離：fused_distance_m（early_energy Tier-B 融合）
#   - 夾爪：--final-gripper 使用預設值 "robotiq"（不指定該旗標），即 Robotiq 2F-85
#     finger joints（透過 ur10e_robotiq_common.initialize_ur10e_manipulator 驅動），
#     不再使用 SurfaceGripper。
#   - 30 episodes，trial_id 0-29
#
# 校正表：
#   實際載入的校正表是
#     runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json
#   （由 ultrasonic_grasp_common.py 的 _tier_b_calibration_tables() 透過
#   acoustic_calibration_v1.load_tier_b_calibration() 讀取），而非
#   acoustic_calibration_v1.DEFAULT_CALIBRATION 內建常數表。
#
# 前提：approach_sweep_v4 確認接近 30/30 = 100%
#
# 用法: bash runtime/run_closed_loop_grasp_sweep_robotiq.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_ultrasonic_closed_loop_grasp.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/grasp_sweep_v4_robotiq
STAGE=/home/lab109/song/isaacsim6.0/runtime/scenes/grasp_sweep_v4_robotiq.usda

mkdir -p "$BASE_OUT"
mkdir -p "$(dirname "$STAGE")"
echo "=== 閉環抓取掃描 v4 (fused_distance_m, acoustic_only, Robotiq 2F-85 finger joints) — $(date) ===" | tee "$BASE_OUT/run.log"
echo "controller: fused_distance_m (early_energy Tier-B, 校正表: tier_b_calibration.json)" | tee -a "$BASE_OUT/run.log"
echo "gripper: Robotiq 2F-85 finger joints（預設 --final-gripper robotiq，不使用 SurfaceGripper）" | tee -a "$BASE_OUT/run.log"
echo "claim_mode: acoustic_only" | tee -a "$BASE_OUT/run.log"
echo "episodes: 30 (trial_id 0-29)" | tee -a "$BASE_OUT/run.log"

$ISAACSIM "$SCRIPT" \
    --output-dir "$BASE_OUT" \
    --output-stage "$STAGE" \
    --overwrite \
    --episode-trial-ids 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29 \
    --control-mode closed_loop \
    --claim-mode acoustic_only \
    --enable-lift \
    --settle-steps 30 \
    --substeps-per-sample 2 \
    2>&1 | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 彙整抓取掃描結果 ===" | tee -a "$BASE_OUT/run.log"

python3 - <<'PYEOF'
import json, pathlib, math

base = pathlib.Path("/home/lab109/song/isaacsim6.0/runtime/outputs/grasp_sweep_v4_robotiq")
ep_path = base / "episodes_summary.json"
if not ep_path.exists():
    print("(無 episodes_summary.json)")
    raise SystemExit(0)

data = json.loads(ep_path.read_text())
episodes = data.get("episodes", [])

APPROACH_SUCCESS = {
    "standoff_reached", "standoff_reached_ik_limit", "standoff_reached_search_limit",
    "standoff_reached_forward_cap", "standoff_reached_fusion_saturation",
    "standoff_reached_forward_cap_rescue", "standoff_reached_fusion_saturation_rescue",
    "tier_b_lateral_complete", "descend_ready",
}

n = len(episodes)
approach_ok = sum(1 for e in episodes if e.get("approach_reason", "") in APPROACH_SUCCESS)
grasp_ok    = sum(1 for e in episodes if e.get("success", False))

print(f"\n=== Phase C 閉環抓取 v4 (fused_distance_m, acoustic_only, Robotiq 2F-85 finger joints) ===")
print(f"  接近成功: {approach_ok}/{n} = {approach_ok/n*100:.1f}%")
print(f"  抓取成功: {grasp_ok}/{n}  = {grasp_ok/n*100:.1f}%")
if approach_ok > 0:
    cond_grasp = sum(1 for e in episodes
                     if e.get("approach_reason","") in APPROACH_SUCCESS and e.get("success", False))
    print(f"  P(grasp|approach_ok): {cond_grasp}/{approach_ok} = {cond_grasp/approach_ok*100:.1f}%")

from collections import Counter
print(f"\n  approach_reason 分布:")
for reason, cnt in sorted(Counter(e.get("approach_reason","?") for e in episodes).items(), key=lambda x: -x[1]):
    ok = reason in APPROACH_SUCCESS
    print(f"    {'✓' if ok else '✗'} {reason}: {cnt}")

print(f"\n  terminal_reason 分布 (含抓取):")
for reason, cnt in sorted(Counter(e.get("terminal_reason","?") for e in episodes).items(), key=lambda x: -x[1]):
    print(f"    {reason}: {cnt}")

print(f"\n  各 episode 結果:")
for e in episodes:
    a_ok = e.get("approach_reason", "") in APPROACH_SUCCESS
    g_ok = e.get("success", False)
    wx = e.get("wrench_oracle_position_m", [float("nan")])[0]
    print(f"  A={'✓' if a_ok else '✗'} G={'✓' if g_ok else '✗'} "
          f"ep={e['episode_id']:02d} trial={e['trial_id']:02d} "
          f"wx={wx:.3f}m  {e.get('approach_reason','?')} → {e.get('terminal_reason','?')}")
PYEOF

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"

python3 /home/lab109/song/isaacsim6.0/scripts/analyze_stop_position.py --run-dir "$BASE_OUT" 2>&1 | tee -a "$BASE_OUT/run.log"
