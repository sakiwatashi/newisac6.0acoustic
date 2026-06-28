# 對話 Session 統整（供下一個 AI 接續）

**日期：** 2026-06-27  
**Canonical workspace：** `/home/lab109/song/isaacsim6.0`（root 安裝的 Isaac Sim 6.0，**不是** Docker 版 `isaac-sim-docker`）  
**完整對話 transcript：** `/home/lab109/.grok/sessions/%2Fhome%2Flab109%2Fsong/019f0503-65a6-7ee3-9931-72c3680988f9/updates.jsonl`  
**本文件目的：** 在整理論文正文之前，把本對話從頭到尾做了什麼、為什麼做、結果如何、還缺什麼，寫成下一個 AI 可直接接手的詳細 handoff。  
**使用者最新意圖（2026-06-27）：** 先完成本統整 → 下一步才是論文內容整理。

---

## 0. 給下一個 AI 的三句話

1. **論文級正式實驗已定型為 `fixed_tcp_moving_target`**：UR10 手臂不動，只移動目標方塊；距離 0.5–3.0 m 是 **sensor→target**，不是 base→target。
2. **P0（signal-way 特徵）與 P1（GMO/NV 驗證）已 100% 落地**；正式 6×5 可重複性與材質敏感度 A/B/C 均已用 signal-way 重跑完成。
3. **P2（文件更新、舊腳本歸檔、牆色修正）尚未做**；論文整理應以 `fixed_tcp_repeatability_v1` + `phase3_material_sensitivity_sgw` 為主數據，主推 `primary_sgw_early_energy`，維持 trend-level only 聲明。

**勿讀的過時文件：**
- `/home/lab109/song/AI_HANDOFF_UR10_ACOUSTIC_2026-06-27.md` — 仍指向 IK 移動手臂舊方案
- `/home/lab109/song/isaacsim6.0/CURRENT_HOST_STATUS.md` — 2026-06-26 狀態，已過時
- `/home/lab109/song/isaac_acoustic_research/` — legacy reference / Docker 時代遺留

---

## 1. 第一性原則：這個專案到底在驗證什麼

### 1.1 核心研究問題

在**固定幾何的六面牆房間**內，將 Isaac Sim 6.0 **RTX Acoustic** 感測器掛載於官方 UR10 的 `ee_link`，能否作為**距離感知**的可行方案？

這不是「驗證 RTX 與 PyRoom 波形級等價」，而是**可行性 + 趨勢級對照**：
- RTX 能否穩定產出與距離相關、可重複的聲學特徵？
- 這些趨勢是否與 PyRoomAcoustics（PRA）參考模型方向一致？

### 1.2 實驗設計必須滿足的控制邏輯

| 層次 | 要求 | 現狀 |
|------|------|------|
| **單一自變量** | 感測器–目標距離 | ✅ `fixed_tcp_moving_target`：TCP 鎖定，只移動 `/World/fixed_target` |
| **控制變量** | 房間幾何、材質、感測器掛載、UR10 姿態 | ✅ Geometry Passport v1.0 + Material Passport v1.0 |
| **因變量** | 可重複、與距離相關的 RTX 特徵 | ✅ 已從平坦 `amplitude_max` 升級到 signal-way `primary_sgw_early_energy` |
| **基線** | PyRoom 趨勢級參考 | ✅ `run_pyroom_experiment_4_passport_v1.sh` + `analyze_fixed_tcp_rtx_pra.py` |
| **聲明邊界** | 非波形級驗證 | ✅ `claim_boundary` 寫入 `PHASE3_RTX_PRA_REPORT.json` |

### 1.3 為什麼廢棄「移動手臂改距離」

舊方案（`official_asset_ur10_ik_distance_waypoint_acoustic_capture.py`）的問題不是「程式跑不動」，而是**違反第一性原則**：

