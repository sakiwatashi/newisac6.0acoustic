# risks.md — 已知風險、未解問題、未驗證假設
# isaacsim6.0 Acoustic Thesis Pipeline
# 健檢日期：2026-07-04

---

## 一、口試前高優先風險

### R-01 🔴 Canonical Phase A 摘要目錄不存在
- **風險描述：** `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/` 在 DATA_MANIFEST.md 和 REPRODUCIBILITY_AUDIT.md 中均標記為「應進 git」的 canonical 輸出，但目前在 `runtime/outputs/` 下不存在。
- **影響：** 口試委員若嘗試驗證 Phase A 的 ρ≈−0.66 數字（claim L1），將找不到任何可直接讀取的摘要。
- **緩解方式：**
  1. 重跑 `bash scripts/run_phase3_repeatability_and_analysis.sh`（需要完整 Isaac Sim 環境）
  2. 或確認此目錄是否在其他位置（如外接硬碟）並補回
- **驗證狀態：** ❌ 未驗證（目錄確認不存在）
- **優先級：** P0 — 口試前必須解決

---

### R-02 🔴 feature_ablation_summary.csv 與文件記載不符
- **風險描述：** REPRODUCIBILITY_AUDIT.md 第 2 節預期 `physical_ai_v9_skip_lift_clean_ablation/feature_ablation_summary.csv`，但實際存在的是 `policy_predictions.csv` 和 `policy_report.json`（三個子目錄：all/acoustic_only/pose_only）。
- **影響：** 若口試委員執行 `--skip-batch` 驗證指令，無法找到預期的 CSV 檔案。F1 數字（0.684/0.598/0.533）可能在 JSON 中，但路徑不符文件。
- **緩解方式：**
  1. 確認 JSON 中是否有對應數字，若有，更新 REPRODUCIBILITY_AUDIT.md 說明實際路徑
  2. 或產生 `feature_ablation_summary.csv` 作為 JSON 的摘要輸出
- **驗證狀態：** ⚠️ 部分驗證（目錄結構確認，CSV 不存在確認，JSON 內容未驗證）
- **優先級：** P0 — 口試前必須解決

---

### R-03 🟡 acoustic_calibration_v1.py 硬寫路徑靜默 fallback
- **風險描述：** `acoustic_calibration_v1.py:13` 硬寫 `tier_b_calibration.json` 的絕對路徑。若路徑不存在，靜默 fallback 至 `DEFAULT_CALIBRATION`，無任何警告訊息。
- **影響：** 若 calibration JSON 因某原因丟失或路徑改變，實驗仍可執行但使用非最新標定表，可能導致距離估算偏差，但無法從輸出察覺。
- **緩解方式：** 確認 `runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json` 存在（Agent D 確認此目錄存在，但未確認 JSON 內容）
- **驗證狀態：** ⚠️ 部分驗證（目錄存在，JSON 存在性未確認）
- **優先級：** P1

---

## 二、中優先技術風險

### R-04 🟡 `extsDeprecated/` 路徑依賴
- **風險描述：** `geometry_passport_v1.py:55,59` 和 `ur10e_robotiq_passport_v1.py:20,24` 等檔案引用 `app/extsDeprecated/isaacsim.robot_motion.motion_generation/` 路徑。
- **影響：** IK 相關腳本（`official_asset_ur10_ik_distance_waypoint_acoustic_capture.py`、`official_asset_ur10_ik_distance_planner.py`）使用此路徑。若 Isaac Sim 更新移除 `extsDeprecated/` 目錄，這些腳本將在啟動時崩潰。
- **說明：** Phase A/B/C 主流程不使用 IK（固定 TCP 或 UR 直接 joint 控制），影響範圍限於 IK 探索腳本（不是論文主流程）。
- **驗證狀態：** ⚠️ 部分驗證（路徑使用確認，extsDeprecated/ 目錄實際存在性未確認）
- **優先級：** P2（口試後確認）

---

