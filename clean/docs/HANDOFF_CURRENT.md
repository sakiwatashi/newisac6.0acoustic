# 專案交接文件(現況版,2026-07-12)— 給任何接手的 AI/人

> 讀我就夠開工。歷史細節按需往下挖,不必預讀。
> 舊版交接(`docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md`)是 7/8 開工前的計畫書,僅供考古。

## 一句話:這專案是什麼、現在在哪

逢甲電聲碩士論文(指導教授蔡鈺鼎):在 Isaac Sim 6.0 RTX Acoustic 模擬中,驗證「純超聲回授引導 UR10e 機械手臂接近、二維定位並夾取隨機目標」。
**現況:八個實驗全部完成、判準全綠;論文(6 章 29 節)與實驗完全同步;GUI 展示可跑;一鍵驗證可過。實驗側是完成式。**

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

1. **教授對齊**(最優先的人類行動):P1/P2 入不入正文、D3 複驗敘事、demo 演示。ML 先導結果已備好。
2. README/REPRODUCIBILITY_AUDIT(主 repo 頂層)仍掛舊敘事,至少加警示 banner(健檢 M1/M2)。
3. 口試後:GitHub 補論文、LICENSE 選擇(用戶決定)。
4. 可選延伸(設計已就緒或已記載):二維夾取(需壓側向誤差)、滑動窗口動態追蹤、佔據柵格地圖、實機 CH201。
