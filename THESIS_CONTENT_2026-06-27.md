# 論文內容整理（2026-06-27）

**狀態：** 基於 Phase 3 正式數據（signal-way 版）的可投稿草稿素材  
**Canonical 數據：** `fixed_tcp_repeatability_v1`（30/30 PASS）+ `phase3_material_sensitivity_sgw`（A/B/C 全 PASS）  
**前置 handoff：** `SESSION_HANDOFF_2026-06-27.md`  
**舊稿參考（部分過時）：** `isaac_acoustic_research/abandoned_md/root/THESIS_MANUSCRIPT_DRAFT.md`

> **重要：** 本文件取代舊稿中關於 Docker、浮動 TCP `(1.0,1.5,1.0)`、以及「UR10 不驅動 articulation」的描述。現行正式實驗使用 **官方 UR10 資產 + 鎖定關節 + 移動目標**。

---

## 0. 論文定位（一句話）

本研究在 Isaac Sim 6.0 中，驗證 **UR10 末端掛載 RTX Acoustic 感測器** 能否在控制幾何與材質的六面牆房間內，產出**可重複、與距離相關**的聲學特徵；並以 PyRoomAcoustics 提供**趨勢級**參考對照，為未來 CH201 實機驗證建立協定基礎。

**不宣稱：** RTX 與 PRA 波形級等價、GMO sample index 即物理 ToF、已完成 CH201 實機驗證。

---

## 1. 研究問題與貢獻

### 1.1 研究問題（Working RQ）

> 在固定幾何的模擬房間中，Isaac Sim 6.0 RTX Acoustic 掛載於 UR10 `ee_link` 時，能否作為**距離感知**的可行模擬工具？其特徵趨勢是否與 PyRoomAcoustics 參考模型方向一致？

### 1.2 三項貢獻（可直接寫入 Introduction）

1. **Geometry Passport v1.0 — 固定 TCP + 移動目標實驗設計**  
   解決舊 IK 移動手臂方案的距離定義混亂、姿態分支跳躍問題；在 UR10 保守工作區（TCP 半徑 ≈ 0.82 m）內，以 sensor frame 定義 0.5–3.0 m 量測距離。

2. **Signal-way RTX 特徵管線**  
   依官方 GMO 語義解析 `(tx, rx, ch)` 結構化波形，提出 `primary_sgw_early_energy` 作為距離敏感特徵，優於平坦 `amplitude_max`（後者在 1.0 m 後飽和）。

3. **RTX×PRA 趨勢級對照 + 材質敏感度**  
   在 NonVisualMaterial A/B/C 三條件下，量化 RTX 與 PRA 的趨勢一致性與差異，明確標示 `claim_boundary`。

### 1.3 Claim Boundary（方法章與討論章必須出現）

| 可宣稱 | 不可宣稱 |
|--------|----------|
| 30/30 模擬 run 全 PASS | RTX GMO 與 PRA RIR 波形等價 |
| 跨 repeat 極低變異（CV < 0.005） | GMO peak / sample index = 物理 ToF |
| `primary_sgw_early_energy` 隨距離下降（ρ≈−0.66） | RTX 與 PRA 材質敏感度完全一致 |
| RTX early energy 與 PRA early energy 趨勢方向一致（ρ≈+0.66） | 已完成 CH201 / 實機 UR10 驗證 |
| PRA 在距離與材質上趨勢清晰 | 6 點 Spearman 的 p-value 多數不顯著 → 勿過度解讀統計顯著性 |

---

## 2. 方法（Methods）— 可直接貼入正文

### 2.1 平台與軟體環境

實驗在 **host 安裝的 Isaac Sim 6.0 standalone**（`/home/lab109/song/isaacsim6.0`）執行，非 Docker 容器。Python 經 `scripts/run_host_python.sh` 呼叫 `app/python.sh`。機器人使用官方資產：

```text
Isaac/Robots/UniversalRobots/ur10/ur10.usd
```

