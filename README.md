# UR10 RTX Acoustic Thesis — Isaac Sim / Lab Pipeline

**逢甲大學 · 電聲碩士學位學程**  
碩士論文：UR10 末端 RTX 聲學感測之可審計模擬管線研究（室內聲學特徵驗證與 Isaac Lab 延伸）  
指導教授：蔡鈺鼎 教授

---

## 這個 repo 是什麼？

可重現的 **Isaac Sim → Isaac Lab** 研究管線，用於驗證：

- 固定 TCP 下 RTX Acoustic **signal-way** 特徵能否支撐**趨勢級**距離推理
- 同一 Passport／特徵工廠能否延伸至 Lab 動態觀測、Sim→Lab 監督學習與 in-sim RL 閉環

**定位：** simulation-based feasibility pipeline（可行性 + 可審計），**非**部署級測距或波形級數位雙生。

---

## 快速導覽

| 路徑 | 內容 |
|------|------|
| [`thesis/THESIS_DRAFT_FCU_v1.docx`](thesis/THESIS_DRAFT_FCU_v1.docx) | **論文 Word 初稿**（六章版） |
| [`thesis/THESIS_OUTLINE_FCU_2026-06-29.md`](thesis/THESIS_OUTLINE_FCU_2026-06-29.md) | 論文大綱（電聲學程 · 六章） |
| [`thesis/REPLICATION_PACKAGE.md`](thesis/REPLICATION_PACKAGE.md) | 口試重現步驟 |
| [`scripts/`](scripts/) | Isaac Sim：Passport、RTX factory、Phase 3 主實驗 |
| [`lab/`](lab/) | Isaac Lab：動態環境、SL、in-sim RSL-RL |
| [`runtime/outputs/`](runtime/outputs/) | Canonical 實驗結果（摘要表、圖；不含 raw repeat CSV） |

---

## 環境需求（本機）

此 repo **不含** Isaac Sim 安裝包（`app/`）與 Isaac Lab 上游 clone，需在本機 DGX 預先安裝：

- Isaac Sim 6.0 host standalone（路徑慣例：`/home/lab109/song/isaacsim6.0/app`）
- Isaac Lab（`IsaacLab/`，符號連結至 `_isaac_sim`）
- NVIDIA GPU + RTX Acoustic experimental 延伸

```bash
cd /home/lab109/song/isaacsim6.0   # 或你的 clone 路徑
source scripts/env_host_isolated.sh
```

Experience（Lab／RTX 必用）：

```text
${APP_ROOT}/apps/isaacsim.exp.base.python.kit
```

---

## 重現主結果（建議順序）

### 1. Sim Phase 3 — 30/30 可重複性（論文主貢獻）

```bash
bash scripts/run_phase3_repeatability_and_analysis.sh
bash scripts/run_phase3_rtx_pra_comparison.sh
```

Canonical 輸出已收錄於：  
`runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/`

### 2. Lab 動態觀測

```bash
bash lab/run_lab_smoke.sh
```

輸出：`runtime/outputs/lab_dynamic_smoke_v1/`

### 3. Sim→Lab 監督學習

```bash
bash lab/run_sl_lab_distance.sh
```

輸出：`runtime/outputs/lab_sl_distance_v1/`

### 4. In-sim RSL-RL（延伸，非主貢獻）

```bash
bash lab/run_rl_distance_in_sim_long_v5.sh   # 長訓練
bash lab/run_eval_rl_distance_in_sim.sh       # hold-out eval
```

---

## 論文 Word 重建

```bash
cd thesis
python3 generate_thesis_figures.py
python3 generate_fig31.py
python3 rebuild_thesis_six_chapters.py   # 六章完整重建
```

輸出：`thesis/THESIS_DRAFT_FCU_v1.docx`

---

## 主要結論（claim boundary）

| 可宣稱 | 不可宣稱 |
|--------|----------|
| 30/30 可重複；early_energy 距離趨勢 ρ≈−0.66 | 厘米級部署測距 |
| RTX×PRA 趨勢一致（ρ≈+0.66） | 波形等價 |
| Lab 動態 ρ≈−0.48；Sim→Lab SL r≈0.47 | MAE 0.41 m 可上實機 |
| in-sim RL 閉環可跑通 | RL 優於 SL |

---

## 授權與引用

學術用途請引用本 repo 與論文初稿。Isaac Sim／Isaac Lab 為 NVIDIA 產品，使用須遵守其授權條款。

---

## 聯絡

GitHub: [@sakiwatashi](https://github.com/sakiwatashi)