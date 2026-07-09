# Reproducibility Audit — UR10 RTX Acoustic Thesis Pipeline

**Repo:** [sakiwatashi/isaacsim6.0acousticthesis](https://github.com/sakiwatashi/isaacsim6.0acousticthesis)  
**Audit date:** 2026-07-01（對齊 [`thesis/PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md`](thesis/PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md)）  
**Purpose:** 口試委員可審計之實驗協定；對照 `DATA_MANIFEST.md` 與 `thesis/REPLICATION_PACKAGE.md`。

---

## 0. 論文驗證鏈（第一性原則）

| 層級 | 問題 | 主實驗 | 狀態 |
|------|------|--------|------|
| **L1** | RTX 特徵可重現、具距離趨勢？ | Phase A · `fixed_tcp_repeatability_v1` | ✅ 30/30 |
| **L2** | 閉環特徵能否改善接近區到達？ | Phase B/C · `physical_ai_v9_skip_lift_clean` | ✅ 84% vs 29% |
| **L3** | 最終夾取/接觸穩定？ | 同上 · final success | ⚠️ ~20%，列為限制 |
| **L4** | 離線 Physical AI 含聲學信號？ | 同上 · ablation | ✅ acoustic_only F1≈0.598 |

**主貢獻：** L1 + L2 + L4。**L3 為下游評估，不作主 claim。**

---

## 1. Phase A — 特徵可審計（地基）

| 項目 | 值 |
|------|-----|
| **實驗名稱** | Fixed-TCP RTX repeatability |
| **Batch ID** | `fixed_tcp_repeatability_v1` |
| **材質條件** | B（medium absorption, α≈0.35） |
| **機器人** | UR10 official USD asset，固定 TCP |
| **距離點** | 0.5, 1.0, 1.5, 2.0, 2.5, 3.0 m |
| **Repeat 數** | 5（`repeat_001` … `repeat_005`） |
| **預期 run 總數** | **30 / 30 PASS** |

### 重現指令

```bash
cd <repo_root>
source scripts/env_host_isolated.sh
bash scripts/run_phase3_repeatability_and_analysis.sh
```

腳本依序執行：

1. `run_host_fixed_tcp_repeatability_batch.sh` — 30 次 Isaac Sim 擷取
2. `extract_fixed_tcp_rtx_features.py` — 特徵聚合
3. `run_phase3_rtx_pra_comparison.sh` — RTX 趨勢圖表（**工程紀錄**；論文正文不引用 PRA 對照）

### 輸出目錄

| 層級 | 路徑 | 進 git？ |
|------|------|----------|
| Raw repeat | `runtime/outputs/fixed_tcp_repeatability_v1/` | ❌ |
| Feature extract | `runtime/outputs/phase3_rtx_features/fixed_tcp_repeatability_v1_distance_features.csv` | ❌ |
| Canonical RTX 摘要 | `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/` | ✅ |

### Phase A 預期產物

- `batch_summary.txt` → `pass=30 fail=0`
- `fixed_tcp_rtx_pra_correlations.csv` → `distance_vs_rtx` × `primary_sgw_early_energy_mean`：ρ≈−0.66, n=6

---

## 2. Phase B/C — 閉環接近與 Physical AI（主貢獻）

| 項目 | 值 |
|------|-----|
| **實驗名稱** | Randomized closed-loop approach + open-loop baseline + offline Physical AI |
| **Canonical Batch ID** | `physical_ai_v9_skip_lift_clean` |
| **機器人** | UR10e + Robotiq 2F-85 official asset |
| **控制** | `ultrasonic_closed_loop_controller.py`（不消費 target pose 作前進決策） |
| **監管** | `approach_supervisor_v1.py`（oracle 僅安全包絡 / fusion 飽和恢復） |
| **夾取模式** | `--skip-lift`（contact-only，`FixedCuboid`） |
| **隨機化** | search start X/Y、wrench Y、trial seed |

### Canonical 資料集（已產出，建議口試引用）

```text
runtime/outputs/physical_ai_v9_skip_lift_clean/
  trial_dir_count = 49
  step_row_count = 284
  closed_loop trials = 25
  open_loop_baseline trials = 24
```

### 重現指令

**Smoke（單次 trial，驗證管線可跑）：**

```bash
bash scripts/run_host_ultrasonic_closed_loop_grasp_smoke.sh
bash scripts/run_host_open_loop_grasp_baseline_smoke.sh
```

**離線分析 only（不重跑 Sim，驗證 ablation 數字）：**

```bash
python3 scripts/run_physical_ai_v8_randomized_pipeline.py \
  --batch-id physical_ai_v9_skip_lift_clean \
  --skip-batch
```

**完整隨機化批次（耗時）：**

```bash
python3 scripts/run_physical_ai_v8_randomized_pipeline.py \
  --batch-id physical_ai_v9_skip_lift_clean \
  --config-count 8 --trials-per-config 6
```

### Phase B/C 預期產物

| 路徑 | 內容 |
|------|------|
| `physical_ai_v9_skip_lift_clean/` | 每 trial 之 summary JSON、step CSV |
| `physical_ai_v9_skip_lift_clean_dataset/physical_ai_acoustic_steps.csv` | 聚合步級資料集 |
| `physical_ai_v9_skip_lift_clean_ablation/feature_ablation_summary.csv` | 特徵消融表 |

### Phase B/C 預期數字（2026-07-01 審計）

**接近成功率（stage-level audit）：**

| 指標 | Closed-loop | Open-loop |
|------|------------:|----------:|
| Approach ≤ 0.45 m | 21/25 = **84.0%** | 7/24 = 29.2% |
| Near ≤ 0.35 m | 21/25 = **84.0%** | 1/24 = 4.2% |
| Final success | 5/25 = 20.0% | 5/24 = 20.8% |

**Physical AI ablation（`stop_region_label`）：**

| Feature set | F1 | Balanced accuracy |
|-------------|---:|------------------:|
| all_features | 0.684 | 0.665 |
| acoustic_only | 0.598 | 0.590 |
| pose_only | 0.533 | 0.650 |

### 關鍵工程約束（重現時必守）

1. **`--skip-lift` 必須生效：** headless 亦須建立 `FixedCuboid`，不可誤入 physics lift 路徑。
2. **控制器 vs supervisor：** 控制器不讀 target world pose；supervisor 可用 oracle 距離作安全仲裁（claim boundary）。
3. **PhysX 非有限態：** 多來自 Robotiq 接觸物理或 lift，**非 RTX Acoustic**；contact-only 模式用於隔離。

---

## 3. 環境釘選

| 元件 | 版本 |
|------|------|
| Isaac Sim | **host standalone 6.0.0-rc.59** |
| Isaac Lab | 3.0.0-beta2（附錄實驗） |
| rsl-rl-lib | 5.0.1（附錄 RL） |
| Experience | `${APP_ROOT}/apps/isaacsim.exp.base.python.kit` |

---

## 4. Claim boundary（可講 / 不可講）

### 可宣稱

| Claim | 依據 |
|-------|------|
| 30/30 可重複性 PASS | Phase A `batch_summary.txt` |
| `primary_sgw_early_energy` 距離下降趨勢（ρ≈−0.66, n=6） | Phase A correlations CSV |
| 閉環接近區到達率顯著優於 open-loop（84% vs 29%） | Phase B/C v9 audit |
| acoustic_only 含可測量狀態信號（F1≈0.598） | v9 ablation CSV |
| Tier B contact-only 示範與階段化評估框架 | grasp smoke + v9 |

### 不可宣稱

| 不可宣稱 | 原因 |
|----------|------|
| 厘米級部署測距 | 僅趨勢級 feasibility |
| 穩定最終夾取（~20% 兩組相近） | L3 未成熟；PhysX / gripper 整合問題 |
| 純超聲端到端夾取（零幾何護欄） | supervisor / passport 幾何仍參與 |
| 可部署學習控制器 | 離線 baseline only |
| RTX 與 PRA 波形等價 | 已移出論文主線 |
| CH201 實機驗證 | 未執行 |

---

## 5. 延伸實驗（附錄 / 工程紀錄，非主審計）

| 實驗 | 腳本 | 輸出 | 論文地位 |
|------|------|------|----------|
| RTX×PRA 趨勢對照 | `run_phase3_rtx_pra_comparison.sh` | `phase3_rtx_pra_comparison_*` | 工程紀錄，正文不引用 |
| 材質敏感度 A/B/C | `run_phase3_material_sensitivity.sh` | `phase3_material_sensitivity_sgw/` | Phase A 補充 |
| Lab 動態 smoke | `lab/run_lab_smoke.sh` | `lab_dynamic_smoke_v1/` | 附錄 |
| Sim→Lab SL | `lab/run_sl_lab_distance.sh` | `lab_sl_distance_v1/` | 附錄 |
| In-sim RSL-RL v5 | `lab/run_rl_distance_in_sim_long_v5.sh` | `lab_rl_distance_in_sim_long_v5/` | 附錄 / 未來工作 |
| SurfaceGripper 嘗試 | `--final-gripper surface` | 未就緒 | 限制章節提及 |

---

## 6. 已知風險與未完成項

| 風險 | 狀態 | 緩解 |
|------|------|------|
| Raw repeat 未上傳 git | 開放 | `DATA_MANIFEST.md` + Phase A 重跑腳本 |
| v9 完整 trial 樹未進 git | 開放 | 口試引用 canonical 摘要 CSV；可 `--skip-batch` 重驗 ablation |
| README / docx 與 7/1 敘事分叉 | **進行中** | 本檔 + README 已更新；docx 待 `rebuild_thesis_six_chapters.py` |
| SurfaceGripper 註冊失敗 | 已知 | 列為限制；需 isolated smoke 後再整合 |
| `SEARCH_END_X_M` 含 +0.05 m 走廊 slack | 設計如此 | 見 `grasp_passport_v1.py` 與 unit test |
| **ToF 標定表為空** | **已確認（2026-07-04）** | `tier_b_calibration.json` 中 `tof_calibration: []`；distance fusion 的 ToF 分量（w=0.28）使用 fallback 預設表，非實測資料；energy 標定（w=0.72）正常有 8 個實測點 |
| **ρ=−0.657 標籤為 no_clear_monotonic_relation** | **已確認（2026-07-04）** | correlations.csv 的程式閾值為 \|ρ\|≥0.7；論文應以「趨勢級可行性（trend-level feasibility）」陳述，避免「單調相關」措辭 |

---

## 7. 相關文件

- [`thesis/PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md`](thesis/PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md) — 最新實證結論
- [`thesis/THESIS_REFRAME_PLAN_2026-06-30.md`](thesis/THESIS_REFRAME_PLAN_2026-06-30.md) — 敘事重構
- [`DATA_MANIFEST.md`](DATA_MANIFEST.md) — raw / summary 檔案契約
- [`thesis/REPLICATION_PACKAGE.md`](thesis/REPLICATION_PACKAGE.md) — 全管線重現步驟
- [`README.md`](README.md) — repo 導覽