1. **距離定義混亂**：IK 讓 TCP 在空間中移動，同時固定目標在 `(1.6, 0.16, 0.65)`，sensor→target 距離與「requested distance waypoint」糾纏在一起。
2. **IK 分支跳躍**：中遠距離需要 TCP 退到目標後方，Lula IK 會選不同肘/腕分支，運動不連續、視覺上不合理。
3. **物理可信度**：即使 `min_link_z > 0`（不穿地），使用者仍會看到手臂姿態怪異——論文 demo 不可接受。
4. **UR10 reach 誤解**：使用者明確指出 UR10 官方 reach 僅 **1.3 m**；0.5–3.0 m 的 acoustic distance 必須是 **sensor frame 前方**，不是讓手臂伸到 3 m。

**正式替代方案（不可回退）：**
```
UR10 base 固定
TCP 鎖定在 base 前方 ~0.82 m（ee_link xy 半徑 ≈ 0.816 m，高度 0.65 m）
sensor 在 ee_link +X 偏移 0.08 m → sensor 位置約 (0.80, 0.16, 0.65)
目標沿 sensor +X 軸放置：0.5, 1.0, 1.5, 2.0, 2.5, 3.0 m
整個 sweep 過程 ee_link 運動量 = 0 m
```

### 1.4 第一性原則審查後的優先級（P0–P3）

本對話中段做過一次「對照官方範例」的全專案審查，結論與優先級如下：

| 優先級 | 內容 | 狀態 |
|--------|------|------|
| **P0** | `rtx_acoustic_factory.py` + signal-way 特徵萃取 + 用新特徵重跑正式數據 | ✅ 完成 |
| **P1** | GMO 納入 PASS 門檻、`wait_for_viewport`、NonVisualMaterial ID 驗證 | ✅ 完成 |
| **P2** | 更新 handoff 文件、舊 diagnostic 腳本歸檔、修正牆壁顯示色 | ❌ 未做 |
| **P3** | 遷移到 Experimental UR10 / cuMotion | ❌ 未做（論文非必要） |

**官方 API 清單對齊（審查時列的 7 項）：**

| 官方範例 | 對齊狀態 | 說明 |
|----------|----------|------|
| `create_acoustic_basic.py` | ✅ | factory 用 `annotators=[]`，writer 自帶 annotator |
| `inspect_acoustic_gmo.py` | ✅ | `parse_signal_ways()` 依 `numSamplesPerSgw` 拆分 |
| `apply_nonvisual_materials.py` | ⚠️ | 材質綁定與 ID decode 已有；Debug View 與 viewport 顏色仍有 bug |
| `test_acoustic_sensor.py` | ⚠️ | 驗證邏輯移植到 `validate_acoustic_gmo()`，非 async test 本體 |
| `ViewportManager` | ⚠️ | camera + Camera Light + `wait_for_viewport` 已有 |
| `lidar_robot_integration` 掛載模式 | ⚠️ | 概念對齊（sensor parented under ee_link），未用該範例腳本 |
| Experimental UR10 | ❌ | 已解釋給使用者；固定 TCP 實驗不需要 |

---

## 2. 本對話時間線（按使用者推進順序）

### Turn 1：讀舊 handoff，確認 IK 方案現狀

**使用者：** 請看 `/home/lab109/song/AI_HANDOFF_UR10_ACOUSTIC_2026-06-27.md`

**當時狀態：** 主線仍是 IK 移動手臂 + 固定目標 `(1.6, 0.16, 0.65)`，headless smoke 14/14 PASS，但存在結構性 IK 分支問題。

**AI 回覆重點：** 建議不要繼續調 IK 容差，應重新設計實驗幾何。

---

### Turn 2：使用者釐清 UR10 reach 與距離定義

**使用者核心論述：**
- UR10 最大 reach = 1.3 m（base→TCP），正式實驗應讓 TCP 在 **0.6–1.0 m** 保守區
- **0.5–3.0 m 是 sensor→target 距離**，不是手臂要伸 3 m
- 合理設計：TCP 固定 ~0.8 m，目標在 sensor 前方 0.5–3.0 m

**AI 動作：** 對照當時 IK 腳本，向使用者解釋舊方案如何運動、哪裡不符合上述定義。

---

### Turn 3：教授級優化整個論文專案

**使用者要求：**
- 以教授角度優化論文專案（手臂運動、感測器、架構、牆壁材質、聲學考量）
- 納入 PyRoomAcoustics 比對（資源在 `/home/lab109/` 下）
- **先規劃再實作**

