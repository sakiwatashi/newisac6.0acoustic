# plan.md — 執行計畫(2026-07-08)

> 粒度目標:Opus/Sonnet 等任何模型照做即可。每步附驗收。狀態欄由執行者隨做隨更。
> 前置閱讀:`docs/HEALTH_CHECK_2026-07-08.md`(F1–F12)、`docs/handoff/decisions.md`(D1–D7)。

## 步驟總表

| # | 步驟 | 執行者 | 狀態 |
|---|------|--------|------|
| 1 | 致盲旗標改碼(D1) | 主 agent | ✅ 完成並離線驗證 |
| 2 | F4 測試修復 + 全測試 | SA1 (haiku) | ✅ 17/17 全綠 |
| 3 | 兩支 sweep shell + 分析腳本 | SA2 (sonnet) | ✅ 驗收通過(對 v4 重現手算值) |
| 4 | E1:盲走裁定 sweep(30 eps) | 主 agent | ✅ 03:24 完成,exit 0 |
| 5 | E1 判讀 → 裁定 F1/D4 | 主 agent | ✅ **F1 CONFIRMED**,見 F1_adjudication_report.md |
| 6 | E2:Robotiq grasp sweep(30 eps) | 主 agent | ✅ 03:44 完成,12/30 lift success |
| 7 | E2 判讀(與 F1 合併解讀) | 主 agent | ✅ 見 E2_grasp_report.md(成功=幾何帶效應) |
| 8 | 裁定報告 + risks.md + 文件收尾 | 主 agent | ✅ 本交接包完成 |

## 各步驟細節與驗收

### 步 1:致盲旗標(已完成)
- 檔案:`scripts/ultrasonic_grasp_common.py`
- 內容:`import dataclasses`;模組層 `BLIND_APPROACH = os.environ.get("GRASP_BLIND_APPROACH","").strip()=="1"` + 啟用告示 print;`_acoustic_features_from_capture` 在旗標開時 `dataclasses.replace(frame, fused_distance_m=inf, estimated_distance_energy_m=inf)`。
- 驗收:✅ 離線驗證 frozen dataclass replace 可行、inf 使 standoff 觸發恆為 False、gmo_valid 不受影響。

### 步 2:F4 測試修復
- 檔案:`scripts/test_ultrasonic_closed_loop_controller.py` 的 `test_calibration_interpolation`,對齊 peak_idx 新語意(22 → ≈0.50 m;NaN/負值 → NaN)。
- 驗收:4 個測試檔全綠(`test_ultrasonic_closed_loop_controller` 6/6、`test_acoustic_calibration_v1` 3/3、`test_acoustic_features` 4/4、`test_grasp_passport_reach` 4/4)。

### 步 3:工具生成
- `scripts/analyze_stop_position.py`(stdlib-only):per-trial 停止位置(history CSV 中該 trial 的 max sensor_x 列)、oracle 距離@停止、Pearson r(wrench_x, stop_x)、≤0.45/≤0.35 比率、reason 分布;`--compare` 雙目錄對照;輸出 JSON+stdout。
- `runtime/run_blind_forward_baseline.sh`:同 v4 幾何/參數 + `export GRASP_BLIND_APPROACH=1`,輸出 `runtime/outputs/blind_forward_baseline_v1/`。
- `runtime/run_closed_loop_grasp_sweep_robotiq.sh`:同 grasp_sweep_v3 但移除 `--final-gripper surface`,輸出 `runtime/outputs/grasp_sweep_v4_robotiq/`。
- 驗收:`bash -n` 通過;`analyze_stop_position.py --run-dir runtime/outputs/approach_sweep_v4` 輸出 stop_x 恆定 ≈0.958、oracle≤0.45 = 29/30(與 health check 手算一致)。

### 步 4:E1 執行
```bash
cd /home/lab109/song/isaacsim6.0 && bash runtime/run_blind_forward_baseline.sh
```
- 驗收:run.log 出現「BLIND_APPROACH=1」告示行;30 episodes 完成;`blind_forward_baseline_v1/episodes_summary.json` 存在。

### 步 5:E1 判讀(裁定規則,判讀前先寫死)
- **若** 盲走 stop_x 分布 ≈ v4(恆定 ~0.958)**且** oracle≤0.45 比率 ≥ v4 − 10%(即 ≥ 27/30 上下):**F1 成立**,v4 指標無效,D4 生效(論文錨定 v9)。
- **若** 盲走顯著更差(例:大量 episode 停不進 0.45,或 stop_x 分布明顯不同):F1 部分推翻,重新分析 v4 中聲學的實際貢獻(檢查觸發時序)。
- 產出:`docs/handoff/F1_adjudication_report.md`,附兩組數據對照表。
- 注意:盲走的 terminal_reason 會是 `ik_failed`(inf 過不了 `standoff_reached_ik_limit` 的 fused≤0.47 門)——**判讀只看停止位置與 oracle 距離,不看 reason 標籤**。

### 步 6:E2 執行
```bash
cd /home/lab109/song/isaacsim6.0 && bash runtime/run_closed_loop_grasp_sweep_robotiq.sh
```
- 驗收:run.log 出現「Robotiq finger joints: [...]」(證明走 Robotiq 路徑,非 SurfaceGripper);30 episodes 完成。
- 若失敗率異常(如 30/30 同一錯誤),檢查 `GRASP_FINGER_PHYSICS_CONTROL` 環境變數(預設 kinematic 手指;必要時 `export GRASP_FINGER_PHYSICS_CONTROL=1` 重跑一次對照,記錄兩版結果)。

### 步 7:E2 判讀
- 主指標:grasp success 數、`P(grasp|approach)`;
- **關鍵交叉分析**:成功 trials 的 wrench_x 分布——若集中在固定停止點附近(約 0.96±0.1 m 帶),成功率不可宣稱為聲學閉環能力(D3 判讀前提)。
- 與 grasp_sweep_v3(0/30, SurfaceGripper)及 v9 final(~20%)並列。

### 步 8:收尾
- `docs/handoff/risks.md`(誠實列,含未驗證項)。
- 更新 `docs/handoff/notes.md` 最終版。
- 總結回報:E1 裁定結論、E2 結果、交接包清單。

## 回滾方式

- 致盲旗標:刪除 `ultrasonic_grasp_common.py` 中標記「Adjudication spike (health check F1, 2026-07-08)」的區塊與 `import dataclasses` 行即可(旗標預設關閉,不刪也不影響正常運行)。
- 新增檔案全部可直接刪除,無其他耦合。
