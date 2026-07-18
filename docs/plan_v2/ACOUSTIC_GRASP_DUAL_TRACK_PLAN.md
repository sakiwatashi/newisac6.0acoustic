# 雙軌計畫：聲學對位 + 夾取執行器（狀態機｜PPO）

| 欄位 | 內容 |
|------|------|
| **建立** | 2026-07-16 |
| **狀態** | 開工中（骨架落地） |
| **原則** | 不覆蓋 D3 r3 正典；新目錄新預註冊；oracle 永不入控制；鐵律 1–8 全守 |
| **上游** | `docs/HANDOFF_CURRENT.md`；D3 notes（摩擦失敗史）；`lab/isaaclab_tasks_ext/ur10_rtx_acoustic_distance/` |

---

## 0. 一句話目標

把「夾取」從 D3 的 weld 工程替代，升級成：

1. **軌道 A（快路徑）**：聲學**規則**對位 + **連續物理夾取狀態機**（官方 lift SM 思路，觀測改聲學估位）。  
2. **軌道 B（完整路徑）**：Isaac Lab **PPO**，觀測＝聲學+本體，動作＝臂/爪，獎勵＝對位→接觸→升舉。

兩者共用：聲學特徵管線、成功分層指標、三臂／消融框架。

---

## 1. 為什麼分兩軌

| | 軌道 A 狀態機 | 軌道 B PPO |
|--|---------------|------------|
| 目的 | 先證明「執行器棧換對就能真夾／真抬」 | 證明「純聲學觀測可學端到端」 |
| 依賴 | 控制工程 | A 的物理棧可跑 + GPU 長訓 |
| 失敗時 | 歸因到對位 or 物理 | 歸因到探索／獎勵／觀測 |
| 論文位置 | 延伸實驗／工程複驗 | 第六章未來工作落地 or 附錄 |

**順序：A 先冒煙可跑 → B env 骨架與 smoke → A 正式三臂 → B 長訓。**

---

## 2. 共用鐵律與成功定義（預註冊）

### 2.1 不可違反

1. 控制路徑**禁止**讀 `target_x/y/z`（oracle 只寫 log）。  
2. 聲學估距／估位僅來自 peak→OLS（或等價自校），與 D3 同源。  
3. 新實驗一律新目錄：`runtime/outputs/v2_d4_*`。  
4. 主指標**分層**，禁止單一「總成功率」當唯一宣稱：  
   - **對位** \(\lvert x_{\mathrm{grasp}}-x_{\mathrm{tgt}}\rvert \le 0.02\,\mathrm{m}\)  
   - **升舉** \(z_{\mathrm{gain}}\ge 0.05\,\mathrm{m}\) 保持 ≥0.5 s  
   - **P(升舉|對位)** 記錄  
5. 消融至少一條：  
   - **blind**：估距作廢（+∞）或聲學觀測置零  
   - （B 另加）隨機 policy baseline  

### 2.2 預註冊判準（草案，正式跑前鎖死在 runner header）

**軌道 A（狀態機三臂，各 n=30，同 seed 目標組）：**

| ID | 判準 | 門檻 |
|----|------|------|
| A1 | closed 對位率 > blind | 且 Fisher one-sided p < 0.05 |
| A2 | closed \(r(\mathrm{grasp}_x,\mathrm{target}_x)\ge 0.9\) | |
| A3 | closed **無 weld** 時 P(升舉\|對位) ≥ 0.70 **或** 相對 D3 r3 的 weld 路徑不更差且姿態乾淨 | 二選一在 g0 閘門後鎖 |
| A4 | 三臂姿態／IK 無效回合 = 0 | |

**軌道 B（PPO，訓練後評估 n≥30）：**

| ID | 判準 | 門檻 |
|----|------|------|
| B1 | 聲學 policy 升舉成功率 > blind-obs policy | p < 0.05（或 95% bootstrap CI 不重疊） |
| B2 | 評估時 obs **不含**物體真值 | 靜態檢查 + 單元測試 |
| B3 | 對位率 ≥ 規則 baseline 的 90% **或** 升舉率嚴格優於規則 | 先鎖「不犧牲對位亂抬」 |

> A3 的「無 weld」是本計畫核心增益；若 g0 證明本資產仍無法摩擦保持，則 A 降級為「連續物理 + 接觸觸發附著（仍非摩擦宣稱）」並如實記錄——**不回改 D3 r3**。

### 2.3 閘門 g0（兩軌共用，先跑）

在寫死三臂／長訓前：

1. **執行器冒煙**：固定 oracle 對位進窗 → 僅測 close+lift（允許暫時 oracle **只在 g0**）→ 摩擦能否抬？  
2. **聲學進窗冒煙**：規則聲學對位 → 進窗率。  
3. 兩者 AND 才進 A 正式三臂；g0 摩擦 FAIL → 改執行器參數或 Franka 對照，不直接開 B 長訓。

---

## 3. 架構

```
                    ┌─────────────────────┐
   GMO / peak       │  acoustic_features  │  (shared)
   OLS calib        └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                                 ▼
     ┌─────────────────┐              ┌──────────────────┐
     │ Track A: FSM    │              │ Track B: PPO     │
     │ approach/align  │              │ obs=ac+joint     │
     │ → descend/close │              │ act=Δpose+grip   │
     │ → lift/hold     │              │ reward shaped    │
     └────────┬────────┘              └────────┬─────────┘
              │                                 │
              └────────────┬────────────────────┘
                           ▼
              continuous physics gripper
              (Lab Articulation / no big teleport)
                           │
                           ▼
              metrics: align / lift / ablation
              runtime/outputs/v2_d4_*
```

### 3.1 與現況對接

