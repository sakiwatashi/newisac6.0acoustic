# 碩士論文全景：Isaac Sim + Isaac Lab 一體展示

**日期：** 2026-06-27  
**定位：** 把「你會的」整理成一套 NVIDIA Isaac 生態系故事，供論文正文、口試簡報、與 Phase 4 實作對齊。  
**核心訊息：** Sim 負責**科學驗證**；Lab 負責**規模化與學習**；兩者是同一套管線的上下層，不是兩個無關專案。

---

## 0. 論文一句話（修訂版，Sim+Lab）

> 本研究建立 **Isaac Sim → Isaac Lab** 連續管線：先在 Isaac Sim 6.0 驗證 UR10 末端 RTX Acoustic 於控制幾何下之可重複距離感知；再將同一 Passport 與感測工廠延伸至 Isaac Lab 動態環境，示範移動目標下之連續觀測與訓練資料生成，為後續監督學習／強化學習與 CH201 實機驗證奠基。

**英文題目建議：**

> *An Isaac Sim-to-Lab Pipeline for UR10-Mounted RTX Acoustic Sensing: Controlled Validation and Dynamic Observation for Robot Learning*

---

## 1. 為什麼 Sim 跟 Lab 要寫成「一套」

```text
┌─────────────────────────────────────────────────────────────────┐
│                    NVIDIA Isaac 生態系（同一套）                  │
├─────────────────────────────────────────────────────────────────┤
│  Isaac Sim 6.0          │  物理場景、RTX 感測、UR10、USD、PhysX   │
│       ↓ 共用            │  你已完成：Passport、Factory、30/30    │
│  Isaac Lab              │  Env API、並行 episode、觀測/動作/獎勵  │
│       ↓                 │  你要展示：動態目標 + 連續聲學觀測      │
│  訓練（SL / RL）         │  未來：特徵→距離、追蹤策略               │
│       ↓                 │                                        │
│  實機（CH201 / UR10）   │  論文邊界：task-level，非波形等價       │
└─────────────────────────────────────────────────────────────────┘
```

| 層次 | 平台 | 你展示的能力 | 論文角色 |
|------|------|-------------|----------|
| **L1 感測管線** | Isaac Sim | RTX API、GMO signal-way、Factory、P1 驗證 | **主結果（第四章）** |
| **L2 實驗設計** | Isaac Sim | Geometry/Material Passport、fixed TCP、統計分析 | **方法（第三章）** |
| **L3 參考對照** | Python PyRoom | 本機 `pyroomacoustics` 批次，非 API | **方法+結果附錄** |
| **L4 規模化** | Isaac Lab | Custom Env、移動目標、obs 串接 Factory | **展示延伸（4.5/第五章）** |
| **L5 實機** | CH201 | 協定、logger 規格 | **未來工作／邊界** |

**口試時可說：** 「我沒有只做一個 Sim demo；我把同一套感測與幾何定義，接到 Lab 的學習迴圈裡。」

---

## 2. 你已經會的、論文要「秀出來」的清單

### 2.1 Isaac Sim 6.0（已完成，有數據）

| 能力 | 證據 | 論文放哪 |
|------|------|----------|
| Host standalone 部署與隔離執行 | `run_host_python.sh` | §3.2 |
| 官方 UR10 + `ee_link` 掛載 | summary JSON | §3.3 |
| RTX experimental API（非 deprecated） | `rtx_acoustic_factory.py` | §3.6 |
| Signal-way 特徵（非平坦 peak） | 30/30 + ρ=−0.66 | §4.2 |
| 第一性原則實驗設計（fixed TCP） | `max_ee_motion=0` | §3.3、§5 討論 |
| 可重複性 6×5 | `fixed_tcp_repeatability_v1` | §4.1 |
| 材質 A/B/C | `phase3_material_sensitivity_sgw` | §4.3 |
| RTX×PyRoom 趨勢對照 | correlations CSV | §4.2 |
| GUI 可觀測 demo | GUI runner | 口試影片/圖3.2 |
| 穩健性 P1（GMO/NV 驗證） | p1_smoke | §4.4 |

