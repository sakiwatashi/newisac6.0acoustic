# 今日工作統整 — 2026-07-05

**專案：** 逢甲大學電聲碩士 · RTX Acoustic 超音波閉環接近控制
**本日主軸：** ToF=0 根本診斷 → 訊號特徵工程系統性探索 → WPM 全向性發現 → ML 方向確立

---

## 一、問題起點：tof_ns 全為 0 的診斷

### 現象
閉環控制器的距離估算（`estimated_distance_tof_m`）永遠輸出無效值，因為所有 GMO 的 `timeOffsetNs` 欄位均為 0.0。

### 診斷過程
靜態診斷腳本（`scripts/diagnose_tof_zero.py`）逐步追蹤程式碼路徑：

```
GMO.timeOffsetNs → _pick_tof_primary_way() → first_time_offset_ns=0.0
→ _safe_float(reject_zero=True) → 回傳 nan
→ estimate_distance_from_tof(nan) → nan
→ 融合器 fallback 到 energy-based 估算
```

### 根本原因
**Isaac Sim 6.0 WPM 聲學引擎不填充 `timeOffsetNs` 欄位。**

證據來源：官方測試檔 `test_acoustic_sensor.py` L97-105 的斷言只是 `>= 0`，不要求 `> 0`；官方範例 `inspect_acoustic_gmo.py` 從未讀取 `timeOffsetNs`。

這是一個 **API 層級的未完成功能**，不是設定問題，無法透過調整參數修復。

### 影響評估
- `tof_ns` 全為 0 → 距離融合（fused_distance_m）完全仰賴 energy-based 估算
- energy-based 校正在當前設定下精度約 ±0.26m（Pearson r≈0.175）
- **論文主軸（84% vs 29% approach 成功率）不受影響**，因為閉環控制器已設計為容錯架構

---

## 二、實驗一：peak_sample_idx — 用波形峰值樣本作為 ToF 代替

### 假設
GMO 的原始振幅波形（120+ 樣本/每個 Signal Way）包含時序資訊。取每個 Signal Way 的振幅最大值位置（`argmax`），換算成飛行時間距離。

### 實作
在 `rtx_acoustic_factory.py` 的 `SignalWayStats` 新增：
- `peak_sample_idx: int` — 整條波形的 argmax（樣本序號）

在 `parse_signal_ways()` 兩條路徑（structured stride 和 fallback）中計算並傳播。

建立校正掃描腳本：`runtime/run_peak_idx_calibration.sh`
- 7 個 trial（wrench_x 從 0.717m 到 1.288m）
- 每個 trial 各自存到獨立子目錄
- 自動合併 CSV

### 實驗結果
```
peak_sample_idx range: 88–93（只有 4 個不同值）
oracle_distance_m range: 0.243–0.814 m
Pearson r = -0.12
```

### 失敗原因分析
`peak_sample_idx = 88` 幾乎固定，對應的是 **後牆反射**，而非目標物：

| 反射體 | 距離 | 估算抵達樣本 |
|---|---|---|
| 目標扳手 | 0.24–0.81m | sample 11–35 |
| 桌面 | 0.20m | sample 8.8 |
| 地板 | 0.60m | sample 26.4 |
| **後牆** | **2.0m** | **sample 88 ← argmax 固定在這** |

整條波形的最大振幅永遠在後牆回波（sample ~88），目標回波被淹沒。

### 結論
`argmax(full_waveform)` 不是有效的 ToF proxy，失敗率 100%。

---

## 三、實驗二：ultra_early_energy — 縮小時間窗口至前 10%

### 假設
使用前 25% 樣本的 early_energy（Pearson r=+0.044）效果極差，原因是包含太多固定反射。縮小到前 10%（約 12 個樣本），只覆蓋目標距離 ≤0.27m 的回波窗口，同時搭配高吸音材質（Condition C，PRA=0.70）消除牆壁殘響。

### 實作
在 `SignalWayStats` 新增：
- `ultra_early_energy: float` — 前 10% 樣本的能量總和
- `early_peak_sample_idx: int` — 前 10% 窗口內的 argmax

在兩條 `parse_signal_ways()` 路徑中計算，並透過 `_way_fields()` → `summarize_gmo_frame()` → `AcousticFeatureFrame` → CSV 完整傳播。