RTX Acoustic API：

```python
from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor, parse_generic_model_output_data
```

數據擷取依 **Replicator Writer + `timeline.play()`** 取得 GenericModelOutput（GMO），不使用 deprecated `isaacsim.sensors.rtx` 或藍色 cube 占位感測器。

### 2.2 實驗模式：fixed_tcp_moving_target

本研究採 **固定 TCP、移動目標** 設計（`EXPERIMENT_MODE = fixed_tcp_moving_target`），理由如下：

- UR10 官方最大 reach 為 **1.3 m**（base→TCP）；0.5–3.0 m 的 acoustic distance 定義為 **sensor→target**，非 base→target。
- 移動手臂改距離會引入 IK 分支跳躍與姿態不連續，不利論文 demo 與距離定義。
- 固定 TCP 使**距離成為唯一自變量**，符合第一性原則。

**流程：**
1. 載入官方 UR10 至 `/World/ur10`，base 固定於世界原點。
2. 以 Lula IK **只求一次**保守 TCP 姿態（目標半徑 0.80 m、高度 0.65 m），驗證 `min_link_z ≥ 0`。
3. **鎖定關節**，整個 sweep 期間 `max_observed_ee_motion_m = 0`。
4. 建立六面牆房間（4.5 × 3.0 × 2.8 m，中心 (2.0, 0, 0)）。
5. 對每個距離 waypoint，沿 sensor +X 軸移動 `/World/fixed_target`，settle 後擷取 GMO。

### 2.3 幾何與感測器配置（Geometry Passport v1.0）

| 參數 | 值 |
|------|-----|
| EE frame | `/World/ur10/ee_link` |
| 感測器路徑 | `/World/ur10/ee_link/official_rtx_acoustic` |
| Sensor local offset | (0.08, 0, 0) m（沿 ee_link +X） |
| Dual-mount spacing | 0.10 m |
| 實測 TCP 半徑（xy） | **0.816 m** |
| 實測 sensor 位置 | **(0.800, 0.160, 0.650) m** |
| 目標反射體 | `/World/fixed_target`，8×8×2 cm 鋁色方塊 |
| 距離 waypoints | 0.5, 1.0, 1.5, 2.0, 2.5, 3.0 m |
| 距離容差 | ±0.05 m |
| 中心頻率 | 40 kHz |
| Tick rate | 20 Hz |

**方法章建議段落（中英對照）：**

> UR10 has a nominal reach of 1.3 m. To avoid near-limit configurations and kinematic singularities, the end-effector was positioned within a conservative workspace region (TCP radius ≈ 0.82 m from base, height 0.65 m). Acoustic target distance was defined along the sensor forward (+X) axis relative to the sensor frame, not the robot base. During each sweep, joint positions remained locked (`max ee_link motion = 0 m`); only the target reflector moved.

> UR10 官方最大 reach 為 1.3 m。本研究將末端設定於距 base 約 0.82 m 的保守工作區（高度 0.65 m），並將 0.5–3.0 m 的 acoustic distance 定義為 sensor frame 前方距離。整個量測過程 UR10 關節鎖定（`ee_link` 運動量 0 m），僅移動目標反射體。

### 2.4 材質條件（Material Passport v1.0）

房間與目標綁定 Isaac Sim **NonVisualMaterial**，對應三種吸收條件：

| 條件 | 標籤 | PRA 吸收係數 | 房間 NV 材質 | 目標 NV 材質 |
|------|------|-------------|-------------|-------------|
| A | low_absorption | 0.10 | concrete + paint | aluminum + retroreflective |
| B | medium_absorption（預設） | 0.35 | concrete + clearcoat | aluminum + paint + retroreflective |
| C | high_absorption | 0.70 | fabric | plastic + paint |

正式可重複性實驗使用條件 **B**；材質敏感度實驗分別在 A/B/C 下各跑一次 6 距離 smoke。

### 2.5 GMO 處理與特徵萃取

