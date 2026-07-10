# D3 執行計畫(粒度:Opus/Sonnet 照做即可)

> 每步附驗收。規格權威:`docs/plan_v2/M3_D3_DESIGN_2026-07-10.md` + `docs/plan_v2/d3/decisions.md`。
> 執行方式:GPU 腳本一律 `./app/python.sh <script>`(repo 根目錄);離線分析 `python3`。
> 中斷點:每步產物落盤即可交接;續作先讀本檔 + notes.md。

## 步 1:包 A — `scripts/d3_gates_runner.py` + `runtime/run_v2_d3_gates.sh` 【sonnet】

骨架:**複製 `scripts/d15_arm_approach_runner.py`**(boot 順序、`_buf` writer、`_extract_frame`、`_measure_block/_measure_point`、桌+臂場景、感測器掛載修正變換、IK 移臂),改動:

1. **掛真夾爪**:把 `_select_bare_arm_variant` 替換為選 `ur10e_robotiq_common.GRIPPER_VARIANT`(同 variant-set 機制,見 ur10e_robotiq_common.py:390-392)。夾爪掛上後感測器掛載/修正變換照舊(0.25 m 前伸本來就是為避開指尖聲影設計的)。
2. **目標 = bar**:Cube prim,`scales=[[0.06, 0.06, 0.12]]`,置桌面(中心 z = 桌頂+0.06)。桌與 D1.5 相同。
3. **四個 mode**(`--mode`,單 session 單 mode;shell 依序呼叫):
   - `g1`:手臂停在走廊起始姿態(D1.5 的 start pose)。bar 依序放 3D 距離 {0.5, 0.8, 1.1} m(移 bar 用 xformOp:translate,已驗證);每距離做 paired capture:with → noise_ref → RemovePrim → without → 重建。SNR 公式照抄 paired_capture_runner.py(snr_peak/snr_energy)。輸出 `gates_g1.json` + waveforms/。
   - `g2`:bar 掃 10 點(0.40–1.10 m 等距),每點 settle 40 + 2×12 幀 block(照 s2 的 drift 稽核);記 peak_sample_idx、true_distance_3d_m。輸出 `g2_points.csv` + waveforms/。
   - `m3b_target`:同 g2 但 13 點(0.40–1.00 m 等距 0.05),感測器固定。輸出 `m3b_target_points.csv`。
   - `m3b_sensor`:bar 固定於 x=1.30;手臂載感測器掃 13 個 x 位置使 3D 距離集合與 m3b_target 相同;每步姿態/位姿稽核照 D1.5。輸出 `m3b_sensor_points.csv`。
4. Header 必含五鐵律逐條(照 d15 樣式)+ 預註冊判準原文(g1: 全部 SNR_peak>10;g2: r≥0.95;m3b: |Δslope|≤2×合併SE)。
5. 判準**只寫不算**——裁定由步 2 主 agent 離線算(鐵律 3 分權慣例)。
6. shell:四 mode 依序、每 mode tee log、任一 mode 崩潰 ABORT 並印診斷;輸出根 `runtime/outputs/v2_d3_gates/`。

**驗收**(sub-agent 自查,主 agent 複核):
- [ ] `python3 -m py_compile scripts/d3_gates_runner.py` 過
- [ ] GPU smoke:`./app/python.sh scripts/d3_gates_runner.py --mode g1 --smoke`(--smoke = 只跑 1 個距離、n_measure 4)正常結束,gates_g1.json 落盤、含 3 條件波形 npy、夾爪 variant log 行(`Set Gripper variant=...`)
- [ ] smoke 的 sensor 位姿自驗行(z=0.65±2cm、前向軸水平 ±5°)出現且通過
- [ ] 不改任何既有檔案(git status 只多新檔)

## 步 2:跑 gates + 裁定 【主 agent】

```bash
bash runtime/run_v2_d3_gates.sh   # 全四 mode,估 <15 分鐘 GPU
```
- 離線算:g1 三距 SNR、g2 OLS(r、slope、SE)、m3b 兩斜率差 vs 2×SE。
- **裁定 g1**:全過 → 續;有失格 → 走 D-3 備援階梯(bar 加深→加高),重跑 g1。
- **裁定 g2**:r≥0.95 → 產出 bar 專用校正(slope/intercept 落 `bar_calibration.json`,D3 控制唯一來源);不過 → 檢查波形再議。
- **裁定 M3b**:寫進 notes.md;若 mover 效應顯著 → D3 改用 m3b_sensor 的斜率當校正(in-situ)。
- 產物:`docs/plan_v2/d3/notes.md` 追加裁定節 + `runtime/outputs/v2_d3_gates/adjudication.json`。

