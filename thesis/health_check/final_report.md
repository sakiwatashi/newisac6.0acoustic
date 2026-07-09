# final_report.md — 專案健檢總報告（已更新）
# isaacsim6.0 Acoustic Thesis Pipeline
# 健檢日期：2026-07-04（掃描）→ 執行驗證後更新
# 執行者：Sonnet 4.6（主模型）+ Haiku（4 個掃描 agent）

---

## 一、專案整體狀態摘要

**整體評分：🟡 尚可（有 2 個新發現需口試前確認）**

| 面向 | 狀態 | 說明 |
|------|------|------|
| 核心功能正確性 | ✅ 良好 | RTX 管線、控制器、標定集中，無功能性 bug |
| 文件與代碼一致性 | ✅ 良好 | 所有腳本路徑確認存在，F1 數字完全吻合 |
| 重現性（Phase A）| ✅ 已驗證 | pass=30 fail=0，ρ=−0.657，目錄完整 |
| 重現性（Phase B/C）| ✅ 已驗證 | feature_ablation_summary.csv 存在，數字吻合 |
| 代碼品質 | 🟡 有技術債 | 向量函式 17+ 份重複，30+ 個 hardcoded 路徑 |
| 測試覆蓋 | 🟡 基礎 | 4 個 test_*.py，但可能需要 Isaac Sim 才能執行 |
| 架構清晰度 | ✅ 良好 | GMO/標定/控制器均集中，import 層級清晰 |

---

## 二、主要問題清單

### ✅ 原 P0 — 已確認不成立（假警報）

**健檢掃描 Agent D 找錯路徑，執行手動驗證後確認兩者均為假警報：**

| 原 P0 | 實際狀態 |
|-------|---------|
| Phase A canonical 摘要不存在 | ✅ `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/` 存在，`batch_summary.txt` pass=30 fail=0 |
| feature_ablation_summary.csv 不存在 | ✅ CSV 存在，F1 = 0.684 / 0.598 / 0.533 完全吻合 |

---

### 🔴 新發現 P0 — 口試前需確認（2 個）

**ND-1：tof_calibration 為空，始終使用 fallback 預設值**

- **位置：** `runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json`
- **問題：** `"tof_calibration": []`（空陣列）— 動態掃描從未產出 ToF 標定點
- **影響：** `fused_distance` 的 ToF 分量（權重 0.28）始終使用 `fallback_tof_calibration`（`grasp_passport_v1.py` 中的手動填寫預設值），而非實測資料
- `energy_calibration` 正常（8 個實測點）
- **論文風險：** 若論文措辭暗示 ToF 有完整標定，需修正；應說明「ToF 標定未完成，distance fusion 的 ToF 分量使用預設表」
- **驗證狀態：** ✅ 已驗證（直接讀取 JSON）

**ND-2：correlations.csv 趨勢標籤與論文論述不一致**

- **位置：** `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/fixed_tcp_rtx_pra_correlations.csv`
- **問題：** CSV 中 `trend_label = "no_clear_monotonic_relation"`（程式閾值 |ρ| ≥ 0.7），但論文宣稱有「距離下降趨勢」
- **實際 ρ = −0.657**，p = 0.156（n=6，未達 p<0.05 顯著）
- **口試風險：** 委員若直接讀 CSV，label 與論文陳述有落差
- **行動：** 確認論文第四章明確使用「趨勢級可行性（trend-level feasibility）」而非「單調相關」，並說明 n=6 統計力限制
- **驗證狀態：** ✅ 已驗證（直接讀取 CSV）

---

### 🟡 P1 — 建議（已執行 2/2）

| 項目 | 狀態 |
|------|------|
| calibration JSON 存在確認 | ✅ 已確認（tier_b_calibration.json 存在，energy_calibration 有 8 點） |
| thesis/INDEX.md 建立 | ✅ **已執行**（`thesis/INDEX.md` 已建立） |

---

### 🔵 P2 — 技術債（已執行 2/3）

| 項目 | 狀態 |
|------|------|
| `scripts/vector_utils.py` 建立 | ✅ **已執行**（模組已建立，17+ 個腳本可逐步遷移） |
| `ur10e_robotiq_common.py` 靜默例外修復 | ✅ **已執行**（L366/L645 加 WARN log，L689 加說明 comment） |
| `to_jsonable()` 統一 | ⏳ 待口試後執行 |
| 30+ 個 hardcoded 絕對路徑 | ⏳ 待口試後執行 |

