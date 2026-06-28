# Isaac Lab Phase 4 實作規格（Sim→Lab 展示）

**目標：** 在碩論中展示 **Isaac Sim 與 Isaac Lab 同一套管線**——重用 Passport + Factory，在動態移動目標下連續輸出聲學觀測。  
**最低成功標準：** 1 個 Isaac Lab env smoke run ≥128 steps，輸出 CSV，論文 §4.5 可引用。  
**不宣稱：** 已完成 RL 訓練、policy 收斂、實機等價。

---

## 1. 版本對齊

| 元件 | 本機現狀 | Lab 需求 |
|------|----------|----------|
| Isaac Sim | `/home/lab109/song/isaacsim6.0`（6.0 host） | Lab 需指向同一 `ISAACSIM_PATH` |
| Isaac Lab | **已安裝** `v3.0.0-beta2` | 對齊 Sim 6.0.0-rc.59 |
| Python | `venvs/isaac_acoustic_pyroom`（PyRoom 用） | Lab 通常自帶 conda/venv，與 Sim 分開 |
| 架構 | aarch64（DGX Spark） | 安裝前確認 Lab 對 ARM 支援狀態 |

**安裝參考（執行時依官方文件為準）：**

```bash
# 範例流程 — 實際以 https://isaac-sim.github.io/IsaacLab/ 為準
export ISAACSIM_PATH=/home/lab109/song/isaacsim6.0/app
git clone https://github.com/isaac-sim/IsaacLab.git /home/lab109/song/IsaacLab
cd /home/lab109/song/IsaacLab
./isaaclab.sh --install
```

安裝完成後在本文件末尾記錄實際版本與 smoke 指令。

---

## 2. 架構：重用 Sim 資產，不重寫感測

```text
isaacsim6.0/scripts/
  geometry_passport_v1.py      ← 房間、TCP、目標尺寸、邊界
  rtx_acoustic_factory.py      ← GMO 解析、early_energy、P1 驗證
  rtx_material_passport_v1.py  ← 材質 B 預設

isaacsim6.0/lab/               ← 新建（Phase 4）
  ur10_rtx_acoustic_env.py     ← Isaac Lab DirectRLEnv 或 ManagerBasedRLEnv
  moving_target_controller.py  ← 目標軌跡（直線 / 圓周 / 隨機 waypoint）
  run_lab_smoke.sh             ← headless smoke 入口
```

**原則：** Lab env 只負責 **reset / step / 目標運動 / 呼叫 Factory**；幾何與特徵定義與 Sim Phase 3 一致。

---

## 3. 環境設計：`Ur10RtxAcousticDynamicEnv`

### 3.1 場景（與 Sim 一致）

| 項目 | 值 |
|------|-----|
| Robot | UR10 `@ /World/ur10`，關節鎖定（與 fixed TCP 相同 locked joints） |
| Sensor | `/World/ur10/ee_link/official_rtx_acoustic` |
| Room | 六面牆 4.5×3.0×2.8 m |
| Target | `/World/fixed_target`，8×8×2 cm |
| Material | B（medium_absorption） |

### 3.2 移動目標（動態核心）

**Smoke 軌跡（建議先做）：** 在 sensor +X 前方 1.0–2.0 m 之間正弦往返

```python
# 概念
distance(t) = 1.5 + 0.5 * sin(2π * t / period_steps)
target_pos = target_position_from_sensor(sensor_pos, sensor_forward, distance(t))
```

| 參數 | Smoke 預設 |
|------|-----------|
| `period_steps` | 64 |
| 距離範圍 | 1.0 – 2.0 m |
| 速度 | 由軌跡隱含，不額外物理推動 |

進階（論文加分，非必須）：xy 平面圓周、或域隨機化初始相位。

### 3.3 觀測空間（Observation）

| 欄位 | 類型 | 說明 |
|------|------|------|
| `primary_sgw_early_energy` | float | 主特徵（與 Sim 一致） |
| `primary_sgw_peak` | float | 對照 |
| `gmo_valid` | bool→float | 品質 |
| `target_distance_m` | float | **Sim GT**（幾何計算，作監督標籤） |
| `target_x/y/z` | float×3 | 可選 |
| `sensor_x/y/z` | float×3 | 可選 |

**維度建議（smoke）：** 6–10 維向量，足夠餵簡單 ML demo。

### 3.4 動作空間（Action）

**Phase 4 smoke：零動作（手臂固定）**

```python
action_space = gym.spaces.Box(0, 0, shape=(0,))  # 或 Discrete(1) no-op
```

