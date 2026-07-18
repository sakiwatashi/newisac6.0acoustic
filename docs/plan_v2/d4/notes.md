# D4 工作筆記

## 2026-07-16 開工

- 計畫：`docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md`
- 既有 Lab 距離 env 為 **fixed-TCP + 距離回歸**，不是夾取；B 需新 package `ur10_rtx_acoustic_grasp`。
- D3 摩擦失敗主因：臂 kinematic 大步 teleport + 指墊保持不足；A/B 改連續小步物理抬升。
- 官方 `lift_cube_sm.py` 狀態名可借；觀測改聲學估位，不可照抄 object_pose 進控制。

## 2026-07-16 骨架落地（零 GPU 過）

- A：`d4_acoustic_grasp_sm_runner` 委派 d3 + `--no-weld-on-stall` 預設；analyzer self-test 過
- d3 新增可選 CLI（預設 weld=True 保持 r3）
- B：`ur10_rtx_acoustic_grasp` gym 註冊；obs/reward 單元測試過；**尚未** GPU env smoke
- 入口：`runtime/run_v2_d4_g0_executor.sh`、`runtime/run_v2_d4_sm_grasp.sh`、`lab/run_d4_grasp_unit_tests.sh`

## 2026-07-16 g0 smoke 結果（GPU，關鍵）

指令：`d4_g0` → g3 smoke、`--no-weld-on-stall`、`lift_up_step=0.002`  
數據：`runtime/outputs/v2_d4_g0_executor/gates/g3_scaffold/`  
裁定：`runtime/outputs/v2_d4_g0_executor/g0_adjudication.json`

| 檢查 | 結果 |
|------|------|
| 對位 (offset=0) | align_err ≈ 0（oracle 進窗 OK） |
| 接觸 pinch-stall | contact_detected=True，finger_q≈0.38–0.40 |
| weld | **False**（設定如此） |
| 升舉 IK | lift_ik_ok=True（手臂有抬） |
| bar z_gain | **~0**（物體幾乎沒離開桌面） |
| grasp_lift_success | **0/2** |

**結論：不是聲學／對位失敗；是「無 weld 時摩擦保持仍不夠」。**  
與 D3 notes 24 輪歸因一致；更細 lift step（0.002）**沒有**單獨解決滑脫。

### 路線調整（g0 後）

1. **主路徑**：Track A 正式三臂用 **聲學對位 + weld-on-stall**——科學宣稱仍是對位；升舉機制如實標附著。  
2. **摩擦-only 不列主判準**（g0 已 FAIL）；除非另開資產／Franka 移植。  
3. **Track B**：優先訓「聲學接近 + 合爪時機」。

### g0 weld sanity（同日稍後）

- 2/2 success，z_gain 0.0569 / 0.0593，weld_applied=True，contact=True  
- PhysX 警告 `D3GraspWeldJoint` disjointed body = 預期附著吸附，不影響 PASS  
- **配對結論**：同一進窗/接觸下，lift 成敗 = weld 開關 → 執行器棧可用；摩擦不可用。

## 2026-07-16 正式三臂 n=30（完成）

目錄：`runtime/outputs/v2_d4_sm_grasp_n30/`  
設定：weld 開、lift_up_step=0.002、seed=20260716、走廊 1.00–1.15  
總時長約 **1.5 h**（exit 0）

| 臂 | 對位 (±2cm) | r(grasp,tgt) | \|err\| RMSE | 升舉 | P(升舉\|對位) | weld | 停止原因 |
|----|-------------|--------------|--------------|------|--------------|------|----------|
| closed | **22/30 (73.3%)** | **0.9764** | 1.73 cm | 24/30 | **86.4%** | 24 | 全 standoff_est |
| blind | 12/30 (40.0%) | ~0 | 4.37 cm | 6/30 | 25.0% | 6 | 全 corridor_end |
| open | 8/30 (26.7%) | n/a（固定點） | 4.05 cm | 8/30 | 87.5%* | 8 | 全 open_fixed |

