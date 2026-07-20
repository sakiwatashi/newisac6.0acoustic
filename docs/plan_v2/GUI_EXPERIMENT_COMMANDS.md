# GUI 實驗指令（平行於 headless 正式版，不覆蓋原碼）

> **原則**
> 1. 正式 headless 腳本 / shell **一律不改**。
> 2. GUI 走 `scripts/gui_formal_exec.py`：讀取原 runner → 記憶體轉寫 → 暫存 `runtime/cache/gui_formal/` 後執行。
> 3. 轉寫內容（對齊已驗證的 `demo_gui_showcase.py` / fixed-TCP `--gui`）：
>    - `SimulationApp({"headless": True})` → `{"headless": False, "hide_ui": False}`
>    - fixed timestep + 嘗試開啟 present（避免黑窗）
>    - `render=False` → `render=True`
>    - **viewport 就緒 + 鏡頭 + Camera Light**（否則畫面全黑像「沒開窗」）
>    - **pre-run preview**（預設 **10s**）與 **post-run hold**（預設 **15s**）— 正式 runner 幾秒就 close，不 hold 會一閃即關
>    - Lab：`parser.set_defaults(headless=True)` → `False`
> 4. 輸出目錄用 `*_gui`，**不寫進** 正式 canon（`v2_d3_grasp_r3`、`v2_d4_sm_grasp_n30` 等）。
> 5. 預設 **smoke**（可看、可錄）；`FORMAL=1` 與 headless 同規模。
>
> **2026-07-19 根因**：S1 smoke 已是 headless=False（kit 參數無 `--no-window`），但 ~4s 結束並 close、無 Camera Light → 看起來像沒開畫面。

唯一已驗證可直接開窗的 demo（邏輯展示，非正式裁決）：

```bash
./app/python.sh scripts/demo_gui_showcase.py
```

---

## 快速一覽（建議先 smoke）

| 實驗 | GUI 指令（預設 smoke） | Headless 正式（不動） |
|------|------------------------|------------------------|
| S1 包絡 | `bash runtime/run_v2_s1_envelope_gui.sh` | `bash runtime/run_v2_s1_envelope.sh` |
| S2 datasheet | `bash runtime/run_v2_s2_datasheet_gui.sh` | `bash runtime/run_v2_s2_datasheet.sh` |
| D1 approach | `bash runtime/run_v2_d1_approach_gui.sh` | `bash runtime/run_v2_d1_approach.sh` |
| D1.5 arm approach | `bash runtime/run_v2_d15_arm_approach_gui.sh` | `bash runtime/run_v2_d15_arm_approach.sh` |
| D2 multilateration | `bash runtime/run_v2_d2v2_formal_gui.sh` | `bash runtime/run_v2_d2v2_formal.sh` |
| D3 gates | `bash runtime/run_v2_d3_gates_gui.sh` | `bash runtime/run_v2_d3_gates.sh` |
| D3 grasp | `bash runtime/run_v2_d3_grasp_gui.sh` | `bash runtime/run_v2_d3_grasp.sh` |
| D4 SM grasp | `bash runtime/run_v2_d4_sm_grasp_gui.sh` | `bash runtime/run_v2_d4_sm_grasp.sh` |
| D4 same-scene policy | `bash runtime/run_v2_d4_same_scene_policy_gui.sh` | `bash runtime/run_v2_d4_same_scene_policy.sh` |
| D4-B PPO eval | `bash lab/run_d4_ppo_eval_gui.sh` | `bash lab/run_d4_ppo_eval.sh` |
| D4 SM policy hookup | `bash lab/run_d4_sm_policy_hookup_gui.sh` | `bash lab/run_d4_sm_policy_hookup.sh` |

同一實驗全量（與 headless 同參數規模）：

```bash
FORMAL=1 bash runtime/run_v2_<name>_gui.sh
```

---

## 底層直接呼叫（進階）

```bash
# 任意正式 runner
./app/python.sh scripts/gui_formal_exec.py scripts/<formal_runner>.py [該 runner 原本的參數...]

# 例：D3 closed smoke
./app/python.sh scripts/gui_formal_exec.py scripts/d3_grasp_runner.py \
  --mode closed --output-dir runtime/outputs/v2_d3_grasp_gui --smoke
```

D4 Track A 編排（subprocess 也走 GUI）：

```bash
python3 scripts/d4_acoustic_grasp_sm_runner_gui.py \
  --mode closed --output-dir runtime/outputs/v2_d4_sm_grasp_gui --smoke
```

---

## 各階段說明

### S1 — 感測包絡（`paired_capture_runner`）

```bash
# smoke：第一個 cell
bash runtime/run_v2_s1_envelope_gui.sh

# 指定 cell
CELL_ID=<cell_id> bash runtime/run_v2_s1_envelope_gui.sh

# 全 52 cells + analyze
FORMAL=1 bash runtime/run_v2_s1_envelope_gui.sh
```

輸出：`runtime/outputs/v2_s1_envelope_gui/`

### S2 — datasheet

```bash
bash runtime/run_v2_s2_datasheet_gui.sh          # distance p1
FORMAL=1 bash runtime/run_v2_s2_datasheet_gui.sh  # 全 sweep + analyze
```

### D1 / D1.5 — closed-loop approach