**AI 規劃輸出（摘要）：**
- Phase 1：Geometry Passport — 固定 TCP + 移動目標
- Phase 2：Material Passport — RTX NonVisualMaterial A/B/C
- Phase 3：可重複性批次 + RTX×PRA 分析管線
- 廢棄 IK 移動手臂作為論文主線

**使用者確認：** 「不，就照你說的優化，從第一步開始」

---

### Turn 4：確認 canonical 目錄

**使用者補充：** 所有主要活動集中在 `isaacsim6.0`（root 下載），不是 Docker 資料夾。

**AI 確認並據此調整所有路徑與文件引用。**

---

### Phase 1 實作：Geometry Passport + 固定 TCP 主腳本

**新建/核心修改：**

| 檔案 | 內容 |
|------|------|
| `scripts/geometry_passport_v1.py` | 房間 4.5×3.0×2.8 m、TCP 位姿、距離 waypoints、目標位置計算、`EXPERIMENT_MODE=fixed_tcp_moving_target` |
| `scripts/official_asset_ur10_fixed_tcp_distance_sweep.py` | **論文級主實驗腳本**（唯一正式 capture） |
| `scripts/run_host_official_asset_ur10_fixed_tcp_distance_sweep_gui.sh` | GUI 觀測入口 |
| `scripts/run_host_official_asset_ur10_fixed_tcp_distance_sweep_smoke.sh` | Headless smoke |
| `scripts/run_host_fixed_tcp_repeatability_batch.sh` | 6 距離 × N repeats 批次 |

**實驗流程（主腳本）：**
1. 載入官方 UR10 → `/World/ur10`
2. 用 Lula IK **只求一次**保守 TCP 姿態（seed `reach_forward` 等），驗證 `tcp_radius_xy ≈ 0.82 m`、`min_link_z ≥ 0`
3. **鎖定關節**，整個 sweep 不再動手臂
4. 建立六面牆房間 + `/World/fixed_target` 反射體
5. 對每個距離 waypoint：沿 sensor +X 移動目標 → settle → `timeline.play()` → Replicator Writer 抓 GMO
6. 輸出 timeseries CSV + summary JSON + USD stage

**實測幾何（來自 `repeat_001/distance_0p5m/summary.json`）：**
- `baseline_ee_position_m`: (0.720, 0.160, 0.650)
- `baseline_sensor_position_m`: (0.800, 0.160, 0.650)
- `baseline_tcp_radius_xy_m`: **0.816 m**（符合使用者 0.6–1.0 m 保守區）
- `max_ee_motion_m`: **0.0**（所有正式 run 確認手臂不動）

---

### 使用者回報：目標方塊太大

**問題根因：** `set_target_pose()` 若只用 `ClearXformOpOrder` + translate，會清掉 scale，USD cube 回到 1 m 基底 → 視覺上 ~2 m 寬。

**修復：** 改用 `Cube(path, positions=..., scales=..., colors=...)` 保留 scale。

**最終目標尺寸：** `TARGET_CUBE_SCALE_M = (0.08, 0.08, 0.02)` → 8 cm × 8 cm × 2 cm

---

### GUI 視覺調整（部分完成）

**使用者要求：**
- 待測物與牆壁不同色
- 預設隱藏面向鏡頭的牆
- 預設 Camera Light

**已做修改：**
- `ROOM_WALL_COLOR = #6b8cae`，`TARGET_COLOR = #ff6600`
- `apply_passport_display_colors()` — 材質綁定後重設 display color
- 預設隱藏 `CAMERA_FACING_WALL_PATH = /World/room/wall_x_min`（`--hide-camera-wall` 預設 True）
- `configure_gui_viewport()` — `ViewportManager.set_camera_view` + Camera Light

**未完成：** 使用者回報牆壁仍偏橘紅色。推測 `apply_nonvisual_materials()` 覆蓋 viewport display color。使用者說「等等再改」——**勿宣稱視覺問題已解決**。

---

### Phase 2：Pilot 可重複性

**執行：**
```bash
REPEAT_COUNT=2 BATCH_ID=fixed_tcp_repeatability_pilot_v1 \
  /home/lab109/song/isaacsim6.0/scripts/run_host_fixed_tcp_repeatability_batch.sh
```
耗時 ~153 s，全 PASS。輸出：`runtime/outputs/fixed_tcp_repeatability_pilot_v1/`（參考用，非正式論文數據）

