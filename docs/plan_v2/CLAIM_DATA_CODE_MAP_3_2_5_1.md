# 主張—資料—程式對照表（3.2–5.1）

**日期**: 2026-07-22  
**敘事底稿**: `thesis/THESIS_CH1_TO_5_1_GPT_INTEGRATED.md`

| 主張（摘要） | 資料 | 程式／文件 | 狀態 |
|--------------|------|------------|------|
| \(\hat d=(k-b)/a\) | S2 points / D1 calib load | `s2_*`、`d1_*`、`d15_*` | 正典 |
| \(k=\arg\max s\) signed | S1/S2 npy | `_peak_idx` = `np.argmax` | P0 關閉 |
| primary 動態 | S2 57/60 way0 | `_measure_block` | P0 關閉 |
| S1 40+6 幀 | cell_result | `n_settle`/`n_measure=6` | 對 |
| S2 QC 12/60 能量 | points.csv | drift>0.05 | 對 |
| S2 校正殘差 1.21 cm | kept 48 OLS | analyze_s2 | 對；**非**獨立精度 |
| S2 LOO-CV ~1.3 cm | 本輪 audit | `S2_DISTANCE_CV_REPORT` | **新增** |
| all-60 r/RMSE | audit / P0 AB | — | 對 |
| primary 0.592 m 切 | P0_FOLLOWUP_AB | — | 對 |
| 側向 ρ=0.357 | S2 lateral | analyze_s2 | 對 |
| 頻率 peak 不變 | armfree_freq_sweep | 診斷級 | 保守寫 |
| 聲影唯一因果 | — | 無單因子 | **禁止**；降級 |
| D1 起點 x=0 | steps.csv | SENSOR_POS | 對 |
| D1 r=0.997, MAE 2.1 | episodes | analyze_d1 | 對 |
| D1 blind 停 1.15 | episodes | — | 對；r 未定義 |
| D1 Welch | analyze | 事前主判準 | 對 |
| D1 配對置換 | 本輪 | `D1_D15_PAIRED_*` | **新增佐證** |
| D0 6/13, r=0.9958 | probe | d1 runner | 對 |
| 斜率 52/58/64 | M3 報告 | 小樣本 CI | 歸因=噪音 |
| D2 圓 | formal | d2v2 + CIRCLE_VS_ELLIPSE | 正典 |
| D3 對位非摩擦 | d3 r3 | 報告 | 邊界 |