GMO 依官方語義解析為 **signal-way** 結構：

```text
gmo.x      → tx mount ID
gmo.y      → rx mount ID
gmo.z      → channel ID
gmo.scalar → amplitude sample
numSamplesPerSgw = 320
num_signal_ways  = 2（dual-mount receiver group）
```

每 frame 萃取特徵（`rtx_acoustic_factory.py`）：

| 特徵 | 定義 | 論文角色 |
|------|------|----------|
| `amplitude_max` | 全 GMO 振幅最大值 | 基線對照；1.0 m 後飽和 |
| `primary_sgw_peak` | primary signal-way 峰值 | 對照；與 amplitude_max 等價 |
| **`primary_sgw_early_energy`** | primary way 前 25% samples 的 \|amplitude\| 之和 | **主推距離特徵** |
| `ref_sgw_*` | reference way (tx=0,rx=0,ch=0) 統計 | 輔助 |

`early_energy` 的物理意義：反映早期回波能量，對距離與幾何更敏感，優於飽和的 peak 特徵。

### 2.6 PyRoomAcoustics 參考基線

PRA 使用與 Geometry Passport 對齊的房間尺寸與麥克風位置 `(0.8, 0.16, 0.65) m`，源位置隨距離移動。萃取特徵：

- `early_energy_50ms` — 前 50 ms 能量
- `direct_delay_ms` — 直射延遲
- `rt60_measured` — 混響時間
- `rir_peak_abs_value` — RIR 峰值

**PRA 不是 ground truth**，僅作趨勢級參考。跨模型比較使用 6 個距離點的 Spearman ρ，並在報告中標註 `claim_boundary`。

### 2.7 可重複性協定

| 項目 | 設定 |
|------|------|
| 距離點 | 6（0.5–3.0 m） |
| 每點 repeats | 5 |
| 總 runs | **30** |
| 每 run 樣本數 | 4–5 frames |
| PASS 條件 | 距離誤差 ≤ 0.05 m、對準角 ≤ 5°、`gmo_valid_rate = 1.0`、GMO modality = ACOUSTIC、NV 材質 ID 驗證通過 |
| 批次 ID | `fixed_tcp_repeatability_v1` |

### 2.8 統計分析

- 距離趨勢：6 點 Spearman rank correlation（`|ρ| ≥ 0.7` 標為 monotonic）
- 可重複性：跨 5 repeats 的 mean、std、CV
- 跨模型：RTX 批次平均特徵 vs PRA 同距離特徵的 Spearman ρ
- **限制：** n=6，p-value 多不顯著；報告以趨勢方向與效應量為主，不以 p<0.05 為唯一標準

---

## 3. 結果（Results）— 可直接貼入正文

### 3.1 實驗可行性與可重複性

正式批次 **`fixed_tcp_repeatability_v1`** 完成 **30/30 PASS**（6 距離 × 5 repeats，材質 B）。

| 指標 | 結果 |
|------|------|
| 總 runs | 30/30 PASS |
| `max_ee_motion_m` | **0.0**（所有 run） |
| `gmo_valid_rate` | **1.0**（所有 run） |
| `num_signal_ways` | 2（一致） |
| `num_samples_per_sgw` | 320（一致） |
| 距離誤差 | < 10⁻⁶ m（sub-mm） |

**跨 repeats 變異（材質 B，5 repeats 平均）：**

| 距離 (m) | `amplitude_max` CV | `primary_sgw_early_energy` CV |
|----------|-------------------|-------------------------------|
| 0.5 | 0.000012 | 0.0035 |
| 1.0 | 0.000006 | 0.0036 |
| 1.5 | 0.000006 | 0.0035 |
| 2.0 | < 10⁻⁶ | < 10⁻⁶ |
| 2.5 | 0.000007 | 0.0046 |
| 3.0 | < 10⁻⁶ | < 10⁻⁶ |

