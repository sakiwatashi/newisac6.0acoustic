# 碩士論文大綱（逢甲 · 電聲學程 · 六章版 · 2026-07-01 更新）

**取代：** `THESIS_OUTLINE_FCU_2026-06-29.md`（含 PyRoom / Lab 主貢獻之舊版）  
**規劃依據：** `THESIS_REFRAME_PLAN_2026-06-30.md`  
**實證依據：** `PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md`  
**初稿 docx：** `THESIS_DRAFT_FCU_v1.docx`（待 `rebuild_thesis_six_chapters.py` 對齊本大綱重跑）

---

## 論文定位

| 類型 | 是 | 不是 |
|------|----|------|
| 主體 | 可審計 RTX 特徵管線 + **超聲閉環接近** + **Physical AI 狀態估計** | 部署級超聲測距儀 |
| 驗證 | Phase A 30/30；Phase B/C v9 隨機化對照 | PyRoom 跨模擬器 ground truth |
| 操作 | Tier B 接觸級夾取（contact-only 預設；下游評估） | 穩定端到端夾取系統 |
| 電聲貢獻 | early energy、多徑、閉環距離感知、離線狀態分類 | 新物理模型推導 |

**一句話：** 證明 RTX 超聲特徵可支撐**不讀目標座標的閉環接近**，在隨機化 Sim 下提供可測量的 Physical AI 狀態信號，並以 Tier B 夾取示範下游限制。

---

## 封面資訊

| 欄位 | 內容 |
|------|------|
| 中文題目 | 基於 RTX Acoustic 超音波感測之機械手臂閉迴路接近控制與 Physical AI 狀態判斷 |
| 英文題目 | RTX Acoustic-Based Closed-Loop Robotic Approach Control and Physical-AI State Estimation in Isaac Sim |
| 學程 | 電聲碩士學位學程 |
| 指導教授 | 蔡鈺鼎 教授 |

---

## 第一章、緒論

### 1.1 研究背景
- 室內主動聲學與多徑；機器人非視覺 last-meter 需求
- RTX Acoustic 實驗性 API 之研究機會
- 與 VLM+相機全任務路線之**互補定位**（1 段）

### 1.2 研究問題
- **RQ1：** 特徵可重現性與距離趨勢？（Phase A）
- **RQ2：** 閉環接近是否改善目標區到達率？（Phase B）
- **RQ3：** 離線 Physical AI 是否含可測量聲學狀態信號？（Phase B/C）
- **RQ4（限制）：** Tier B 接觸夾取是否趨勢級可行？（Phase C，不作主貢獻）

### 1.3 範圍與限制
- Sim only；experimental API；單走廊；claim boundary 表
- 最終夾取 ~20% → 歸因 PhysX 接觸，非聲學失敗

### 1.4 貢獻
1. Passport + 30/30 可審計管線（Phase A）
2. 超聲閉環接近 + supervisor v1（Phase B）
3. 隨機化 Sim 下 Physical AI 狀態估計基線（Phase B/C）
4. Tier B contact-only 示範與階段化評估框架（Phase C，附貢獻）

---

## 第二章、文獻探討

| 節 | 內容 |
|----|------|
| 2.1 | 非視覺測距、主動回波 |
| 2.2 | 機器人模擬與 Sim2Real 認識論 |
| 2.3 | 室內多徑、early energy |
| 2.4 | RTX Acoustic / GMO |
| 2.5 | **閉環感知與視覺語義操作（VLM）對照** ← 取代原 PRA |
| 2.6 | Physical AI / 狀態估計於機器人操作（簡短） |
| 2.7 | 研究缺口 G0 與本研究定位 |

**刪除：** 原 §2.5 PyRoomAcoustics、Brinkmann round-robin 主體討論。

---

## 第三章、研究方法