### R-05 🟡 7 個靜默例外吞噬
- **風險描述：** `ur10e_robotiq_common.py`（L366, L645, L689）、`official_asset_ur10_fixed_tcp_distance_sweep.py`（L539, L544）等處的 `except Exception: pass`。
- **影響：** 若 robot 初始化、速度重置、kinematic joint 定位失敗，不會有任何 log。在批次實驗中，特定 trial 可能因此產生錯誤資料而不被察覺。
- **最高風險位置：** `ur10e_robotiq_common.py:366`（robot 初始化 retry）— 若此處失敗，機器人可能在未正確初始化狀態下執行接近動作。
- **驗證狀態：** ✅ 已驗證（7 個位置確認）
- **優先級：** P2

---

### R-06 🟡 向量數學函式 17+ 份複製
- **風險描述：** `vec_tuple`, `vec_sub`, `vec_norm`, `vec_dot`, `vec_unit` 等完全相同的函式散佈於 17+ 個檔案。
- **影響：** 若發現任何 edge case bug（如 NaN 輸入、除以零），需在 17 個地方同步修復，極易漏改。
- **現況評估：** 目前這些函式的使用範圍（3D float 向量，輸入皆已確認有效）不太可能觸發 edge case。
- **驗證狀態：** ✅ 已驗證（掃描確認各版本實作完全相同）
- **優先級：** P3（口試後重構）

---

## 三、文件風險

### R-07 🟡 論文大綱版本混亂
- **風險描述：** `thesis/` 下存在三個版本的 THESIS_OUTLINE：`06-27`、`06-29`、`06-30`。論文現行版本為 `06-30`，但舊版仍存在。
- **影響：** 口試委員或共同作者若閱讀舊版（特別是 `06-29`，仍有 PyRoom 主貢獻的描述），可能使用過時架構。
- **緩解方式：** 在 `thesis/` 下加入 `INDEX.md` 或在 README 中明確標示 canonical 版本
- **驗證狀態：** ✅ 已驗證（檔案存在確認）
- **優先級：** P1

---

### R-08 🟡 run_pyroom_experiment_4_passport_v1.sh 殘留
- **風險描述：** `scripts/run_pyroom_experiment_4_passport_v1.sh` 仍存在，但 PyRoomAcoustics 已從論文主線移除。
- **影響：** 清單中出現此腳本可能造成混淆，讓閱讀者誤解 PRA 仍是有效實驗路徑。
- **驗證狀態：** ✅ 已驗證（檔案存在確認）
- **優先級：** P3（文件整理）

---

## 四、未驗證假設

### A-01 SurfaceGripper C++ Plugin 時序假設
- **假設：** 修復後的 `setup_surface_gripper`（parent under ee_link）會讓 C++ plugin 在 `world.reset()` 時正確發現 gripper prim。
- **未驗證原因：** 需要完整 Isaac Sim 執行環境才能測試。
- **風險：** 若 plugin 仍在 `world.reset()` 之前掃描，gripper 可能仍找不到。
- **建議：** 執行 `run_host_ultrasonic_closed_loop_grasp_smoke.sh` 觀察是否仍有 "Gripper not found" 錯誤。

### A-02 calibration JSON 內容的時效性
- **假設：** `tier_b_calibration.json` 的標定值對應於當前 Isaac Sim 版本和場景設定。
- **未驗證原因：** JSON 檔案存在但內容未讀取。
- **風險：** 若標定是在不同場景配置下產生，融合距離估算可能有系統性偏差。

### A-03 Phase A raw data 可重現性
- **假設：** 執行 `run_phase3_repeatability_and_analysis.sh` 可重現 30/30 PASS 和 ρ≈−0.66 結果。
- **未驗證原因：** Raw data 未進 git，最近一次確認重現時間不明。
- **風險：** Isaac Sim 版本或場景格式的微小變動可能導致 GMO 統計略有不同。

---

## 五、後續開發注意事項

### 技術債優先順序（口試後）
1. 建立 `vector_utils.py`，消除 17+ 份重複（影響最大）
2. 統一 `to_jsonable()`（可同時進行）
3. 修復 7 個靜默例外（加 log）
4. 用相對路徑替換 30+ 個硬寫絕對路徑
5. 確認 `extsDeprecated/` 路徑的長期支援性