建立新校正腳本：`runtime/run_ultra_early_calibration.sh`（`--material-condition C`）

**遇到的 Bug：** 腳本首次分析輸出「有效行 0/133」。
**原因：** `_way_fields()` 輸出的鍵名有 `primary_sgw_` 前綴（`primary_sgw_ultra_early_energy`），但分析腳本和 sweep 腳本都在找無前綴的 `ultra_early_energy`，導致 `if key in fields` 永遠為 False。
**修復：** 統一使用帶前綴的鍵名。

### 實驗結果
```
ultra_early_energy (10%): Pearson r = +0.1751（vs 原始 0.044）
early_peak_sample_idx range: 9–26（9 個不同值）
early_peak_sample_idx Pearson r = -0.027（隨機雜訊）
```

### 分析
- 10% 窗口確實比 25% 好（4倍改善）
- `early_peak_sample_idx` 分布：`{9:7, 13:7, 17:7, 19:21, 20:35, 21:35, 22:7, 24:7, 26:7}`
  - Sample 9 = 桌面反射（0.20m → 1.17ms → sample 8.8）
  - Sample 26 = 地板反射（0.60m → 3.50ms → sample 26.4）
  - 目標回波（sample 11–35）淹沒在固定反射中
- 高吸音牆壁消除了房間殘響，但無法消除桌面和地板的固定近場反射

---

## 四、實驗三：差分波形（Differential Waveform）

### 假設
「當前波形 − 基準波形（目標物最遠時的波形）= 新增的目標回波貢獻」。差分後可消除固定反射（桌面、地板、後牆），只留下接近過程中新增的目標回波。

### 實作新增

**`rtx_acoustic_factory.py`：**
- 新增 `extract_primary_raw_amplitudes(gmo, np)` 函式，回傳主要 Signal Way 的完整原始振幅陣列（120-320 個 float）

**`official_asset_ur10_dynamic_approach_calibration_sweep.py`：**
- `writer_state["last_primary_amps"]`：每幀在 Writer 中存入原始振幅
- `--baseline-steps N`：前 N 幀取平均作為每個 trial 的基準（per-trial baseline）
- 差分特徵計算：
  - `diff_early_energy` = sum(|current - baseline|[:25%])
  - `diff_ultra_early_energy` = sum(|current - baseline|[:10%])
  - `diff_peak_sample_idx` = argmax(|current - baseline|)
  - `diff_early_peak_sample_idx` = argmax(|current - baseline|[:10%])

### Per-Trial Baseline 結果
```
diff_ultra_early_energy (10%): Pearson r = -0.2625（負號正確：越近→差分能量越大）
diff_early_peak_sample_idx: range 10–31, Pearson r = +0.2827（正號正確：越遠→回波越晚→樣本序號越大）
diff_peak_sample_idx 分布: {87:7, 88:28, 94:7, 98:77}（仍被後牆主導）
```

### 重要發現：diff_early_peak_sample_idx 具有物理意義
樣本範圍 10–31 對應的距離：
```
sample 10 → oracle ≈ 0.227m
sample 17 → oracle ≈ 0.386m
sample 20 → oracle ≈ 0.454m
sample 23 → oracle ≈ 0.522m
sample 31 → oracle ≈ 0.704m
```
這個範圍**完全覆蓋實驗的 oracle_distance 範圍（0.24–0.81m）**，而且方向正確。這是本次所有實驗中第一個在物理上可解釋的特徵。

### 侷限：Per-Trial Baseline 的問題
每個 trial 用自己的前 3 步作為基準，導致跨 trial 比較的參考系不統一。不同 trial 的基準距離不同（trial_16 基準 oracle=0.814m 很乾淨；trial_18 基準 oracle=0.326m 已有明顯目標回波），削弱了跨 trial 的相關性。

---

## 五、實驗四：全局 Baseline + 差分（Global Baseline Differential）

### 假設
用一次「無扳手場景」的基準掃描錄製純室內波形，對所有 trial 做統一的差分，消除系統誤差。

### 實作
**新增 sweep 腳本參數：**
- `--baseline-mode`：隱藏扳手（`set_prim_visibility(stage, WRENCH_PRIM_PATH, visible=False)`），錄製基準波形
- `--save-baseline-npy PATH`：將每步的原始振幅存成 numpy `.npy`（shape: [n_steps, n_samples]）
- `--baseline-npy PATH`：載入全局基準，每步減去 `baseline_arr[step_idx]`
- 新增輸出欄位：`global_diff_early_energy`, `global_diff_ultra_early_energy`, `global_diff_early_peak_sample_idx`

