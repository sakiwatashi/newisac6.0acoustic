# plan.md — 可執行改善步驟
# isaacsim6.0 Acoustic Thesis Pipeline
# 健檢日期：2026-07-04

---

## 第一階段：口試前（P0 — 必須完成）

### Step 1：確認 / 補回 Phase A Canonical 摘要
**目的：** 讓口試委員可直接查詢 Phase A 結果（ρ≈−0.66）
**範圍：** `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/`

**執行步驟：**
```bash
# 方式 A：重跑（需要完整 Isaac Sim 環境，耗時）
source scripts/env_host_isolated.sh
bash scripts/run_phase3_repeatability_and_analysis.sh

# 方式 B：若有備份，直接複製回 runtime/outputs/
cp -r /path/to/backup/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1 \
      runtime/outputs/

# 確認步驟
ls runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/
cat runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/batch_summary.txt
```

**驗收標準：**
- `batch_summary.txt` 中 `pass=30 fail=0`
- `fixed_tcp_rtx_pra_correlations.csv` 存在

**適合執行者：** 主研究員（需要 Isaac Sim 環境）
**驗證狀態：** ❌ 未執行

---

### Step 2：解決 feature_ablation_summary.csv 與文件不符
**目的：** 確保 REPRODUCIBILITY_AUDIT.md 中的 `--skip-batch` 指令可驗證 F1 數字

**執行步驟：**
```bash
# 先確認 JSON 中有 F1 數字
cat runtime/outputs/physical_ai_v9_skip_lift_clean_ablation/all/policy_report.json
cat runtime/outputs/physical_ai_v9_skip_lift_clean_ablation/acoustic_only/policy_report.json
cat runtime/outputs/physical_ai_v9_skip_lift_clean_ablation/pose_only/policy_report.json
```

**若 JSON 中有 F1 數字：**
- 更新 REPRODUCIBILITY_AUDIT.md §2「Phase B/C 預期產物」表格，將路徑改為實際 JSON 路徑
- 或撰寫一個簡單腳本 `scripts/summarize_ablation.py` 從三個 JSON 產生 `feature_ablation_summary.csv`

**若 JSON 中無 F1 數字：**
- 重跑：`python3 scripts/run_physical_ai_v8_randomized_pipeline.py --batch-id physical_ai_v9_skip_lift_clean --skip-batch`

**驗收標準：**
- F1 數字（0.684 / 0.598 / 0.533）可從指定路徑驗證
- REPRODUCIBILITY_AUDIT.md 路徑正確

**適合執行者：** 主研究員（需要確認 JSON 格式）
**驗證狀態：** ❌ 未執行

---

### Step 3：確認 calibration JSON 存在
**目的：** 確保 `acoustic_calibration_v1.py` 載入的是正確標定表（非 fallback default）

**執行步驟：**
```bash
ls runtime/outputs/ur10e_dynamic_approach_calibration_v1/
cat runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json
# 確認 JSON 結構中有 energy_calibration_points 和 tof_calibration_points
```

**驗收標準：**
- `tier_b_calibration.json` 存在且包含有效標定點

**適合執行者：** Haiku（純檔案讀取任務）
**驗證狀態：** ❌ 未執行

---

### Step 4：建立 thesis/INDEX.md 明確標示 canonical 版本
**目的：** 避免口試委員使用舊版論文大綱（06-27/06-29）

**執行步驟：**
建立 `thesis/INDEX.md`，內容：
```markdown
# Thesis Document Index

## Canonical（當前版本）
- 論文大綱：THESIS_OUTLINE_FCU_2026-06-30.md
- 技術參考：TECHNICAL_REFERENCE_2026-07-03.md
- 名詞數學：CONCEPTS_AND_MATH_2026-07-03.md
- 實驗摘要：PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_2026-07-01.md

## 歸檔（舊版，請勿引用）
- THESIS_OUTLINE_FCU_2026-06-27.md（已廢棄）
- THESIS_OUTLINE_FCU_2026-06-29.md（已廢棄，含 PyRoom 主貢獻舊版）
```

**驗收標準：** `thesis/INDEX.md` 存在，canonical 版本有明確標記

**適合執行者：** Haiku（文件撰寫）
**驗證狀態：** ❌ 未執行

---

## 第二階段：口試後（P1 — 建議）

### Step 5：消除向量數學函式重複
**目的：** 減少維護負擔（17+ 個檔案各自複製 vec_*）

