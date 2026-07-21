# S2 距離編碼：未見距離交叉驗證（P2）

**日期**: 2026-07-22（封口修訂：CI 數字 + 用詞）  
**性質**: 零 GPU；既有 `v2_s2_datasheet`  
**產物**: `runtime/outputs/thesis_32_51_audit/audit_metrics.json`、`s2_loo_errors_kept.csv`

---

## 結論（封口）

| 量 | kept-48 | all-60 |
|----|--------:|-------:|
| 校正內殘差 RMSE | **1.21 cm** | **1.10 cm** |
| **LOO-distance** RMSE（point） | **1.33 cm** | **1.19 cm** |
| LOO MAE（point） | 0.82 cm | 0.73 cm |
| LOO max \|err\| | 4.59 cm | 4.60 cm |
| LOO bias（point） | +0.04 cm | +0.03 cm |

**Bootstrap 95% CI**（對 LOO **逐點誤差**重抽樣；`n_boot=10000`，`seed=20260722`）：

| 量（kept-48 LOO） | point | 95% CI |
|-------------------|------:|--------|
| MAE | 0.82 cm | **[0.56, 1.15] cm** |
| RMSE | 1.33 cm | **[0.69, 1.85] cm** |
| bias | +0.04 cm | **[−0.37, +0.38] cm** |

最大絕對誤差位於 **d≈0.592 m**（primary-way 切換點），其餘距離平均絕對誤差多在 1 cm 內。

---

## 方法

- 單位：獨特 `true_distance_3d_m`（**禁止**以 p1/p2/p3 當 fold）。  
- LOO：hold-out 一距離之全部紀錄 → 其餘擬合 \(k=ad+b\) → \(\hat d=(k-b)/a\)。  
- 首尾距離被留出時含**有限外插**，故不稱「純插值驗證」，而稱：  
  **「距離網格 leave-one-distance-out 驗證」**。  
- Bootstrap：對 LOO 得到的誤差向量做有放回重抽，報 MAE／RMSE／bias 的 2.5–97.5 百分位。

---

## 論文用詞

| 可寫 | 不可寫 |
|------|--------|
| 校正資料內殘差 RMSE 1.21 cm（kept） | 不附條件的「測距精度 1.21 cm」 |
| 距離網格 LOO 驗證 RMSE 1.33 cm（95% CI 見上） | 實機／跨場景精度 |
| 高 r 不依賴排除 12 點 | 排除製造了線性 |

---

## 重現

```bash
# 數字見
python3 -c "import json;print(json.load(open('runtime/outputs/thesis_32_51_audit/audit_metrics.json'))['p2']['loo_kept_boot'])"
```
