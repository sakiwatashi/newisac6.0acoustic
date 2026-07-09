# 專案健檢報告 — 2026-07-09

**範圍**:7/7–7/9 產出的完整審查(V2 實驗鏈 S1→S2→D1→D1.5、論文 v2、交接文件),以及新舊資產的重複/衝突盤點。
**方法**:唯讀審計;所有裁定數字由原始落盤數據(cells.csv / points.csv / episodes.csv / .npy)重新計算,不信任報告文字。每條發現附驗證指令。
**對照基準**:`docs/WPM_EXPERIMENT_RULES.md`、`docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md` §4 五條鐵律、各 runner header 的預註冊判準。
**與前次健檢的關係**:`docs/HEALTH_CHECK_2026-07-08.md` 審的是舊管線(v4/v9),其 F1–F12 已導致歸零重做;本次審的是重做後的 V2 產物。

---

## 總覽

| 類別 | 數量 | 摘要 |
|------|------|------|
| ✅ 核心驗證通過 | 8 | V2 全鏈裁定數字 100% 可從原始數據重現(見下表) |
| 🟡 中(衝突/風險) | 4 | M1 頂層文件仍掛已推翻的 84% 敘事、M2 session summary 無警示、M3 斜率漂移未歸因、M4 全部成果未 commit |
| 🟢 低(清理候選) | 3 | L1 舊管線遺留檔、L2 死路 shell 佔多數、L3 summary 欄位缺漏 |

---

## ✅ 核心驗證:V2 裁定鏈全數重現(本報告最重要結論)

7/8–7/9 的四個實驗階段,**每一個預註冊裁定都能由本次健檢從原始數據獨立重算,且與 PROGRESS.md / 各報告宣稱一致**:

| 階段 | 宣稱(PROGRESS.md / 報告) | 本次重算 | 判定 |
|------|--------------------------|----------|------|
| S1 包絡 | 36/52 可偵測;兩止損點未觸發 | cells.csv 52 列、snr_peak>10 者 36 格、stationarity_false=0;`block_D_all_fail=False`、`all_cells_fail=False` | ✅ |
| S2 距離編碼 | r=0.9994、RMSE 1.2 cm、T≈103 µs | combined_p1_p3:r=0.9994、RMSE 0.0121 m、T_cal=103.088 µs;tableh r=0.9998、RMSE 5.3 mm | ✅ |
| S2 側向(負結果) | Spearman ρ=0.36 → False,D2 剪除 | ρ=0.3571 → `lateral_monotonic_ge_0.9: False` | ✅ |
| S2 重複性 | 10/10 逐位相同 | n_valid=10、peak_idx_range=0、CV=0.0000 → True | ✅ |
| D1 三臂 | closed r=0.9970、RMSE 2.5 cm、30/30 聲學停止;blind RMSE 79 cm;三裁定全過 | r=0.9970、RMSE 0.0246、reasons 30×`standoff_est`;blind 0.7927;Welch t=−25.13;D0 r=0.9958 → 三裁定 True | ✅ |
| D1.5 手臂載具 | closed r=0.9856、RMSE 2.8 cm;90 eps 姿態零違規;四裁定全過 | r=0.9856、RMSE 0.0282、30×`standoff_est`;posture=sensor_pose=ik_failed=0、invalid=0;t=−10.58;D0.5 r=0.9918 → 四裁定 True | ✅ |
| 論文 v2 | 禁詞歸零、引用 24/24 | docx XML 直接掃描:9 個禁詞(舊管線/前導實驗/審計/v9/v4/scaffold/claim_mode/84%/V2)全 0;引用 [1]–[24] 覆蓋 24/24 | ✅ |
| 單元測試 | 17/17 綠 | 4 檔 unittest 3+4+4+6=17 全 OK(舊健檢 F4 已修復) | ✅ |

重現指令(任何人可跑):

```bash
python3 scripts/analyze_envelope.py     --scan-dir runtime/outputs/v2_s1_envelope
python3 scripts/analyze_s2_datasheet.py --scan-dir runtime/outputs/v2_s2_datasheet
python3 scripts/analyze_d1_approach.py  --scan-dir runtime/outputs/v2_d1_approach
python3 scripts/analyze_d15_arm_approach.py --scan-dir runtime/outputs/v2_d15_arm_approach
for t in scripts/test_*.py; do python3 "$t"; done
```

