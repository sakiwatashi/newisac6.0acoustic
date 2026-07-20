# Isaac Sim 6.0 · RTX Acoustic · UR10e 聲學回授研究管線（V2 正典）

**逢甲大學 · 電聲碩士學位學程**  
指導教授：蔡鈺鼎 教授 · 研究生：宋思遠  

**論文題旨（現用）：** Isaac Sim 機械手臂超音波感測回授接近之模擬驗證  
（包絡優先 → 三臂消融閉環 → 對位夾取 → D4 雙軌延伸）

**定位：** 模擬內**可行性 + 實驗效度**管線，**非**部署級測距、**非**物理摩擦夾持已驗證、**非** CH201 波形等價。

**Git 追蹤 remote（本機 `main`）：** `newisac` →  
`https://github.com/sakiwatashi/newisac6.0acoustic.git`  

> 論文 Word（`thesis/THESIS_DRAFT_FCU_v2.docx`）以本機為準，**預設不隨日常 push 更新公開 repo**。  
> 訓練權重 `runtime/outputs/**/model_*.pt` **不進 git**（見 `.gitignore`）。

---

## 現況一句話（2026-07-20）

| 階段 | 狀態 |
|------|------|
| V2 主線 S1→S2→D1→D1.5→D2→D3（r3 正典） | **完成、判準全綠（本機 canon 數據）** |
| D4 Track A 狀態機三臂 + weld 邊界 | **完成** |
| D4 Track B PPO + 消融 + SM hookup | **完成（權重本機）** |
| D4 同場景策略串聯 n=90 | **完成** |
| GUI 平行入口（不覆寫 headless） | **程式已就緒** |
| README 對齊 V2／D4 | **本檔** |

---

## 研究邏輯順序（勿與第五章寫作順序混淆）

```text
S1 感測包絡（52 條件格點，非地板地磚）
 → S2 距離編碼／datasheet
 → D1 未掛臂閉環三臂
 → D1.5 腕載 UR10e 三臂（接近主結果 r≈0.9856）
 → D2 五視點多點定位 + 二維閉環
 → D3 對位夾取 + 接觸觸發附著升舉（正典 r3：對位 80% vs 盲 33%）
 → D4 執行器／摩擦負結果／PPO／同場景串聯（不取代 r3）
```

第五章正文為敘事可先寫 D3 再寫 D2；**邏輯順序以上表為準**。

---

## 快速導覽

| 路徑 | 內容 |
|------|------|
| [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) | **最新交接（先讀）** |
| [`docs/plan_v2/reports/`](docs/plan_v2/reports/) | 各實驗正式報告 |
| [`docs/plan_v2/METHOD_LITERATURE_MAP.md`](docs/plan_v2/METHOD_LITERATURE_MAP.md) | 方法↔文獻一頁表 |
| [`docs/plan_v2/EXPERIMENT_MATH_LITERATURE_GROUNDING.md`](docs/plan_v2/EXPERIMENT_MATH_LITERATURE_GROUNDING.md) | 公式×文獻詳版 |
| [`docs/plan_v2/DEFENSE_QA_PREP.md`](docs/plan_v2/DEFENSE_QA_PREP.md) | 口試 Q&A |
| [`docs/plan_v2/GUI_EXPERIMENT_COMMANDS.md`](docs/plan_v2/GUI_EXPERIMENT_COMMANDS.md) | **GUI 指令對照** |
| [`docs/WPM_EXPERIMENT_RULES.md`](docs/WPM_EXPERIMENT_RULES.md) | GMO／WPM 工程鐵律 |
| [`runtime/run_v2_*.sh`](runtime/) | **Headless 正式實驗入口** |
| [`runtime/run_v2_*_gui.sh`](runtime/) | **GUI 平行入口（smoke 預設）** |
| [`scripts/gui_formal_exec.py`](scripts/gui_formal_exec.py) | 正式 runner → GUI 轉寫啟動器 |
| [`lab/run_d4_*.sh`](lab/) | D4 PPO 訓練／評估／hookup |
| [`scripts/demo_gui_showcase.py`](scripts/demo_gui_showcase.py) | 已驗證 GUI 展示（非裁決） |
| [`thesis/`](thesis/) | 論文資產（docx 以本機為準） |

---

## 環境