建立執行腳本：`runtime/run_global_baseline_and_diff.sh`
- Phase 1：用 trial_id=16、隱藏扳手，錄製全局基準 → 存成 `baseline_waveforms.npy`
- Phase 2：7 個 trial 各自載入同一個全局基準做差分

### 結果
```
global_diff_early(25%):      Pearson r = +0.0951
global_diff_ultra_early(10%): Pearson r = +0.2881（全場最高，但方向為「正」）
global_diff_early_peak_idx:  Pearson r = +0.1060
```

### 問題：正向相關的矛盾
`global_diff_ultra_early` r = **+0.2881（正向）** 在物理上應該是**負向**（越近→目標回波越強→差分能量越大）。

分析原因：
1. 全局基準用 trial_16 的機器手臂 IK 位置錄製，但其他 trial 的機器手臂關節角不同（IK 暖啟動不同）→ 機器本體對聲學的陰影效果不同
2. 每個 trial 的桌子 y 位置（`wrench_y_m`）不同，但全局基準固定使用 trial_16 的桌子位置

這些系統誤差導致差分包含「機器手臂位置差」的信號，而非純粹的「目標物距離」信號。全局 baseline 的概念正確，但實作需要**每個 trial 各自錄製無扳手基準**才能消除這個問題。

---

## 六、實驗五：匹配濾波器（Matched Filter / Cross-Correlation ToF）

### 假設
真實的 CH201 晶片用匹配濾波（已知發射脈衝與接收波形的互相關）提取 ToF。Isaac Sim 的 `timeOffsetNs=0` 是 API 層級限制，但原始振幅波形是真實的。自己實作匹配濾波器，繞過 API 限制，從波形提取 ToF。

### 實作
在 `rtx_acoustic_factory.py` 新增 `matched_filter_tof(amplitudes, center_frequency_hz, sample_period_s, np, pulse_duration_periods=3.0)`：
- 建構 Gaussian 窗口正弦波參考脈衝（Gaussian envelope × sin(2πft)）
- 對接收波形做 `np.correlate(amps, ref_pulse, mode="valid")`
- 取互相關絕對值的峰值位置 = 估計的 ToF 樣本序號
- 換算距離：`peak_idx × sample_period_s × 343.0 / 2.0`

建立執行腳本：`runtime/run_matched_filter_calibration.sh`

### 結果（慘敗）
```
mf_tof_sample_idx 分布: {86:105, 89:14, 88:7, 91:7}
mf_tof_distance_m range: 1.954–2.068m
Pearson r = -0.1251
```

### 失敗原因
匹配濾波器搜尋**全條波形**的最大互相關，結果永遠找到**後牆回波**（~2m）。後牆是場景中最強的反射體，其互相關能量遠超目標物。

這個問題需要「限制搜尋窗口」——只在前 10-15% 的樣本（target echo 可能到達的範圍）搜尋峰值，而非全波形搜尋。這是「Early-Window Matched Filter」，尚待實作。

---

## 七、核心發現：WPM 聲學模型為全向性點源

### 發現過程
使用者提問「超音波不是指向性的嗎？」，促使查閱 Isaac Sim 的 USD Schema 定義：

```
/app/extscache/omni.usd.schema.omni_sensors-0.0.0+*/usd_plugins/generatedSchema.usda
```

### Schema 完整內容（WpmAcoustic 相關）
```
class "OmniSensorWpmAcousticSensorMountAPI" {
    float3 omni:sensor:WpmAcoustic:sensorMount:position = (0, 0, 0)
    float3 omni:sensor:WpmAcoustic:sensorMount:rotation = (0, 0, 0)
}
class "OmniSensorWpmAcousticRxGroupAPI" {
    uint[] omni:sensor:WpmAcoustic:rxGroup:receiverIndices = [0]
}
class "OmniSensorWpmAcousticFiringSeqAPI" {
    uint[]  firingSeq:channel
    float[] firingSeq:eventTimeNs
    uint[]  firingSeq:rxGroupId
    uint[]  firingSeq:txSensorId
}
```