```bash
bash runtime/run_v2_d1_approach_gui.sh                 # closed n=2
MODE=blind N_EPISODES=3 bash runtime/run_v2_d1_approach_gui.sh
FORMAL=1 bash runtime/run_v2_d1_approach_gui.sh       # probe + 三臂 n=30

bash runtime/run_v2_d15_arm_approach_gui.sh
FORMAL=1 bash runtime/run_v2_d15_arm_approach_gui.sh
```

### D2 — 2D multilateration

```bash
bash runtime/run_v2_d2v2_formal_gui.sh            # closed --smoke
ARM=blind bash runtime/run_v2_d2v2_formal_gui.sh
FORMAL=1 bash runtime/run_v2_d2v2_formal_gui.sh  # closed/blind/open
```

### D3 gates / grasp

```bash
bash runtime/run_v2_d3_gates_gui.sh               # g1 smoke
FORMAL=1 bash runtime/run_v2_d3_gates_gui.sh     # g1/g2/m3b_*

bash runtime/run_v2_d3_grasp_gui.sh               # closed --smoke
MODE=open bash runtime/run_v2_d3_grasp_gui.sh
FORMAL=1 bash runtime/run_v2_d3_grasp_gui.sh     # g3 + 三臂
```

### D4

```bash
# Track A SM（weld-on-stall，與 headless 同實驗）
bash runtime/run_v2_d4_sm_grasp_gui.sh
FORMAL=1 bash runtime/run_v2_d4_sm_grasp_gui.sh

# same-scene B policy @ d3 場景
bash runtime/run_v2_d4_same_scene_policy_gui.sh
N_EP=5 bash runtime/run_v2_d4_same_scene_policy_gui.sh
FORMAL=1 bash runtime/run_v2_d4_same_scene_policy_gui.sh   # n=90

# Track B PPO episode eval（Isaac Lab viewport）
bash lab/run_d4_ppo_eval_gui.sh
EPISODES=5 CHECKPOINT=runtime/outputs/.../model_49.pt bash lab/run_d4_ppo_eval_gui.sh

# SM policy hookup
bash lab/run_d4_sm_policy_hookup_gui.sh
```

---

## 新增檔案清單（全部為新檔，不覆蓋）

| 檔案 | 角色 |
|------|------|
| `scripts/gui_formal_exec.py` | 共用 GUI 轉寫啟動器 |
| `scripts/d4_acoustic_grasp_sm_runner_gui.py` | D4 SM 編排 GUI 版 |
| `runtime/run_v2_*_gui.sh` | S1–D4 各實驗 shell |
| `lab/run_d4_ppo_eval_gui.sh` | Lab PPO eval GUI |
| `lab/run_d4_sm_policy_hookup_gui.sh` | Lab hookup GUI |
| `docs/plan_v2/GUI_EXPERIMENT_COMMANDS.md` | 本說明 |

暫存轉寫產物：`runtime/cache/gui_formal/*_gui_*.py`（可刪，下次重產）。

---

## 注意

- **需要有顯示**：必須在能看到 `DISPLAY` 的桌面跑（本機 log 為 `DISPLAY=:0`）。SSH 且沒有轉到同一 X server 時，視窗會開在主機螢幕上，你的終端機看不到。
- 環境變數（**預設已是開始 10s / 結束 15s**）：
  - `GUI_PREVIEW_S=10` — 場景建好後、量測前等待（秒）
  - `GUI_HOLD_S=15` — 實驗結束後等待（秒）；`0` 關閉
  - `GUI_FOCUS=1.0,0.0,0.55` — 鏡頭 look-at（S1 預設 `0.15,0,0.65`）
  - `GUI_CAM_DIST=2.5` — 鏡頭距離（S1 預設 `0.55`，小方塊才看得到）
- **S1 畫面說明**：正式 cell 幾乎是空場景（感測器 + 4cm 方塊，無手臂）；`without_target` 會刪方塊。若只見黑底網格＋方塊一閃，是場景內容問題，不是沒開窗。GUI 會補光、拉近鏡頭、在方塊還在時等 10s，結束後放一顆**僅供觀看**的橘色 display cube。
- **不要**把 `gui_formal_exec` 改成預設 headless 路徑；正式裁決結果仍以 headless 輸出為準。
- GUI smoke 數字可用於錄影 / 截圖；論文表內 n=30 / n=90 以 headless 正式 run 為準。
- 已驗證 demo：`scripts/demo_gui_showcase.py`（非裁決實驗）。

### 建議重測 S1（應先看到「Isaac Sim Python」視窗）

```bash
rm -rf runtime/outputs/v2_s1_envelope_gui/A_d0.15_z0.04_p0_cnone
bash runtime/run_v2_s1_envelope_gui.sh
# 預設：開始前等 10s、結束後等 15s（可用 GUI_PREVIEW_S / GUI_HOLD_S 覆寫）
```

預期 log 關鍵行：

- `[gui_formal_exec] SimulationApp headless=False hide_ui=False; ... DISPLAY=':0'`
- `[gui_formal_exec] Camera Light ON (boot)`
- `[gui_formal_exec] pre-run preview (10s): keeping Isaac Sim window open for 10s…`
- 實驗結果列印後：`post-run hold (15s): keeping Isaac Sim window open for 15s…`
