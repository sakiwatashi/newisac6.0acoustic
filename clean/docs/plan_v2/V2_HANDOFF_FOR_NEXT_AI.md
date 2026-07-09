# V2 實驗規劃 — 完整交接文件(給任何接手的 AI)

**日期**:2026-07-08
**狀態**:規劃完成、尚未動工。本文件自足——照著做即可,不需要讀舊實驗的任何結果。
**上層摘要版**:`docs/EXPERIMENT_PLAN_V2.md`(一頁版);本文件是可執行細節版,兩者衝突時以本文件為準。

---

## 1. 一句話任務

在 Isaac Sim 6.0 的 RTX Acoustic(WPM)超聲模擬上,**先量測「感測器在什麼幾何條件下讀得到目標」的包絡地圖,再把機械手臂閉環任務設計進包絡內**,產出一本每個宣稱都有對照組的碩士論文。

## 2. 專案背景(30 秒版)

- 逢甲大學電聲碩士,指導教授蔡鈺鼎。論文方向:RTX Acoustic 超聲感測 × UR10e 機械手臂閉環接近 × 狀態估計(模擬可行性,非部署宣稱)。
- 上一代實驗程式(v9/v4 系列)被三層審計推翻:接近成功率是幾何/oracle 人工產物,且目標在原任務場景中聲學不可見。詳細證據鏈在 `docs/handoff/E3_target_invisibility_and_v9_audit.md`,**但 V2 的設計不依賴那些結論**——V2 自帶重新驗證(Stage 1 的 clutter 因子會直接重測「桌+手臂場景目標是否可見」)。
- 用戶最在乎的事(吃過大虧):**不要基於未驗證的前提繼續蓋**。V2 的全部結構就是為此設計。

## 3. 必知的模擬器事實(工具知識,非實驗結論;附驗證方式)

這些是 Isaac Sim 6.0 RTX Acoustic 的 API/行為事實,寫腳本前必讀。完整規則文本:`docs/WPM_EXPERIMENT_RULES.md`(權威,先讀它)。速記:

| # | 事實 | 驗證方式 |
|---|------|----------|
| 1 | GMO 的 `z` 是 channel ID,不是時間軸;時間波形用 `numSamplesPerSgw` stride 重建 | 規則 1-1/1-2;範例程式碼在規則 4-3 |
| 2 | `timeOffsetNs` 全為 0(引擎不填),不可用於任何距離計算 | 每次擷取印 `tof_first_ns` 確認 |
| 3 | 樣本週期需自行校正(歷史校正值 132.5e-6 s;V2 的 S2 會重新自校,勿直接沿用) | S2 距離掃描斜率反推 |
| 4 | `argparse` 必須在 `from isaacsim import SimulationApp` 之前,用 `parse_known_args()` | 規則 4-1 |
| 5 | Replicator Writer 拿資料要用 module-level dict(`_buf = {"latest": None}`) | 規則 4-2 |
| 6 | `set_prim_visibility(False)`、xform translate 移遠、`stage.RemovePrim` 三者都能把 prim 從 WPM ray tracing 移除(已用探針驗證,Δ=雜訊 400 倍) | 跑 `./app/python.sh scripts/visibility_wpm_probe.py`,看三行 VERDICT |
| 7 | 感測器 warmup:≥20 frames 直到 `numElements > 0` | 探針腳本有現成寫法 |
| 8 | 移動 prim 用直接 USD xformOp(規則 3-4),不用高階 API | 規則 3-4 有程式碼 |
| 9 | 跨 session 浮點雜訊 ~1e-5 量級(絕對值);同 session 連續擷取更小 | 探針的 A2 條件 |
| 10 | **樣本週期實測 ≈ 103 µs**(V2 S2 自校,兩種高度 103.1/100.8),≈ schema 預設 102.4;**舊說 132.5 µs 不適用於 V2 場景** | `runtime/outputs/v2_s2_datasheet/datasheet_summary.json` |
| 11 | GMO 每幀 2 個 way,**id 欄 (tx,rx,ch) 全零**——接收器身分不編碼;way 序數能量差不含側向資訊(側向掃描證偽,ρ=0.36) | S2 報告;重測:`S2_DEBUG_IDS=1` 跑 s2_datasheet_runner |
| 12 | 幀間輪替結構:量測 block ≥12 幀才穩(6 幀 drift 8%、12 幀 3.9%);peak_idx 通道對能量慢震盪免疫,控制器以 peak_idx 為主 | S2 報告 |