### 規則合規抽查(V2 四支 runner)

- **五條鐵律 header**(交接文件 §4):四支 runner 逐條寫明如何滿足/為何不適用 ✅。
- **鐵律 5(acoustic_only)**:grep 全部 oracle 引用,`oracle_horiz_dist`/`target_x` 只出現在記錄欄與離線評估;closed 臂 30/30 停止 reason 均為 `standoff_est`(聲學觸發),無 oracle 出口 ✅。
- **鐵律 4(原始波形落地)**:D1 closed 267 個 .npy、D1.5 全臂 404 個 .npy;S1 每 cell 三條波形、S2 每點三條 ✅。
- **規則 4-1(argparse 先於 SimulationApp)**:paired_capture@96/120、s2@150/157、d1@179/309、d15@245/405 全過 ✅。
- **輸出慣例**(§9):S1 每 cell `cell_result.json`+`waveforms/`;S2/D1/D1.5 每 pass/arm `meta.json`+`points.csv`+`waveforms/` ✅(命名為 meta.json 而非 run_meta.json,語意等價)。
- **鐵律 2(資訊消融)**:blind 臂跑相同量測管線但估距強制 +inf、open 臂零量測——三臂設計完整,且 blind 的徹底失能(r≈0、RMSE 0.79 m)反向證明 closed 的追蹤確實來自聲學 ✅。

---

## 🟡 中嚴重度(衝突與風險)

### M1:repo 頂層文件仍以「84% vs 29%」為主敘事——與 7/8 裁定直接衝突

- `README.md:143`「閉環接近 ≤0.45 m:**84.0%** vs open-loop 29.2%(v9)」、`REPRODUCIBILITY_AUDIT.md:14`「✅ 84% vs 29%」仍是門面數字。
- 但 `docs/handoff/E3_target_invisibility_and_v9_audit.md` 已裁定:v9 全部 closed_loop trials `claim_mode='scaffold'`,84% 是 oracle 上限爬行 vs oracle IK 的運動策略差,**不是聲學證據**;此裁定已被用戶採納(論文 v2 已徹底移除該敘事)。
- 現狀 = 任何人打開 repo 首頁讀到的第一個關鍵數字是已推翻的宣稱,而正確的主結果(D1/D1.5)只存在於 `docs/plan_v2/reports/`。E3 的 N3 待辦(與教授對齊後批次更新)迄今未執行——這是目前**全 repo 最大的敘事衝突點**。
- 驗證:`grep -n "84" README.md REPRODUCIBILITY_AUDIT.md`;`python3 -c "import json; print(json.load(open('runtime/outputs/physical_ai_v9_skip_lift_clean/closed_loop_trial_1/episodes_summary.json'))['claim_mode'])"` → `scaffold`。
- 建議:教授拍板後同步(已在 PROGRESS 待辦內);過渡期至少在兩檔頂部加一行「⚠️ 本文件數字已被 2026-07-08 裁定推翻,現行主結果見 docs/plan_v2/reports/」。

### M2:`runtime/SESSION_SUMMARY_2026-07-08.md` 開頭仍把 v4 30/30=100% 當「成果」引述,無任何警示

- 該檔寫於 F1 裁定之前(同日稍早),開篇「接續 approach_sweep_v4(接近成功率 30/30 = 100%)的成果」。
- v4 的 100% 已被同日的 F1 + 盲走對照裁定為幾何假象。檔案本身是史料可留,但無 banner 的話,未來任何人(含接手 AI)按日期讀 summary 會再度吸收錯誤前提——這正是本專案吃過虧的模式。
- 建議:檔案頂部加一行指向 `docs/HEALTH_CHECK_2026-07-08.md` F1 與 E3 報告。

### M3:校正斜率系列漂移(52.4 / 57.9 / 64.3 smp/m)未歸因 + 探針保留率低

- D0 探針 6/13 點、D0.5 探針 7/13 點通過 drift 稽核(其餘落在已知慢震盪帶);三個獨立量測的斜率相差 ~±10%。
- 兩份報告都**如實記載並列為開放問題**(D1_approach_report.md:35、D15_arm_approach_report.md:36),且以「實測停止誤差 2–2.8 cm」論證影響有限——處理誠實,不是隱瞞。
- 但這是主宣稱校正鏈上唯一未閉合的環節,口試被問「你的校正到底準不準」時,目前的答辯只有間接證據。建議列入 D3 前的補強候選(單一 session 內 probe+tableh 同幾何對測即可歸因)。

