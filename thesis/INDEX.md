# Thesis Document Index — 逢甲大學電聲碩士論文

**最後更新：** 2026-07-04

---

## Canonical 版本（口試引用這些）

| 文件 | 路徑 | 說明 |
|------|------|------|
| **論文大綱** | `THESIS_OUTLINE_FCU_2026-06-30.md` | ✅ 六章版，含 Physical AI，**唯一 canonical** |
| **技術參考** | `TECHNICAL_REFERENCE_2026-07-03.md` | 每個 API / 函式 / 常數的完整代碼說明 |
| **名詞與數學** | `CONCEPTS_AND_MATH_2026-07-03.md` | 白話名詞解釋 + 9 個核心數學公式 |
| **實驗結果摘要** | `PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md` | Phase A/B/C 最終數字 |
| **日誌統整** | `DAILY_SUMMARY_2026-07-04.md` | 今日工作紀錄 |
| **健檢報告** | `health_check/final_report.md` | 2026-07-04 完整專案健檢 |

---

## 可重現驗證（口試委員用）

| 文件 | 路徑（根目錄） | 說明 |
|------|------|------|
| **可重現審計** | `REPRODUCIBILITY_AUDIT.md` | 腳本路徑 + 預期輸出 + 驗證指令 |
| **資料契約** | `DATA_MANIFEST.md` | 各輸出目錄的 git 收錄狀態 |
| **重現包** | `thesis/REPLICATION_PACKAGE.md` | 完整管線重現步驟 |

---

## 歸檔版本（舊版，請勿引用）

> ⚠️ 以下文件為舊版或過渡版本，保留作歷史紀錄。論文及口試請使用上方 canonical 版本。

| 文件 | 狀態 | 原因 |
|------|------|------|
| `THESIS_OUTLINE_FCU_2026-06-27.md` | 🗄️ 廢棄 | 初始草案，無 Physical AI |
| `THESIS_OUTLINE_FCU_2026-06-29.md` | 🗄️ 廢棄 | 含 PyRoom 主貢獻敘述（已移出主線） |
| `THESIS_LAB_SECTIONS_2026-06-28.md` | 🗄️ 草稿 | Isaac Lab 附錄草稿 |
| `THESIS_PHASE5_INSIM_RL_2026-06-28.md` | 🗄️ 草稿 | In-sim RL 探索（附錄） |
| `THESIS_SIM_LAB_SHOWCASE.md` | 🗄️ 草稿 | Sim→Lab 展示文件 |
| `THESIS_CHAPTER2_DRAFT_2026-06-29.md` | 🗄️ 草稿 | 第二章舊草稿 |
| `論文統整_指導教授用.md` | ⚠️ 確認版本 | 需確認是否與 06-30 大綱同步 |

---

## 核心數字快速查詢

| Claim | 數字 | 來源文件 | 驗證指令 |
|-------|------|---------|---------|
| Phase A 可重複性 | pass=30 fail=0 | `runtime/outputs/fixed_tcp_repeatability_v1/batch_summary.txt` | `cat batch_summary.txt` |
| early_energy 距離趨勢 | ρ = −0.657 (n=6) | `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/fixed_tcp_rtx_pra_correlations.csv` | `cat fixed_tcp_rtx_pra_correlations.csv` |
| 閉環 vs 開環接近率 | 84% vs 29% | `physical_ai_v9_skip_lift_clean_ablation/feature_ablation_summary.csv` | `--skip-batch` |
| acoustic_only F1 | 0.598 | 同上 | 同上 |

---

## 論文主貢獻快速確認

✅ **可宣稱：**
- L1：RTX 特徵 30/30 可重現 + ρ≈−0.66 距離趨勢（趨勢級，n=6 未達 p<0.05）
- L2：閉環接近率 84% vs 開環 29%
- L4：acoustic_only F1 = 0.598（聲學特徵有獨立信息量）

❌ **不可宣稱：**
- 厘米級精確測距 / 穩定最終夾取（~20% contact-only）/ 純聲學控制 / CH201 實機驗證