### 2.2 PyRoomAcoustics（已完成，要寫對）

| 能力 | 證據 | 論文怎麼寫 |
|------|------|-----------|
| 本機函式庫批次 RIR | `experiment_4_pra_reference.py` | 「PyRoomAcoustics v0.10.1 批次參考」 |
| 與 Geometry Passport 對齊 | `mic (0.8,0.16,0.65)` | §3.8 |
| **不要寫** | `external_backend_path` 欄位 | 不提 ai-pyroomacoustics API |

### 2.3 Isaac Lab（✅ Phase 4 + 4.6 已完成）

| 能力 | 狀態 | 證據 |
|------|------|------|
| 與 Sim 6.0 版本對齊安裝 | ✅ | `IsaacLab` v3.0.0-beta2 + `Setup complete` |
| Custom Environment | ✅ | `lab/ur10_rtx_acoustic_env.py` |
| 場景重用 Passport | ✅ | 同 geometry/factory/material passport |
| 移動目標 | ✅ | 正弦 1.0–2.0 m，128 steps |
| 連續聲學觀測 | ✅ | 27 GMO captures，valid_rate=1.0 |
| 資料輸出 | ✅ | `lab_dynamic_smoke_v1/` |
| 監督學習 Sim→Lab | ✅ | `lab_sl_distance_v1/`，r=0.47，MAE=0.41 m |
| 強化學習 | ⏸ Phase 5 | 見 `ISAAC_LAB_PHASE5_RL_PLAN.md` |

**碩論不必完成完整 RL**；Lab smoke + SL 遷移已足 §4.5–§4.6。正文素材：`THESIS_LAB_SECTIONS_2026-06-28.md`。

---

## 3. 修訂後論文大綱（逢甲 13b + Sim/Lab 一體）

### 第一章、緒論
- 1.1 動機：非視覺感測 + NVIDIA Isaac 生態
- 1.2 目的：**Sim 驗證 + Lab 延伸**（兩段式貢獻）
- 1.3 範圍：Sim 主實驗已完成；Lab 為動態觀測原型；CH201 為邊界
- 1.4 限制與名詞（claim boundary、Sim GT 標籤）

### 第二章、文獻探討
- 2.1 非視覺機器人感測
- 2.2 Sim-to-real / 模擬訓練
- 2.3 RTX Acoustic 與房間聲學
- 2.4 **Isaac Sim 與 Isaac Lab 在機器人學習中的角色**（新增，展示你知道整套）

### 第三章、研究流程與方法
- 3.1 **Isaac Sim–Lab 一體架構圖**（核心圖，口試必講）
- 3.2 Isaac Sim 平台與 Passport 設計
- 3.3 fixed_tcp_moving_target 實驗
- 3.4 RTX signal-way 特徵與 P1 驗證
- 3.5 PyRoomAcoustics 批次參考
- 3.6 **Isaac Lab 動態環境設計**（obs/action/reset，見 `ISAAC_LAB_PHASE4_SPEC.md`）

### 第四章、實證結果與分析
- 4.1 Sim：30/30 可重複性
- 4.2 Sim：距離趨勢 RTX×PRA
- 4.3 Sim：材質敏感度
- 4.4 Sim：穩健性 P1
- **4.5 Lab：動態目標觀測原型** ← ✅ `lab_dynamic_smoke_v1`
- **4.6 Lab：監督學習 Sim→Lab 遷移** ← ✅ `lab_sl_distance_v1`
- **4.7 綜合討論**（Sim + Lab + PRA）

### 第五章、結論與建議
- 5.1 研究結論（Sim 主 + Lab 延伸 + SL 示範）
- 5.2 建議：Phase 5 RL smoke、離軸點位、CH201 實機

---