**解讀：** 模擬管線在控制場景下具有極高軟體可重複性；此為**精度（precision）**證據，非物理準確度（accuracy）。

### 3.2 距離趨勢：RTX vs PRA（材質 B，主實驗）

**表 1 — 距離掃描特徵（5 repeats 平均）**

| 距離 (m) | RTX `amplitude_max` | RTX `primary_sgw_early_energy` | PRA `early_energy_50ms` | PRA `direct_delay_ms` | PRA `rir_peak_abs` |
|----------|--------------------:|-------------------------------:|------------------------:|----------------------:|-------------------:|
| 0.5 | 4822 | **167.2** | 7.31 | 1.46 | 1.966 |
| 1.0 | 5171 | **163.0** | 2.98 | 2.92 | 0.950 |
| 1.5 | 5171 | **168.4** | 1.86 | 4.38 | 0.602 |
| 2.0 | 5171 | **156.3** | 1.50 | 5.83 | 0.443 |
| 2.5 | 5171 | **155.7** | 1.30 | 7.29 | 0.313 |
| 3.0 | 5171 | **156.3** | 1.14 | 8.75 | 0.271 |

**表 2 — Spearman 趨勢相關（n=6）**

| 比較 | 特徵對 | ρ | 趨勢標籤 |
|------|--------|---|----------|
| RTX vs 距離 | `amplitude_max_mean` | +0.31 | 無單調（飽和） |
| RTX vs 距離 | **`primary_sgw_early_energy_mean`** | **−0.66** | 隨距離下降 |
| PRA vs 距離 | `early_energy_50ms` | −1.00 | 強單調下降 |
| PRA vs 距離 | `direct_delay_ms` | +1.00 | 強單調上升 |
| RTX vs PRA | `primary_sgw_early_energy` × `early_energy_50ms` | **+0.66** | 趨勢方向一致 |
| RTX vs PRA | `amplitude_max` × `early_energy_50ms` | −0.31 | 不一致 |

**關鍵發現（Results 段落草稿）：**

> RTX `amplitude_max` saturated near 5171 for distances ≥ 1.0 m, showing no useful distance sensitivity (ρ = +0.31). In contrast, `primary_sgw_early_energy` decreased from 167.2 at 0.5 m to 156.3 at 3.0 m (ρ = −0.66). PyRoomAcoustics `early_energy_50ms` showed a strong monotonic decrease (ρ = −1.0). Cross-model Spearman correlation between RTX early energy and PRA early energy was ρ = +0.66, indicating trend-level agreement in the expected direction, without claiming waveform equivalence.

> 平坦 `amplitude_max` 在 1.0 m 後飽和於 ~5171，不具距離區分力。Signal-way `primary_sgw_early_energy` 從 0.5 m 的 167.2 降至 3.0 m 的 156.3（ρ = −0.66），優於 peak 特徵。PRA `early_energy_50ms` 呈強單調下降。兩者的 early energy 趨勢 Spearman ρ = +0.66，方向一致，但**不代表波形級等價**。

### 3.3 材質敏感度（A/B/C）

**表 3 — 跨材質比較（0.5 m 與 3.0 m 快照）**

| 材質 | 吸收係數 | @0.5m RTX peak | @0.5m RTX early_energy | @3.0m RTX early_energy | @0.5m PRA RT60 |
|------|---------|---------------:|-----------------------:|-----------------------:|---------------:|
| A | 0.10 | 5054.6 | 165.4 | 157.1 | 0.87 s |
| B | 0.35 | 5054.6 | 165.4 | 157.1 | 0.21 s |
| C | 0.70 | 5054.6 | **190.6** | 157.1 | 0.11 s |

**觀察：**
- RTX **peak 特徵**對三種材質幾乎無差異（5054→5171 飽和曲線相同）
- RTX **early_energy** 在 **0.5 m 近距離**能區分條件 C（190.6 vs 165.4）；3.0 m 時三者趨同（~157.1）
- PRA 對材質高度敏感（RT60：A=0.87 s, B=0.21 s, C=0.11 s @ 0.5 m）
- 三條件下 RTX early_energy vs 距離的 Spearman ρ 皆為 **−0.77**（6 點，趨勢一致）