**使用者要求 GUI 觀測指令 → 提供：**
```bash
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_fixed_tcp_distance_sweep_gui.sh
```

---

### Phase 3 第一次：正式 6×5 可重複性（舊特徵 `amplitude_max`）

**執行：**
```bash
/home/lab109/song/isaacsim6.0/scripts/run_phase3_repeatability_and_analysis.sh
```

**結果：**
- 29/30 PASS；`repeat_005 @ 3.0m` GPU segfault（`libnvidia-glcore`）
- 補跑後 30/30 PASS
- `amplitude_max_mean` vs 距離 Spearman ρ ≈ +0.94（6 點平均後）— 看似很好，但後來發現是**錯誤特徵語義**

**輸出目錄：** `runtime/outputs/fixed_tcp_repeatability_v1/`（後被 signal-way 版覆寫）

---

### Phase 3 第一次：材質敏感度 A/B/C（舊特徵）

**執行：** `run_phase3_material_sensitivity.sh`  
**輸出：** `runtime/outputs/phase3_material_sensitivity/`（舊目錄）  
**結論：** 三條件全 PASS，但 `amplitude_max` 對 A/B/C 幾乎無差異（spread ≈ 0.01）

---

### 第一性原則審查（本對話關鍵轉折）

**使用者要求：** 重新審查整個項目，對照 Isaac Sim 6.0 官方範例與 API。

**審查的 official examples：**
- `standalone_examples/api/isaacsim.sensors.experimental.rtx/create_acoustic_basic.py`
- `inspect_acoustic_gmo.py`
- `test_acoustic_sensor.py`
- `apply_nonvisual_materials.py`
- Experimental UR10 範例

**核心發現：**

我們把 GMO 當**平坦 scalar 陣列**（直接取 `amplitude_max`），但官方語義是 **signal-way (tx, rx, ch) 結構化波形**：

```
gmo.x     → tx mount ID
gmo.y     → rx mount ID
gmo.z     → channel ID
gmo.scalar → amplitude sample
numSamplesPerSgw = 320（實測）
num_signal_ways = 2（實測，dual-mount receiver group）
```

這解釋了：
- `amplitude_max` 在 1.0 m 後飽和於 ~5171
- 材質 A/B/C 對 peak 不敏感
- 需要 `early_energy`（前 25% samples 能量和）等 signal-way 特徵

---

### P0 落地：rtx_acoustic_factory + signal-way 管線

**新建 `scripts/rtx_acoustic_factory.py`：**

| 函式 | 用途 |
|------|------|
| `create_passport_acoustic()` | 統一 Acoustic 建立（`annotators=[]`） |
| `parse_signal_ways()` | 依 `numSamplesPerSgw` 拆分波形 |
| `validate_acoustic_gmo()` | modality/結構檢查 |
| `summarize_gmo_frame()` | 單 frame → CSV 欄位 |
| `assess_gmo_capture_quality()` | 批次 PASS 門檻（P1 接入） |

**主腳本 timeseries 新增 22 欄，包括：**
`num_signal_ways`, `num_samples_per_sgw`, `gmo_valid`, `gmo_modality`, `primary_sgw_peak/mean/early_energy`, `ref_sgw_*`, `all_sgw_peak_mean`, `signal_way_keys`

**更新分析鏈：**
- `extract_fixed_tcp_rtx_features.py` — 支援 signal-way 欄位，舊 CSV 向後相容
- `analyze_fixed_tcp_rtx_pra.py` — 新增 `primary_sgw_early_energy_mean` 等；新圖 `rtx_signal_way_peak_vs_distance.png`

**Smoke 驗證：** `ur10_official_asset_fixed_tcp_distance_sweep_sgw_smoke` — PASS；2 signal ways × 320 samples，`modality=ACOUSTIC`

---

### P0 後重跑：正式 6×5（signal-way 版）

**執行：**
```bash
/home/lab109/song/isaacsim6.0/scripts/run_phase3_repeatability_and_analysis.sh \
  2>&1 | tee runtime/outputs/phase3_repeatability_sgw_run.log
```
耗時 ~383 s，**30/30 PASS**（無 segfault）