\* open 對位成功幾乎都升舉＝運氣對位後 weld 仍會抬；主宣稱不看 open 升舉。

**裁定（analyze_d4_sm_grasp）：**
- `d4_align_tracking`: **True**（r≥0.9）
- `d4_align_beats_blind`: **True**（73% vs 40%，Fisher p≈0.009）
- `d4_posture_clean`: **True**（0 invalid）
- lift gate：報告用，未鎖死過閘

對照 D3 r3（正典）：對位 80% vs 33%；本輪 73% vs 40%（走廊/seed 不同，方向一致：聲學閉環贏盲走）。

## 2026-07-16 Track B 訓練開工

- `lab/train_rl_acoustic_grasp.py`：RSL-RL PPO 入口
- env 已改：action[0] **移動目標距離**（TCP 固定 + GMO 聲學），action[1] 合爪；obs **無 target xyz**
- 短訓：`bash lab/run_d4_ppo_smoke.sh`（預設 5 iter × 16 steps）
- 長訓：`bash lab/run_d4_ppo_train.sh`（100 iter）
- 盲消融：`BLIND=1 bash lab/run_d4_ppo_train.sh`

**宣稱邊界**：學的是「聲學接近 + 合爪時機」，**不是**摩擦夾取／官方 Lab lift 復現。

## 待跑（GPU）

1. [x] g0 friction smoke → **FAIL lift**
2. [x] g0 weld sanity → **PASS 2/2**
3. [x] smoke 三臂
4. [x] 正式三臂 30×3 → A1–A4 主判準過
5. [x] Track B PPO smoke + 100-iter 長訓（exit 0，但 d_hat 曾卡死）
6. [x] 修 d_hat：禁止振幅 peak、gated multi-frame peak（smoke_dhatfix3 有跟蹤）
7. [x] 以修好的 d_hat **重跑 100-iter 長訓** → `v2_d4_ppo_grasp_dhatfix` PASS
8. [x] scaffold close_ft → true success 100%
9. [x] 純聲學 obs + true reward close_ft → 100%
10. [x] BLIND 消融（true reward）→ 也 100%（開環）
11. [x] pure reward acoustic / blind → true success **0%**（d_hat 假近）
12. [x] ④ SM + B policy 掛接（handoff 100%；lift 仍 A weld）
13. [x] 寫 `docs/plan_v2/reports/D4_sm_grasp_report.md`（2026-07-18）
14. [x] 同場景串聯 policy@d3 n=90 — 對位 76.7%、升舉 74.4%（2026-07-18）
15. [x] n=90 入 `D4_sm_grasp_report.md` + 論文草稿 `thesis/THESIS_CH5_3_D4_SUPPLEMENT_DRAFT.md`
16. [x] 貼入 `THESIS_DRAFT_FCU_v2.docx` §5.3 末＋6.2/6.3/RQ4（2026-07-18；bak=`*.bak_before_d4`）

## 2026-07-18 同場景串聯（B policy @ d3 物理場景）

### 設計

```
同一 d3 場景 / 同一 episode：
  接近：Track-B actor（model_49）輸出 a0→Δx、a1→合爪意圖
  停靠距離：d3 經典 argmax peak → d_horiz（避免 gated 假近）
  末端：_grasp_and_lift（descend / close / weld-on-stall / lift）
```

- 入口：`bash runtime/run_v2_d4_same_scene_policy.sh`
- Actor：`scripts/d4_policy_actor.py`（純 torch MLP，無 rsl_rl）
- CLI：`d3_grasp_runner.py --policy-checkpoint ...`（預設不開 = 原規則臂）
- **不寫** `v2_d3_grasp_r3` / `v2_d4_sm_grasp_n30`

### Smoke（n=2, seed=20260718）

| | aligned | lift | note |
|--|---------|------|------|
| smoke4 | **2/2** | **1/2** | standoff_est 停靠；domain gap 預期 |

### 正式 n=90（完成，~1.5 h）

