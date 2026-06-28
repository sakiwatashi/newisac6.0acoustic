# 論文正文素材：Isaac Lab §3.9、§4.5、§4.6（2026-06-28）

**狀態：** 可直接貼入 Word 初稿（逢甲 13b 格式）  
**Canonical 數據：**
- Lab smoke：`runtime/outputs/lab_dynamic_smoke_v1/`
- SL 回歸：`runtime/outputs/lab_sl_distance_v1/`（主模型）；`lab_sl_distance_v2/`（雙特徵對照，未採用）

**執行腳本：**
- `lab/run_lab_smoke.sh`
- `lab/run_sl_lab_distance.sh`

---

## 摘要修訂句（中英文各加一段）

**中文（加在摘要末段）：**

> 此外，本研究將同一 Geometry Passport 與 RTX 特徵工廠延伸至 Isaac Lab，於固定 TCP 與正弦移動目標之動態場景中連續擷取 128 步觀測；並以 Sim 靜態標定資料訓練之線性回歸器，在 Lab 動態測試集上達趨勢級距離追蹤（Pearson r≈0.47，MAE≈0.41 m），示範 Sim→Lab 訓練前管線之可行性。上述結果為趨勢級代理指標，非部署級測距精度。

**英文：**

> The same geometry passport and RTX feature factory were extended in Isaac Lab under a fixed-TCP, sinusoidally moving-target dynamic scenario (128 steps). A linear regressor trained on static Isaac Sim captures achieved trend-level distance tracking on the Lab dynamic hold-out set (Pearson r≈0.47, MAE≈0.41 m), demonstrating a feasible Sim-to-Lab pre-training pipeline. These results are trend-level proxies, not deployment-grade ranging.

---

## 第三章 新增小節

### 3.9 Isaac Lab 動態環境與 Sim 管線延伸

Isaac Lab（v3.0.0-beta2）安裝於 `isaacsim6.0/IsaacLab`，透過 `_isaac_sim` 符號連結指向同一 Isaac Sim 6.0 host（6.0.0-rc.59）。Lab 端不重新實作 RTX 感測解析，而是直接呼叫 Phase 3 已驗證之 `geometry_passport_v1.py`、`rtx_acoustic_factory.py` 與 `rtx_material_passport_v1.py`。

動態環境 `Ur10RtxAcousticDynamicEnv`（腳本：`lab/ur10_rtx_acoustic_env.py`）維持與 Sim 一致之場景定義：官方 UR10、關節鎖定、材質條件 B、8 cm×8 cm×2 cm 目標板、感測器掛載於 `ee_link/official_rtx_acoustic`。差異在於目標沿感測器 +X 軸以正弦軌跡運動：

```text
d(t) = 1.5 + 0.5·sin(2π·step / 64)   [m]，step = 0…127
```

觀測向量包含 `primary_sgw_early_energy`、`primary_sgw_peak`、`gmo_valid` 與幾何 GT 距離 `target_distance_m_gt`（由模擬座標計算，非實機讀值）。動作空間為零動作（fixed TCP）；每 4 步擷取一次 GMO（decimation=4），以降低 RTX 擷取成本。

啟動使用 Isaac Lab `AppLauncher`，experience 採 `isaacsim.exp.base.python.kit` 以載入 `omni.replicator` 與 RTX experimental 延伸模組。隔離執行沿用 `scripts/env_host_isolated.sh`。

---

## 第四章 §4.5 Isaac Lab 動態觀測原型

#### 4.5.1 實驗設定

| 項目 | 設定 |
|------|------|
| 模式 | `fixed_tcp_moving_target_dynamic` |
| 總步數 | 128 |
| GMO decimation | 4 |
| 距離範圍 | 1.0 – 2.0 m（正弦，週期 64 steps） |
| 材質 | B（medium_absorption） |
| 輸出 | `lab_dynamic_obs_timeseries.csv` |

#### 4.5.2 結果摘要

動態 smoke 執行 PASS。共記錄 128 列逐步觀測（含 GT 距離與目標座標）；其中 27 步完成有效 GMO 擷取（擷取率 84%），`gmo_valid_rate = 1.0`，模態皆為 ACOUSTIC。鎖定 TCP 之 sensor 位置維持不變（`max_sensor_position_motion_m = 0`），TCP 半徑 xy ≈ 0.816 m，與 Sim Phase 3 一致。

`primary_sgw_early_energy` 與 GT 距離之 Pearson 相關為 **ρ = −0.475**（n=27），方向與 Sim 靜態掃描一致（距離增加時 early energy 下降），惟動態樣本數較少、距離範圍僅 1–2 m，故不宣稱統計顯著性。

#### 4.5.3 圖表

| 圖號 | 檔案 | 說明 |
|------|------|------|
| 圖4.5 | `lab_target_trajectory_xy.png` | 動態目標 GT 距離隨 step 變化 |
| 圖4.6 | `lab_obs_vs_gt_distance.png` | early_energy vs GT 距離散佈 |

**圖4.5 說明文字（範本）：** 固定 TCP 下，目標沿感測器前向軸正弦往返，GT 距離於 1.0–2.0 m 間週期變化。

**圖4.6 說明文字（範本）：** 動態場景中 `primary_sgw_early_energy` 與模擬 GT 距離呈負相關趨勢（ρ≈−0.48），顯示 Sim 主特徵可延伸至 Lab 連續觀測。