**最佳範本腳本**(抄它的骨架,不要從零寫):`scripts/visibility_wpm_probe.py`——它已含:正確 argparse 順序、writer、warmup、stride 波形重建、條件間 settle、RemovePrim、JSON 輸出。V2 的配對擷取引擎就是它的一般化。

**執行方式**:`./app/python.sh <script>`(repo 根目錄);headless 預設;GPU 上單一 session 啟動 ~10 s;實驗本體通常秒級到分鐘級。跑長批次用 `nohup` 或後台,log tee 到輸出目錄。

## 4. 五條鐵律(每個 runner 的 header 必須逐條寫明如何滿足)

1. **配對對照**:任何「感測到 X」宣稱 → 同 session、同幾何的 X-物理移除配對 run。
2. **資訊消融對照**:任何「閉環優於 Y」宣稱 → 致盲組(感測輸入置換為常數)跑完全相同管線。
3. **預註冊判準**:成功/失敗判準寫在 runner header,先於執行。主指標一律「行為量 vs 目標量的相關/誤差」;到達率、reason 標籤只能當次指標。
4. **原始波形落地**:每次擷取保存 primary-way 波形(.npy),離線可重算一切。
5. **acoustic_only 唯一**:正式數據中,oracle 量(目標真實位置等)只能進評估欄位,不得進控制、運動上限、出口條件。除錯 run 放獨立目錄並在 summary 標記 `debug_scaffold: true`。

## 5. Stage 0 — 基建(第一個要寫的東西)

### 5.1 `scripts/paired_capture_runner.py`(配對擷取引擎,S1 的心臟)

以 `visibility_wpm_probe.py` 為骨架一般化。

> **架構決策(2026-07-08,已定案)**:單 session 單 cell。不做同 session 多 cell 迭代,因為那需要中途移動感測器 prim,而 WPM 感測器建立後是否追蹤 transform 未經驗證(高風險未知)。批次 = 外層 shell 每 cell 呼叫一次(52 cells ≈ 26 分鐘 GPU,成本可接受)。感測器的位置與俯仰在建立時一次設定,擷取開始後絕不改動。

CLI:

```
--cell-json PATH      # 一個 cell 的場景描述(見 5.2 schema)
--output-dir PATH     # cell 子目錄由腳本以 cell_id 建立
--n-measure 6         # 每條件平均幀數
--n-settle 10
```

單一 cell 的流程(全部同一 session 內):

1. 依 cell 描述建場景:感測器 prim(位置+俯仰)、目標 Cube、clutter prims。
2. warmup(≥20 frames,直到 numElements>0)。
3. 擷取 `with_target`(settle n-settle → 平均 n-measure 幀)。
4. 再擷取一次同條件 → `noise_ref`(與 with_target 的差 = session 雜訊底)。
5. `stage.RemovePrim(target)` → settle → 擷取 `without_target`。
6. 重建目標(下一 cell 或結束)。

每 cell 計算並寫入:

```
snr_peak  = max|mean_with − mean_without| / max(max|mean_with − mean_noise_ref|, 1e-12)
snr_energy = Σ|mean_with − mean_without| / max(Σ|mean_with − mean_noise_ref|, 1e-12)
peak_idx_with, peak_idx_without, early_energy_with/without(前 20 樣本平方和)
```

輸出:`<output-dir>/cells.csv`(一 cell 一列,含全部因子值+上述指標)+ `<output-dir>/waveforms/<cell_id>_{with,without,noise}.npy` + `run_meta.json`(args、時間、git describe)。

**驗收**:對一個「已知可見」cell(無 clutter、水平、0.2m 目標、0.5m 距離)跑出 snr_peak > 100;對一個空場景假 cell(目標尺寸 0)跑出 snr ≈ 1。

### 5.2 Cell JSON schema

```json
{
  "cell_id": "A_d0.5_z0.20_p0_cnone",
  "target_distance_m": 0.5,
  "target_size_m": 0.20,
  "sensor_pitch_deg": 0,
  "clutter": "none | table | table_arm",
  "sensor_pos_m": [0, 0, 0.65],
  "notes": ""
}
```

- 感測器高度預設 0.65 m(接手可調,記錄即可)。俯仰 = 感測器 prim 繞 Y 軸旋轉(俯視為正)。目標中心放在感測器指向軸上距離 d 處(俯仰非 0 時目標隨軸線放低)。
- clutter=table:0.4 m 高實心桌(1.2×0.8 m)置於目標下方,目標置桌面上。
- clutter=table_arm:桌 + UR10e USD 資產(`Isaac/Robots/UniversalRobots/ur10e/ur10e.usd`,官方雲端路徑見既有腳本 `scripts/ur10e_robotiq_common.py` 的 ROBOT_USD 常數)以固定姿態擺在感測器正後方~0.1 m,模擬腕載幾何。不需要物理/articulation,純靜態 mesh 即可。