| 指標 | 值 |
|------|-----|
| 對位 | **69/90 = 76.7%** |
| 升舉 | **67/90 = 74.4%** |
| P(升舉\|對位) | **76.8%** |
| mean \|err\| | **1.46 cm** |
| 停靠 | 全 standoff_est |

產物：`runtime/outputs/v2_d4_same_scene_policy_n90/`  
論文草稿：`thesis/THESIS_CH5_3_D4_SUPPLEMENT_DRAFT.md`

### 宣稱邊界

同場景串聯 ≠ pure-reward 成功；obs 訓練在 fixed-TCP，控制在桌面幾何 → **domain gap**。  
主數字仍分層：對位 / P(升舉|對位) / weld，不合成假 e2e。對位正典仍 **D3 r3**。

## 2026-07-16 Track B d_hat 卡死修復

**症狀**：100-iter 長訓 `Metrics/d_hat_xy` 全程 0.7000，`true_range_m` 有變、success=0。

**根因（兩層）**：
1. env 誤把 `primary_sgw_peak`（**振幅**）當 sample index 做 OLS → 估距荒謬 → guard 粘在初始 `true_range=0.7`。
2. 改用 sample idx 後：全波形 `peak_sample_idx` 被房間反射鎖在 **64**；10% `early_peak` 窗太短（peak 落在 7–14），與 D3 走廊 19–60 不合。

**修法**（`ur10_rtx_acoustic_grasp_env.py` + `scene_bootstrap` 存 raw amps）：
- 只吃 sample-index 欄位，永不吃振幅
- multi-frame mean waveform（`gmo_avg_frames=4`）
- **距離閘**內 first local max（corridor 0.40–1.05 m，排除 near-ringing 與 room≈64）
- 診斷 metrics：`peak_sample_idx` / `d_hat_valid` / `d_hat_abs_err` / `peak_full_idx` / `peak_early_idx`

**驗證 smoke** `runtime/outputs/v2_d4_ppo_grasp_smoke_dhatfix3/`：
| iter | d_hat | true | peak | |err| |
|------|-------|------|------|------|
| 0 | 0.45 | 0.41 | 22 | 0.04 |
| 1 | 0.39 | 0.40 | 19 | 0.01 |
| 3 | 0.53 | 0.56 | 27 | 0.03 |

（仍有單步噪聲；已可當 RL 距離訊號，不再常數。）

## 2026-07-16 Track B 100-iter 重訓（d_hat 修復後）

- 指令：`OUT=runtime/outputs/v2_d4_ppo_grasp_dhatfix ITERS=100 STEPS=32 bash lab/run_d4_ppo_train.sh`
- 牆鐘 **~58 min**（多幀 GMO），exit 0，`status=PASS`
- ckpt：`model_{0,25,50,75,99}.pt`

| 對比 | 舊（d_hat 卡死） | 新（gated peak） |
|------|------------------|------------------|
| d_hat | 全程 0.7000 | 0.36–1.05，21 個不同值 |
| mean reward | 0→**−10.6** | 0.5→**~8.2**（峰 ~9.3） |
| success_near_and_closed（log 末步） | 0/100 | **24/100** |
| d_hat_abs_err | n/a | mean 0.27 m（仍有噪聲） |

**解讀**：觀測修復後策略有正 reward 與部分 success；未達穩定收斂／高成功率。可選加長訓練、調 reward、或 BLIND 消融。  
**宣稱不變**：無 object xyz；非摩擦夾取。

## 2026-07-17 真實成功率重算（oracle true_range）

腳本：`scripts/analyze_d4_ppo_success.py`  
數據：`runtime/outputs/v2_d4_ppo_grasp_dhatfix/success_true_vs_dhat.json`

| 定義（iteration 末步快照，非 episode） | 次數 | 率 |
|----------------------------------------|------|-----|
| **d_hat** near + closed（原 log） | 24/100 | **24%** |
| **true_range** near + closed（oracle） | **1/100** | **1%** |
| 假陽性（d_hat 成功但 true 仍遠） | 23/100 | 23% |
| d_hat-success 精確度（真的也 near） | 1/24 | **4.2%** |