**執行步驟：**
1. 建立 `scripts/vector_utils.py`：
   ```python
   import math

   def vec_tuple(values): return tuple(float(values[i]) for i in range(3))
   def vec_add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
   def vec_sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
   def vec_scale(v, s): return (v[0]*s, v[1]*s, v[2]*s)
   def vec_norm(v): return math.sqrt(sum(float(x)*float(x) for x in v))
   def vec_dot(a, b): return sum(float(a[i])*float(b[i]) for i in range(3))
   def vec_unit(v):
       n = max(vec_norm(v), 1e-12)
       return (v[0]/n, v[1]/n, v[2]/n)
   def distance(a, b): return vec_norm(vec_sub(a, b))
   ```
2. 在 17 個受影響檔案中：刪除 local 定義，加入 `from vector_utils import *`（或個別 import）
3. 對每個改動的腳本執行 smoke test 確認無 NameError

**驗收標準：** `grep -r "def vec_tuple" scripts/` 只返回 `vector_utils.py`

**適合執行者：** 主模型（架構判斷）+ Haiku（批量替換）
**預計工時：** 2 小時（含測試）

---

### Step 6：統一 to_jsonable()
**目的：** 消除 13+ 份複製，減少未來序列化行為分歧

**執行步驟：**
1. 在 `vector_utils.py`（或新建 `script_utils.py`）中加入統一版本
2. 逐一比對各複製版本的差異，確認最完整的版本
3. 替換 13 個檔案的 local 定義

**驗收標準：** `grep -r "def to_jsonable" scripts/` 只返回一個檔案

**適合執行者：** Haiku（機械性替換）+ 主模型（版本差異判斷）

---

### Step 7：修復 7 個靜默例外
**目的：** 讓失敗可見，便於 debug

**執行步驟：**
對每個 `except Exception: pass`，改為：
```python
except Exception as e:
    print(f"WARN [{__file__}:{lineno}]: {e}", flush=True)
```

**驗收標準：** 若機器人初始化失敗，有可見輸出

**適合執行者：** Haiku（機械性替換）

---

### Step 8：用相對路徑替換 hardcoded 絕對路徑
**目的：** 讓專案可在其他機器執行

**執行步驟：**
每個含 `/home/lab109/song/isaacsim6.0/` 的檔案，改為：
```python
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "runtime" / "outputs" / "xxx"
```

**優先：** `acoustic_calibration_v1.py:13`（影響標定正確性）

**驗收標準：** `grep -r "/home/lab109" scripts/` 返回 0 結果

**適合執行者：** Haiku（文字替換）

---

## 第三階段：長期（P3 — 可選）

### Step 9：lab/ 目錄清理
- 移除 `__pycache__/`（`.gitignore` 添加 `lab/__pycache__/`）
- 清理 `run_rl_distance_in_sim_long_v4.sh`（若 v5 為最終版）
- 確認哪個 RL 腳本是附錄實驗的 canonical 版本

### Step 10：舊根目錄文件整理
- `SESSION_HANDOFF_2026-06-27.md`、`06-28.md` 移至 `thesis/archive/`
- `THESIS_CONTENT_2026-06-27.md` 移至 `thesis/archive/`
- `CURRENT_HOST_STATUS.md` 更新或歸檔

### Step 11：確認 extsDeprecated 路徑
- 確認 `app/extsDeprecated/isaacsim.robot_motion.motion_generation/` 是否在 Isaac Sim 6.0 中存在
- 若不存在，IK 腳本需要更新擴充路徑

---

## 執行優先矩陣

| Step | 優先級 | 影響 | 難度 | 執行者 |
|------|--------|------|------|--------|
| 1: Phase A 摘要補回 | P0 🔴 | 口試可驗證 | 中（需 Isaac Sim） | 主研究員 |
| 2: ablation CSV 問題 | P0 🔴 | 口試可驗證 | 低（讀 JSON） | Haiku |
| 3: calibration JSON 確認 | P1 🟡 | 標定正確性 | 低（讀檔） | Haiku |
| 4: thesis/INDEX.md | P1 🟡 | 文件導覽 | 低（撰文） | Haiku |
| 5: vec_* 統一 | P2 🔵 | 維護性 | 中 | 主模型+Haiku |
| 6: to_jsonable 統一 | P2 🔵 | 維護性 | 中 | Haiku |
| 7: 修復靜默例外 | P2 🔵 | 可除錯性 | 低 | Haiku |
| 8: 相對路徑 | P3 ⚪ | 移植性 | 低 | Haiku |
| 9-11: 長期清理 | P3 ⚪ | 整潔 | 低 | Haiku |