#### 4.5.4 小結（§4.5）

Isaac Lab 端成功重用 Sim Passport 與 Factory，無需重寫感測解析即可在動態目標下產生訓練級觀測序列。此節證明 **Sim 科學驗證管線可接入 Lab 學習迴圈**；未宣稱已完成強化學習或 policy 收斂。

---

## 第四章 §4.6 監督學習距離估計（Sim→Lab 遷移）

#### 4.6.1 動機

§4.5 證明動態觀測可取得；§4.6 進一步示範：能否以 Sim 靜態標定資料訓練簡單估計器，並在 Lab 動態場景測試？此為 **趨勢級可行性示範**，非論文主貢獻之終極測距器。

#### 4.6.2 方法

- **特徵：** `primary_sgw_early_energy`（單變量線性回歸；見 §4.6.4 雙特徵對照）
- **訓練集：** Sim `fixed_tcp_repeatability_v1` 之 GMO 列（材質 B，n=125）
- **測試集：** Lab 動態 smoke 之 27 筆有效 GMO
- **對照：** Lab-only 5-fold 交叉驗證（僅 27 樣本，易過擬合，作參考）

腳本：`lab/train_sl_distance_regressor.py`

#### 4.6.3 結果

| 評估 | MAE (m) | RMSE (m) | Pearson r | 備註 |
|------|---------|----------|-----------|------|
| Lab-only 5-fold CV | 0.31 | 0.35 | 0.27 | 樣本少，僅參考 |
| **Sim→Lab（主結果）** | **0.41** | **0.52** | **0.47** | 與 §4.5 特徵–距離 ρ 一致 |

Sim→Lab 之 r≈0.47 表示：以 Sim 靜態資料學習之線性映射，在 Lab 動態 hold-out 上仍能追蹤距離**趨勢**，支持「同一特徵定義可跨平台遷移」之論述。

#### 4.6.4 特徵消融：加入 peak 未改善

另以 `[early_energy, peak]` 雙特徵訓練（`lab_sl_distance_v2`）：Sim→Lab MAE 升至 0.44 m，Lab CV 之 r 降至 0.13。原因為 Lab 1–2 m 區間內 `primary_sgw_peak` 飽和於 ≈5171，與 Sim Phase 3 現象一致。**論文主模型採 early_energy 單特徵。**

#### 4.6.5 圖表

| 圖號 | 檔案 | 說明 |
|------|------|------|
| 圖4.7 | `sl_sim_to_lab_pred_vs_gt.png` | Sim 訓練→Lab 測試：預測 vs GT |
| 圖4.8 | `sl_sim_to_lab_trajectory.png` | 依 GT 排序之軌跡對照 |

#### 4.6.6 Claim boundary（§4.6 必寫）

| 可宣稱 | 不可宣稱 |
|--------|----------|
| Sim 標定可遷移至 Lab 動態場景（趨勢級） | MAE 0.41 m 可部署於實機 |
| early_energy 為跨 Sim/Lab 之主要距離 proxy | 已完成端到端學習系統 |
| 雙特徵消融支持 peak 飽和結論 | R² 高、可當物理測距儀 |

---

## 第四章 §4.7 綜合討論（原 §4.5 討論移至此）

1. **Sim 主結果：** `primary_sgw_early_energy` 優於飽和之 `amplitude_max`（ρ≈−0.66，30/30 PASS）。
2. **Lab 延伸：** 動態場景下特徵–距離趨勢方向一致（ρ≈−0.48），Sim→Lab SL r≈0.47。
3. **RTX×PRA：** 趨勢級一致（early energy ρ≈+0.66），非波形等價。
4. **實機路徑：** CH201 驗證應採 task-level 指標；Lab/SL 輸出為協定與資料格式參考。

---

## 第五章 §5.2 研究建議（增補）

### 5.2.1 已完成之 Lab 階段
- Phase 4 動態 smoke（128 steps）✅
- Phase 4.6 SL Sim→Lab 線性遷移 ✅

### 5.2.2 建議後續：強化學習（Phase 5，見 `ISAAC_LAB_PHASE5_RL_PLAN.md`）
- 將環境註冊為 `DirectRLEnv`，以 RSL-RL 做距離估計或採樣策略之 smoke 訓練
- 擴充離軸點位、多 episode 資料量
- CH201 實機 task-level 驗證

---

## 修訂後三項貢獻（口試用）

1. **Isaac Sim：** 可審計 UR10 RTX 距離感知管線（30/30、signal-way、Passport）
2. **跨模型方法：** RTX×PyRoom 趨勢對照與 claim boundary
3. **Isaac Lab：** Passport 延伸至動態觀測 + Sim→Lab 監督學習遷移示範（非 RL 主貢獻）

---

## Word 貼上檢查清單

- [ ] 摘要中英文各加 Lab/SL 一段
- [ ] 第三章插入 §3.9
- [ ] 第四章插入 §4.5、§4.6；原討論改 §4.7
- [ ] 插入圖4.5–4.8（路徑見上表）
- [ ] 第五章 §5.2 增補 Lab 完成項與 RL 建議
- [ ] 題目可選修訂：加入「Isaac Sim–Lab 管線」字樣