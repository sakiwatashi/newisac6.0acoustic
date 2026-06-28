# 碩士論文大綱（逢甲大學 13b 格式）

**學程：** 電聲碩士學位學程（全職碩士）— **詳見** `THESIS_OUTLINE_FCU_2026-06-29.md`（六章版）  
**指導教授：** 蔡鈺鼎 教授
**格式依據：** `/home/lab109/下載/13b-論文格式範本v.20221005.docx`  
**參考文件：** `/home/lab109/下載/fcuformat202203 (1).docx`（學術倫理聲明書、APA 參考文獻格式）  
**初稿 docx：** `isaacsim6.0/thesis/THESIS_DRAFT_FCU_v1.docx`

---

## 封面資訊（待填）

| 欄位 | 建議內容 |
|------|----------|
| 中文題目 | UR10 末端 RTX 聲學感測之 Isaac Sim–Lab 管線研究：固定 TCP 驗證與動態觀測延伸 |
| 英文題目 | An Isaac Sim-to-Lab Pipeline for UR10 RTX Acoustic Sensing: Fixed-TCP Validation and Dynamic Observation Extension |
| 指導教授 | （待填） |
| 研究生 | （待填） |
| 完成年月 | 中華民國 115 年 6 月（2026 年 6 月，依實際口試調整） |

---

## 前置頁（依 13b 順序）

1. 封面  
2. 誌謝（1 頁，最多 2 頁）— 初稿留占位  
3. 摘要（中文，1–2 頁）— **初稿已寫**  
4. Abstract（英文，1–2 頁）— **初稿已寫**  
5. 目錄（Word 自動目錄，更新後填入頁碼）  
6. 圖目錄  
7. 表目錄  

**格式提醒（13b）：**
- 章標題：`第一章、緒論`（頓號、20pt 粗體）
- 節標題：`1.1 研究動機及背景`（18pt 粗體）
- 內文：14pt 標楷體、左右對齊
- 圖號：`圖3.1`（勿用 `圖3-1`）；圖名在圖**下方**
- 表號：`表4.1`；表名在表**上方**

---

## 第一章、緒論

### 1.1 研究動機及背景
- 視覺為主的機器人感知在遮蔽、低光、反光、粉塵等場景的侷限
- 非視覺主動測距（超音波 / ToF）的互補角色
- Isaac Sim 6.0 RTX Acoustic 作為模擬驗證工具的機會
- UR10 工業手臂 + 未來 CH201 實機路徑的研究脈絡
- **問題意識：** 模擬數據能否支撐距離感知可行性，而非宣稱波形級等價

### 1.2 研究目的
1. 建立可重現的 UR10 末端 RTX Acoustic 距離掃描模擬管線（Isaac Sim）  
2. 以 Geometry / Material Passport 控制實驗變量（固定 TCP、移動目標）  
3. 萃取 signal-way 特徵並評估距離與材質敏感度  
4. 以 PyRoomAcoustics 提供趨勢級參考對照  
5. 將同一管線延伸至 Isaac Lab 動態觀測與 Sim→Lab 監督學習示範  
6. 為未來 CH201 實機與強化學習驗證建立協定與 claim boundary

### 1.3 研究範圍
- **納入：** Isaac Sim 6.0 host standalone、官方 UR10、六面牆房間、0.5–3.0 m sensor→target 距離、材質 A/B/C、30 次正式可重複性實驗  
- **排除：** CH201 實機量測、波形級 RTX–PRA 等價驗證、移動手臂 IK 距離掃描（已廢棄）、Docker 舊環境數據  

### 1.4 研究限制（建議納入，13b 範本未列但 fcuformat 有）
- 模擬_only、n=6 距離點、單一 TCP 姿態、材質映射近似、early_energy 啟發式定義  

### 1.5 名詞解釋（可併入 1.3 或獨立小節）
- RTX Acoustic / GMO / signal-way / fixed_tcp_moving_target / claim_boundary  

---

## 第二章、文獻探討

### 2.1 機器人非視覺感測與超音波測距
- 手臂掛載測距感測器之安裝與校正議題
- ToF / 超音波在機器人任務中的互補角色

### 2.2 模擬與虛實整合（Sim-to-Real）
- 模擬器非物理真值；應以任務級指標驗證
- Isaac Sim 在機器人感測模擬中的定位

### 2.3 聲學模擬與多徑效應
- 幾何、材質、多徑對接收特徵的影響
- 不宜將模擬輸出直接等同物理 ToF

### 2.4 RTX Acoustic 與 GenericModelOutput
- Isaac Sim 6.0 experimental API
- Signal-way 語義（tx/rx/ch + 320 samples）

### 2.5 PyRoomAcoustics 房間聲學基線
- RIR、RT60、early energy 作為趨勢參考
- 與 RTX 的模型差異（非 ground truth）

### 2.6 文獻缺口與本研究定位
- 缺乏 RTX Acoustic + UR10 + 系統可重複性之整合研究
- 本研究定位：可行性與方法論，非終極物理驗證

---

## 第三章、研究流程與方法

### 3.1 研究架構與流程
- 圖3.1 研究流程圖（Geometry Passport → Capture → Feature → PRA 對照）
- Phase 1–3 階段說明

### 3.2 實驗平台與軟體環境
- Host Isaac Sim 6.0、`run_host_python.sh`
- 官方 UR10 資產路徑

### 3.3 實驗設計：fixed_tcp_moving_target
- UR10 reach 1.3 m 與距離定義（sensor frame）
- 固定 TCP（≈0.82 m）+ 移動目標之理由
- 廢棄 IK 移動手臂方案之說明

### 3.4 Geometry Passport v1.0
- 房間 4.5×3.0×2.8 m、感測器掛載、目標尺寸 8×8×2 cm
- 距離 waypoints 0.5–3.0 m