**Phase 5 擴展：** 6-DOF 關節速度或 3D 末端速度（需 Experimental UR10 / IK）。

### 3.5 獎勵（Reward）

Smoke 可全 0 或僅記錄不訓練。若要做 RL 雛形：

```text
reward = -|estimated_distance - gt_distance|  # 需估計器
# 或
reward = early_energy 信號品質 proxy（不建議當唯一獎勵）
```

碩論 smoke **不必定義 reward**。

### 3.6 Step 迴圈

```text
reset():
  載入場景、鎖 UR10、目標初始距離 = 1.0 m
  settle 40 steps

step(action):
  更新目標位置（kinematic）
  settle 10–20 sim steps
  timeline.play() + 抓 GMO（呼叫 rtx_acoustic_factory）
  計算 gt distance（sensor→target）
  寫入 row 至 episode buffer
  return obs, reward, done, info
```

**效能注意：** RTX 每 step 都抓 GMO 很慢。Smoke 可 `decimation=4`（每 4 sim step 抓 1 次 obs）。

---

## 4. 輸出與論文 §4.5

### 4.1 輸出路徑

```text
isaacsim6.0/runtime/outputs/lab_dynamic_smoke_v1/
  lab_dynamic_obs_timeseries.csv
  lab_dynamic_obs_summary.json
  lab_target_trajectory_xy.png      # 腳本後處理生成
  lab_obs_vs_gt_distance.png
```

### 4.2 CSV 欄位（與 Sim timeseries 對齊 + 動態欄位）

```
step_index, sim_time_s, target_distance_m_gt, target_x_m, target_y_m, target_z_m,
primary_sgw_early_energy, primary_sgw_peak, gmo_valid, gmo_modality,
material_condition, experiment_mode=fixed_tcp_moving_target_dynamic
```

### 4.3 論文 §4.5 可寫結論（若 smoke PASS）

- Lab env 可重用 Sim Passport 幾何與 Factory，無需重寫感測解析
- 移動目標下 `gmo_valid_rate` 維持可接受水準（待實測填數字）
- `primary_sgw_early_energy` 與 GT 距離呈可追蹤變化（待實測 ρ）
- 證明 Sim 驗證管線可延伸至 **訓練級資料生成**

---

## 5. Smoke 指令（實作後填入）

```bash
# 待 Isaac Lab 安裝完成後啟用
/home/lab109/song/isaacsim6.0/lab/run_lab_smoke.sh
```

預期腳本內容：

```bash
#!/usr/bin/env bash
set -euo pipefail
ISAACLAB_ROOT="${ISAACLAB_ROOT:-/home/lab109/song/IsaacLab}"
OUTPUT_DIR="/home/lab109/song/isaacsim6.0/runtime/outputs/lab_dynamic_smoke_v1"
"${ISAACLAB_ROOT}/isaaclab.sh" -p \
  /home/lab109/song/isaacsim6.0/lab/ur10_rtx_acoustic_env.py \
  --headless --steps 128 --output-dir "${OUTPUT_DIR}"
```

---

## 6. 與碩論 claim boundary

| 可宣稱（Lab smoke 後） | 不可宣稱 |
|------------------------|----------|
| Sim-Lab 管線連續性 | 已訓練出可用 policy |
| 動態場景連續觀測可行 | Lab obs 已驗證實機 |
| GT 距離來自模擬幾何 | GT 等於 CH201 讀值 |
| 為 SL/RL 準備資料格式 | 已完成端到端學習 |

---

## 7. 檢查清單

- [x] Isaac Lab 安裝並能 import `isaaclab`
- [x] `ur10_rtx_acoustic_env.py` smoke 128 steps
- [x] 重用 `rtx_acoustic_factory.summarize_gmo_frame()`
- [x] 128 steps smoke CSV 產出（`lab_dynamic_smoke_v1/`）
- [x] 圖4.5、圖4.6 產出
- [x] SL Sim→Lab（`lab_sl_distance_v1/`，§4.6 素材見 `THESIS_LAB_SECTIONS_2026-06-28.md`）
- [ ] 更新 `THESIS_DRAFT_FCU_v1.docx` §4.5–§4.6（正文已備，待貼 Word）
- [ ] 口試簡報加入圖3.1 Sim-Lab 架構
- [ ] Phase 5 RL smoke（見 `ISAAC_LAB_PHASE5_RL_PLAN.md`）

---

*Phase 4 的價值不是「訓練完成」，而是「證明 Sim 的科學結論能接到 Lab 的學習迴圈」。*