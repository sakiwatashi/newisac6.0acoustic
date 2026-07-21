# 3.2～5.1 審查關閉聲明

**日期**: 2026-07-22  
**狀態**: **審查關閉**（主結論成立；部分物理原因採保守邊界）  
**不阻塞**: 進入 **5.2** 及後續章節審查  
**等待（非阻塞）**: 正式 Word 合併、圖檔同步  

---

## 封口三項（零 GPU，已完成）

| # | 要求 | 處置 |
|---|------|------|
| 1 | P1 勿寫「已證明=小樣本噪音」 | 改為「未充分支持 mover effect；**唯一物理原因未完全歸因**；各配置獨立校正」 |
| 2 | P2 CI 寫明；「插值」改 LOO 用詞 | MAE/RMSE/bias **95% CI 已寫入**；稱「**距離網格 LOO 驗證**」 |
| 3 | P3 perm metadata | `n_perm=50000`，`seed=0`，Monte Carlo sign-flip，**\(p\le 2\times 10^{-5}\)** |

---

## 不阻塞的後續實驗（全文審完再批次規劃）

- P1 同 session A/B/C  
- P5 聲影單因子  
- 多 seed 穩健性（D1 → D1.5 → …）  

---

## 正典檔案

- 敘事：`thesis/THESIS_CH1_TO_5_1_GPT_INTEGRATED.md`  
- P2：`S2_DISTANCE_CV_REPORT.md`  
- P3：`D1_D15_PAIRED_SENSITIVITY.md`  
- P4：`FREQUENCY_INVARIANCE_REPORT.md`  
- P1：`M3_slope_attribution_report.md`（措辭已軟化）  
