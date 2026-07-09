#!/usr/bin/env bash
# 無手臂 WPM 聲學接近偵測測試
#
# 場景：只有固定感測器 + 單一 Cube 目標，無手臂、無房間牆壁
# 目標：驗證 WPM 是否能回應 Cube 目標的距離變化
#
# 結果解讀：
#   peak_sample_idx r > 0.80 → WPM 可偵測 Cube 距離 → 無手臂方案可行！
#   peak_sample_idx r < 0.40 → WPM 對 Cube 無響應 → 參數化模型徹底確認
#   numElements = 0 全部 → WPM 完全看不到 Cube prim
#
# 用法: bash runtime/run_armfree_proximity_test.sh

set -e
ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
SCRIPT=/home/lab109/song/isaacsim6.0/scripts/armfree_acoustic_proximity_test.py
OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/armfree_test_v1

mkdir -p "$OUT"
echo "=== 無手臂 WPM 聲學接近偵測 — $(date) ===" | tee "$OUT/run.log"
echo "場景: 感測器(0,0,0) + Cube 沿 +X 軸 0.30m→1.00m" | tee -a "$OUT/run.log"

$ISAACSIM "$SCRIPT" \
    --min-dist 0.20 \
    --max-dist 1.50 \
    --n-steps 30 \
    --n-settle 12 \
    --n-measure 6 \
    --cube-size 0.20 \
    --center-freq 40000 \
    --mount-spacing 0.10 \
    --az-span 90 \
    --el-span 90 \
    --output-dir "$OUT" \
    2>&1 | tee -a "$OUT/run.log"

echo "" | tee -a "$OUT/run.log"
echo "=== 完成 $(date) ===" | tee -a "$OUT/run.log"