### M4:V2 全部成果(77 個檔案變更)零 commit——單點災難風險

- V2 四階段數據、四份報告、四支 runner、論文 v2、交接文件全部 untracked/modified;git log 在 7/6 之後無任何 commit。
- 依交接規則 commit 決策屬於用戶,本次未動;但客觀事實是:一次磁碟故障/誤刪會同時失去論文主結果與其全部證據鏈。`runtime/outputs/v2_*` 共約 11 MB,連同 docs/scripts 可一次 commit。
- 建議:盡快由用戶執行一次 commit(或至少 tar 備份到另一磁碟)。

---

## 🟢 低嚴重度(清理候選,本次未動手)

### L1:舊管線遺留檔維持原狀(舊健檢 F2/F5/F7/F10/F11/F12 的後續)

V2 歸零後,舊健檢的程式類發現(F2 死門檻、F5 校正雙源、F7 early_energy 雙定義、F10 四支重疊校正腳本、F11 vector_utils 孤兒、F12 硬編碼路徑)全數**因舊管線退役而失效(moot)**,檔案本身仍在且未再被 V2 引用(V2 只 import 過 `ur10e_robotiq_common` 的 IK/夾爪與 `rtx_acoustic_factory` 的 parse 系列——兩者是白名單工具)。不建議現在動:等論文敘事定稿後一次歸檔(`scripts/legacy/`)即可,現在動反而增加 diff 噪音。

### L2:`runtime/` 26 支 shell 中 22 支屬舊管線,其中多支對應死路清單

`run_v2_*` 僅 4 支;其餘(matched_filter / differential / direct_echo / peak_idx / open_space calibration 等)多屬交接文件 §11 死路清單的產物。同 L1,建議與舊腳本同批歸檔,shell 檔名前綴已能區分,不緊急。

### L3:`envelope_summary.json` 未落 `n_detectable` 欄位

分析器 stdout 有印可偵測清單,但 summary JSON 只有 `n_cells_total`/`n_missing`;36/52 這個論文數字要從 cells.csv 重算才能拿到。一行級補強,重跑 analyzer 即再生。

---

## 交接/對話紀錄鏈完整性(7/7–7/9)

按時間序核對,無斷點:

1. 7/7–7/8 凌晨:E2(Robotiq 夾取)、F1(v4 裁定)→ `docs/handoff/`
2. 7/8 15:25:E3(目標不可見+v9 scaffold)+ decisions/risks/notes → 全鏈崩塌裁定
3. 7/8 16:00:`docs/HEALTH_CHECK_2026-07-08.md` + V2 交接文件(歸零重設計)
4. 7/8 16:50–7/9 01:50:S1 → S2 → D1 → D1.5,每步追加 PROGRESS.md,數據/報告齊備
5. 7/9:敘事對齊文件 → 教授回饋四項修正 → 論文 v2 擴寫+引用補齊(PROGRESS.md 共 10 節,與檔案時間戳一致)

---

## 驗收對照

| 驗收條件 | 狀態 |
|----------|------|
| 1. 滿足原先規則要求 | V2 四 runner 逐條核對五鐵律+WPM 規則 4-1、輸出慣例 §9、預註冊判準先於執行:全過。舊規則文本 F7 矛盾對 V2 無效(V2 統一 20 樣本定義) |
| 2. 輸出可驗證報告 | 本檔;每條發現附驗證指令,核心表格全部數字由原始數據重算 |
| 邊界:不動 main/正式設定、不順手重構、不加功能 | 全程唯讀審計。唯一副作用:重跑四支離線分析器時,其確定性輸出(summary JSON/熱圖 PNG)在 `runtime/outputs/v2_*` 原地再生,數值與原版相同;原始量測數據(csv/npy)未觸碰 |

## 建議處理順序(供決策)

1. **M4 commit/備份**(用戶一個指令,消除最大單點風險)。
2. M1/M2 加警示 banner(兩行改動;完整同步等教授拍板)。
3. M3 斜率歸因小實驗(D3 之前做,口試防線)。
4. L1/L2 舊檔歸檔 + L3 補欄位(論文定稿後一批處理)。
