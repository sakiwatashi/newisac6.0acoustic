#!/usr/bin/env bash
# 實驗：盲走前進基準線 v1 — 健檢 F1 裁定對照組
#
# 目的：
#   這是健檢 F1（approach_sweep_v4 停止位置與目標位置相關性偏低）的裁定對照組。
#   設定 GRASP_BLIND_APPROACH=1 後，ultrasonic_grasp_common.py 會把 fused_distance_m
#   與 estimated_distance_energy_m 強制覆寫為 +inf（感測器致盲），使控制器的聲學
#   standoff 觸發條件永遠無法成立 —— 手臂只能靠其他終止條件（IK 極限 / 搜尋極限 /
#   forward cap 等）停下，完全不接收聲學距離資訊。
#
#   幾何設置（wrench 位置、trial_id 序列、settle/substep 參數）與 approach_sweep_v4
#   完全相同，僅差在這個環境變數。若盲走情況下的停止位置分布與 approach_sweep_v4
#   的停止位置分布在統計上無顯著差異，則可支持「approach_sweep_v4 的停止位置其實
#   主要由 IK/搜尋極限而非聲學閉環決定」的假設。
#
#   注意：實際載入的校正表仍是
#     runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json
#   （由 ultrasonic_grasp_common.py 的 _tier_b_calibration_tables() 透過
#   acoustic_calibration_v1.load_tier_b_calibration() 讀取），但在盲走模式
#   （GRASP_BLIND_APPROACH=1）下這張表完全不影響結果，因為 fused/energy 距離
#   在特徵計算後被直接覆寫為 +inf。
#
# 用法: bash runtime/run_blind_forward_baseline.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_ultrasonic_closed_loop_grasp.py
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/blind_forward_baseline_v1
STAGE=/home/lab109/song/isaacsim6.0/runtime/scenes/blind_forward_baseline_v1.usda

mkdir -p "$BASE_OUT"
mkdir -p "$(dirname "$STAGE")"
echo "=== 盲走前進基準線 v1（GRASP_BLIND_APPROACH=1，健檢 F1 裁定對照組） — $(date) ===" | tee "$BASE_OUT/run.log"
echo "controller: fused/energy distance 強制為 +inf（感測器致盲，聲學觸發永不生效）" | tee -a "$BASE_OUT/run.log"
echo "claim_mode: acoustic_only（與 approach_sweep_v4 相同，但聲學資訊被致盲）" | tee -a "$BASE_OUT/run.log"
echo "幾何與 trial_id 序列與 approach_sweep_v4 完全相同" | tee -a "$BASE_OUT/run.log"
echo "校正表: runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json（盲走模式下無作用）" | tee -a "$BASE_OUT/run.log"
echo "episodes: 30 (trial_id 0-29)" | tee -a "$BASE_OUT/run.log"

export GRASP_BLIND_APPROACH=1
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
echo "=== 彙整盲走基準線結果，並與 approach_sweep_v4 對照 ===" | tee -a "$BASE_OUT/run.log"

python3 /home/lab109/song/isaacsim6.0/scripts/analyze_stop_position.py --run-dir "$BASE_OUT" --compare /home/lab109/song/isaacsim6.0/runtime/outputs/approach_sweep_v4 2>&1 | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$BASE_OUT/run.log"