| 節 | 內容 |
|----|------|
| 3.1 | 研究架構（圖3.1：Phase A→B→C + Physical AI） |
| 3.2 | Isaac Sim 平台與可重現執行 |
| 3.3 | Phase A：fixed_tcp_moving_target |
| 3.4 | Geometry / Material / Grasp Passport |
| 3.5 | RTX GMO 與 signal-way 特徵工廠 |
| 3.6 | Phase B：UltrasonicClosedLoopController |
| 3.7 | Phase C：UR10e+Robotiq 協定、supervisor、contact-only（`--skip-lift`） |
| 3.8 | v8/v9 隨機化資料集協定與離線 Physical AI 管線 |
| 3.9 | 評估指標與 claim boundary |

**刪除：** 原 §3.6 PyRoomAcoustics。

---

## 第四章、特徵驗證結果（Phase A）

| 節 | 內容 | 圖表 |
|----|------|------|
| 4.1 | 30/30 可重複性 | 表4.1–4.2 |
| 4.2 | 距離趨勢（early_energy） | 圖4.1–4.2 |
| 4.3 | 材質 A/B/C | 圖4.3、表4.3 |
| 4.4 | P1 管線穩健性（可精簡） | — |

**刪除：** 原 §4.2 RTX×PRA、圖4.3 PRA 曲線。

---

## 第五章、閉環接近、Physical AI 與夾取評估（Phase B/C）

| 節 | 內容 | 圖表 |
|----|------|------|
| 5.1 | 搜尋走廊、感測器掛載、隨機化協定 | 圖5.1 |
| 5.2 | 閉環 vs open-loop 接近成功率 | **表5.1**（84% vs 29%） |
| 5.3 | 規則監管員 v1（oracle 僅安全包絡） | 圖5.3 |
| 5.4 | **離線 Physical AI 特徵消融** | **表5.2**（F1 0.684 / 0.598 / 0.533） |
| 5.5 | Tier B 夾取：contact-only、PhysX 診斷、SurfaceGripper 嘗試 | 表5.3（階段化：approach / contact / final） |
| 5.6 | 與 VLM 端到端路線之討論（短節） | — |

**原第五章 Isaac Lab / SL / RL → 附錄 A（可選，≤3 頁）。**

### 表5.1 建議內容（來自 v9）

| Metric | Closed-loop | Open-loop |
|---|---:|---:|
| Approach ≤ 0.45 m | 84.0% | 29.2% |
| Near ≤ 0.35 m | 84.0% | 4.2% |
| Final success | 20.0% | 20.8% |

### 表5.2 建議內容（stop_region_label ablation）

| Feature Set | F1 | Balanced Accuracy |
|---|---:|---:|
| All features | 0.684 | 0.665 |
| Acoustic only | 0.598 | 0.590 |
| Pose only | 0.533 | 0.650 |

---

## 第六章、結論與建議

| 節 | 內容 |
|----|------|
| 6.1 | 結論（對應 RQ1–3；RQ4 列限制） |
| 6.2 | 綜合討論（聲學特徵 + 閉環 + Physical AI + 夾取瓶頸） |
| 6.3 | 限制與 claim boundary |
| 6.4 | 後續：CH201 實機、SurfaceGripper isolated smoke、VLM hybrid、線上策略 |

---

## 附錄 A（可選）

- Isaac Lab 動態 smoke、Sim→Lab SL、in-sim RL（**不計入主貢獻**）
- RTX×PRA 工程紀錄（一句帶過或省略）

---

## 下一步

1. [ ] 導師確認本大綱（含 7/1 Physical AI 章節）
2. [x] 重繪圖3.1（A→B→C + Physical AI）
3. [x] 執行 `rebuild_thesis_six_chapters.py` 大改（2026-07-01 對齊）
4. [x] 摘要中英文改寫（刪 PRA / Lab SL 主貢獻句）
5. [x] README + `REPRODUCIBILITY_AUDIT.md` 對齊 7/1
6. [ ] 口試前嵌入 Phase B/C 軌跡圖（圖5.1–5.2，可選）
7. [ ] 填入封面研究生姓名