**解讀：** RTX NonVisualMaterial 的材質效應在 peak 特徵上被飽和掩蓋；early energy 在近距離提供有限的材質區分力，但仍弱於 PRA。這支持將 PRA 定位為趨勢參考而非 RTX 的 ground truth。

### 3.4 穩健性驗證（P1）

| 驗證項 | 結果 |
|--------|------|
| GMO 結構驗證 | 全 sample `gmo_valid=True`, modality=ACOUSTIC |
| Signal-way 一致性 | 2 ways × 320 samples，跨 sample 無漂移 |
| NV 材質 ID decode | room_id=537, target_id=4353（條件 B），與 passport 一致 |
| GUI viewport | `wait_for_viewport` 已接入 |

---

## 4. 圖表清單（Figure Manifest）

| 圖號建議 | 檔案路徑 | 內容 | 論文章節 |
|----------|----------|------|----------|
| Fig. 1 | 需自行截圖 GUI | 實驗場景：UR10 + 房間 + 目標（手臂不動、目標移動） | Methods |
| Fig. 2 | `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/rtx_amplitude_max_vs_distance.png` | RTX amplitude_max 飽和曲線 | Results 3.2 |
| Fig. 3 | 需新增 early_energy 圖 | RTX early_energy vs 距離（可從 Table 1 重繪） | Results 3.2 |
| Fig. 4 | `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/pra_features_vs_distance.png` | PRA 特徵 vs 距離 | Results 3.2 |
| Fig. 5 | `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/rtx_signal_way_peak_vs_distance.png` | Signal-way peak vs 距離 | Results 3.2 補充 |
| Fig. 6 | 需新增 | 材質 A/B/C 的 early_energy 比較（0.5 m vs 3.0 m bar chart） | Results 3.3 |

**待補圖：** Fig. 3 與 Fig. 6 目前無現成 PNG，可用 `fixed_tcp_rtx_pra_comparison.csv` 與 `material_cross_condition_features.csv` 快速生成。

---

## 5. 討論（Discussion）— 段落草稿

### 5.1 為何 fixed_tcp 優於 IK 移動手臂

IK 方案在固定目標下需將 TCP 退至目標後方才能增大距離，導致 IK 分支跳躍與視覺不連續。Fixed TCP 方案將距離定義為 sensor frame 上的純幾何量，使 UR10 保持在保守工作區（0.82 m），同時覆蓋 0.5–3.0 m 的 acoustic range。這符合 UR10 1.3 m reach 的物理限制，也使實驗變量控制更嚴格。

### 5.2 為何 early_energy 優於 amplitude_max

官方 GMO 為 signal-way 結構化波形，而非單一標量。將 640 elements 平坦取 max 會在 1.0 m 後飽和（~5171），失去距離區分力。Signal-way 的 early_energy 捕捉前段回波能量，對幾何路徑更敏感。這與 PRA `early_energy_50ms` 的趨勢方向一致（ρ = +0.66），支持「早期能量」作為跨模型對照的合理橋樑——但仍非波形匹配。

### 5.3 RTX 與 PRA 的差異

PRA 使用幾何聲學 + 數值吸收係數，RTX 使用 NonVisualMaterial 的光譜聲學模型。兩者在材質敏感度上表現不同：PRA RT60 對 A/B/C 差異顯著，RTX peak 幾乎無差異。這不是實驗失敗，而是**提醒不可將 PRA 當 RTX 的 validator**。論文應將 PRA 定位為 interpretability baseline。

### 5.4 與 CH201 實機路徑的銜接

本階段建立了：
- 可審計的 RTX 擷取管線（30/30 PASS）
- 幾何護照（robot/sensor/target 位姿可追溯）
- Task-level 比較 schema（距離誤差、有效回波率、repeatability）

