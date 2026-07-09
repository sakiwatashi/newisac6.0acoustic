#!/usr/bin/env bash
# V2 S1 — 感測包絡量測掃描（52 cells,4 blocks:A/B/C/D）
#
# 規格來源:docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md §6(S1 block 定義與判準)、
#           §5.2(cell schema)、§5.3(analyze_envelope.py)。
#
# 內容:對 docs/plan_v2/s1_cells/*.json(52 個 cell,由
#       docs/plan_v2/s1_cells/generate_cells.py 生成)逐一呼叫
#       scripts/paired_capture_runner.py(單 session 單 cell,§5.1 架構決策),
#       輸出落在 runtime/outputs/v2_s1_envelope/<cell_id>/;全部跑完後呼叫
#       scripts/analyze_envelope.py 產生 cells.csv + envelope_summary.json + 熱圖。
#
# 五條鐵律(§4)如何滿足:
#   1. 配對對照   — paired_capture_runner.py 每 cell 內同 session 跑
#                    with_target / noise_ref / without_target 三條件配對擷取。
#   2. 資訊消融   — 不適用(S1 無控制迴路;此律屬於 Stage 2 D1 三臂設計)。
#   3. 預註冊判準 — 見下方「預註冊判準」區塊,先於任何一格資料寫在此處。
#   4. 原始波形落地 — paired_capture_runner.py 對每 cell 寫
#                      <cell_id>/waveforms/{with,noise_ref,without}.npy。
#   5. acoustic_only — cell JSON 的 target_distance_m/target_size_m 等只用於
#                       建場景與標註輸出,S1 沒有控制迴路可能誤用 oracle 量。
#
# 預註冊判準(§6,執行前已定案,不得依資料調整):
#   - SNR_peak > 10  =>  該 cell 可偵測(由 scripts/analyze_envelope.py 自動裁定)。
#   - Block D(桌+手臂,12 cells)全數不可偵測
#       => 判定「腕載水平構型不可行」,Stage 2 場景構型必須改為俯視/墊高/合作目標。
#   - 52 格全數不可偵測
#       => 提前止損點 #1:論文降級為「WPM 特性化 + 負結果」,停止 Stage 2。
#
# 續跑:若 $BASE_OUT/<cell_id>/cell_result.json 已存在則視為該 cell 已完成,
#       跳過並印 "SKIP <cell_id>"(額度中斷後重跑不重複燒 GPU)。
#
# 用法: bash runtime/run_v2_s1_envelope.sh
# 不會由本次任務執行(建立即止,不跑 Isaac Sim)。

set -e

ISAACSIM=/home/lab109/song/isaacsim6.0/app/python.sh
RUNNER=/home/lab109/song/isaacsim6.0/scripts/paired_capture_runner.py
ANALYZER=/home/lab109/song/isaacsim6.0/scripts/analyze_envelope.py
CELLS_DIR=/home/lab109/song/isaacsim6.0/docs/plan_v2/s1_cells
BASE_OUT=/home/lab109/song/isaacsim6.0/runtime/outputs/v2_s1_envelope

mkdir -p "$BASE_OUT"
echo "=== V2 S1 包絡掃描 — $(date) ===" | tee -a "$BASE_OUT/run.log"
echo "cells 目錄: $CELLS_DIR" | tee -a "$BASE_OUT/run.log"
echo "輸出目錄: $BASE_OUT" | tee -a "$BASE_OUT/run.log"

n_total=0
n_skip=0
n_run=0

for J in "$CELLS_DIR"/*.json; do
    [ -e "$J" ] || continue
    base="$(basename "$J")"
    # generate_cells.py 只生成 *.json,理論上不會出現在這個 glob 裡;
    # 仍明確排除以防萬一有人把產生器複製成 .json 名稱。
    if [ "$base" = "generate_cells.py" ]; then
        continue
    fi

    n_total=$((n_total + 1))
    cell_id="$(basename "$J" .json)"
    result_json="$BASE_OUT/$cell_id/cell_result.json"

    if [ -f "$result_json" ]; then
        echo "SKIP $cell_id"
        n_skip=$((n_skip + 1))
        continue
    fi

    echo "" | tee -a "$BASE_OUT/run.log"
    echo "--- RUN $cell_id ---" | tee -a "$BASE_OUT/run.log"
    "$ISAACSIM" "$RUNNER" \
        --cell-json "$J" \
        --output-dir "$BASE_OUT" \
        2>&1 | tee -a "$BASE_OUT/run.log"
    n_run=$((n_run + 1))
done

echo "" | tee -a "$BASE_OUT/run.log"
echo "=== 掃描完成: $n_total cells 總計, $n_run 新跑, $n_skip 跳過(續跑) ===" | tee -a "$BASE_OUT/run.log"

echo "" | tee -a "$BASE_OUT/run.log"
echo "--- ANALYZE ---" | tee -a "$BASE_OUT/run.log"
python3 "$ANALYZER" --scan-dir "$BASE_OUT" 2>&1 | tee -a "$BASE_OUT/run.log"