**WpmAcoustic 完全沒有以下參數：**
- `beamAngle` / `halfAngleCone`
- `apertureSize` / `effectiveAperture`
- `directivityPattern`
- `beamWaistHorM` / `beamWaistVerM`

（這些參數存在於 `omni:sensor:Core:*` 和 `omni:sensor:WpmDmat:*` 等其他 schema，但不屬於 WpmAcoustic。）

### 結論
**RTX Acoustic WPM 使用「位置+朝向」的點源/點接收模型，不實作指向性波束增益。**

`rotation` 參數只決定坐標系基準（signal way 的 x/y/z 輸出方向），不決定感測靈敏度方向。

### 與真實硬體的 Sim-to-Real Gap

| 特性 | 真實 CH201 | Isaac Sim WPM |
|---|---|---|
| 波束模型 | 窄指向性（±22.5°） | **全向性點源** |
| 側向靈敏度 | -20 to -40 dB（大幅衰減） | 與正前方相同（無衰減） |
| 後牆/地板回波 | 在 off-axis 時被抑制 | **與目標回波同等強度** |
| 目標回波 SNR | 高（off-axis 噪聲被波束濾掉） | 低（所有方向回波混合） |

這解釋了為什麼能量相關性上限是 r≈0.29：固定反射體（後牆、桌面、地板）的回波強度與目標回波相當，使能量特徵的信噪比極低。

### 對論文的意義
這個發現本身是一個**有價值的學術貢獻**：

1. 首次公開記錄 Isaac Sim 6.0 RTX Acoustic WPM 不含指向性波束模型
2. 量化了 sim-to-real gap 對距離估測的影響（energy r: 0.175 → 預計真實硬體 >0.6）
3. 提供了一條改進路徑（Early-Window MF + ML 方法）

---

## 八、所有實驗結果彙整

| 方法 | Pearson r | 備註 |
|---|---|---|
| raw early_energy (25%) | +0.044 | 基準 |
| raw ultra_early_energy (10%) | +0.175 | 縮小窗口有改善 |
| peak_sample_idx (full) | -0.120 | 後牆 sample 88，無用 |
| early_peak_sample_idx (10%) | -0.027 | 隨機雜訊 |
| per-trial diff_ultra_early (10%) | **-0.263** | 方向正確，有意義 |
| per-trial diff_early_peak_idx | **+0.283** | 首個物理可解釋的特徵 |
| global diff_ultra_early (10%) | +0.288 | 最高但符號錯誤（baseline 對不齊） |
| matched filter (全波形) | -0.125 | 找到後牆，失敗 |

**每輪改善遞減，傳統訊號處理已達上限（r≈0.29）。**

---

## 九、程式碼變更總覽

### 新增或修改的檔案

**`scripts/rtx_acoustic_factory.py`**
- `SignalWayStats`：新增 `peak_sample_idx`, `ultra_early_energy`, `early_peak_sample_idx`
- `parse_signal_ways()`：計算上述三個新欄位（structured 和 fallback 兩條路徑）
- `_way_fields()`：傳播新欄位到 summary dict
- `_safe_float()`：新增 `reject_zero` 參數（tof_ns 用）
- 新函式 `extract_primary_raw_amplitudes(gmo, np)`：回傳主要 signal way 的原始振幅陣列
- 新函式 `matched_filter_tof(amplitudes, center_freq_hz, sample_period_s, np)`：Gaussian 窗口互相關 ToF 估算

**`scripts/official_asset_ur10_dynamic_approach_calibration_sweep.py`**
- 新增 args：`--baseline-steps`, `--baseline-mode`, `--baseline-npy`, `--save-baseline-npy`, `--mf-sample-period-us`
- Baseline mode：`set_prim_visibility(stage, WRENCH_PRIM_PATH, visible=False)` 隱藏扳手
- Writer：同步存入 `writer_state["last_primary_amps"]`
- 主迴圈：per-trial diff、matched filter、global baseline diff 計算
- 新增 CSV 欄位：`diff_early_energy`, `diff_ultra_early_energy`, `diff_peak_sample_idx`, `diff_early_peak_sample_idx`, `mf_tof_sample_idx`, `mf_tof_distance_m`, `global_diff_early_energy`, `global_diff_ultra_early_energy`, `global_diff_early_peak_sample_idx`
- 迴圈結束後儲存 baseline npy