未來 CH201 實機實驗應比較 **task-level metrics**（量測距離誤差、有效回波率），而非宣稱 CH201 raw waveform 與 RTX GMO 等價。

---

## 6. 限制（Limitations）— 段落草稿

1. **模擬_only：** 無 CH201 或實機 UR10 量測數據。
2. **n=6 距離點：** Spearman 檢定檢定力不足，趨勢方向比 p-value 更有意義。
3. **單一 TCP 姿態：** 未掃描不同手臂姿態對特徵的影響。
4. **材質映射近似：** RTX NonVisualMaterial 與 PRA 吸收係數的對應為工程近似，非物理等價。
5. **Early energy 定義：** 取前 25% samples 的啟發式選擇，尚未與物理延遲語義對齊。
6. **飽和效應：** `amplitude_max` 飽和可能掩蓋部分材質效應。
7. **Host vs Docker：** 正式數據在 host standalone 產生；舊稿 Docker 描述不適用。

---

## 7. 結論（Conclusion）— 段落草稿

本研究在 Isaac Sim 6.0 中建立了一套可重現的 UR10 末端 RTX Acoustic 距離感知模擬管線。透過 Geometry Passport v1.0 的固定 TCP + 移動目標設計，在 6 距離 × 5 repeats = 30 runs 中達成 100% PASS，且跨 repeat 變異極低。Signal-way 解析揭示 `primary_sgw_early_energy` 優於平坦 `amplitude_max` 作為距離特徵，並與 PyRoomAcoustics early energy 呈趨勢級一致（ρ = +0.66）。材質敏感度實驗顯示 RTX peak 對吸收條件不敏感，但 early energy 在近距離能部分區分高吸收條件。這些結果支持 RTX Acoustic 作為非視覺機器人距離感知的**模擬可行性研究工具**，但尚需在 CH201 實機實驗中驗證 task-level 一致性。

---

## 8. 摘要（Abstract）— 更新版

### 中文摘要（草稿）

本研究評估 NVIDIA Isaac Sim 6.0 RTX Acoustic 懸掛於 Universal Robots UR10 末端時，能否在控制幾何與材質的模擬房間中，產出可重複且與距離相關的聲學特徵。實驗採固定 TCP、移動目標設計：UR10 關節鎖定於距 base 約 0.82 m 的保守工作區，目標反射體沿感測器前方 0.5–3.0 m 移動。在材質條件 B 下，6 距離 × 5 次重複共 30 次擷取全部通過驗證，跨次變異係數低於 0.005。依官方 GenericModelOutput signal-way 語義，本文發現 `primary_sgw_early_energy` 優於平坦振幅峰值作為距離特徵（Spearman ρ = −0.66），而峰值特徵在 1.0 m 後飽和。與 PyRoomAcoustics 參考模型的趨勢級對照顯示，兩者 early energy 方向一致（ρ = +0.66），但材質敏感度表現不同。結果支持 RTX Acoustic 作為超音波機器人距離感知的模擬可行性工具，惟尚未完成 CH201 實機驗證，且不宣稱模擬與參考模型之波形級等價。

### English Abstract (draft)

This study evaluates whether NVIDIA Isaac Sim 6.0 RTX Acoustic, mounted on a Universal Robots UR10 end-effector, can produce repeatable, distance-sensitive acoustic features in a controlled six-wall room. A fixed-TCP, moving-target design locks the UR10 joints at a conservative workspace radius of approximately 0.82 m while translating the reflector along the sensor forward axis from 0.5 to 3.0 m. Under material condition B, all 30 capture runs (6 distances × 5 repeats) passed validation with cross-run coefficients of variation below 0.005. Using official GenericModelOutput signal-way semantics, we show that `primary_sgw_early_energy` outperforms flat amplitude peak as a distance feature (Spearman ρ = −0.66), while peak features saturate beyond 1.0 m. Trend-level comparison with a PyRoomAcoustics reference model shows consistent early-energy directions (ρ = +0.66) but divergent material sensitivity. These results support RTX Acoustic as a feasible simulation instrument for non-visual robotic distance sensing, without claiming waveform equivalence or completed CH201 physical validation.