### 3.5 Material Passport v1.0
- NonVisualMaterial 條件 A/B/C 對照表

### 3.6 RTX Acoustic 數據擷取
- Writer + timeline.play()
- `rtx_acoustic_factory.py`：GMO 驗證、signal-way 解析

### 3.7 特徵萃取與分析
- `primary_sgw_early_energy` 定義（前 25% samples）
- 可重複性協定（6×5=30 runs）
- Spearman 趨勢相關、claim boundary

### 3.8 PyRoomAcoustics 參考實驗
- 幾何對齊、吸收係數、萃取特徵

### 3.9 Isaac Lab 動態環境（新增）
- 安裝、AppLauncher、experience 設定
- `fixed_tcp_moving_target_dynamic`、正弦軌跡、decimation
- 正文見 `THESIS_LAB_SECTIONS_2026-06-28.md` §3.9

---

## 第四章、實證結果與分析

### 4.1 實驗可行性與可重複性
- 表4.1 30/30 PASS 摘要
- 表4.2 跨 repeat CV（amplitude_max、early_energy）
- `max_ee_motion_m = 0`、`gmo_valid_rate = 1.0`

### 4.2 距離趨勢分析（材質 B）
- 表4.3 RTX vs PRA 距離特徵（6 點）
- 圖4.1 RTX amplitude_max 飽和曲線
- 圖4.2 RTX primary_sgw_early_energy vs 距離
- 圖4.3 PRA 特徵 vs 距離
- Spearman ρ 解讀（主推 early_energy ρ=−0.66；RTX×PRA ρ=+0.66）

### 4.3 材質敏感度分析（A/B/C）
- 表4.4 跨材質 0.5 m / 3.0 m 比較
- 圖4.4 材質 early_energy 長條圖（待繪）
- Peak 不敏感 vs early_energy 近距離可區分 C

### 4.4 穩健性驗證（P1）
- GMO 結構驗證、NV 材質 ID decode

### 4.5 Isaac Lab 動態觀測原型（新增，✅ 有數據）
- 128 steps、27 GMO、ρ(early_energy, GT)=−0.475
- 圖4.5 軌跡、圖4.6 散佈

### 4.6 監督學習 Sim→Lab 遷移（新增，✅ 有數據）
- Sim 125 訓練 / Lab 27 測試；MAE=0.41 m，r=0.47
- 雙特徵消融：peak 無幫助
- 圖4.7、圖4.8

### 4.7 綜合討論（原 4.5 討論移至此）
- early_energy vs amplitude_max；Sim+Lab+PRA；CH201 意涵

---

## 第五章、結論與建議

### 5.1 研究結論
- Sim 主結果 + Lab 動態延伸 + SL 遷移示範（六條）

### 5.2 研究建議
- 短期：Word 貼 §4.5–§4.6、CH201 協定
- 中期：Phase 5 RL smoke（見 `ISAAC_LAB_PHASE5_RL_PLAN.md`）、離軸點位
- 長期：sim-to-real 任務級驗證

---

## 參考文獻
- APA 格式（中文筆劃、英文 A–Z）
- 初稿列 8–10 筆占位 + 已確認之 Isaac Sim / UR10 官方來源

---

## 圖表清單（論文用）

| 編號 | 標題 | 狀態 | 來源 |
|------|------|------|------|
| 圖3.1 | 研究流程圖 | 待繪 | 依 Phase 1–3 流程 |
| 圖3.2 | 實驗場景示意（UR10+房間+目標） | 待截圖 | GUI |
| 圖4.1 | RTX amplitude_max vs 距離 | 已有 | `rtx_amplitude_max_vs_distance.png` |
| 圖4.2 | RTX early_energy vs 距離 | 待繪 | 由 Table 4.3 |
| 圖4.3 | PRA 特徵 vs 距離 | 已有 | `pra_features_vs_distance.png` |
| 圖4.4 | 材質 A/B/C early_energy 比較 | 待繪 | material_cross_condition |
| 圖4.5 | Lab 動態 GT 距離軌跡 | ✅ | `lab_target_trajectory_xy.png` |
| 圖4.6 | Lab early_energy vs GT | ✅ | `lab_obs_vs_gt_distance.png` |
| 圖4.7 | SL Sim→Lab 預測 vs GT | ✅ | `sl_sim_to_lab_pred_vs_gt.png` |
| 圖4.8 | SL 軌跡對照 | ✅ | `sl_sim_to_lab_trajectory.png` |
| 表3.1 | Geometry Passport 參數 | 初稿有 | geometry_passport_v1 |
| 表4.5 | Lab smoke 摘要 | 待貼 | `lab_dynamic_obs_summary.json` |
| 表4.6 | SL Sim→Lab 指標 | 待貼 | `sl_distance_summary.json` |
| 表3.2 | Material Passport A/B/C | 初稿有 | rtx_material_passport |
| 表4.1 | 正式實驗 PASS 摘要 | 初稿有 | 30/30 |
| 表4.2 | 可重複性 CV | 初稿有 | features CSV |
| 表4.3 | 距離趨勢 RTX×PRA | 初稿有 | comparison CSV |
| 表4.4 | 材質敏感度 | 初稿有 | material_cross |

---

## 兩份格式文件差異（採用建議）

| 項目 | 13b（智能製造） | fcuformat202203（通則） |
|------|----------------|------------------------|
| 適用 | **本論文首選** | 學術倫理聲明、APA 範例 |
| 章節標示 | `第一章、緒論` + `1.1` | `第一章緒論` + `第一節` |
| 圖號 | `圖1.1` | `圖1` |
| 建議 | 正文依 13b | 繳交時加倫理聲明書（fcuformat 前段） |