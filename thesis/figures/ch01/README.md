# 第一章 圖檔（重製版・供審閱）

路徑：`thesis/figures/ch01/`

## 技術
- **Pillow** 直接繪製（不用 matplotlib）
- 字型：**Noto Sans CJK Regular/Bold**（`.ttc` index=0），中英數字同一字型
- 風格：論文線稿、白底、細線、低彩（避免 Colab／seaborn 預設感）

## 檔案
| 檔名 | 圖號 | 小節 |
|------|------|------|
| fig_1_1_last_meter_hierarchy | 圖 1-1 | 1.1 |
| fig_1_2_rq_experiment_map | 圖 1-2 | 1.2 |
| fig_1_3_platform_chain | 圖 1-3 | 1.5 |
| fig_1_4_sensor_mount_extension | 圖 1-4 | 1.5 |
| fig_1_5_multipath_concept | 圖 1-5 | 1.1 |

PNG 供預覽；PDF 供插入論文。

## 重跑
```bash
python3 thesis/figures/gen_ch01_figures.py
```