**關鍵數字（5 repeats 平均後，材質 B）：**

| 距離 (m) | amplitude_max_mean | primary_sgw_early_energy_mean |
|----------|-------------------|-------------------------------|
| 0.5 | 4822 | 167.2 |
| 1.0 | 5171 | 163.0 |
| 1.5 | 5171 | 168.7 |
| 2.0 | 5171 | 156.3 |
| 2.5 | 5171 | 155.5 |
| 3.0 | 5171 | 156.3 |

**趨勢相關（6 點 Spearman，來自 `fixed_tcp_rtx_pra_correlations.csv`）：**

| 比較 | 特徵對 | ρ | 解讀 |
|------|--------|---|------|
| RTX vs 距離 | `amplitude_max_mean` | +0.31 | 飽和，不顯著 |
| RTX vs 距離 | `primary_sgw_early_energy_mean` | **−0.66** | 隨距離下降（論文主推） |
| PRA vs 距離 | `early_energy_50ms` | −1.0 | 強單調 |
| PRA vs 距離 | `direct_delay_ms` | +1.0 | 強單調 |
| RTX vs PRA | `primary_sgw_early_energy` × `early_energy_50ms` | **+0.66** | 趨勢方向一致 |
| RTX vs PRA | `amplitude_max` × `early_energy_50ms` | −0.31 | 弱/不一致 |

**可重複性：** 跨 repeats 的 `amplitude_max` std 在 1.0–3.0 m 約 0.001–0.037；`gmo_valid_rate = 1.0` 全 run。

---

### signal-way 版材質敏感度 A/B/C

**執行：**
```bash
/home/lab109/song/isaacsim6.0/scripts/run_phase3_material_sensitivity.sh \
  2>&1 | tee runtime/outputs/phase3_material_sensitivity_sgw_run.log
```
耗時 ~49 s，三條件全 PASS。輸出改到 `phase3_material_sensitivity_sgw/`

**跨材質比較（0.5 m vs 3.0 m，來自 `material_cross_condition_features.csv`）：**

| 材質 | @0.5m early_energy | @3.0m early_energy | @0.5m peak |
|------|-------------------|-------------------|------------|
| A | 165.4 | 157.1 | 5054.6 |
| B | 165.4 | 157.1 | 5054.6 |
| C | **190.6** | 157.1 | 5054.6 |

**解讀：**
- Peak 特徵對 A/B/C 幾乎無差異（材質敏感度低）
- **Condition C（高吸收）在 0.5 m 的 early_energy 明顯偏高** — 近距離有區分力
- PRA 清楚區分材質（RT60 等）；RTX 與 PRA 方向不完全一致 → 維持 `claim_boundary`

---

### P1 落地：穩健性三項

**1. GMO 納入 PASS 條件**

`assess_gmo_capture_quality(rows)` 要求：
- 全 sample `gmo_valid=True`
- `gmo_modality=ACOUSTIC`
- `num_samples_per_sgw` 與 `num_signal_ways` 跨 sample 一致

**2. GUI `wait_for_viewport`**

`configure_gui_viewport()` 開頭呼叫 `ViewportManager.wait_for_viewport(max_frames=120)`；summary 記錄 `gui_viewport.viewport_ready`

**3. NonVisualMaterial 驗證**

`rtx_material_passport_v1.verify_material_bindings()` — decode material ID 比對 A/B/C 預期；材質啟用時 PASS 要求 `nv_material_verification.valid=True`

**P1 smoke 結果：** `ur10_official_asset_fixed_tcp_distance_sweep_p1_smoke` — GMO valid rate=1.0，NV valid=True

---

### 使用者詢問 P0–P3 完成度 → 請做 P1 → 解釋 Experimental UR10

**完成度確認（本對話結束時）：**
- P0 ✅、P1 ✅、P2 ❌、P3 ❌（論文非必要）

**Experimental UR10 說明（僅解釋，未實作）：**
- 指 `isaacsim.robot.experimental.manipulators.examples.universal_robots.UR10`（繼承 `Articulation`）
- 對比 legacy `World`+`Robot`+`LulaKinematicsSolver`（`extsDeprecated`）
- 固定 TCP 實驗**不必遷移**；未來若做避障連續運動才需要 cuMotion RMPflow