### 5.3 `scripts/analyze_envelope.py`(離線分析器,純 stdlib+可用 numpy)

讀 cells.csv → 印偵測度表(依因子分組)、標記 SNR>10 的可偵測格 → 輸出 `envelope_summary.json` + matplotlib 熱圖(距離×尺寸,每個 pitch×clutter 一張)。

## 6. Stage 1 — 感測包絡量測

### S1:偵測度地圖(52 cells,4 個 block)

因子水準:距離 D={0.15, 0.3, 0.5, 0.8, 1.2} m;尺寸 Z={0.04, 0.10, 0.20} m;俯仰 P={0, 30, 60}°;clutter C={none, table, table_arm}。

| Block | 固定 | 變動 | cells |
|-------|------|------|-------|
| A(基線) | P=0, C=none | D×Z | 15 |
| B(俯仰效應) | Z=0.10, C=none | D×{30,60} | 10 |
| C(桌面效應) | Z=0.10, C=table | D×P | 15 |
| D(桌+手臂) | C=table_arm, D={0.3,0.5,0.8} | {Z=0.10,0.20}×{P=0,60} | 12 |

計 52 cells;一個 block 一個 session(runner 的 --cells-json)。估 GPU 總時 <1 小時。

**預註冊判準**(寫進 runner header):
- SNR_peak > 10 → 可偵測。
- Block D 全滅 → 記錄為「腕載水平構型不可行」,任務場景必須改構型(Stage 2 選項收斂到俯視/墊高/合作目標)。
- **全部 52 格全滅 → 提前止損點 #1**:論文降級為「WPM 特性化+負結果」,停止 Stage 2。

依首輪結果可加密格點(例:可見/不可見邊界附近加距離水準)。

### S2:datasheet(只做可偵測格)

1. **距離編碼**:選代表格(通常 Block A 最佳格),20 個距離點(等距覆蓋該格可偵測範圍)× 3 重複,單 session。回歸 peak_idx vs 距離:報 r、RMSE、斜率(自校樣本週期 = 2/(斜率×343))。**判準:r ≥ 0.95**。
2. **側向編碼**:目標在 ±0.15 m 橫移 13 點,雙 RX 能量差(rx0−rx1)/(rx0+rx1) vs 偏移量。**判準:Spearman 單調 |ρ| ≥ 0.9**。
3. **重複性**:最佳格同條件 10 次,peak_idx 眾數穩定、early_energy CV < 5%。

### S3:遮蔽歸因(只在 Block C/D 有失格時做)

單因子拆解序列(每步一對 cells):桌向下平移 0.1 m / 手臂撤走只留桌 / 感測器前移 0.1 m(離開假想夾爪陰影)/ 目標墊高 0.15 m。輸出:每個操作恢復多少 SNR → 歸因表。這章是論文「邊界」章的數據。

## 7. Stage 2 — 閉環任務(設計進包絡)

**場景決策點(需用戶/指導教授拍板,提供 S1 數據佐證)**:
(a) 俯視構型:接近末段感測器俯視目標,垂直/斜向伺服;
(b) 墊高目標(pedestal):目標離開桌面平面,水平接近;
(c) 合作目標:更大反射體(超聲信標類比)。

### D1:1-DOF 閉環接近(主實驗)

- 新腳本(勿繼承舊 controller 檔;可抄 IK/運動的工具函式):簡單比例步進控制器——估距 > standoff 就前進一步(步長 0.02–0.04 m),估距 ≤ standoff 停止;max_steps 護欄。估距 = peak_idx × 自校樣本週期 × 343/2(S2 的公式)。
- 目標位置均勻隨機於包絡內(範圍由 S1 定),n=30/臂。
- **三臂**:closed(聲學)/ blind(估距置換 +inf,同管線)/ open(固定行程 = 訓練前隨機抽一次的名義距離)。
- **預註冊主判準**:r(停止位置, 目標位置) ≥ 0.9,且 closed 的停止誤差 RMSE 顯著低於 blind(Welch t,α=0.05)。
- blind ≈ closed → **止損點 #2**:回 S3 檢討,不硬跑 D2/D3。
- 每 episode 記錄:目標真實位置(僅評估)、每步估距、停止位置、原始波形。

### D2:2-DOF(前向+側向)——僅當 S2 側向判準通過

