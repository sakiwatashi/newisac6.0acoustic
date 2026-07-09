# notes.md — 健檢過程發現、背景脈絡、後續接手者須知
# isaacsim6.0 Acoustic Thesis Pipeline
# 健檢日期：2026-07-04

---

## 一、專案規則（健檢中學到的）

### 規則 1：口試前不動核心腳本
- Phase A/B/C 的核心腳本（`official_asset_ur10_fixed_tcp_distance_sweep.py`、`official_asset_ur10_ultrasonic_closed_loop_grasp.py`）不可在口試前重構
- 任何 import 鏈的改動都需要重新執行 smoke test

### 規則 2：Claim Boundary 至關重要
- 這個專案最特別的地方：有明確的「不可宣稱」清單
- Supervisor 用 oracle 距離（幾何護欄）這件事必須始終在 claim boundary 中說清楚
- 最終夾取 ~20% 兩組相近 → 不是聲學問題，不可宣稱聲學控制了夾取

### 規則 3：Passport 系統是唯一真實來源
- 幾何常數只從 `geometry_passport_v1.py` 和 `grasp_passport_v1.py` 讀取
- 不要在其他腳本中硬寫幾何數字
- `surface_gripper_path()` 已修復並與 `setup_surface_gripper()` 一致

### 規則 4：v9 canonical dataset 是論文數字的來源
- `physical_ai_v9_skip_lift_clean`（49 trials，closed_loop=25，open_loop=24）
- 所有論文數字（84% vs 29%，F1 0.598）均來自此 batch

### 規則 5：PyRoom (PRA) 已移出論文主線
- `run_pyroom_experiment_4_passport_v1.sh` 仍存在但不應引用
- 相關文件（`thesis/paper_rewriting_output/`）是文獻搜尋輸出，非實驗結果

---

## 二、架構發現

### 發現 1：核心 Library 集中度良好
以下三個檔案是整個管線的核心：
```
rtx_acoustic_factory.py      ← GMO 解析中心（不分散）
acoustic_calibration_v1.py   ← 標定表中心（不分散）
ultrasonic_closed_loop_controller.py ← 控制器（不分散）
```
這三個檔案的設計是好的，沒有重複。

### 發現 2：試驗腳本呈現「快速迭代」模式
17+ 個 `official_asset_ur10_*.py` 腳本均複製相同的向量工具，說明開發模式是「複製模板→修改業務邏輯」。這是實驗管線的典型開發方式，技術債是刻意的（快速迭代優先）。

### 發現 3：兩層 Passport 分工清晰
```
geometry_passport_v1.py  →  場景幾何（房間、感測器）
grasp_passport_v1.py     →  夾取任務幾何（目標物、走廊）
```
雖然有 `ROBOT_PRIM_PATH` 重複定義，但邏輯上合理。

### 發現 4：Lab 目錄是獨立的 Isaac Lab 附錄
`lab/` 下的 RL/SL 實驗與主論文（scripts/）在 Python 環境上是分開的：
- scripts/ 使用 Isaac Sim standalone Python（from isaac sim app）
- lab/ 使用 Isaac Lab 的 Python（另一個 Python 環境）
不可混用。

### 發現 5：Shell 腳本版本演進軌跡
`run_rl_distance_in_sim_long.sh` → `_long_v4.sh` → `_long_v5.sh` 表示多次調整 RL 訓練超參數。v5 是最終版，v4 是歷史紀錄。

---

## 三、走過但放棄的死路

### 死路 1：試圖確認 runtime/outputs/ 完整結構
健檢工具無法讀取所有 runtime 輸出目錄的完整內容（檔案太多）。只確認了關鍵目錄是否存在，未逐一確認所有 trial CSV 的內容完整性。

### 死路 2：比對各 to_jsonable() 版本差異
Agent C 發現 13+ 份 `to_jsonable()`「基本相同（略有微差）」，但未能精確定位每個版本的差異。若要統一，需要手動讀取並比對每個版本。

### 死路 3：確認 extsDeprecated 是否存在
健檢範圍不包含讀取 `app/` 目錄（太大），因此無法確認 `app/extsDeprecated/isaacsim.robot_motion.motion_generation/` 是否實際存在。

---

## 四、意外發現

### 意外 1：沒有任何 TODO/FIXME/HACK
完全乾淨。243 個 print() 都是刻意的 pipeline logging（帶 `flush=True`）。這說明代碼是相對成熟的。

### 意外 2：test_*.py 存在 4 個
```
test_acoustic_calibration_v1.py
test_acoustic_features.py
test_grasp_passport_reach.py
test_ultrasonic_closed_loop_controller.py
```
這些測試的覆蓋率未知，但它們的存在說明關鍵 library 有被測試。建議健檢完成後確認這些測試是否可以獨立執行（不需要 Isaac Sim）。

### 意外 3：論文統整有提供給指導教授的版本
`thesis/論文統整_指導教授用.md` — 這個中文命名的文件是給指導教授看的論文統整。口試前應確認此版本是否對齊 `THESIS_OUTLINE_FCU_2026-06-30.md`（canonical 版本）。

### 意外 4：`host_official_rtx_acoustic_ur10_smoke.py:24` 的 debug 場景
`DEFAULT_INPUT_SCENE = .../ur10_ee_articulated_debug/...` — smoke 腳本預設載入一個帶 `debug` 名稱的場景。若此場景與正式實驗場景有差異，smoke 測試結果可能不代表正式實驗行為。

---

## 五、後續接手者必須知道的背景

### 背景 1：Isaac Sim 的 RTX Acoustic 是「實驗性 API」
- 位於 `isaacsim.sensors.experimental.rtx` — 以 `experimental` 命名的 API 有可能在 Isaac Sim 更新中消失或改變介面
- 本論文使用 6.0.0-rc.59，任何升級都需要重新確認 API 相容性

### 背景 2：SurfaceGripper 的 C++ Plugin 時序問題（未解）
- 修復了 gripper prim 路徑（`ee_link` 下），但 C++ plugin 在 `world.reset()` 時才掃描 prim
- 若 `setup_surface_gripper` 在 `world.reset()` 之後呼叫，plugin 可能仍找不到 gripper
- 這是**殘留風險**，需要實際執行 smoke test 才能確認

### 背景 3：open-loop baseline 的定義
- open-loop 直接讀 oracle target pose → 這是最理想的 open-loop（知道目標在哪）
- 若要用更嚴格的 open-loop（完全不知道目標座標），結果差距會更大
- 論文應清楚描述 open-loop baseline 的定義

### 背景 4：--skip-lift 是論文數字的前提
- v9 所有 25 個 closed-loop trials 都使用 `--skip-lift`（FixedCuboid）
- 最終成功率 20% 是在 **contact-only** 條件下的數字，不是真實提升夾取
- 這個條件必須在論文中說清楚，否則讀者會誤解夾取能力

---

## 六、健檢工具使用紀錄

| Agent | 模型 | 用途 | 耗時 | 工具使用數 |
|-------|------|------|------|----------|
| A | Haiku | 檔案結構掃描 | ~56 s | 30 |
| B | Haiku | TODO/FIXME/例外掃描 | ~69 s | 48 |
| C | Haiku | 重複代碼偵測 | ~82 s | 26 |
| D | Haiku | 文件一致性比對 | ~74 s | 43 |

主模型（Sonnet 4.6）負責：架構判斷、優先級排序、文件撰寫、風險判讀。
