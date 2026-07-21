# 專案交接文件(現況版,2026-07-22 更新)— 給任何接手的 AI/人

> 讀我就夠開工。歷史細節按需往下挖,不必預讀。
> 舊版交接(`docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md`)是 7/8 開工前的計畫書,僅供考古。
> **公開 git remote：** `newisac` → `https://github.com/sakiwatashi/newisac6.0acoustic.git`  
> **論文 docx 以本機為準**（預設不隨 push）；**`.pt` 權重不進 git**。


## 2026-07-22 交接增量（論證閘門 + P0 感測鏈審計 + 軸向 P0 關閉）

### 完成
1. **論文論證閘門**（補「合規全綠仍被論證層重寫」）：`docs/plan_v2/THESIS_ARGUMENTATION_GATES.md`  
   - G0 節職能 → G1 論證鏈 → G2 減肥 → G3 主張–證據 → G4 尺度 → G5 句服務職能 → G6 章串線  
   - **三層全綠才算論述可對外**：實驗鐵律 / 數字合規 / **論證閘門**
2. **P0 離線審計（A，零 GPU，已全過）**  
   - 腳本：`scripts/p0_gmo_chain_offline_audit.py`  
   - 報告：`docs/plan_v2/reports/P0_GMO_CHAIN_AUDIT.md`  
   - 產物：`runtime/outputs/p0_gmo_chain_audit/{metrics.json,figures/}`  
   - 結論：way 不串接；scalar≠40kHz 載波；控制用 OLS；S1 峰=目標相關；S2 r≈0.9994 且斜率貼 sampleDuration
3. **P0 可選 GPU dump**：`scripts/p0_fixed_sensor_gmo_dump.py`
4. **P0 follow-up A/B**：`docs/plan_v2/reports/P0_FOLLOWUP_AB.md`
5. **Signedness + primary 正典表述 → 軸向 P0 正式關閉**  
   - `docs/plan_v2/reports/P0_AXIAL_CLOSED.md`  
   - `runtime/outputs/p0_gmo_chain_audit/p0_signedness_check.json`  
   - 規則：\(k=\arg\max s[i]\)（有號）；primary=有號 max 較大 way（**非**固定 way0）  
   - 正典 S1/S2 波形全非負 → 與 \|·\| 重合；CSV 與有號 argmax 一致
6. **3.1 可貼段落**：`thesis/P0_SECTION_3_1_PATCH.md`（已改 primary／有號峰）

### 宣稱
- 可：軸向 P0 關閉；3.1 貼修訂稿。  
- 不可：因 P0 重跑 D1–D3；稱 40 kHz 原始波形；稱 way 串接；稱已固定 way0 為正典；D2 橢圓已驗證。  
- **下一優先（已做）**：D2 圓 vs 橢圓 → **保持圓正典**（`docs/plan_v2/reports/D2_CIRCLE_VS_ELLIPSE.md`）；\(\hat r\) 貼 \(R\) 不貼 \(L/2\)。  
- **給 GPT 回覆稿**：`docs/plan_v2/REPLY_TO_GPT_P0_CLOSED_AND_D2.md`  
- **GPT 第一章～3.1 整合稿入庫**：`thesis/THESIS_CH1_TO_3_1_GPT_INTEGRATED.md`（原文 `thesis/sources/THESIS_CH1_TO_3_1_GPT_SOURCE.docx`；3.1 已換 P0 正典）

## 2026-07-20 交接增量（GUI 平行入口 + README 對齊 + 本機論文資產）

### 完成（程式／文件 → 應進 git；論文 docx → 本機）
1. **GUI 平行入口（不覆寫 headless 原檔）**
   - `scripts/gui_formal_exec.py`：headless→開窗、fixed dt、render、Camera Light、開始前 10s／結束後 15s
   - `runtime/run_v2_*_gui.sh`、`lab/run_d4_*_gui.sh`、`scripts/d4_acoustic_grasp_sm_runner_gui.py`
   - 說明：`docs/plan_v2/GUI_EXPERIMENT_COMMANDS.md`