同三臂;加側向停止誤差與 r(停止 y, 目標 y)。

### D3:端到端夾取

D1(或 D2)通過後接 Robotiq 2F-85。夾爪控制抄 `scripts/ur10e_robotiq_common.py` 的 `RobotiqGripperRuntime`(close/hold_closed/open,finger_joint 位置控制;此為工具程式,可信)。
- **報告格式(預註冊)**:P(對位成功) 與 P(夾取|對位成功) 分開報,不給混合單一成功率。
- 對位成功定義:停止時 tool0 在目標 footprint ± 夾爪開口半寬內(幾何量測,非 reason 標籤)。

## 8. Stage 3 — 狀態估計

### P1:自體狀態(acoustic proprioception)

用 D1/D2 過程數據(或專門採集):聲學特徵 → 感測器位姿回歸(Ridge/GBM 皆可,報 R²、5-fold)。宣稱上限:「聲學特徵編碼機器人自體構型」。

### P2:目標狀態(僅包絡內場景)

- 資料集混入 **25% 無目標 trials**(物理移除)。
- **第一關(預註冊)**:目標存在二元偵測 AUC;< 0.7 → 停止,不做任何後續目標狀態宣稱。
- 通過後:near/far、stop-region 分類;特徵消融 = 聲學-only / 位姿-only / 全部;聲學-only 特徵集**不得**含任何由校正表推出的距離欄位。

## 9. 輸出與命名慣例

- 全部進 `runtime/outputs/v2_*/`(v2_s1_envelope、v2_s2_datasheet、v2_d1_approach…),與舊輸出隔離。
- 每個輸出目錄:`run_meta.json`(參數、日期、腳本路徑)、`run.log`、數據 csv/json、`waveforms/`。
- 新 runner shell 放 `runtime/`,前綴 `run_v2_`。
- 分析報告寫 `docs/plan_v2/reports/`。

## 10. Repo 現狀(2026-07-08,接手前必讀)

- **大量未 commit**:12 個 modified(含 `scripts/ultrasonic_grasp_common.py` 的 GRASP_BLIND_APPROACH spike 旗標、測試修復)+ 大量 untracked(docs/、runtime/run_*.sh、新分析腳本)。**commit 決策屬於用戶**,接手 AI 不要擅自 commit/branch。
- 舊實驗腳本(`official_asset_ur10_*`、`ultrasonic_*`)**不要修改**——V2 一律寫新檔。可以 import 其中的工具函式(GMO 解析:`rtx_acoustic_factory.py` 的 parse 系列可信;IK/夾爪:`ur10e_robotiq_common.py`)。
- 測試:`python3 scripts/test_*.py` 四檔目前 17/17 綠;動到共用模組後要重跑。
- 交接歷史:`docs/handoff/`(decisions D1–D10、三份裁定報告、risks、notes)——**只在需要理解「為什麼歸零」時讀**,V2 執行不依賴它。

## 11. 死路清單(不要浪費額度重試)

1. 用 `timeOffsetNs` 做距離 —— 全為 0。
2. NonVisualMaterial 材質條件 A/B/C/D 影響 acoustic —— 無效。
3. closeDirectAmpl/closeIndirectAmpl 調參 —— 無效(byte-identical)。
4. SurfaceGripper —— 註冊/吸附整條鏈有坑,Robotiq finger-joint 路徑可用,直接用後者。
5. 腕載水平構型下對桌面小目標做能量/差分/matched-filter 特徵工程 —— 目標貢獻為浮點雜訊級(此結論會被 S1 Block D 重新驗證;若 S1 推翻它,以 S1 為準)。
6. 舊 sweep 的 reason 標籤當成功指標 —— 同字串多語意,只看幾何量。

## 12. 建議執行順序(含額度中斷點)

每步結束都是乾淨中斷點,產物落盤即可交接:

1. 寫 `paired_capture_runner.py` + 驗收(5.1 末的兩個驗收 case)。 【~1 session】
2. S1 Block A(15 cells)→ analyze → 熱圖。 【~1 session】
3. S1 Block B/C/D → 包絡裁定 → 寫 `docs/plan_v2/reports/S1_envelope_report.md`。 【~1-2 sessions】
4. S2 三項 → datasheet 報告。 【~1 session】
5. (需用戶拍板場景選項)D1 三臂 → 裁定報告。 【~1-2 sessions】
6. D2/D3、P1/P2、論文素材整理。 【視結果】

每完成一步,把狀態追加到本資料夾的 `PROGRESS.md`(不存在就建立:日期、完成項、數據路徑、下一步)。
