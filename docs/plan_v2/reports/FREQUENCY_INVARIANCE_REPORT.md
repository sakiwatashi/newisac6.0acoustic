# 中心頻率設定之不變性診斷（P4 正典）

**日期**: 2026-07-22  
**正典資料**: `runtime/outputs/armfree_freq_sweep/freq_{20,30,40,60,80,100}000hz/armfree_proximity_sweep.csv`  
**指標**: `runtime/outputs/armfree_freq_sweep/frequency_invariance_metrics.json`  
**驗證**: `bash runtime/verify_all.sh`（**缺檔或峰值序列不一致 → exit 1**）

---

## 一句話

在所測 armfree 近距掃描場景與 GMO 特徵下，將 `centerFrequency` 設為 20–100 kHz 時，**peak_sample_idx 序列六檔完全相同**；early_energy 最大相對差約 **6×10⁻⁷**（浮點尾數）。  
**可寫**：所測特徵對該參數不敏感。  
**不可寫**：RTX Acoustic／WPM 完全沒有頻率物理。

---

## 實驗摘要

| 項目 | 值 |
|------|-----|
| 名義頻率 | 20, 30, 40, 60, 80, 100 kHz |
| 距離點 | 20（`oracle_distance_m` ≈ 0.2–1.5 m） |
| 峰值序列種類 | **1**（六檔逐位相同） |
| vs 40 kHz 能量 max 相對差 | **≈ 6.5×10⁻⁷** |

場景：歷史 armfree proximity 掃描（固定感測器、沿前向多距離）。完整 USD 未必在快照中；**可重算產物為六份 CSV**。

---

## 與 40 kHz 敘事的關係

- `centerFrequency` 為名義脈衝參數；GMO 時間格為 `sampleDuration`≈102.4 µs。  
- 本文 40 kHz 為產品敘事對齊，**不是**靠改頻率調測距的有效旋鈕（在此掃描內）。

---

## 重現

```bash
# 六檔必須存在
ls runtime/outputs/armfree_freq_sweep/freq_*hz/armfree_proximity_sweep.csv
bash runtime/verify_all.sh   # 頻率段硬檢查
python3 -c "import json;print(json.load(open('runtime/outputs/armfree_freq_sweep/frequency_invariance_metrics.json'))['adjudication'])"
```