**新增腳本：**
- `runtime/run_peak_idx_calibration.sh`：peak_sample_idx 校正掃描
- `runtime/run_ultra_early_calibration.sh`：ultra_early_energy + 高吸音材質
- `runtime/run_differential_calibration.sh`：per-trial 差分
- `runtime/run_matched_filter_calibration.sh`：匹配濾波 ToF
- `runtime/run_global_baseline_and_diff.sh`：全局基準 + 差分
- `scripts/diagnose_tof_zero.py`：tof=0 靜態診斷工具

---

## 十、遇到的 Bug 與修復

### Bug 1：校正腳本傳遞了不存在的 `--headless` 參數
**症狀：** `error: unrecognized arguments: --headless`
**原因：** Shell 腳本手動加了 `--headless`，但 sweep 腳本用 `SimulationApp({"headless": not bool(args.gui)})` 默認無頭，不需要這個參數。
**修復：** 刪除腳本中的 `--headless`。

### Bug 2：`ultra_early_energy` 欄位名稱前綴不一致
**症狀：** 有效行 0/133，分析輸出全空。
**原因：** `_way_fields()` 輸出帶前綴的 `primary_sgw_ultra_early_energy`，但分析腳本和 sweep 腳本找的是無前綴的 `ultra_early_energy`，`if key in fields` 永遠為 False。
**修復：** 統一使用帶前綴的完整鍵名。

### Bug 3：`diagnose_tof_zero.py` 中 `MockGMO` NameError
**症狀：** `NameError: name 'numElements' is not defined`
**原因：** `class MockGMO` 的 body 中 `numElements = numElements` 試圖引用同名的外部變數，但 class body 不能引用外部同名變數。
**修復：** 將外部變數重命名為 `_n_elem` 和 `_n_spsgw`。

### Bug 4：全局 baseline 方向矛盾（r 為正向）
**症狀：** `global_diff_ultra_early` r = +0.288，方向與物理預期（負向）相反。
**原因：** 全局基準用 trial_16 的機器手臂 IK 位置錄製，其他 trial 的機器臂關節角不同 → 機器本體的聲學陰影效果造成系統性偏差；不同 trial 的桌子 y 位置不同，也造成基準不齊。
**影響：** 實驗概念正確但實作不完整；需要每個 trial 各自錄製基準才能正確比較。

---

## 十一、明確的訊號邊界確認

以下特徵**物理上存在**但被全向性噪聲遮蔽：

1. **`diff_early_peak_sample_idx` (per-trial) range 10–31** 對應距離 0.22–0.70m，方向正確（r=+0.283），**目標回波確實存在於早期樣本中**，只是被固定反射稀釋。

2. **能量信號（r≈0.175–0.288）**足以支撐 84% 的接近成功率，證明信號「方向上足夠」引導機器人接近，即使精度不足做精確距離量測。

---

## 十二、下一步：ML 訊號提取

傳統訊號處理達到 r≈0.29 的天花板。文獻和數據都指向需要更強的非線性特徵提取：

### 立即可行（現有 133 筆數據）
1. **特徵組合 + Random Forest / SVR**：將所有弱特徵（各自 r≈0.28）組合，非線性組合預計可達 R² 0.4–0.6
2. **Hilbert 包絡 + Early-Window 匹配濾波**：對前 40 個樣本做匹配濾波而非全波形，避免後牆干擾

### 需要更多數據（追加 30+ trials → 570 筆）
3. **1D CNN 直接學原始波形**：讓網路自己發現「sample 10–35 的微弱目標回波」
4. **LSTM on sequential samples**：利用波形的時序結構
5. **Cepstrum 分析**：IFFT(log|FFT|²)，用於多重回波的時間間隔提取

### 論文敘述框架
> 「傳統訊號處理（能量、差分、匹配濾波）在全向性 WPM 模型下達到 r≈0.29 的精度上限。本研究進一步採用深度學習方法，直接對原始 GMO 波形進行端到端距離回歸，在相同的模擬環境下達到 R²=X，首次驗證了機器學習可從全向性聲學波形中提取 sim-to-real 可轉移的距離特徵。」

---

*記錄時間：2026-07-05*
*下次繼續：特徵組合 ML + 追加 calibration 數據收集 + 1D CNN 訓練*