## 步 3:包 B — `scripts/d3_grasp_runner.py` + `runtime/run_v2_d3_grasp.sh` 【sonnet】

骨架:複製包 A(場景/夾爪/量測),加:

1. **夾取序列**(g3 與三臂共用):停止姿態 → 推進 Δx(見 mode)→ `RobotiqGripperRuntime.close`(抄 ur10e_robotiq_common,finger_joint 位置控制,E2 已驗證)→ 升舉 0.10 m(tool0 目標 z + 0.10,IK)→ 保持 60 幀 → 記 bar z 軌跡。
2. **每步稽核**:D1.5 的姿態/位姿/IK 稽核原樣;夾取/升舉階段同樣稽核(sensor pose 稽核在推進後可豁免俯仰──推進不改姿態,只查穿模)。
3. **modes**:
   - `g3`(oracle-scaffold):bar 放已知位置(oracle 直接算推進),掃 5 個 x 偏移 {0, ±0.02, ±0.04} × 2 重複 = 10 次夾取;每次記錄成功/失敗+接觸幾何。summary 必含 `"debug_scaffold": true`;輸出目錄 `gates/g3_scaffold/`(與正式臂隔離)。
   - `closed`:D1.5 closed 管線(standoff 0.35,bar_calibration.json 估距)→ Δx = d̂_stop − D_GRASP_M → 夾取序列。0.32 m 內量測照做只落記錄。
   - `blind`:估距強制 +inf → 走到走廊護欄端 → Δx = 固定名義值(= open 的)→ 夾取序列。
   - `open`:無量測,固定名義停點+固定名義推進 → 夾取序列。
4. 三臂 n=30,同 seed 目標位置組(配對);目標 x ∈ [0.55, 1.05] 均勻。
5. Header:五鐵律 + 四條預註冊判準原文(d3_align_tracking / d3_align_beats_blind / d3_grasp_given_align / d3_posture_clean)+ 對位容差引用 `gates/g3_scaffold/` 校訂值(步 4 鎖定後填入 TOL_ALIGN_X_M 常數並在 header 註記鎖定時刻)。
6. shell:g3 → ABORT 閘(<8/10 或有違規)→ 三臂依序,續跑 skip 已完成 episode。

**驗收**:
- [ ] py_compile 過
- [ ] GPU smoke:g3 mode 跑 2 次夾取(offset 0)正常落盤,summary 含 debug_scaffold:true
- [ ] closed mode 跑 1 episode smoke:聲學停止觸發、推進、合爪、升舉全序列不炸,steps.csv/episode json 落盤
- [ ] 不改既有檔案

## 步 4:跑 g3 → 鎖容差 → 跑三臂 【主 agent】

- `bash runtime/run_v2_d3_grasp.sh --gates-only` → 判 g3(≥8/10 且零違規)。
- 由 g3 偏移-成功曲線實測捕捉半寬 → 更新 runner 的 TOL_ALIGN_X_M → **鎖定**(git 註記或 notes.md 記時刻,先於三臂)。
- 三臂全跑(估 90 × ~40 s ≈ 1 小時,nohup 背景 + log)。

## 步 5:包 C — `scripts/analyze_d3_grasp.py` 【sonnet】

照 analyze_d15 樣式:讀 gates/三臂原始 csv/json → 印四條 `ADJUDICATION` 行 + 三臂對照表(r、P(align)、P(grasp|align)、步數、稽核計數)+ Fisher exact(自實作,精確超幾何)+ `d3_summary.json` + 散點圖。`--self-test` 內建合成數據。
**驗收**:self-test 過;對真數據跑出四行裁定;數字與 raw csv 抽查一致(主 agent 核)。

## 步 6:報告與收尾 【主 agent】

- `docs/plan_v2/reports/D3_grasp_report.md`(裁定、三臂表、誠實記錄、口試措辭上限)。
- M3 正式關閉:把 M3a+M3b 寫成 `docs/plan_v2/reports/M3_slope_attribution_report.md`。
- 更新 PROGRESS.md、d3/notes.md、d3/risks.md(已解/未解狀態)、記憶。
- 提醒用戶 commit。

## 額度中斷交接規則

任一步中斷:產物已落盤;接手者讀本檔 + notes.md 最末節,從未勾的驗收項繼續。sub-agent 包中斷 = 重派同規格(規格全在本檔+設計文件,無隱藏上下文)。