2. **示意圖產線**：`thesis/figures/gen_schematic_figures.py` + `thesis/figures/schematic/*.png`
3. **插入表／圖工具**：`thesis/insert_tables_and_schematics.py`（本機 docx 已插入表 3.1/3.2 與示意圖）
4. **口試便利貼腳本**：`thesis/annotate_defense_sticky_notes.py` + 索引 md
5. **README.md** 改寫為 V2 S1–D4 正典導覽（淘汰 7/1 Physical AI 舊入口為主敘事）

### 本機論文（不預設 push）
- `thesis/THESIS_DRAFT_FCU_v2.docx`：頁首題名、1.3 邏輯順序、表／示意圖、便利貼等
- 備份多份 `*.bak_*` 在本機

### 宣稱／禁止（不變）
- 正典對位：**D3 r3**；D4 為延伸
- 禁止覆寫 `v2_d3_grasp_r3`；禁止摩擦夾持／pure-reward e2e 宣稱


## 2026-07-18 交接增量（D4 雙軌收束 + 報告）

### 完成
1. **Track A 正式三臂** `v2_d4_sm_grasp_n30/`：closed 對位 **73%** vs blind **40%**，r=0.976，Fisher p≈0.009；weld 升舉；**無 weld g0 FAIL**。
2. **Track B 正典** `v2_d4_ppo_grasp_acoustic_close_ft/model_49.pt`：8-D 聲學 obs、true scaffold reward；eval true success **100%**。
3. **消融**：② BLIND+true → 也 100%（開環可過）；③ pure d_hat reward → true **0%**（假近）。
4. **④ SM 掛接**：`bash lab/run_d4_sm_policy_hookup.sh` → LIFT_HANDOFF **100%**；物理 lift 仍 A。
5. **報告**：`docs/plan_v2/reports/D4_sm_grasp_report.md`

### 宣稱上限
- 可：聲學對位贏盲走；B 學接近+合爪（obs 無 xyz）；協議 handoff；weld 升舉分欄。
- 不可：pure-reward 成功、必須聽音、摩擦-only 升舉、handoff×lift 當未跑 e2e。

### 同場景 n=90（完成）
- `runtime/outputs/v2_d4_same_scene_policy_n90/`：對位 **76.7%**、升舉 **74.4%**、P(lift|align) **76.8%**
- 報告：`docs/plan_v2/reports/D4_sm_grasp_report.md` §5.4
- **論文 §5.3 增補草稿**：`thesis/THESIS_CH5_3_D4_SUPPLEMENT_DRAFT.md`（待貼入 docx）

### 下一步（可選）
1. 將 §5.3 草稿貼入 `THESIS_DRAFT_FCU_v2.docx`  
2. 修 d_hat 再試 pure reward（非必須）  

### 禁止
- 覆寫 `v2_d3_grasp_r3`
- 宣稱 B 為物理摩擦夾取或官方 Franka lift 復現

---

## 2026-07-16 交接增量（D4 雙軌 + 訓練開工）— 考古

### 當時完成
1. Track A n30 + B PPO 短訓骨架。
2. 誠實邊界：B ≠ 摩擦夾取 / ≠ D3 r3 替代。

### 當時已知問題（已在後續修復）
- d_hat 卡死 → gated sample-index peak 已修；見 D4 報告 §3.3。
---

## 2026-07-15 交接增量（文獻×數學詳版 + Nosek PDF）

### 今天做了什麼
1. 新增**逐步實驗—數學—文獻原文**對照（非標題表）：
   - **`docs/plan_v2/EXPERIMENT_MATH_LITERATURE_GROUNDING.md`**
   - 自第一次 ToF／peak 公式起，經 S1 SNR、OLS、三臂／預註冊、D1–D3 控制、D2 Gauss–Newton，每步含：公式、文獻角色、**PDF 可摘之原文**、自有部分、口試答法。
2. `METHOD_LITERATURE_MAP.md` 頂部加上指向詳版的連結。
3. 補下載 **Nosek 2018** 開放稿至  
   `thesis/literature_key_papers/02_Nosek_2018_The_preregistration_revolution_PNAS.pdf`，並更新 `MISSING_PAPERS_TO_DOWNLOAD.md` 註記。