## 4. 三項貢獻（修訂，對齊口試）

1. **Isaac Sim 端：可審計的 UR10 RTX 距離感知管線**（30/30、signal-way、Passport）  
2. **跨模型方法：RTX×PyRoom 趨勢級對照與 claim boundary**  
3. **Isaac Lab 端：同一 Passport 延伸至動態環境之觀測原型**（移動目標 + 連續 GMO 特徵流）

第三項即使只有 smoke，也是碩論「我會 Lab」的實質證據。

---

## 5. 執行狀態（2026-06-28）

| Phase | 狀態 | 產出 |
|-------|------|------|
| 4 安裝 + smoke | ✅ | `lab_dynamic_smoke_v1/` |
| 4.6 SL | ✅ | `lab_sl_distance_v1/` |
| 論文 §4.5–§4.6 素材 | ✅ | `THESIS_LAB_SECTIONS_2026-06-28.md` |
| 5 RL smoke | ⏸ 規劃完成 | `ISAAC_LAB_PHASE5_RL_PLAN.md` |
| Word 貼上 | 待做 | 依 `THESIS_LAB_SECTIONS` 檢查清單 |

---

## 6. 圖表清單（Sim + Lab 合併）

| 圖號 | 內容 | 來源 | 狀態 |
|------|------|------|------|
| 圖3.1 | **Sim–Lab 一體架構** | 本文件 §1 改繪 | 待繪 |
| 圖3.2 | 實驗場景（UR10+房間+目標） | GUI 截圖 | 待截 |
| 圖4.1 | RTX amplitude 飽和 | 已有 PNG | ✅ |
| 圖4.2 | RTX early_energy vs 距離 | 待繪 | 待繪 |
| 圖4.3 | PRA 特徵 vs 距離 | 已有 PNG | ✅ |
| 圖4.4 | 材質 A/B/C | 待繪 | 待繪 |
| **圖4.5** | **Lab：移動目標 GT 距離軌跡** | `lab_target_trajectory_xy.png` | ✅ |
| **圖4.6** | **Lab：early_energy vs GT 距離** | `lab_obs_vs_gt_distance.png` | ✅ |
| **圖4.7** | **SL：Sim→Lab 預測 vs GT** | `sl_sim_to_lab_pred_vs_gt.png` | ✅ |
| **圖4.8** | **SL：軌跡對照** | `sl_sim_to_lab_trajectory.png` | ✅ |

---

## 7. 口試「我會的」30 秒版

> 我用 Isaac Sim 6.0 在官方 UR10 上完成 RTX 聲學感測的可重複驗證，包含 Passport 幾何、signal-way 特徵、30 次正式實驗，並用本機 PyRoom 做趨勢對照。同一套感測工廠我延伸到 Isaac Lab，在移動目標的動態場景裡連續收觀測，示範 Sim 到 Lab 的訓練前資料管線；實機 CH201 留作 task-level 驗證，不宣稱波形等價。

---

## 8. 相關文件

| 文件 | 用途 |
|------|------|
| `SESSION_HANDOFF_2026-06-27.md` | Sim 階段完整技術紀錄 |
| `THESIS_CONTENT_2026-06-27.md` | Sim 結果正文素材 |
| `THESIS_OUTLINE_FCU_2026-06-27.md` | 逢甲章節大綱 |
| `ISAAC_LAB_PHASE4_SPEC.md` | Lab 環境實作規格（Phase 4 已完成） |
| `THESIS_LAB_SECTIONS_2026-06-28.md` | **§3.9、§4.5、§4.6 正文（貼 Word 用）** |
| `ISAAC_LAB_PHASE5_RL_PLAN.md` | Phase 5 RL 規劃 |
| `THESIS_DRAFT_FCU_v1.docx` | Word 初稿（待貼 §4.5–§4.6） |

---

*Sim 是科學；Lab 是規模。碩論要讓委員看見你兩者都接得上同一條管線。*