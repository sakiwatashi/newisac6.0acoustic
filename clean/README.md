# 超聲感測回授之機械手臂閉環接近與夾取 — Isaac Sim 6.0 RTX Acoustic 實驗全集

碩士論文實驗之**可驗證快照**:全部實驗程式、原始量測數據、設計與裁定文件。
每一項研究宣稱皆有:預先寫定之判準(先於執行)、資訊消融對照組(盲走臂)、原始波形落盤(離線可重算)。

> 註:本目錄同時作為原始工作目錄(`isaacsim6.0/clean/`)內之精選快照與 GitHub 公開倉庫之根目錄;
> 論文全文(`thesis/`)於口試前不隨公開倉庫發佈。
> **正典狀態一頁看懂**: [`STATUS.md`](STATUS.md) · 資料目錄角色: [`runtime/outputs/MANIFEST.md`](runtime/outputs/MANIFEST.md)

## Current canonical result

```text
S1 36/52 detectable
S2 ranging r=0.9994 (lateral pre-registered falsification)
D1.5 stop r=0.9856, RMSE=2.8 cm   ← main closed-loop result
D2  lateral r=0.950; 2-D stop RMSE=1.9 cm
D3-r3  alignment 80% vs blind 33%; 90 eps posture/IK clean  ← grasp primary
D3-r1  historical failure (3/90 lift IK) retained under v2_d3_grasp/
```

## 快速驗證(30 秒,零 GPU)

```bash
git clone https://github.com/sakiwatashi/isaacsimacousticfinal.git
cd isaacsimacousticfinal
python3 -m pip install -r requirements-analysis.txt   # numpy
bash runtime/verify_all.sh    # 從原始數據當場重算全部裁定;全過 exit 0,否則 exit 1
```

重跑 GPU 實驗需 Isaac Sim 6.0 本體(標準安裝後以 `./app/python.sh <script>` 執行;本倉庫不含 `app/`)。

## 實驗鏈與結果總覽

```
S1 感測包絡 → S2 距離特性 → D1 閉環(飛行) → D1.5 閉環(手臂) → D2 二維定位 → D3 夾取
```

| 階段 | Runner | Analyzer | 數據目錄 | 主結果 | 判準 |
|------|--------|----------|----------|--------|------|
| S1 包絡 | `paired_capture_runner.py` | `analyze_envelope.py` | `v2_s1_envelope/` | 52 格 36 可偵測;指向主宰 | ✅ 止損未觸發 |
| S2 特性表 | `s2_datasheet_runner.py` | `analyze_s2_datasheet.py` | `v2_s2_datasheet/` | 測距 r=0.9994;側向誠實證偽 | ✅(側向 False=預定證偽)|
| D1 閉環 | `d1_approach_runner.py` | `analyze_d1_approach.py` | `v2_d1_approach/` | r=0.9970,RMSE 2.5 cm | ✅ 3/3 |
| D1.5 手臂載具 | `d15_arm_approach_runner.py` | `analyze_d15_arm_approach.py` | `v2_d15_arm_approach/` | r=0.9856,RMSE 2.8 cm,90 回合零違規 | ✅ 4/4 |
| D2 二維定位 | `d2v2_formal_runner.py` | `analyze_d2v2.py` | `v2_d2v2_formal/` | 側向 r=0.950;2D 停止 RMSE 1.9 cm;盲走 15.0 cm | ✅ 4/4 |
| D3 夾取(首輪) | `d3_grasp_runner.py` | `analyze_d3_grasp.py` | `v2_d3_grasp/` | 對位 r=0.9885、60% vs 23%(p=0.004) | ⚠️ 3/4(3/90 遠端升舉 IK,如實記錄)|
| D3 複驗 r2/r3 | 同上(走廊 1.18→1.15) | 同上 | `v2_d3_grasp_r2/`、`_r3/` | r3:r=0.9781、80% vs 33%(p=2.9e-4)、零違規 | ✅ **4/4** |
| 側向四重證偽 | `rxgroup_probe.py` 等 | verify_all 內建重算 | `rxgroup_probe_v1/` 等 | 能量/時間/身分/分組全證偽 → 多點定位為唯一路徑 | ✅ 負結果 |

統計:主檢定為預先寫定之 Welch/Fisher;另附成對佐證(成對置換檢定、McNemar exact,結論一致)。

閘門與方法學文件:`docs/plan_v2/`(設計、預註冊判準、決策記錄 D-1~D-13、風險、逐日進度)、
`docs/plan_v2/reports/`(六份裁定報告,含 D3 失效—歸因—修正—驗證全紀錄)。

## 校正常數版本(重要)

- `docs/WPM_EXPERIMENT_RULES.md` 文中之 132.5 µs 為**舊管線歷史值,已不適用**(文件頂部有沿革註記)。
- 正式實驗一律以**當輪自校**之斜率/截距換算距離,校正檔含來源與擬合統計
  (例:`runtime/outputs/v2_d3_gates/bar_calibration.json`)。

## 目錄結構

```
scripts/    實驗 runner、離線分析器(裁定唯一出口)、診斷探針、GUI 展示
runtime/    執行 shell、verify_all.sh、outputs/(全部原始數據:csv/波形 npy/裁定 json)
docs/       實驗規則、設計文件、決策記錄、六份裁定報告、健檢報告
thesis/     (公開倉庫未含)論文與產生器
```

## GUI 即時展示(需 Isaac Sim 6.0 + 顯示器)

```bash
./app/python.sh scripts/demo_gui_showcase.py    # 掃描→定位→聲學停止→夾取升舉,終端中文旁白
```

## 環境

Isaac Sim **6.0.0-rc.59**(host standalone)/ Python 3.12 / 分析器僅需 python3 + numpy + matplotlib(選配)。
模擬保真度邊界(頻率物理不建模、夾持摩擦限制等)詳見 `docs/plan_v2/reports/` 與論文第六章。