4. 本交接檔日期改為 **2026-07-15**。

### 接手若要講「我們對照哪篇論文」
- **先讀詳版** `EXPERIMENT_MATH_LITERATURE_GROUNDING.md`（有 Zhmud \(S=vT/2\)、Kapoor multilateration 定義、Meyes ablation、Nosek preregistration 等原文）。
- 一頁速查仍用 `METHOD_LITERATURE_MAP.md`。
- PDF 包：`thesis/literature_key_papers/`；仍缺 Hayes / Valin / Höfer / Kerstens / He / Tsuchiya 等見 MISSING 清單。

### 未變動的鐵律
- commit 政策、論文不上公開 GitHub、預註冊不放寬、三臂／配對規則——仍見下文「鐵律」。

### 與 7/12 交接的關係
- 7/12 晚間實驗／論文／口試 Q&A 現況**仍然有效**；本節只追加文獻對照資產與 Nosek PDF。

---

## 一句話:這專案是什麼、現在在哪

逢甲電聲碩士論文(指導教授蔡鈺鼎):在 Isaac Sim 6.0 RTX Acoustic 模擬中,驗證「純超聲回授引導 UR10e 機械手臂接近、二維定位並夾取隨機目標」。
**現況:八個實驗全部完成、判準全綠;論文與實驗同步;口試 Q&A 備妥。另已開工 D4 雙軌(聲學規則對位+連續夾取狀態機 / 聲學 PPO 骨架),正典 D3 r3 不動。主軸=口試準備 + D4 g0/GPU 冒煙。**

## 7/12 晚間新增(嚴格自審輪+三個零/低成本延伸,細節見 PROGRESS 最後三節)

- 論文第六章兩處「敘事落後於實驗」的自相矛盾已修(6.2 殘句/6.3 過期未來工作);5.3 補升舉失敗逐回合歸因(容差 ±2 cm vs 物理捕捉窗 ±1.5 cm 之縫隙)。
- **E1 MLP 延伸**:非線性小模型(64 隱藏元)RMSE 51.9 cm 仍完敗解析法 1.93——E1 負結果升級,封掉「只比線性是稻草人」質疑(`ml_stage3_e1_mlp_ext.py`)。
- **噪聲敏感度探針**:解析測距鏈呈閾值行為,SNR ≥20 dB 精度無損、20→14 dB 斷崖失效(`noise_sensitivity_probe.py`)。
- **2D 夾取三段閘門走完前兩段並止損**:誤差預算(`d2v2_error_budget.py`,含 v1 iid 模型被錨定否決之完整失效鏈)→ g2-wide 探針(`d2v2_trilat_probe_wide.py`,195 點)→ **側向 RMSE 1.84 > 1.5 cm 判死,依預註冊止損終止**。死因=方位角相關測距偏置(斜視角回波來自方目標近側稜角),非偵測/噪聲。裁定與再設計路徑(未執行)見 `runtime/outputs/v2_d2v2_probe_wide/adjudication.json`。論文 6.3 寫法不變且多了直接數據支撐。
- **口試 Q&A 準備文件**:`docs/plan_v2/DEFENSE_QA_PREP.md`(六個嚴格委員問題+排練答案+現場資產)。

## 30 秒驗證現況(先跑這個)

```bash
cd /home/lab109/song/isaacsim6.0
bash runtime/verify_all.sh    # 零 GPU,重算全部裁定;全過 exit 0
```

## 成果地圖

| 東西 | 位置 |
|------|------|
| 實驗鏈結果總覽 + 逐日歷程 | `docs/plan_v2/PROGRESS.md`(權威,倒序讀最後幾節即最新)|
| 六份裁定報告(含 D3 失效—修正—複驗全紀錄)| `docs/plan_v2/reports/` |
| 設計/預註冊/決策 D-1~D-13 | `docs/plan_v2/`(含 `d3/decisions.md`、`D2V2_DESIGN_*.md`)|
| 全部原始數據(csv/波形 npy/裁定 json)| `runtime/outputs/v2_*`、`_r2/_r3`、`ml_stage3/` |
| 論文(docx+pdf;產生器=唯一改動入口)| `thesis/THESIS_DRAFT_FCU_v2.*`、`thesis/rebuild_thesis_v2.py` |
| GUI 展示(掃描→定位→聲學停止→夾取)| `./app/python.sh scripts/demo_gui_showcase.py` |
| 精選快照(=GitHub 公開版根目錄,不含論文)| `clean/`;遠端 https://github.com/sakiwatashi/isaacsimacousticfinal |

