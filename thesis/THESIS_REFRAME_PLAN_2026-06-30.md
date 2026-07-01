# 論文重構規劃（第一性原則 · 2026-06-30）

**目的：** 移除 PyRoomAcoustics（PRA）主線與相關敘事，改以「可審計模擬管線 → 超聲閉環接近 → Tier B 夾取示範」為論文主軸。  
**格式不變：** 逢甲 13b 六章 + `THESIS_DRAFT_FCU_v1.docx` 版面。  
**狀態：** 規劃稿（待導師確認後執行 docx 大改）。

---

## 一、第一性原則：論文到底要證明什麼？

### 1.1 一層問題（必須成立，否則後面無意義）

> 在控制幾何與材質的 Isaac Sim 六面牆場景中，RTX Acoustic 能否產出**可重複、可解析、與距離有趨勢關係**的 signal-way 特徵？

**證據：** Phase A · `fixed_tcp_repeatability_v1` · **30/30 PASS** · `primary_sgw_early_energy` ρ≈−0.66。

**這一層不宣稱：** 厘米級測距、波形等於實機 CH201、已完成硬體驗證。

### 1.2 二層問題（本輪開發核心，取代 PRA 對照）

> 在**不將目標世界座標餵給接近控制器**的前提下，閉環超聲特徵能否驅動機器人**沿搜尋走廊接近**至可夾取之前進上限？

**證據：** Phase B/C · UR10e + Robotiq · `ultrasonic_closed_loop_controller` · GUI/headless：
- 9 步接近至 `standoff_reached_forward_cap`
- `fusion` 飽和（~0.73 m）下以幾何前進上限 + 規則監管員（supervisor v1）收斂
- Tier B **`grasp_contact_success`**（預設 contact-only，非部署級物理抬升）

**這一層不宣稱：** 端到端純超聲夾取（對準/下降用 passport 幾何）、優於 VLM 全任務管線、穩定物理抬升。

### 1.3 三層問題（可寫、篇幅宜短）

> 與「相機 + VLM 端到端操作」相比，本研究定位為何？

**論述（不硬比成功率）：**
- VLM 路線賣**語義 + 全任務**；本研究賣**非視覺距離閉環之 last-meter approach**。
- 互補而非取代：VLM 粗定位，超聲精接近（未來工作可寫 hybrid）。

### 1.4 明確排除（不再作為論文貢獻）

| 排除項 | 理由 |
|--------|------|
| **PyRoomAcoustics 趨勢對照** | 與閉環主線無直接因果；分散篇幅；實務上已用 Isaac RTX 自洽驗證 |
| RTX×PRA Spearman、圖4.3 PRA 曲線 | 同上 |
| `experiment_4`、PRA citation 主體引用 | 從正文與 CITATION_BANK 移除或降為附錄一句 |
| Isaac Lab / Sim→Lab SL / in-sim RL 作**主貢獻** | 與目前實作重心（Sim 閉環夾取）脫節；改**附錄或未來工作** 1–2 頁 |
| 部署級測距、波形級數位雙生 | 維持 claim boundary |

---

## 二、新論文敘事弧（Storyline）

```
Phase A  特徵可不可信？     → 30/30 + early_energy 距離趨勢 + 材質 A/B/C
    ↓
Phase B  特徵能否閉環控制？ → 超聲閉環接近（controller 不讀 target pose）
    ↓
Phase C  接近後能否接到操作？→ UR10e+Robotiq Tier B contact grasp + supervisor
    ↓
Discussion  vs VLM、限制、CH201 未來
```

**一句話（新）：**  
在 Isaac Sim 建立可審計 RTX 超聲特徵管線，證明其可支撐**非視覺閉環接近**至工業搜尋走廊內目標，並示範 Tier B 接觸級夾取可行性。

---

## 三、新六章架構（取代現行大綱）