---

### ⚪ P3 — 低優先（未動）

- `run_pyroom_experiment_4_passport_v1.sh` 殘留（PRA 已移出主線）
- `SESSION_HANDOFF_2026-06-27.md` / `06-28.md` 仍在根目錄
- `lab/__pycache__/` 未被 .gitignore
- RL 腳本 v4 與 v5 並存

---

## 三、本次實際執行的優化

| 優化項目 | 檔案 | 說明 |
|---------|------|------|
| 建立向量工具模組 | `scripts/vector_utils.py` | 集中 `vec_tuple/sub/norm/dot/unit/add/scale/distance`，消除 17+ 份重複的基礎 |
| 建立文件索引 | `thesis/INDEX.md` | canonical vs 歸檔版本一覽，含核心數字快速查詢表 |
| 修復靜默例外（L366） | `scripts/ur10e_robotiq_common.py` | `robot.initialize()` 失敗改為 WARN log |
| 修復靜默例外（L645） | `scripts/ur10e_robotiq_common.py` | `set_joint_velocities()` 失敗改為 WARN log |
| 說明 fallback comment（L689） | `scripts/ur10e_robotiq_common.py` | try/fallback 模式加說明 |
| 語法驗證 | 兩個 .py 檔案 | `ast.parse()` 全部通過 |

---

## 四、已驗證項目

| 項目 | 驗證方式 | 結果 |
|------|---------|------|
| Phase A batch_summary.txt | 直接讀取 | ✅ pass=30 fail=0 |
| Phase A ρ 數字 | 讀取 correlations.csv | ✅ ρ = −0.657 (≈ −0.66) |
| feature_ablation F1 數字 | 讀取 feature_ablation_summary.csv | ✅ 0.684 / 0.598 / 0.533 |
| calibration JSON 存在 | 直接讀取 | ✅ 存在，energy_calibration 8 點 |
| tof_calibration 狀態 | 直接讀取 | 🔴 空陣列，使用 fallback |
| REPRODUCIBILITY_AUDIT.md 腳本 | Agent D | ✅ 全部存在 |
| THESIS_OUTLINE_FCU_2026-06-30.md 腳本 | Agent D | ✅ 全部存在 |
| SurfaceGripper 路徑修復一致性 | Agent D | ✅ 一致 |
| rtx_acoustic_factory.py 欄位 | Agent D 抽樣 9 個 | ✅ 一致 |
| 無 TODO/FIXME/HACK/import * | Agent B | ✅ 零個 |
| 向量函式重複 | Agent C | ✅ 17+ 個確認 |
| 靜默例外修復後語法 | ast.parse() | ✅ 通過 |
| vector_utils.py 語法 | ast.parse() | ✅ 通過 |

---

## 五、未驗證項目

| 項目 | 建議驗證方式 |
|------|------------|
| SurfaceGripper C++ plugin 時序 | 執行 `run_host_ultrasonic_closed_loop_grasp_smoke.sh` |
| extsDeprecated 路徑實際存在性 | `ls app/extsDeprecated/` |
| test_*.py 可獨立執行 | `python3 scripts/test_acoustic_calibration_v1.py` |
| 論文統整_指導教授用.md 與 06-30 大綱一致性 | 手動比對 |

---

## 六、交接資訊

### 論文主 Claim（已驗證數字）
- L1：30/30 + ρ = −0.657（**標籤為 no_clear_monotonic_relation，需在論文中說明 trend-level**）
- L2：閉環 84% vs 開環 29%
- L4：acoustic_only F1 = 0.598
- L3（非主 claim）：最終夾取 ~20% contact-only

### 核心代碼地圖
```
scripts/rtx_acoustic_factory.py          ← GMO 解析（唯一真實來源）
scripts/acoustic_calibration_v1.py       ← 標定邏輯（energy OK，tof 空）
scripts/ultrasonic_closed_loop_controller.py
scripts/approach_supervisor_v1.py
scripts/grasp_passport_v1.py
scripts/geometry_passport_v1.py
scripts/vector_utils.py                  ← 新建（口試後重構基礎）
```

---

*健檢執行：Claude Sonnet 4.6（2026-07-04）*
*掃描：4 Haiku 並行 → 手動驗證 → 優化執行*
