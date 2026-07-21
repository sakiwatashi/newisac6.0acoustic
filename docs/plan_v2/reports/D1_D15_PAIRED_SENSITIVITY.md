# D1／D1.5 配對敏感度分析（P3）

**日期**: 2026-07-22（封口：補 permutation metadata）  
**性質**: 佐證；**不取代**事前 Welch 主判準  
**定義**: \(e_i=|d_{h,i}^{\mathrm{oracle}}-0.35|\)；\(\Delta e_i=e_{\mathrm{blind},i}-e_{\mathrm{closed},i}\)  
**資料**: `runtime/outputs/v2_d1_approach/`、`v2_d15_arm_approach/`  
**產物**: `runtime/outputs/thesis_32_51_audit/D1_paired_rows.csv`、`D15_paired_rows.csv`、`audit_metrics.json` → `p3` / `p3_meta`

---

## 結果摘要

| 實驗 | n | \(\bar e_{\mathrm{closed}}\) | \(\bar e_{\mathrm{blind}}\) | \(\overline{\Delta e}\) (bootstrap 95% CI) | 配對置換 p | Wilcoxon p | Welch t（事前風格） |
|------|--:|------------------------------:|-----------------------------:|-------------------------------------------:|-----------:|-----------:|---------------------|
| **D1** | 30 | 2.11 cm | 77.6 cm | **75.5 cm** [69.7, 81.0] | **\(p\le 2\times 10^{-5}\)** | ≈8×10⁻⁷ | t=−25.1 |
| **D1.5** | 30 | 2.53 cm | 17.4 cm | **14.8 cm** [12.2, 17.3] | **\(p\le 2\times 10^{-5}\)** | ≈1.6×10⁻⁶ | t=−10.6 |

- closed 停止位置–目標 Pearson：D1 **0.997**；D1.5 **0.986**  
- blind 停止位置**恆定**（D1: **1.15 m**；D1.5: **≈0.950 m**）→ Pearson **未定義**  
- 容差 ≤10 cm：closed 30/30；blind D1 0/30，D1.5 4/30  

---

## 統計方法 metadata（重現）

### 配對置換（Monte Carlo sign-flip）

| 項目 | 值 |
|------|-----|
| 類型 | 配對符號翻轉置換（非精確枚舉 \(2^{30}\)） |
| `n_perm` | **50 000** |
| 隨機種子 | **`seed=0`**（`numpy.random.default_rng(0)`） |
| 對立假設 | \(H_1:\ \mathrm{mean}(\Delta e)>0\)（closed 誤差更小） |
| p 值 | \(p=\dfrac{\#\{\overline{\mathrm{sign}\odot\Delta}\ge \overline{\Delta}\}+1}{n_{\mathrm{perm}}+1}\) |
| 解析度 | 若計數為 0，\(p=1/(n_{\mathrm{perm}}+1)\approx 2\times 10^{-5}\) → 報告 **\(p\le 2\times 10^{-5}\)** |

### Wilcoxon

- `scipy.stats.wilcoxon(deltas, alternative="greater", zero_method="wilcox")`

### Bootstrap（\(\overline{\Delta e}\) 的 95% CI）

- `n_boot=5000`，`seed=0`，對 \(\Delta e_i\) 有放回重抽後取均值的 2.5–97.5 百分位。

### Welch（事前主判準，保留）

- 兩樣本 Welch t 於 closed vs blind 之 \(e_i\)；正文主判準仍引用原 analyze 管線之 t／p。  
- 本報告 t 為當場重算：D1 t=−25.1；D1.5 t=−10.6（與主文一致量級）。

---

## 詮釋

1. 置換／Wilcoxon／Welch **同向**。  
2. 正式正文：Welch 主判準 + 一句配對敏感度。  
3. 不得把 blind 的 r 寫成 0。