補充：合爪 46 步中，true≤0.40 僅 **2.2%**；true near 任意爪 19%、d_hat near 56% → **d_hat 系統性偏近**。

**結論**：24% 不可當真實接近成功率；主數字應報 **~1% oracle**，並標 d_hat 假陽性。  
env 已加 log：`Metrics/success_true_near_and_closed`、`Metrics/false_pos_dhat_success`（oracle 不進 obs）。

## 2026-07-17 幾何 + 防假近 reward

**改動**
- `range_min_m`: 0.40 → **0.30**（standoff 0.35 可達）
- reward scaffold：`rew_true_approach=1.0` 主塑形 true 距離；`rew_approach=0.25` 保留 d_hat；`rew_false_close=0.5` 遠距合爪懲罰
- **obs 仍無 true/xyz**；claim 改寫 train scaffold

**smoke** `v2_d4_ppo_grasp_geom_rew_smoke`（10 iter）PASS；已見 `success_true` / `false_pos` log。

### 50-iter `v2_d4_ppo_grasp_geom_rew50`（僅 reward scaffold、obs 無 true）

| 指標 | 率 |
|------|-----|
| success_dhat | 28/50 = 56% |
| **success_true** | **0/50 = 0%** |
| true near（任意爪） | **0/50** |
| d_hat near | 49/50 |

**診斷**：d_hat 系統性假近 → policy 觀測「已到 standoff」；true_range 只在 reward 不在 obs → 無法 credit assignment。幾何可達但沒學到接近。

### 修復2：obs 加入 true_range scaffold + peak 閘 floor≥0.32

- `obs_include_true_range=True`（9-D；**仍無 xyz**）
- peak 搜索 lo ≥ 0.32 m 減 near-ringing
- smoke `v2_d4_ppo_grasp_priv_smoke` 15 iter：true_range 偶見下降（~0.57），**success_true 仍 0**（iters 太短）

**宣稱**：scaffold 訓練 ≠ 純聲學 policy；純聲學需 `obs_include_true_range=False` 且 d_hat 可信後再訓。

## 2026-07-17 RL 調參輪（scaffold 接近）

**策略**：先證明「有 true_range 時能學會接近+合爪」；d_hat 修好後再切純聲學。

| 旋鈕 | 舊 | 新 |
|------|----|----|
| episode / steps | 32 | **48** |
| max_forward_step | 4 cm | **5 cm** |
| gmo_avg_frames | 4 | **2**（加速） |
| MLP | 64×64 | **128×128** |
| init_std | 0.8 | **0.5** |
| entropy_coef | 0.05 | **0.01** |
| lr / epochs | 2e-4 / 4 | **3e-4 / 8** |
| rew_progress | — | **2.0**（true 縮近獎勵） |
| obs true_range | on | **on**（scaffold） |

跑：`OUT=runtime/outputs/v2_d4_ppo_grasp_rl_tune` 100×48。  
主看：`success_true_near_and_closed`、`true_range_m` 下降、reward 由負轉正。

### 結果（PASS，~53 min）

| 指標 | 值 |
|------|-----|
| status | PASS |
| mean reward | −1 → **+51**（末 20 均 ~49） |
| true_range 前/後 20 均 | 0.42 → **0.33**（min 0.30） |
| **true near**（末步） | **80/100** |
| **success_true**（近+合爪） | **51/100 = 51%** |
| success_dhat | 58%（precision vs true **79%**） |
| false positive | 12%（遠低於舊 56%） |

**結論**：scaffold 下 **接近已學會**；合爪時機約半數末步對上。非純聲學、非摩擦夾取。  
產物：`runtime/outputs/v2_d4_ppo_grasp_rl_tune/` + `success_true_vs_dhat.json`。

## 2026-07-17 Episode-level eval（model_99）

```bash
EPISODES=20 bash lab/run_d4_ppo_eval.sh
# lab/eval_rl_acoustic_grasp.py
```

