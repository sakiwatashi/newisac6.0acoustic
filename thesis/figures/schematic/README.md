# 論文示意圖（非 Isaac Sim 畫面）

**生成**：`python3 thesis/figures/gen_schematic_figures.py`  
**風格**：白底、Noto CJK、與 `gen_ch01_figures.py` 一致。

| 檔名 | 內容 |
|------|------|
| `fig_pipeline_s1_to_d4` | S1→S2→D1→D1.5→D3→D4 實驗鏈 |
| `fig_three_arm_ablation` | closed / blind / open 三臂 |
| `fig_d3_grasp_sequence` | D3 夾取六步序列 |
| `fig_d4_dual_track` | D4 雙軌 A/B |
| `fig_same_scene_policy_n90` | 同場景串聯 n=90 結果 |
| `fig_claim_boundary` | 可／不可宣稱 |
| `fig_acoustic_range_pipeline` | peak→距離→控制管線 |
| `fig_lab_ablation_summary` | Lab 消融表視覺化 |
| `fig_gmo_structure` | GMO 欄位語意 + signal way |
| `fig_four_pillars` | 方法四支柱 |
| `fig_paired_removal` | 配對移除三段 |
| `fig_multilateration` | D2 五視點多點定位 |

**嵌入論文**：`python3 thesis/insert_tables_and_schematics.py`  
（表 3.1／3.2 + 圖 3.1–3.6、5.4–5.7、6.1）

**不含**：Isaac Sim 視窗截圖、GMO 原始波形螢幕錄影。  
既有結果圖仍見 `ch04/`、`ch05/`（散點／對位率等由數據腳本產出）。

## Paper2Any

本機已 clone：`/home/lab109/song/tools/Paper2Any`（見該目錄 `LOCAL_SETUP_NOTE.md`）。  
文字 API 已指到 Ollama；**生圖 API 未設**，故架構圖目前由此腳本產出以保證數字與宣稱邊界正確。