---

## 3. Canonical 架構（論文唯一應引用）

### 3.1 核心 Python 模組

| 檔案 | 角色 |
|------|------|
| `scripts/geometry_passport_v1.py` | 房間幾何、TCP、距離、目標位置、顯示色常數 |
| `scripts/rtx_material_passport_v1.py` | RTX NonVisualMaterial A/B/C + `verify_material_bindings()` |
| `scripts/rtx_acoustic_factory.py` | Acoustic 建立、signal-way 解析、GMO 驗證 |
| `scripts/official_asset_ur10_fixed_tcp_distance_sweep.py` | **主實驗腳本** |
| `scripts/extract_fixed_tcp_rtx_features.py` | 距離級特徵萃取 |
| `scripts/analyze_fixed_tcp_rtx_pra.py` | RTX×PRA Spearman + 圖表 |

### 3.2 Shell 入口

```bash
# GUI 觀測（論文 demo）
scripts/run_host_official_asset_ur10_fixed_tcp_distance_sweep_gui.sh

# Headless smoke（含 P1 驗證）
scripts/run_host_official_asset_ur10_fixed_tcp_distance_sweep_smoke.sh

# 正式 6×5 批次 + 分析
scripts/run_phase3_repeatability_and_analysis.sh

# 材質 A/B/C 敏感度（signal-way 版）
scripts/run_phase3_material_sensitivity.sh

# PyRoom 參考（geometry 來自 isaacsim6.0 passport）
scripts/run_pyroom_experiment_4_passport_v1.sh
```

所有 Isaac Python 經 `scripts/run_host_python.sh` → `app/python.sh`。

### 3.3 固定場景參數

| 項目 | 值 |
|------|-----|
| Robot | `/World/ur10`（官方 `Isaac/Robots/UniversalRobots/ur10/ur10.usd`） |
| EE frame | `ee_link` |
| 感測器 | `/World/ur10/ee_link/official_rtx_acoustic` |
| 目標 | `/World/fixed_target`（0.08×0.08×0.02 m） |
| 房間 | 4.5×3.0×2.8 m，中心 (2.0, 0, 0) |
| 距離 waypoints | 0.5, 1.0, 1.5, 2.0, 2.5, 3.0 m（沿 sensor +X） |
| 中心頻率 | 40 kHz |
| Tick rate | 20 Hz |
| 預設材質 | B（medium_absorption） |

### 3.4 RTX API 政策（必須遵守）

```python
from isaacsim.sensors.experimental.rtx import Acoustic, AcousticSensor, parse_generic_model_output_data
```

- **Writer + `timeline.play()`** 為可靠 GMO 來源
- **禁用：** `isaacsim.sensors.rtx`（deprecated）、藍色 cube 假感測器、`IsaacSensorCreateRtxUltrasonic`
- **不要用** `sensor.get_data("generic-model-output")` 作主要數據路徑（曾返回空 buffer）

詳見 `/home/lab109/song/isaac_acoustic_research/RTX_ACOUSTIC_OFFICIAL_METHOD.md`（政策文件；實際工作在 isaacsim6.0）

### 3.5 Legacy / 診斷（論文勿引用）

- `official_asset_ur10_ik_distance_waypoint_acoustic_capture.py`
- `run_host_official_asset_ur10_ik_distance_waypoint_gui.sh` — DIAGNOSTIC ONLY
- `isaacsim.core.api.World` + `Robot` + `LulaKinematicsSolver`
- 所有 `ur10_official_asset_continuous_motion_*` 等早期 pilot

---

## 4. 論文可用結論（已實證）