| 指標（n=20，deterministic） | 率 |
|-----------------------------|-----|
| **final true near** | **100%** |
| **final true success**（近+合爪） | **55%** |
| ever true near | **100%** |
| ever true success（episode 內曾達成） | **100%** |
| mean final / min true | 0.305 / **0.300 m** |
| mean return | **+50.4** |

**解讀**：接近已穩；失敗幾乎全是「已到 0.30 m 但末步爪開著」。下一步可加 close 獎勵或 early-stop when near+closed。  
JSON：`runtime/outputs/v2_d4_ppo_grasp_rl_tune/eval_episode_summary.json`。

## 2026-07-17 close-hold 再訓（失敗對照）

加 `rew_hold_closed` / `rew_open_when_near` + early_stop，50-iter → `v2_d4_ppo_grasp_close_tune`。  
Eval n=20：true near **100%**，但 **final/ever success 0%**（永不合爪）。  
**結論**：從零再訓 50 iter 未學到合爪；**正典仍用 rl_tune/model_99（final success 55%）**。

## 為何現在成功？（對照一開始）

| 階段 | 觀測 | 距離訊號 | Reward | 真實成功 |
|------|------|----------|--------|----------|
| 初訓 `v2_d4_ppo_grasp` | 聲學 | d_hat **卡死 0.70**（誤用振幅 peak） | d_hat-only | **0%** |
| d_hat 修復 `dhatfix` | 聲學 | gated peak 可動 | d_hat-only | log 24% 但 **true ~1%**（假近） |
| 僅 true reward `geom_rew50` | 聲學（無 true） | d_hat 假近 | true 塑形 | **0%**（credit 斷） |
| **rl_tune** | **true_range scaffold + 聲學** | true 進 obs | progress+approach+合爪 | **final 55% / ever 100%** |
| close_tune 從零 | 同上 + hold | 同上 | hold/open 重懲罰 | near 100% **success 0%** |

**關鍵差異（不是「PPO 突然變強」）**：

1. **訊號先修對**：sample-index peak + 距離閘，不再振幅／room peak 假成功。  
2. **評測改 oracle**：`success_true` 才算；避免 d_hat 24% 假象。  
3. **credit assignment**：true_range 進 **obs+reward**（scaffold），policy 才學得動接近；只放 reward 不夠。  
4. **幾何可達**：`range_min=0.30`、步長/episode 夠走到 standoff。  
5. **超參**：更長 rollout、較低 entropy、稍大網、progress bonus。  

**宣稱邊界不變**：scaffold ≠ 純聲學；無 object xyz；非摩擦夾取。

## 2026-07-17 下一步：從 model_99 續訓合爪

- close_tune 證明「從零 + 重 hold 獎勵」會只接近不合爪。  
- 正確路徑：**載入 rl_tune/model_99**，在已會接近的 policy 上 fine-tune hold/close。  
- 入口：`CHECKPOINT=.../model_99.pt OUT=...close_ft ITERS=40 bash lab/run_d4_ppo_train.sh`

### close_ft 結果（PASS，~22 min，40 iter）

- 起點：`v2_d4_ppo_grasp_rl_tune/rsl_rl_logs/model_99.pt`
- 產物：`runtime/outputs/v2_d4_ppo_grasp_close_ft/` + `model_39.pt`
- train 支援：`--checkpoint` / `CHECKPOINT=`（見 `train_rl_acoustic_grasp.py`）

**Episode eval n=20（deterministic，model_39）**

| 指標 | rl_tune model_99 | **close_ft model_39** |
|------|------------------|------------------------|
| final true near | 100% | **100%** |
| **final true success** | 55% | **100%** |
| ever true success | 100% | **100%** |
| mean final true | 0.305 m | 0.379 m（near 門檻內即 early-stop） |
| mean steps | 47 | **~11**（early_stop 生效） |
| mean return | +50 | ~0（短 episode + hold 獎勵尺度不同） |

