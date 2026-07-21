# D1／D1.5 配對敏感度分析（P3）

**日期**: 2026-07-22  
**性質**: 佐證；**不取代**事前 Welch 主判準  
**定義**: \(e_i=|d_{h,i}^{\mathrm{oracle}}-0.35|\)；\(\Delta e_i=e_{\mathrm{blind},i}-e_{\mathrm{closed},i}\)  
**資料**: `runtime/outputs/v2_d1_approach/`、`v2_d15_arm_approach/`  
**產物**: `runtime/outputs/thesis_32_51_audit/D1_paired_rows.csv`、`D15_paired_rows.csv`

---

## 結果摘要

| 實驗 | n | \(\bar e_{\mathrm{closed}}\) | \(\bar e_{\mathrm{blind}}\) | \(\overline{\Delta e}\) (95% CI) | 配對置換 p（單尾 \(\Delta>0\)） | Wilcoxon p（單尾） | Welch t / p（事前風格） |
|------|--:|------------------------------:|-----------------------------:|--------------------------------:|-------------------------------:|-------------------:|------------------------|
| **D1** | 30 | 2.11 cm | 77.6 cm | **75.5 cm** [69.7, 81.0] | **≈2×10⁻⁵** | **≈8×10⁻⁷** | t=−25.1 / ≪0.001 |
| **D1.5** | 30 | 2.53 cm | 17.4 cm | **14.8 cm** [12.2, 17.3] | **≈2×10⁻⁵** | **≈1.6×10⁻⁶** | t=−10.6 / ≪0.001 |

- closed 停止位置–目標 Pearson：D1 **0.997**；D1.5 **0.986**  
- blind 停止位置**恆定**（D1: **1.15 m**；D1.5: **≈0.950 m**）→ **Pearson 未定義**（非 r=0）  
- 容差 ≤10 cm：closed 皆 30/30；blind D1 0/30，D1.5 4/30  

---

## 詮釋

1. 配對置換／Wilcoxon 與 Welch **同向**：closed 停止誤差顯著低於 blind。  
2. 正式正文應保留事前 Welch，並加一句「配對敏感度分析支持相同結論」。  
3. 不得事後刪除 Welch；不得把 blind 的 r 寫成 0。

---

## 重現

`runtime/outputs/thesis_32_51_audit/audit_metrics.json` → `p3`。