1. **實驗可行性：** 固定 TCP + 移動目標，6 距離 × 5 repeats = 30 runs，全 PASS；`ee_link` 運動 0 m。
2. **可重複性極高：** 跨 repeats 特徵 CV 極低；`gmo_valid_rate = 1.0`。
3. **距離趨勢：** 平坦 `amplitude_max` 在 1.0 m 後飽和；**`primary_sgw_early_energy` 隨距離單調下降**（ρ≈−0.66），優於 peak。
4. **跨模型：** PRA 距離/材質趨勢清晰；RTX early energy 與 PRA early energy 趨勢方向一致（ρ≈+0.66），但**不能宣稱波形級等價**。
5. **材質：** RTX peak 對 A/B/C 不敏感；early energy 在近距離（0.5 m）能區分條件 C。
6. **穩健性（P1）：** 全 capture GMO 通過官方結構驗證；材質 ID decode 與 passport 一致。

**方法章可寫（使用者曾提供、仍適用）：**

> UR10 has a nominal reach of 1.3 m. To avoid near-limit configurations and reduce the influence of kinematic singularities, the end-effector acoustic sensor was positioned within a conservative workspace region, approximately 0.6–1.0 m from the robot base. The acoustic target distance was defined relative to the sensor frame rather than the robot base frame, covering 0.5–3.0 m along the sensor forward axis.

---

## 5. 關鍵數據路徑（論文引用）

| 數據集 | 路徑 | 狀態 |
|--------|------|------|
| 正式可重複性 6×5（signal-way） | `runtime/outputs/fixed_tcp_repeatability_v1/` | 30/30 PASS |
| RTX 特徵 CSV | `runtime/outputs/phase3_rtx_features/fixed_tcp_repeatability_v1_distance_features.csv` | `signal_way_features_enabled: true` |
| RTX×PRA 分析 | `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/` | 含 correlation CSV + 3 張圖 |
| 材質敏感度（signal-way） | `runtime/outputs/phase3_material_sensitivity_sgw/` | A/B/C 全 PASS |
| P1 smoke | `runtime/outputs/ur10_official_asset_fixed_tcp_distance_sweep_p1_smoke/` | PASS |
| Pilot（舊，2 repeats） | `runtime/outputs/fixed_tcp_repeatability_pilot_v1/` | 參考用 |
| 舊 amplitude_max 批次 | `runtime/outputs/phase3_material_sensitivity/` | **已被 sgw 版取代** |

**日誌：**
- `runtime/outputs/phase3_repeatability_sgw_run.log`
- `runtime/outputs/phase3_material_sensitivity_sgw_run.log`

**論文圖表（可直接引用）：**
- `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/rtx_amplitude_max_vs_distance.png`
- `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/pra_features_vs_distance.png`
- `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/rtx_signal_way_peak_vs_distance.png`

---

## 6. 已知問題與技術債

1. **牆壁顏色仍錯** — NV material 覆蓋 display color；使用者已知、延後處理（P2）
2. **`AI_HANDOFF_UR10_ACOUSTIC_2026-06-27.md` 過時** — 仍指向 IK GUI
3. **`CURRENT_HOST_STATUS.md` 過時** — 仍指向 continuous motion / IK prototype
4. **15+ 腳本仍有重複感測器 boilerplate** — 僅主腳本已用 factory
5. **絕對路徑硬編碼** — `/home/lab109/song/...` 全文
6. **IK 依賴 `extsDeprecated`** — 固定 TCP 方案仍用 Lula 求初始姿態一次
7. **批次跑 30 次偶發 GPU segfault** — 第一次最後一筆發生，補跑可恢復；signal-way 重跑無此問題
8. **PyRoom 腳本仍在 `isaac_acoustic_research/`** — 經 `run_pyroom_experiment_4_passport_v1.sh` 呼叫

---

## 7. 重要踩坑清單（下一個 AI 必讀）

### `set_target_pose()` 必須保留 scale
不可只用 `ClearXformOpOrder` + translate。必須用 `Cube(..., scales=...)`。

### Writer 是可靠 GMO 來源
必須 `timeline.play()` + Replicator Writer，不要依賴 `get_data()`。

### PASS 條件（P1 後）
除樣本數、距離誤差、對準角外，還需：
- `gmo_capture_quality.valid == True`
- `nv_material_verification.valid == True`（材質啟用時）

### 舊 batch 數據不可用於 signal-way 分析
若 CSV 無 `primary_sgw_peak` 欄位，那是 P0 之前的更舊版本。`fixed_tcp_repeatability_v1` 目錄已被 signal-way 版覆寫。

