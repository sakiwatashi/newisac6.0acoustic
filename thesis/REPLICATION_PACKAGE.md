# Replication Package — UR10 RTX Acoustic Thesis Pipeline

**目的：** 口試委員／未來自己可重跑主結果  
**主機（原始產生環境）：** DGX `spark-68ef`，路徑 `/home/lab109/song/isaacsim6.0`  
**審計文件：** [`../REPRODUCIBILITY_AUDIT.md`](../REPRODUCIBILITY_AUDIT.md)、[`../DATA_MANIFEST.md`](../DATA_MANIFEST.md)  
**最新結論：** [`PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md`](PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md)

---

## 1. 環境

```bash
cd <repo_root>
source scripts/env_host_isolated.sh
# 必要：APP_ROOT, IsaacLab/_isaac_sim（附錄實驗才需要 Lab）
```

**Experience（必用）：** `${APP_ROOT}/apps/isaacsim.exp.base.python.kit`

**版本釘選：**

| 元件 | 版本 |
|------|------|
| Isaac Sim | **host standalone 6.0.0-rc.59** |
| Isaac Lab | 3.0.0-beta2（附錄） |
| rsl-rl-lib | 5.0.1（附錄 RL） |
| Python | 3.12（kit 內建） |
| GPU | NVIDIA GB10 |

---

## 2. 主結果重現順序

### Phase A — Sim 靜態 30/30（論文地基）

```bash
bash scripts/run_phase3_repeatability_and_analysis.sh
```

- **Batch ID：** `fixed_tcp_repeatability_v1`
- **預期：** 30/30 PASS → `batch_summary.txt`
- **Canonical：** `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/`

### Phase B/C — 閉環接近 smoke

```bash
# 閉環接近
bash scripts/run_host_ultrasonic_closed_loop_approach_smoke.sh

# 閉環 + Tier B contact-only 夾取
bash scripts/run_host_ultrasonic_closed_loop_grasp_smoke.sh

# Open-loop 對照
bash scripts/run_host_open_loop_grasp_baseline_smoke.sh
```

- **輸出範例：** `runtime/outputs/ur10e_robotiq_ultrasonic_grasp_smoke_v1/`
- **必守：** `--skip-lift` / `GRASP_SKIP_LIFT=1` → `FixedCuboid`（contact-only）

### Phase B/C — Physical AI 隨機化批次（論文主貢獻數據）

**Canonical 已產出（建議口試直接引用）：**

```text
runtime/outputs/physical_ai_v9_skip_lift_clean/
runtime/outputs/physical_ai_v9_skip_lift_clean_ablation/feature_ablation_summary.csv
```

**僅重跑離線分析（驗證 ablation 數字，不需 Sim）：**

```bash
python3 scripts/run_physical_ai_v8_randomized_pipeline.py \
  --batch-id physical_ai_v9_skip_lift_clean \
  --skip-batch
```

**完整重跑隨機化批次（耗時）：**

```bash
python3 scripts/run_physical_ai_v8_randomized_pipeline.py \
  --batch-id physical_ai_v9_skip_lift_clean \
  --config-count 8 --trials-per-config 6
```

---

## 3. 附錄實驗（非主貢獻）

### Isaac Lab 動態 smoke

```bash
bash lab/run_lab_smoke.sh
# 輸出：runtime/outputs/lab_dynamic_smoke_v1/
```

### Sim→Lab 監督學習

```bash
bash lab/run_sl_lab_distance.sh
# 輸出：runtime/outputs/lab_sl_distance_v1/
```

### In-sim RSL-RL

```bash
bash lab/run_rl_distance_in_sim_long_v5.sh
bash lab/run_eval_rl_distance_in_sim.sh
```

---

## 4. 論文圖表 ↔ 檔案對照

| 圖表 | 路徑 |
|------|------|
| 圖4.1–4.2（Phase A RTX 趨勢） | `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/rtx_*.png` |
| 圖4.3（材質 A/B/C） | `runtime/outputs/phase3_material_sensitivity_sgw/` |
| **表5.1（接近成功率）** | `physical_ai_v9_skip_lift_clean/` trial summaries（見 7/1 summary §4.1） |
| **表5.2（Physical AI ablation）** | `physical_ai_v9_skip_lift_clean_ablation/feature_ablation_summary.csv` |
| 附錄 Lab 圖 | `runtime/outputs/lab_dynamic_smoke_v1/*.png` |

**刪除正文引用：** RTX×PRA 圖表（保留於 `phase3_rtx_pra_comparison_*` 作工程紀錄）。

---

## 5. 統計分析腳本

| 分析 | 腳本 |
|------|------|
| Phase A RTX 特徵 | `scripts/extract_fixed_tcp_rtx_features.py` |
| Physical AI 資料集 | `scripts/build_physical_ai_acoustic_dataset.py` |
| Physical AI 策略 / ablation | `scripts/train_physical_ai_acoustic_policy.py` |
| v8/v9 批次編排 | `scripts/run_physical_ai_v8_randomized_pipeline.py` |
| 附錄：Lab ρ | `lab/plot_lab_smoke_results.py` |
| 附錄：SL | `lab/train_sl_distance_regressor.py` |

---

## 6. Claim boundary（重現時請對照）

| 可宣稱 | 不可宣稱 |
|--------|----------|
| 30/30 PASS；early_energy 距離趨勢 ρ≈−0.66 (n=6) | 厘米級部署測距 |
| 閉環 approach ≤0.45 m：**84%** vs open-loop **29%** | 穩定最終夾取 |
| acoustic_only stop_region F1≈**0.598** | 可部署學習控制器 |
| Tier B contact-only 階段化評估 | RTX×PRA 波形等價、CH201 實機 |

---

## 7. 交付清單（口試前）

- [x] `REPRODUCIBILITY_AUDIT.md` + `DATA_MANIFEST.md` 對齊 7/1
- [x] `README.md` 對齊 7/1
- [x] `THESIS_OUTLINE_FCU_2026-06-30.md` 含 Physical AI 章節
- [ ] `thesis/THESIS_DRAFT_FCU_v1.docx` 對齊新大綱重跑
- [ ] 圖3.1、圖5.1–5.3 嵌入 Word
- [ ] 摘要中英文改寫