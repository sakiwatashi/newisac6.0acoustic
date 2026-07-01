# UR10 RTX Acoustic Thesis — Isaac Sim Pipeline

**逢甲大學 · 電聲碩士學位學程**  
碩士論文：基於 RTX Acoustic 超音波感測之機械手臂閉迴路接近控制與 Physical AI 狀態判斷  
指導教授：蔡鈺鼎 教授

---

## 這個 repo 是什麼？

可重現、可審計的 **Isaac Sim** 研究管線，用於驗證：

- **Phase A：** 固定 TCP 下 RTX Acoustic **signal-way** 特徵能否可重複、具距離趨勢
- **Phase B/C：** 閉環超聲特徵能否驅動機器人接近至目標區域（不將目標世界座標餵給控制器）
- **Physical AI：** 隨機化幾何下，離線狀態估計是否含可測量的聲學信號

**定位：** simulation-based feasibility pipeline（可行性 + 可審計），**非**部署級測距、穩定夾取或波形級數位雙生。

**權威敘事（2026-07-01）：** [`thesis/PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md`](thesis/PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md)

---

## 快速導覽

| 路徑 | 內容 |
|------|------|
| [`thesis/PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md`](thesis/PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md) | **最新實證結論與 claim boundary** |
| [`thesis/THESIS_OUTLINE_FCU_2026-06-30.md`](thesis/THESIS_OUTLINE_FCU_2026-06-30.md) | 論文大綱（六章 · 閉環 + Physical AI） |
| [`thesis/THESIS_REFRAME_PLAN_2026-06-30.md`](thesis/THESIS_REFRAME_PLAN_2026-06-30.md) | 敘事重構規劃（刪 PRA 主線） |
| [`thesis/THESIS_DRAFT_FCU_v1.docx`](thesis/THESIS_DRAFT_FCU_v1.docx) | 論文 Word 初稿（待對齊 7/1 重跑） |
| [`thesis/REPLICATION_PACKAGE.md`](thesis/REPLICATION_PACKAGE.md) | 口試重現步驟 |
| [`REPRODUCIBILITY_AUDIT.md`](REPRODUCIBILITY_AUDIT.md) | Phase A/B/C 可審計協定 |
| [`DATA_MANIFEST.md`](DATA_MANIFEST.md) | Raw / canonical 資料契約 |
| [`scripts/`](scripts/) | Passport、RTX factory、閉環接近、Physical AI |
| [`lab/`](lab/) | Isaac Lab 延伸（附錄，非主貢獻） |
| [`runtime/outputs/`](runtime/outputs/) | 實驗結果 |

---

## 環境需求（本機）

此 repo **不含** Isaac Sim 安裝包（`app/`）與 Isaac Lab 上游 clone，需在本機 DGX 預先安裝：

- Isaac Sim **6.0.0-rc.59** host standalone（路徑慣例：`/home/lab109/song/isaacsim6.0/app`）
- Isaac Lab（`IsaacLab/`，符號連結至 `_isaac_sim`）— 僅附錄實驗需要
- NVIDIA GPU + RTX Acoustic experimental 延伸

```bash
cd /home/lab109/song/isaacsim6.0   # 或你的 clone 路徑
source scripts/env_host_isolated.sh
```

Experience（RTX 必用）：

```text
${APP_ROOT}/apps/isaacsim.exp.base.python.kit
```

---

## 重現主結果（建議順序）

### 1. Phase A — 30/30 特徵可重複性（論文地基）

```bash
bash scripts/run_phase3_repeatability_and_analysis.sh
```

| 層級 | 路徑 | 進 git？ |
|------|------|----------|
| Raw repeat（6×5 runs） | `runtime/outputs/fixed_tcp_repeatability_v1/` | ❌ |
| Feature extract | `runtime/outputs/phase3_rtx_features/fixed_tcp_repeatability_v1_distance_features.csv` | ❌ |
| Canonical RTX 摘要 | `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/` | ✅ |

### 2. Phase B/C — 閉環接近 smoke（單次 trial）

```bash
# 閉環接近（不含夾取）
bash scripts/run_host_ultrasonic_closed_loop_approach_smoke.sh

# 閉環接近 + Tier B contact-only 夾取
bash scripts/run_host_ultrasonic_closed_loop_grasp_smoke.sh

# Open-loop 對照
bash scripts/run_host_open_loop_grasp_baseline_smoke.sh
```

### 3. Phase B/C + Physical AI — 隨機化批次（論文主貢獻數據）

**Canonical 已產出資料集（建議口試直接引用）：**

```text
runtime/outputs/physical_ai_v9_skip_lift_clean/
runtime/outputs/physical_ai_v9_skip_lift_clean_ablation/feature_ablation_summary.csv
```

**僅重跑離線分析（不需重開 Isaac Sim）：**

```bash
python3 scripts/run_physical_ai_v8_randomized_pipeline.py \
  --batch-id physical_ai_v9_skip_lift_clean \
  --skip-batch
```

**完整重跑隨機化批次（耗時，需 GPU）：**

```bash
python3 scripts/run_physical_ai_v8_randomized_pipeline.py \
  --batch-id physical_ai_v9_skip_lift_clean \
  --config-count 8 --trials-per-config 6
```

> 重跑時請確認 wrapper 傳入 `--skip-lift`（contact-only，`FixedCuboid`），避免 PhysX lift 污染資料集。詳見 7/1 summary §3.1。

### 4. Isaac Lab 延伸（附錄，非主貢獻）

```bash
bash lab/run_lab_smoke.sh              # 動態觀測
bash lab/run_sl_lab_distance.sh        # Sim→Lab 監督學習
bash lab/run_rl_distance_in_sim_long_v5.sh   # in-sim RL
```

---

## 論文 Word 重建

```bash
cd thesis
python3 generate_thesis_figures.py
python3 generate_fig31.py
python3 rebuild_thesis_six_chapters.py   # 待對齊 7/1 大綱後重跑
```

輸出：`thesis/THESIS_DRAFT_FCU_v1.docx`

---

## 主要結論（claim boundary · 2026-07-01）

| 可宣稱 | 不可宣稱 |
|--------|----------|
| Phase A：30/30 PASS；`primary_sgw_early_energy` 距離趨勢 ρ≈−0.66 (n=6) | 厘米級部署測距 |
| 閉環接近 ≤0.45 m：**84.0%** vs open-loop **29.2%**（v9, n=25/24） | 穩定端到端超聲夾取 |
| 閉環 near ≤0.35 m：**84.0%** vs open-loop **4.2%** | 優於 VLM 全任務管線 |
| acoustic_only `stop_region` F1≈**0.598**（隨機化 Sim） | 可部署的學習控制器 |
| Tier B contact-only 示範與明確階段化評估 | 波形等價、CH201 實機已驗證 |

**最終夾取成功率約 20%（closed-loop 與 open-loop 相近）→ 應歸因於下游 PhysX 接觸/夾爪整合，非聲學接近失敗。**

---

## 授權與引用

學術用途請引用本 repo 與論文初稿。Isaac Sim／Isaac Lab 為 NVIDIA 產品，使用須遵守其授權條款。

---

## 聯絡

GitHub: [@sakiwatashi](https://github.com/sakiwatashi)