| 章 | 標題 | 篇幅目標 | 核心內容 |
|----|------|----------|----------|
| **一** | 緒論 | 10% | 電聲+機器人背景；三層 RQ；貢獻重排；vs VLM 定位 |
| **二** | 文獻探討 | 15% | 室內主動聲學、RTX/GMO、非視覺機器人感知、閉環控制；**刪 §2.5 PRA** |
| **三** | 研究方法 | 20% | Passport；Phase A 協定；**閉環控制器**；UR10e/Robotiq Phase C 協定；supervisor；claim boundary |
| **四** | 特徵驗證結果（Phase A） | 30% | 30/30、距離趨勢、材質敏感度；**刪 RTX×PRA §** |
| **五** | 閉環接近與夾取示範（Phase B/C） | 20% | 接近軌跡、fusion 飽和、監管員、GUI/headless 結果、Tier B 邊界 |
| **六** | 結論與建議 | 5% | 三層 RQ 回應；限制；CH201、GUI_LIFT、與 VLM 整合 |

**附錄（可選）：** Isaac Lab 動態觀測 + SL smoke（原第五章精簡移入，不佔主貢獻）。

---

## 四、研究問題與貢獻（改寫對照）

### 4.1 研究問題（新）

| 層級 | 問題 |
|------|------|
| RQ1 | 固定 TCP 下 RTX 特徵是否可重現且具距離趨勢？ |
| RQ2 | 閉環控制器僅憑超聲特徵，能否在搜尋走廊內接近至前進上限？ |
| RQ3 | 接近後之 Tier B 接觸級夾取是否具趨勢級可行性？ |

### 4.2 貢獻（新）

1. **主貢獻：** Geometry/Material Passport + signal-way 特徵工廠 + **30/30** 可審計 Sim 管線。  
2. **次貢獻：** **超聲閉環接近**（不消費目標世界座標）+ 規則型 fusion/oracle **監管員**（安全包絡，非逐步控制）。  
3. **附貢獻：** UR10e+Robotiq **Tier B** 接觸成功示範與明確 claim boundary（contact-only / 可選 GUI_LIFT）。

**刪除為貢獻：** RTX×PRA 趨勢對照、Sim→Lab r≈0.47、RL 閉環示範（改附錄或未來工作）。

---

## 五、Claim Boundary（更新表 6.1 要點）

| 可宣稱 | 不可宣稱 |
|--------|----------|
| 30/30 PASS；early_energy 距離趨勢 | PRA/RTX 波形等價 |
| 閉環接近不讀 target pose 作控制輸入 | 「純超聲端到端夾取」 |
| Supervisor 用 oracle 僅安全仲裁 | Supervisor 是 LLM 或逐步策略 |
| Tier B contact success（Sim） | 部署級 grasp rate / 穩定抬升 |
| 與 VLM 互補之 last-meter 定位 | 優於 VLM 全任務成功率 |

---

## 六、圖表清單（重排）

### 保留（Phase A）

| 編號 | 內容 | 狀態 |
|------|------|------|
| 圖3.1 | 研究架構（**重繪**：A→B→C，刪 PRA 框） | 待重繪 |
| 圖4.1–4.2 | RTX amplitude / early_energy vs distance | ✅ |
| 圖4.3 | 材質 A/B/C @0.5 m（原 4.4） | ✅ |
| 表4.1–4.2 | 30/30、CV | ✅ |

### 刪除

| 編號 | 原因 |
|------|------|
| 圖4.3 PRA vs distance | PRA 主線移除 |
| 所有 RTX×PRA 相關表 | 同上 |

### 新增（Phase B/C）

| 編號 | 內容 | 來源 |
|------|------|------|
| 圖5.1 | 搜尋走廊 + 感測器掛載示意（wrist_3_link） | GUI 截圖 / 既有 fig3.1 變體 |
| 圖5.2 | 接近過程 oracle/fused/tool0_x（trial 9） | `approach_live_status` / history CSV |
| 圖5.3 | 閉環狀態機 / supervisor 決策流 | 自繪 |
| 表5.1 | Phase C 單次/多次 trial 摘要 | `ultrasonic_closed_loop_grasp_summary.json` |

---

## 七、檔案搬移與刪改清單

### 7.1 論文正文（必改）