- Isaac Sim **6.0.0-rc.59** host（`app/` 不進 repo）
- GPU + RTX Acoustic（`isaacsim.sensors.experimental.rtx`）
- Experience：`${APP_ROOT}/apps/isaacsim.exp.base.python.kit`

```bash
cd /path/to/isaacsim6.0
source scripts/env_host_isolated.sh
```

---

## Headless 正式入口（裁決用）

```bash
# 感測
bash runtime/run_v2_s1_envelope.sh          # S1 包絡 52 cells
bash runtime/run_v2_s2_datasheet.sh         # S2 datasheet

# 閉環接近
bash runtime/run_v2_d1_approach.sh          # D1 未掛臂
bash runtime/run_v2_d15_arm_approach.sh     # D1.5 腕載主結果
bash runtime/run_v2_d2v2_formal.sh          # D2 三臂

# 閘門與夾取
bash runtime/run_v2_d3_gates.sh             # D3.0 gates
bash runtime/run_v2_d3_grasp.sh             # D3 夾取（正典目錄勿覆寫 r3）

# D4
bash runtime/run_v2_d4_sm_grasp.sh          # Track A SM
bash lab/run_d4_ppo_train.sh                # Track B 訓練（權重落本機 outputs）
bash lab/run_d4_ppo_eval.sh                 # Track B 評估
bash runtime/run_v2_d4_same_scene_policy.sh # 同場景 n=90
bash lab/run_d4_sm_policy_hookup.sh         # SM 掛接
```

**禁止覆寫：** `runtime/outputs/v2_d3_grasp_r3`（及正式 n30 正典目錄）。

---

## GUI 平行入口（展示／錄影；預設 smoke）

不修改 headless 原檔；經 `scripts/gui_formal_exec.py` 開窗、補光、開始前約 10 s／結束後約 15 s。

```bash
bash runtime/run_v2_s1_envelope_gui.sh
bash runtime/run_v2_d15_arm_approach_gui.sh
bash runtime/run_v2_d3_grasp_gui.sh
# 完整對照見 docs/plan_v2/GUI_EXPERIMENT_COMMANDS.md

# 展示 demo（非正式裁決）
./app/python.sh scripts/demo_gui_showcase.py
```

`FORMAL=1` 可跑與 headless 同規模（很慢）。S1 GUI 場景幾乎只有感測器+小方塊屬正常。

---

## 宣稱邊界（摘要）

| 可支持 | 不支持 |
|--------|--------|
| 包絡內純聲學 1D 閉環；盲走失能 | 厘米級實機部署測距 |
| D3 r3 聲學對位優於盲走 | 物理摩擦夾持已驗證 |
| 接觸觸發附著後升舉（分層報） | 對位×升舉合成假 e2e 總成功率 |
| D2 合成側向定位（誤差仍＞夾取窗） | 二維定位後再夾取已完成 |
| D4 同場景串聯接口（約 77%／74%） | pure d̂ 獎勵 end-to-end 成功 |
| 效度框架（三臂／預註冊／稽核） | 「必須聽音」全稱命題（Lab 消融） |

細節：`docs/plan_v2/reports/`、論文 §6.2（本機 docx）。

---

## 本機 canon 數據（多半 gitignore）

| 內容 | 典型路徑 |
|------|----------|
| D3 正典 | `runtime/outputs/v2_d3_grasp_r3/` |
| D4 SM n30 | `runtime/outputs/v2_d4_sm_grasp_n30/` 等 |
| D4 PPO 權重 | `.../v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt` |
| 同場景 n90 | `runtime/outputs/v2_d4_same_scene_policy_n90/` |

**Clone 後不會自動有 `.pt` 與完整 outputs**——需本機訓練或拷貝。

---

## 舊管線（考古，非 V2 正典入口）

`physical_ai_v9_*`、`run_host_ultrasonic_closed_loop_*`、Phase A fixed_tcp 等仍可能在 repo／磁碟，**論文主宣稱以 V2 `run_v2_*` 與 D3 r3／D4 報告為準**。

---

## 授權

學術用途請依學校與指導教授規範引用。Isaac Sim／Isaac Lab 為 NVIDIA 產品，遵守其授權。

GitHub: [@sakiwatashi](https://github.com/sakiwatashi) · 主 remote：`newisac6.0acoustic`
