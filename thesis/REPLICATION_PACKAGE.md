# Replication Package — UR10 RTX Acoustic Thesis Pipeline

**目的：** 口試委員／未來自己可重跑主結果（AERS 精神，無需專用 skill）  
**主機：** DGX `spark-68ef`，路徑 `/home/lab109/song/isaacsim6.0`

---

## 1. 環境

```bash
cd /home/lab109/song/isaacsim6.0
source scripts/env_host_isolated.sh
# 必要：APP_ROOT, IsaacLab/_isaac_sim
```

**Experience（必用）：** `${APP_ROOT}/apps/isaacsim.exp.base.python.kit`

---

## 2. 主結果重現順序

### Phase 3 — Sim 靜態 30/30（論文主貢獻）

```bash
# 見 runtime/outputs/fixed_tcp_repeatability_v1/
# 腳本：scripts/ 下 Phase 3 正式實驗（勿與 Lab 混淆）
```

### Phase 4 — Lab 動態 smoke

```bash
bash lab/run_lab_smoke.sh
# 輸出：runtime/outputs/lab_dynamic_smoke_v1/
bash lab/plot_lab_smoke_results.py --output-dir runtime/outputs/lab_dynamic_smoke_v1
```

### Phase 4.6 — Sim→Lab 監督學習

```bash
bash lab/run_sl_lab_distance.sh
# 輸出：runtime/outputs/lab_sl_distance_v1/
```

### Phase 5 — In-sim RSL-RL

```bash
# Smoke（2 iter）
bash lab/run_rl_distance_in_sim.sh

# 長訓練 v5（500 iter，塑形獎勵）
bash lab/run_rl_distance_in_sim_long_v5.sh

# 評估
cd IsaacLab && source ../scripts/env_host_isolated.sh
export PYTHONPATH="../lab:../scripts:${PYTHONPATH:-}"
./isaaclab.sh -p ../lab/eval_rl_distance_in_sim.py --headless \
  --experience "${APP_ROOT}/apps/isaacsim.exp.base.python.kit" \
  --steps 64 --checkpoints ../runtime/outputs/lab_rl_distance_in_sim_long_v5/model_499.pt
```

---

## 3. 論文圖表 ↔ 檔案對照

| 圖表 | 路徑 |
|------|------|
| 圖4.5–4.6 | `runtime/outputs/lab_dynamic_smoke_v1/*.png` |
| 圖4.7–4.8 | `runtime/outputs/lab_sl_distance_v1/*.png` |
| 圖4.1–4.3 | `runtime/outputs/fixed_tcp_repeatability_v1/` 或 phase3 目錄 |
| 表4.6 | `runtime/outputs/lab_sl_distance_v1/sl_distance_summary.json` |
| 表4.7（RL） | 見 `thesis/THESIS_PHASE5_INSIM_RL_2026-06-28.md` |

---

## 4. 統計分析腳本

| 分析 | 腳本 |
|------|------|
| Lab E vs GT ρ | `lab/plot_lab_smoke_results.py` |
| SL 指標 | `lab/train_sl_distance_regressor.py` |
| RL eval ρ, MAE | `lab/eval_rl_distance_in_sim.py` |
| 離線 RL smoke | `lab/train_rl_distance_smoke.py` |

---

## 5. 版本釘選（論文方法節應寫）

| 元件 | 版本 |
|------|------|
| Isaac Sim | 6.0.0-rc.59 |
| Isaac Lab | 3.0.0-beta2 |
| rsl-rl-lib | 5.0.1 |
| Python | 3.12（kit 內建） |
| GPU | NVIDIA GB10 |

---

## 6. 交付清單（口試前）

- [ ] `thesis/THESIS_DRAFT_FCU_v1.docx` 更新 §3.9–§4.8
- [ ] 圖4.1–4.10 嵌入 Word
- [ ] `CITATION_BANK.md` 轉正式參考文獻
- [ ] 本檔 + `THESIS_OUTLINE_FCU_2026-06-27.md` 一併存檔