## 八實驗一覽(細節見 PROGRESS/報告)

S1 包絡(36/52)→ S2 特性(r=0.9994;側向預定證偽)→ D1(r=0.997)→ D1.5 手臂(r=0.986,主結果)
→ D2 二維多點定位(側向 r=0.950、停止 1.9cm,4/4)→ D3 夾取(首輪 3/4 如實 False → 走廊修正 r3 4/4)
→ M3 校正歸因關閉 → 側向四重證偽 + 頻率無效(負結果)→ ML 三件套(E2 AUC=0.981 過閘、E3 R²=0.925、E1 解析法勝出之教學負結果)。

## 鐵律(接手後必守,違反=重蹈舊轍)

1. 任何「感測到 X」宣稱 → 同 session 配對移除對照。
2. 任何「閉環優於 Y」宣稱 → 盲走消融同管線對照。
3. 判準先寫後跑(runner header);主指標=行為量 vs 目標量之相關/誤差,不用到達率。
4. 原始波形一律落盤;裁定只由離線 analyzer 計算。
5. oracle 量只進記錄欄,永不入控制。
6. 判準沒過:不放寬,歸因→修設計→新目錄完整重跑(D3 為範例)。
7. 舊管線腳本(`official_asset_*`、`ultrasonic_*`)不修改;白名單工具:`rtx_acoustic_factory` parse 系列、`ur10e_robotiq_common`、`ur10e_robotiq_passport_v1`、`geometry_passport_v1`。
8. commit 由用戶拍板;GitHub 公開倉庫**不上論文檔**(口試前)。

## 高價值教訓索引(踩過的坑,勿重踩)

- 模擬器事實表+死路清單:`docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md` §3/§11(仍有效)+ `docs/WPM_EXPERIMENT_RULES.md`(注意頂部校正沿革:132.5µs 已廢,一律當輪自校)。
- 夾爪物理 24 輪除錯史(tool0/ee_link 靜態框架、夾爪朝下、close 終端間隙≈5cm、weld-on-stall):`docs/plan_v2/d3/notes.md`。
- GUI vs headless 時間模型(牆鐘巨步、逐幀瞬移能量泵、出生姿態掃桌):`scripts/demo_gui_showcase.py` 頭部註解 + `gui_physics_probe.py`。
- 確定性引擎下 ML 必須分組交叉驗證(雙胞胎洩漏):`scripts/ml_stage3_suite.py` 頭部。

## 未結事項(全部非緊急)

1. **教授對齊**(最優先的人類行動,教授目前出門中)。會面決策清單已備齊:
   - P1/P2 入不入正文;ML 三件套+E1 MLP 延伸是否入 appendix。
   - 跨 seed 補跑(~2h GPU,回應單 seed 質疑的低成本補強)。
   - 層二閉環內噪聲注入(正式實驗,GPU+預註冊+改 CH5)。
   - 2D 夾取再設計(方位角相關校正→新閘門重跑;g2-wide 已判死現行設計,主 agent 建議不走)。
2. **口試演練**:以 `docs/plan_v2/DEFENSE_QA_PREP.md` 為本;Q7(近場開環)/Q8(電聲身分)兩題尚未補寫。
3. README/REPRODUCIBILITY_AUDIT(主 repo 頂層)仍掛舊敘事,至少加警示 banner(健檢 M1/M2)。
4. 口試後:GitHub 補論文、LICENSE 選擇(用戶決定)。GitHub 公開倉庫尚未同步 7/12 晚間新增(等用戶指示)。
5. 可選延伸(設計已記載):滑動窗口動態追蹤、佔據柵格地圖、實機 CH201。二維夾取已由閘門判死(見上)。