| 現況 | 角色 |
|------|------|
| `scripts/d3_grasp_runner.py` | 對位／三臂協議參考；**不修改**正典邏輯當默認 |
| `lab/.../ur10_rtx_acoustic_distance/` | B 的 GMO obs / DirectRL 範本 |
| `IsaacLab/.../lift_cube_sm.py` | A 的狀態機狀態名與時序參考 |
| `scripts/ur10e_robotiq_common.py` | 手臂／爪 runtime 白名單 |

---

## 4. 目錄與產物

```
docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md   # 本檔
docs/plan_v2/d4/
  decisions.md
  notes.md
  risks.md
lab/isaaclab_tasks_ext/ur10_rtx_acoustic_grasp/ # Track B env
scripts/d4_g0_executor_smoke.py                 # g0 執行器
scripts/d4_acoustic_grasp_sm_runner.py          # Track A
scripts/analyze_d4_sm_grasp.py
lab/train_rl_acoustic_grasp.py                  # Track B entry
lab/run_d4_*.sh
runtime/outputs/v2_d4_g0_executor/
runtime/outputs/v2_d4_sm_grasp/                 # A formal
runtime/outputs/v2_d4_ppo_grasp/                # B
```

---

## 5. 時程（可中斷）

| 步 | 內容 | 產出 | 預估 |
|----|------|------|------|
| **0** | 計畫 + 骨架 + 註冊入口 | 本檔 + 空模組可 import | ✅ 本日 |
| **1** | g0 執行器冒煙（oracle 進窗） | adjudication.json | 0.5–1 日 GPU |
| **2** | Track A 狀態機單臂 closed smoke | episodes.csv | 1 日 |
| **3** | Track A 三臂 + analyzer | 四條 ADJUDICATION | 1–2 日 |
| **4** | Track B env：obs/act/reward 單元測試（無長訓） | gym register + smoke 數步 | 1 日 |
| **5** | Track B PPO 短訓 smoke → 長訓 | checkpoint + eval | 2–5 日 GPU |
| **6** | 報告 + 是否入論文附錄（教授拍板） | `reports/D4_*.md` | 0.5 日 |

每步結束可乾淨交接。

---

## 6. 軌道 A 狀態機規格

```
REST
  → ACOUSTIC_APPROACH   # 水平前進，d̂_xy > standoff
  → ACOUSTIC_ALIGN_STOP # d̂_xy ≤ standoff
  → DESCEND             # 連續 IK/關節小步下降（非 teleport 巨步）
  → CLOSE               # gripper effort/position，等接觸或 timeout
  → LIFT                # 連續上升 0.10 m
  → HOLD                # ≥0.5 s，讀 z_gain
  → DONE
```

- **blind**：ACOUSTIC_* 階段永不滿足 standoff（d̂=∞）→ 走廊末端再嘗試固定 open-loop 序列（與 D3 對齊）。  
- **open**：無量測，固定步數推進後同一 DESCEND/CLOSE/LIFT。  
- 預設 **嘗試真摩擦**；若 g0 失敗，開關 `--weld-on-stall` 僅作對照臂，主表分欄。

---

## 7. 軌道 B PPO 規格

### 觀測（禁止物體 xyz）

```
[ early_energy_scaled, peak_scaled, gmo_valid,
  d_hat_xy or peak_raw,  # 二選一，header 鎖
  q_ee_related..., gripper_open,
  # 可選：上一動 action
]
```

靜態 assert：obs 維度表不含 `target_*`。

### 動作

```
Δx (或 forward speed), Δz, gripper_cmd ∈ [-1,1]
```

初期可 **1-DOF 走廊 + gripper**（降維易訓），再擴 2D。

### 獎勵（草案）

```
r = -w1 * |d_hat - standoff|_+          # 接近
  - w2 * align_err_log_only_shaping?    # 謹慎：對位 shaping 勿用 oracle
  + w3 * contact_bonus
  + w4 * lift_height
  - w5 * drop / table_penetration
  - w6 * action_rate
```

**對位 shaping 不得用 oracle 位置**；可用「聲學 standoff 達成」與「接觸力／指關節 stall」。

### 訓練

- `num_envs=1` 若 GMO 仍單例（與 distance env 同）；或 GMO 降頻 + 並行僅物理。  
- rsl_rl PPO，延續 `agents/rsl_rl_ppo_cfg.py` 風格。  
- 評估：固定 seed 目標集 vs blind-obs。

---

## 8. 風險

| ID | 風險 | 緩解 |
|----|------|------|
| R1 | 摩擦仍不可用 | g0 先驗；Franka/DexCube 對照；weld 僅對照 |
| R2 | GMO 太慢無法訓 PPO | 降 capture 頻率；先 peak 緩存；規則特徵 |
| R3 | 近場 0.32 m 無聲學 | 狀態機最後開環；PPO 獎勵分開 near-field |
| R4 | 與 D3 結果混淆 | 目錄／文案強制 v2_d4；r3 只讀 |
| R5 | Lab 與 Sim runner 雙棧 | 共用 `rtx_acoustic_factory` / passport；單一校正源 |

---

## 9. 今日開工清單（步 0）

- [x] 本計畫檔  
- [x] `docs/plan_v2/d4/{decisions,notes,risks}.md`  
- [x] Track A runner + analyzer（self-test）  
- [x] Track B package 骨架（cfg/env/register + 單元測試）  
- [x] shell 入口 `runtime/run_v2_d4_*.sh`  
- [x] 更新 `docs/HANDOFF_CURRENT.md` 增量一節  

下一步 GPU：**g0 執行器冒煙** → A smoke 三臂 → 正式跑。

---

## 10. 給接手的一句話

> D4 = 聲學仍負責「走到窗內」；夾取改走連續物理執行器。A 用狀態機快速驗證執行器，B 用 PPO 學同一任務。D3 r3 不動。