| 檔案 | 動作 |
|------|------|
| `THESIS_OUTLINE_FCU_2026-06-29.md` | 依本規劃重寫 |
| `THESIS_CONTENT_2026-06-27.md` | 重寫 §0–1、刪 PRA 方法/結果 |
| `THESIS_CHAPTER2_DRAFT_2026-06-29.md` | 刪 §2.5 PRA；增 §2.5 閉環機器人感知 |
| `rebuild_thesis_six_chapters.py` | 摘要、Ch1/3/4/5 全文替換；刪 PRA 圖 |
| `build_chapter2_docx.py` | 刪 PRA 段 |
| `build_chapters34_docx.py` | 刪 PRA 段 |
| `CITATION_BANK.md` | 移除 `scheibler2018_pyroom` 正文錨點 |
| `THESIS_DRAFT_FCU_v1.docx` | 執行 `rebuild_thesis_six_chapters.py` 後覆寫 |

### 7.2 保留但不寫入正文

| 路徑 | 處理 |
|------|------|
| `runtime/outputs/phase3_rtx_pra_comparison_*` | 保留作工程紀錄，論文不引用 |
| `scripts/run_pyroom_*`、`experiment_4_pra_*` | 不刪 code，論文不提 |
| `THESIS_SIM_LAB_SHOWCASE.md` | 標記 deprecated 或改 Lab 附錄說明 |

### 7.3 新素材來源（Phase B/C）

| 素材 | 路徑 |
|------|------|
| 閉環接近 smoke | `scripts/official_asset_ur10_ultrasonic_closed_loop_approach.py` |
| 夾取 smoke | `scripts/official_asset_ur10_ultrasonic_closed_loop_grasp.py` |
| 控制器 | `scripts/ultrasonic_closed_loop_controller.py` |
| 監管員 | `scripts/approach_supervisor_v1.py` |
| 結果 JSON | `runtime/outputs/ur10e_robotiq_ultrasonic_grasp_smoke_v1/` |
| Passport | `grasp_passport_v1.py`、`geometry_passport_v1.py` |

---

## 八、摘要改寫方向（中英文）

**中文要點：**
1. Isaac Sim 6.0 · UR10/UR10e · RTX Acoustic · 30/30 特徵可重現。  
2. 提出超聲閉環接近：控制器不讀目標座標；trial 9 示範 9 步至前進上限。  
3. Tier B 接觸級夾取示範；規則監管員處理 fusion 飽和。  
4. 明確限制：模擬、趨勢級、非 VLM 端到端替代。

**刪除摘要句：** 一切 PyRoom、RTX×PRA ρ、Lab SL r≈0.47、RL PPO。

---

## 九、執行順序（建議）

1. [x] 本規劃文件（你正在讀）  
2. [ ] 導師口頭確認：刪 PRA、Lab 降附錄、主軸改閉環  
3. [ ] 重繪圖3.1（A→B→C 架構圖）  
4. [ ] 改 `rebuild_thesis_six_chapters.py` + 重跑 docx  
5. [ ] 更新 `THESIS_CHAPTER2` + `CITATION_BANK`  
6. [ ] 從 history JSON 產圖5.2（可選 `generate_thesis_figures.py`）  
7. [ ] 摘要/結論與口試稿對齊  

---

## 十、封面題目建議（可選微調）

**中文：**  
UR10 系列機器人 RTX 超聲閉環接近之模擬驗證：可審計特徵管線與 Tier B 夾取示範

**英文：**  
Simulation of RTX Ultrasonic Closed-Loop Approach on UR10-Class Manipulators: An Auditable Feature Pipeline and Tier-B Grasp Demonstration

（刪除題目中 “PyRoom”“Isaac Lab Extension” 若原封面仍有）

---

## 十一、與程式 repo 的 Phase 對照（論文用）

| 論文章節 | 工程 Phase | 腳本 |
|----------|------------|------|
| 第四章 | Phase A（特徵） | `official_asset_ur10_fixed_tcp_distance_sweep.py` |
| 第五章 §5.1–5.2 | Phase B（接近） | `official_asset_ur10_ultrasonic_closed_loop_approach.py` |
| 第五章 §5.3–5.4 | Phase C（夾取） | `official_asset_ur10_ultrasonic_closed_loop_grasp.py` |

---

*本文件為重構之單一真相來源（SSOT）；後續 docx 生成以本檔 + `THESIS_OUTLINE_FCU_2026-06-30.md` 為準。*