---

## 9. 數據引用速查（給審稿人 / 下一個 AI）

| 用途 | 路徑 |
|------|------|
| 30 runs 原始 timeseries | `runtime/outputs/fixed_tcp_repeatability_v1/repeat_*/distance_*/` |
| 距離級特徵 | `runtime/outputs/phase3_rtx_features/fixed_tcp_repeatability_v1_distance_features.csv` |
| RTX×PRA 合併表 | `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/fixed_tcp_rtx_pra_comparison.csv` |
| Spearman 相關 | `.../fixed_tcp_rtx_pra_correlations.csv` |
| 分析報告 JSON | `.../PHASE3_RTX_PRA_REPORT.json` |
| 材質敏感度 | `runtime/outputs/phase3_material_sensitivity_sgw/` |
| PRA 條件 B | `runtime/outputs/experiment_4_pra_reference_passport_v1_cond_B/pra_reference_features.csv` |
| 重跑日誌 | `runtime/outputs/phase3_repeatability_sgw_run.log` |

---

## 10. 與舊稿差異對照（更新時必改）

| 項目 | 舊稿 (2026-06-22) | 現行 (2026-06-27) |
|------|-------------------|-------------------|
| 環境 | Docker `nvcr.io/nvidia/isaac-sim:6.0.0` | Host standalone `isaacsim6.0` |
| UR10 | 浮動 TCP `(1.0,1.5,1.0)`，不驅動 articulation | 官方 UR10 + Lula IK 求姿態一次 + 鎖關節 |
| 距離控制 | 移動目標（舊 repeatability）或 IK 移動手臂 | **固定 TCP + 移動目標**（Geometry Passport v1.0） |
| 特徵 | amplitude mean/peak/energy | **signal-way `primary_sgw_early_energy`** 主推 |
| PRA 角色 | secondary / project history | **趨勢級對照基線**（Phase 3 正式管線） |
| 材質 | 未系統化 | NonVisualMaterial A/B/C Material Passport |
| 數據集 | UR10-context 30 runs（舊幾何） | `fixed_tcp_repeatability_v1` 30/30 PASS |

---

## 11. 下一步建議（寫作流程）

1. **補圖：** early_energy vs distance、材質 bar chart（§4 Sim 待補項）
2. **Lab 章節：** 貼入 `thesis/THESIS_LAB_SECTIONS_2026-06-28.md`（§3.9、§4.5、§4.6）
3. **Word：** 更新 `THESIS_DRAFT_FCU_v1.docx` 摘要 + 第四章
4. **P2 收尾：** 更新 handoff 文件指向本文件 + Lab 素材

---

## 12. Isaac Lab 延伸（2026-06-28，見 `thesis/THESIS_LAB_SECTIONS_2026-06-28.md`）

| 項目 | 結果 |
|------|------|
| 動態 smoke | 128 steps，27 GMO，ρ(early_energy, GT)=**−0.475** |
| SL Sim→Lab | MAE **0.41 m**，r **0.47**（early_energy 單特徵） |
| 雙特徵 peak | 未改善（飽和），不採用 |
| RL | 規劃見 `thesis/ISAAC_LAB_PHASE5_RL_PLAN.md`，未實作 |

**第四項貢獻（修訂）：** Sim Passport 延伸至 Lab 動態觀測 + Sim→Lab 監督學習遷移（趨勢級，非 RL 主貢獻）。

---

*本文件由 2026-06-27 Phase 3 正式數據整理產生；§12 為 2026-06-28 Lab/SL 增補。Sim 正文見 §2–§10；Lab 正文見 `THESIS_LAB_SECTIONS_2026-06-28.md`。*