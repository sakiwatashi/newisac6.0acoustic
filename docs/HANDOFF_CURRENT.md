# 專案交接文件(現況版,2026-07-12 晚間更新)— 給任何接手的 AI/人

> 讀我就夠開工。歷史細節按需往下挖,不必預讀。
> 舊版交接(`docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md`)是 7/8 開工前的計畫書,僅供考古。

## 一句話:這專案是什麼、現在在哪

逢甲電聲碩士論文(指導教授蔡鈺鼎):在 Isaac Sim 6.0 RTX Acoustic 模擬中,驗證「純超聲回授引導 UR10e 機械手臂接近、二維定位並夾取隨機目標」。
**現況:八個實驗全部完成、判準全綠;論文(6 章 29 節)與實驗完全同步且經嚴格自審修正;口試 Q&A 備妥;GUI 展示可跑;一鍵驗證可過。實驗側是完成式,現階段主軸=口試準備與教授對齊。**

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