**解讀**：從已會接近的 policy 接 hold/open 獎勵後，**合爪時機補上**；episode 一到 near+closed 就結束。  
**正典改為** `v2_d4_ppo_grasp_close_ft/rsl_rl_logs/model_39.pt`（scaffold 下 approach+close）。  
宣稱仍：scaffold ≠ 純聲學；無 xyz；非摩擦夾取。

## 2026-07-17 純聲學 policy obs

- 目標：`obs_include_true_range=False`（8-D），**reward 仍可用 true scaffold**。  
- 入口：`ACOUSTIC_ONLY=1 OUT=runtime/outputs/v2_d4_ppo_grasp_acoustic ITERS=100 bash lab/run_d4_ppo_train.sh`  
- 不可從 9-D scaffold ckpt 直接 load（obs 維度不同）→ **從零訓**。  
- 宣稱：acoustic-only **policy**；非純 reward；非摩擦。

### 結果（PASS，~54 min，100 iter）

| 指標（eval n=20, model_99） | geom_rew50（舊，obs 無 true） | **acoustic model_99** | close_ft scaffold |
|-----------------------------|------------------------------|------------------------|-------------------|
| final true near | **0%** | **100%** | 100% |
| final true success | 0% | **0%**（永不關爪） | **100%** |
| ever true near | 0% | **100%** | 100% |
| mean final / min true | — | 0.303 / **0.300 m** | 0.379 / — |
| obs true_range | no | **no（8-D）** | yes（9-D） |

**解讀**：
1. **接近已可純聲學 obs 學會**（有 true reward 塑形）— 對比 geom_rew50 的 0% near，關鍵是 d_hat peak 修復 + progress/true reward 夠強。  
2. **合爪仍未學**：ever_success 0%；同 close_tune「只接近不合爪」模式。  
3. scaffold 正典仍是 `close_ft/model_39`（9-D, success 100%）。  
4. 下一步：從 acoustic/model_99 **續訓合爪**（8-D + CLOSE_FT=1）。

## 2026-07-17 純聲學合爪續訓（close_ft）— **成功**

- 起點：`v2_d4_ppo_grasp_acoustic/rsl_rl_logs/model_99.pt`（8-D 只聽聲會靠近）
- 指令：`ACOUSTIC_ONLY=1 CLOSE_FT=1 CHECKPOINT=.../model_99.pt OUT=.../acoustic_close_ft ITERS=50`
- 獎勵：close_near=2.5, hold=3.0, open_when_near=2.0, false_close=0.25, progress=1.0
- 牆鐘 ~28 min，PASS

**Episode eval n=20（deterministic）**

| ckpt | final near | **final success** | ever success |
|------|------------|-------------------|--------------|
| model_30 | 100% | **100%** | 100% |
| model_40 | 100% | **100%** | 100% |
| **model_49** | 100% | **100%** | 100% |

對照：起點 acoustic/model_99 為 near 100% / success **0%**。  
**正典（純聲學 policy obs）**：`v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt`  
宣稱：obs **無 true_range / 無 xyz**；reward 訓練仍可用 true scaffold；非摩擦夾取。  
scaffold 全開掛版仍可報 close_ft/model_39 作對照上限。

## 2026-07-17 BLIND 消融（下一步 ②）— 完成，結果要誠實報

公平對照：與純聲學成功配方同構  
- `ACOUSTIC_ONLY=1`（8-D、無 true_range）  
- `BLIND=1`（energy/peak/gmo/d_hat 全 0）  
- `CLOSE_FT=1`（同合爪獎勵）  
- 從零 100 iter，~55 min  
- 產物：`runtime/outputs/v2_d4_ppo_blind_control_blind/`

**Episode eval n=20（model_99, deterministic）**

| 條件 | final near | final success | 解讀 |
|------|------------|---------------|------|
| 純聲學 acoustic_close_ft | 100% | **100%** | 聽音 OK |
| **BLIND（聲學通道=0）** | **100%** | **100%** | 開環也能過 |

