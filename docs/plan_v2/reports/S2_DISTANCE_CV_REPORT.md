# S2 距離編碼：未見距離交叉驗證（P2）

**日期**: 2026-07-22  
**性質**: 零 GPU；既有 `v2_s2_datasheet`  
**產物**: `runtime/outputs/thesis_32_51_audit/audit_metrics.json`、`s2_loo_errors_kept.csv`  
**結論**: 1.21 cm / 1.10 cm 為**校正內殘差**；leave-one-**distance**-out CV RMSE 同量級（約 1.2–1.3 cm），可稱為**距離插值驗證**（非實機、非跨場景）。

---

## 方法

- 單位：獨特 `true_distance_3d_m`（**禁止**以 p1/p2/p3 當 fold——三遍 peak 逐位相同）。  
- LOO：hold-out 一個距離之全部紀錄，其餘距離擬合 \(k=ad+b\)，預測 hold-out 之 \(\hat d=(k-b)/a\)。  
- 另報：奇偶 `point_index` train/test；kept-48 與 all-60。

---

## 結果

| 分析 | n 預測 | MAE | RMSE | max\|err\| | bias |
|------|-------:|----:|-----:|----------:|-----:|
| **LOO 距離（kept 48）** | 48 | **0.82 cm** | **1.33 cm** | 4.59 cm | +0.04 cm |
| LOO 距離（all 60） | 60 | 0.73 cm | 1.19 cm | 4.60 cm | +0.03 cm |
| 奇偶 idx（kept） | 24 test | 0.47 cm | 0.57 cm | 0.99 cm | +0.27 cm |
| 奇偶 idx（all） | 30 test | 0.49 cm | 0.58 cm | 0.96 cm | +0.30 cm |

**校正內（同資料擬合）對照**

| 集合 | Pearson r | 殘差 RMSE |
|------|----------:|----------:|
| kept 48 | 0.99941 | **1.21 cm** |
| all 60 | 0.99940 | **1.10 cm** |

LOO 最大絕對誤差 ≈ **4.6 cm** 出現在 **d≈0.592 m**（與 primary-way 切換點一致），其餘距離平均絕對誤差多在 1 cm 內。

---

## 論文用詞

| 可寫 | 不可寫 |
|------|--------|
| 校正資料內殘差 RMSE 1.21 cm（kept） | 「測距精度 1.21 cm」不附條件 |
| leave-one-distance-out 插值 RMSE ≈ 1.3 cm | 實機／未見場景精度 |
| 高 r 不依賴排除 12 點（all-60 仍 r≈0.9994） | 排除製造了線性 |

---

## 重現

見 `runtime/outputs/thesis_32_51_audit/audit_metrics.json` 之 `p2` 欄（由本輪審計腳本生成；後續可固化為 `scripts/s2_distance_cv.py`）。
