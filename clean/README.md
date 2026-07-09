# clean/ — 現行版本(V2)完整快照

**建立日期**:2026-07-09
**性質**:複製快照(原始位置檔案一個都沒動、沒刪、沒搬)。這裡是「目前我們要的版本」的單一集中處:V2 實驗鏈的代碼、原始數據、報告、規則文件、與論文 v2。
**篩選依據**:`docs/HEALTH_CHECK_2026-07-09.md` 驗證通過的現行資產;舊管線(v4/v9、死路 calibration 系列)一律不收。

## 功能驗證(建立當日已在本資料夾內實測)

- 四支分析器在本資料夾內對本資料夾數據重跑,12 條預註冊裁定輸出與正式版完全一致。
- `thesis/rebuild_thesis_v2.py` 在本資料夾內重建,產出 docx 正文與正式版逐字一致(TOC 34/34、PDF 再生成功)。

```bash
cd clean
python3 scripts/analyze_envelope.py         --scan-dir runtime/outputs/v2_s1_envelope
python3 scripts/analyze_s2_datasheet.py     --scan-dir runtime/outputs/v2_s2_datasheet
python3 scripts/analyze_d1_approach.py      --scan-dir runtime/outputs/v2_d1_approach
python3 scripts/analyze_d15_arm_approach.py --scan-dir runtime/outputs/v2_d15_arm_approach
cd thesis && python3 rebuild_thesis_v2.py    # 需 python-docx;PDF 需 libreoffice
```

## 結構與角色

```
clean/
├── scripts/                          # V2 代碼(13 支,依賴自足)
│   ├── paired_capture_runner.py      # S1 配對擷取引擎(GPU,需 Isaac Sim)
│   ├── s2_datasheet_runner.py        # S2 距離/側向/重複性 runner(GPU)
│   ├── d1_approach_runner.py         # D1 三臂閉環 runner(GPU)
│   ├── d15_arm_approach_runner.py    # D1.5 手臂載具版 runner(GPU)
│   ├── analyze_{envelope,s2_datasheet,d1_approach,d15_arm_approach}.py
│   │                                 # 離線分析器(純 python3,裁定的唯一出口)
│   ├── visibility_wpm_probe.py       # 已驗證的範本腳本(V2 骨架來源)
│   └── geometry_passport_v1.py / rtx_acoustic_factory.py /
│       ur10e_robotiq_common.py / ur10e_robotiq_passport_v1.py
│                                     # runner 的 import 依賴(白名單工具模組)
├── runtime/
│   ├── run_v2_*.sh                   # 四支批次 shell(注意:內含指向原 repo 的絕對路徑)
│   └── outputs/                      # 原始數據(csv/json/npy/png,離線可重算一切)
│       ├── v2_acceptance/            # Stage 0 驗收 case
│       ├── v2_s1_envelope/           # S1:52 cells,36 可偵測
│       ├── v2_s2_datasheet/          # S2:r=0.9994、T≈103µs、側向證偽
│       ├── v2_d1_approach/           # D1:closed r=0.9970 vs blind 失能
│       ├── v2_d15_arm_approach/      # D1.5:closed r=0.9856、姿態零違規
│       └── visibility_wpm_probe_v1/  # 目標移除機制驗證(規則 6 證據)
├── docs/
│   ├── plan_v2/                      # V2 交接文件、PROGRESS、四份報告、cell 定義、驗收
│   ├── handoff/                      # 7/8 三層裁定證據鏈(E2/E3/F1/decisions/risks/notes)
│   ├── WPM_EXPERIMENT_RULES.md       # 模擬器規則權威文本
│   ├── EXPERIMENT_PLAN_V2.md         # V2 一頁摘要
│   └── HEALTH_CHECK_2026-07-08.md / HEALTH_CHECK_2026-07-09.md
└── thesis/
    ├── THESIS_DRAFT_FCU_v2.docx / .pdf   # 現行論文草稿(40 頁)
    ├── rebuild_thesis_v2.py              # v2 產生器(唯一改動入口)
    ├── build_chapter2_docx.py            # CH2 內容模組(rebuild 的 import 依賴)
    ├── THESIS_DRAFT_FCU_v1.docx          # rebuild 的輸入模板(只讀,勿刪)
    └── 論文敘事對齊_V2_2026-07-09.md      # 給指導教授的敘事對齊文件
```

## 邊界說明

1. **GPU 實驗不能直接在本資料夾跑**:runner 需要 Isaac Sim(原 repo 的 `app/python.sh`,~數十 GB,不複製);四支 shell 內的絕對路徑仍指向 `/home/lab109/song/isaacsim6.0/` 原位。要重跑模擬,回原 repo 執行即可——本快照的離線部分(分析、裁定、論文)完全自足。
2. **本資料夾是快照不是工作區**:日常開發仍在原位置進行;若原位置有更新,重新同步對應檔案即可。
3. 原 repo 的一切未受影響(健檢報告的邊界條款同樣適用於本次整理)。