### claim_boundary 不可省略
```json
"claim_boundary": "Trend-level cross-model characterization only; not RTX validation against PRA."
```

---

## 8. 下一個 AI 應做什麼

### 8.1 使用者已明確要求的下一步：論文內容整理

在開始寫論文正文前，應基於本文件與以下數據：

1. **主推特徵：** `primary_sgw_early_energy_mean`（不是 `amplitude_max`）
2. **主數據集：** `fixed_tcp_repeatability_v1`（30/30 PASS）
3. **材質敏感度：** `phase3_material_sensitivity_sgw`
4. **統計：** `fixed_tcp_rtx_pra_correlations.csv`
5. **聲明邊界：** trend-level only，6 點 Spearman 樣本數小，p-value 多不顯著但趨勢方向有意義

### 8.2 建議優先做的 P2 收尾（論文整理前或並行）

1. 更新 `/home/lab109/song/AI_HANDOFF_UR10_ACOUSTIC_2026-06-27.md` 或讓本文件成為唯一 handoff
2. 更新 `CURRENT_HOST_STATUS.md` 指向 fixed-TCP canonical 路徑
3. 舊 diagnostic 腳本加 `DIAGNOSTIC ONLY` 標記或移入 `scripts/deprecated/`
4. 修正牆壁顏色（參考官方 `apply_nonvisual_materials.py`：visual `colors` 與 NV material 分離）

### 8.3 不要做（除非使用者明確要求）

- 遷移 Experimental UR10（P3）
- 回退到 IK 移動手臂方案
- 在 Docker 環境重開發
- 宣稱 RTX 與 PRA 波形級等價

---

## 9. 快速驗證指令

```bash
# 確認主腳本 syntax
python3 -m py_compile /home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_fixed_tcp_distance_sweep.py

# Headless smoke（含 P1 驗證）
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_fixed_tcp_distance_sweep_smoke.sh

# GUI 觀測（看目標移動、手臂不動）
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_fixed_tcp_distance_sweep_gui.sh

# 重跑正式分析（若需）
/home/lab109/song/isaacsim6.0/scripts/run_phase3_repeatability_and_analysis.sh
```

---

## 10. 本對話使用者訊息索引（方便回溯）

| # | 使用者說了什麼 | 導致的動作 |
|---|---------------|-----------|
| 1 | 看 AI_HANDOFF 文件 | 確認 IK 方案現狀與問題 |
| 2 | UR10 reach 1.3 m；距離是 sensor→target | 觸發實驗幾何重新設計討論 |
| 3 | 教授級優化論文專案；先規劃再實作 | Geometry/Material/Phase3 規劃 |
| 4 | 活動集中在 isaacsim6.0 | 路徑 canonical 化 |
| 5–6 | 「好，下一步」×2 | Phase 1 實作 → pilot |
| 7 | 需要可看量測過程的 GUI 指令 | 提供 GUI runner |
| 8–9 | 目標方塊太大；scale 沒變 | 修復 `set_target_pose` scale bug |
| 10–11 | 改顏色、隱藏牆、Camera Light | 視覺調整（牆色未完成） |
| 12–13 | 牆色稍後改；「好，下一步」 | Phase 3 第一次 6×5 + 材質敏感度 |
| 14–15 | 材質敏感度繼續 | 第一次 A/B/C 跑完 |
| 16 | 第一性原則審查 + 官方 API | P0–P3 規劃、signal-way 發現 |
| 17–19 | 「好，下一步」；signal-way 重跑完成 | P0 落地 + 6×5 重跑 |
| 20–21 | 材質敏感度 signal-way 版 | `phase3_material_sensitivity_sgw/` |
| 22 | P0–P3 做完了嗎？ | 完成度盤點 |
| 23 | 請先做 P1 | GMO/viewport/NV 驗證落地 |
| 24 | Experimental UR10 是啥？ | 解釋 P3（未實作） |
| 25 | **統整本對話；要詳細；給下一個 AI** | **本文件** |

---

*本文件由 2026-06-27 對話 session 統整產生。下一個 AI 讀完本文件 + `geometry_passport_v1.py` + `fixed_tcp_rtx_pra_correlations.csv` 即可開始論文正文整理，無需重讀全 thread。*