**關鍵解讀（不可隱瞞）**：
1. 本任務是 **1-DOF 走廊**（只調距離）+ 訓練時 **true_range 仍在 reward**。  
2. BLIND 時 policy 只剩 gripper / ee_x / prev_a；eval 20 集 **步數與 final true 全相同**（12 步、0.317 m）→ 實為 **開環時序策略**（固定前進再合爪），靠 oracle reward 學成。  
3. 因此：**現有設定下 BLIND 不能證明「必須有聲音」**；只能證明「有/無聲學觀測都能用 true reward 學到」。  
4. 若要主張聲學必要，需 **③ 拿掉 reward 的 true scaffold**，或加大隨機／多自由度，讓開環失效。

## 2026-07-17 ③ 純聲學 reward（obs+reward 皆無 true）

- `PURE_REWARD=1`：`reward_use_true_range=False`，progress/near/false_close 全走 **d_hat**
- early-stop 只看 **oracle true**（不可用 d_hat early-stop，否則 ep 長~2 假近合爪）
- 主看 eval `success_true`（oracle 仍只記 log / 評測）

### ③a pure acoustic（有聲學 obs，純 d_hat reward）

- 指令：`ACOUSTIC_ONLY=1 PURE_REWARD=1 CLOSE_FT=1 OUT=.../v2_d4_ppo_pure_reward_acoustic ITERS=100`
- 牆鐘 ~54 min，train `status=PASS`，ckpt `model_99.pt`
- Episode eval n=20（deterministic）：

| 指標 | 率 / 值 |
|------|---------|
| **final true near** | **0%** |
| **final true success** | **0%** |
| final **d_hat** success | **90%** |
| ever true near / success | 0% / 0% |
| mean final / min true | **0.833 / 0.764 m**（遠） |
| mean return | **−73.6** |
| 典型行為 | 全程 closed=1，true 仍 0.5–1.0 m → **假近合爪** |

**解讀**：去掉 true scaffold 後，policy 用 **d_hat 假近** 刷 hold/close 獎勵；oracle 真實接近 **完全沒學到**。  
對照 `acoustic_close_ft`（obs 純聲學、**reward 有 true**）= 100% true success → **瓶頸在 d_hat 信用，不是「缺 PPO 算力」**。

產物：`runtime/outputs/v2_d4_ppo_pure_reward_acoustic/` + `eval_episode_summary.json`

### ③b BLIND pure reward（完成）

- 指令：`BLIND=1 ACOUSTIC_ONLY=1 PURE_REWARD=1 CLOSE_FT=1 OUT=.../v2_d4_ppo_pure_reward` → 目錄 `v2_d4_ppo_pure_reward_blind/`
- 牆鐘 ~53 min，train `status=PASS`，ckpt `model_99.pt`
- Episode eval n=20（deterministic）：

| 指標 | 率 / 值 |
|------|---------|
| **final true near** | **0%** |
| **final true success** | **0%** |
| final **d_hat** success | **90%** |
| mean final / min true | **1.050 / 0.865 m**（卡遠端） |
| mean return | **−81.9** |
| 行為 | 20 集完全同形：true_f=1.05、closed=1 → **開環假近合爪** |

**注**：BLIND 只把 **obs** 聲學通道置 0；env 仍算 d_hat，pure reward 仍吃 d_hat → 訓練 reward 對 policy 是「看不見的假近特權」。  
eval 時 20 集軌跡一致 = 開環時序，不是跟蹤距離。

### ②+③ 對照總表（episode eval n=20，oracle true）

| 配方 | obs | reward | final true near | **final true success** | final d_hat succ |
|------|-----|--------|-----------------|------------------------|------------------|
| **acoustic_close_ft**（正典） | 聲學 8-D | **true** scaffold | 100% | **100%** | — |
| **blind_control**（②） | 全 0 | **true** scaffold | 100% | **100%** | — |
| **pure_reward_acoustic**（③a） | 聲學 8-D | **d_hat only** | **0%** | **0%** | **90%** |
| **pure_reward_blind**（③b） | 全 0 | **d_hat only** | **0%** | **0%** | **90%** |

**裁定（必須誠實寫進報告）**：

1. **有 true reward 時**：有聲／BLIND 都能 100% → 1-DOF 走廊 + oracle reward 足夠開環過關；**不能**據此宣稱「必須聽音」。
2. **純 d_hat reward 時**：有聲／BLIND **皆 0% true**；d_hat success 卻 90% → **假近合爪刷分**，不是真接近。
3. 因此：**現階段不可宣稱「純聲學 end-to-end 夾取成功」**；正典仍是 `acoustic_close_ft`（obs 純聲學、reward 有 true scaffold）。
4. 瓶頸在 **d_hat 偏差／假近**，不是 PPO 迭代不夠。下一步優先：修 d_hat / 降 hold-on-d_hat-near / 或 **④ SM 掛接**（A 軌閉環對位 + B 策略時機）。

產物：
- `runtime/outputs/v2_d4_ppo_pure_reward_acoustic/{train_summary,eval_episode_summary}.json`
- `runtime/outputs/v2_d4_ppo_pure_reward_blind/{train_summary,eval_episode_summary}.json`

## 2026-07-18 ④ SM + Track-B policy 掛接

### 設計（誠實邊界）

雙棧不可同場景直接插權重（A=`d3_grasp_runner` 物理臂+weld；B=Lab fixed-TCP 虛擬接近）：

```
B policy (acoustic_close_ft)          A SM (n30 formal)
REST → ACOUSTIC_APPROACH              DESCEND → CLOSE contact
     → ALIGN → CLOSE                  → weld-on-stall → LIFT → HOLD
     → LIFT_HANDOFF  ───────────────►  (物理升舉在 A；B 不執行 lift)
```

- **B 負責**：聲學 obs 下接近 + 合爪時機（SM 相位追蹤）  
- **A 負責**：接觸後 weld 升舉（已驗證 n30）  
- **不可**把 `handoff × lift|align` 乘成「純聲學 end-to-end 升舉」而不做同場景串聯實驗

### 入口

```bash
bash lab/run_d4_sm_policy_hookup.sh
# EPISODES=5 bash lab/run_d4_sm_policy_hookup.sh   # smoke
python3 scripts/analyze_d4_sm_policy_hookup.py
```

- `lab/eval_sm_policy_hookup.py`：SM 狀態機包 B policy  
- 預設 ckpt：`v2_d4_ppo_grasp_acoustic_close_ft/.../model_49.pt`

### 結果（n=20，deterministic，~2 min）

| 指標 | 值 |
|------|-----|
| final true near | **100%** |
| final true success（近+合爪） | **100%** |
| **LIFT_HANDOFF ready**（B→A） | **100%** |
| mean handoff step | **5.5** |
| 本 env 執行物理升舉 | **否** |

典型 trace：`REST→ACOUSTIC_APPROACH→ALIGN→CLOSE→LIFT_HANDOFF→DONE`

### 與 A 正式三臂合併（offline）

| 段 | 來源 | 率 |
|----|------|-----|
| B 接近+合爪 handoff | ④ hookup n=20 | **100%** |
| A closed 對位 | n30 | **73.3%** |
| A P(升舉\|對位) weld | n30 | **86.4%** |

`runtime/outputs/v2_d4_sm_policy_hookup/sm_policy_hookup_combined.json`

### 宣稱

- 雙軌**協議掛接完成**：B 策略可填入 A 的 approach/close 相位並 100% 到 handoff。  
- 物理升舉仍屬 A + weld（g0 已證無 weld 摩擦不可用）。  
- 非 pure-reward 成功；非「必須聽音」（見 ②）；obs 無 target xyz。

### 後續可選

1. 同場景串聯：在 d3 runner 內嵌 policy 推理（工程量大，跨 app/Lab 棧）  
2. 修 d_hat 再試 pure reward  
3. 寫 `reports/D4_sm_grasp_report.md` 收束 A+B+②③④  
