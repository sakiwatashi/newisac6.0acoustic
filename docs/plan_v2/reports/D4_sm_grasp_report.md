# D4 雙軌聲學夾取報告（2026-07-18）

**實驗**：V2 Stage 2 / D4——在 D3 r3 之上，雙軌驗證「聲學負責走到窗內 + 連續物理執行器夾取」。  
**計畫**：`docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md`  
**筆記**：`docs/plan_v2/d4/notes.md`  
**D3 r3**：只讀正典，**不覆寫** `runtime/outputs/v2_d3_grasp_r3/`。

| 軌道 | 內容 | 主產物 |
|------|------|--------|
| **A（快路徑）** | 規則聲學對位 + 狀態機 descend/close/weld/lift | `runtime/outputs/v2_d4_sm_grasp_n30/` |
| **B（學習）** | PPO 學接近 + 合爪時機（obs 無 target xyz） | `runtime/outputs/v2_d4_ppo_grasp_acoustic_close_ft/` |
| **消融 ②③** | BLIND / pure-reward | `v2_d4_ppo_blind_control_blind/`、`v2_d4_ppo_pure_reward_*` |
| **④ 掛接** | B policy 填入 SM 相位 → LIFT_HANDOFF | `runtime/outputs/v2_d4_sm_policy_hookup/` |
| **⑤ 同場景串聯** | policy 接近 @ d3 物理 + weld 升舉，n=90 | `runtime/outputs/v2_d4_same_scene_policy_n90/` |
| **論文增補草稿** | §5.3 可貼正文 | `thesis/THESIS_CH5_3_D4_SUPPLEMENT_DRAFT.md` |

---

## 1. 科學問題與邊界

### 1.1 要證明什麼

1. **聲學對位在夾取鏈仍有效**：closed 臂對位率顯著高於 blind（同 seed 同目標組）。  
2. **連續小步物理執行器可用**：相對 D3 大步 teleport，D4 預設 `lift_up_step=0.002`。  
3. **策略可學「接近 + 合爪時機」**：觀測禁物體 xyz；主數字用 **oracle true_range** 評測。  
4. **雙軌可協議對接**：B 到 `LIFT_HANDOFF` 後，升舉仍由 A 的 weld SM 負責。

### 1.2 不可宣稱（預先鎖定）

| 禁止 | 原因 |
|------|------|
| 無 weld 真摩擦升舉 | g0：`v2_d4_g0_executor` 無 weld 時 z_gain≈0、lift 0/2 |
| 單一混合成功率 P(對位)×P(升舉) 當唯一主數字 | D4-3 / E2 教訓：分層報告 |
| 「純聲學 end-to-end 夾取成功」 | pure-reward true success **0%**；reward 仍常需 true scaffold |
| 「必須聽音才能接近合爪」 | ② BLIND + true reward 也 **100%**（1-DOF 開環可過） |
| B 替代 D3 r3 或官方 Franka lift | B 為 fixed-TCP 虛擬接近 + 合爪時機，非摩擦物理 |

**夾持機制（繼承 D-13）**：接觸觸發 weld-on-stall；科學主宣稱仍是**對位**，升舉如實標附著。

---

## 2. Track A — 狀態機三臂（n=30）

**指令**：`bash runtime/run_v2_d4_sm_grasp.sh`（預設 weld 開）  
**目錄**：`runtime/outputs/v2_d4_sm_grasp_n30/`  
**設定**：seed=20260716，走廊 1.00–1.15，standoff=0.35，lift_up_step=0.002

| 臂 | 對位 (±2 cm) | r(grasp, tgt) | 升舉 | P(升舉\|對位) | weld |
|----|--------------|---------------|------|---------------|------|
| **closed** | **22/30 (73.3%)** | **0.976** | 24/30 | **86.4%** | 24 |
| blind | 12/30 (40.0%) | — | 6/30 | 25.0% | 6 |
| open | 8/30 (26.7%) | — | 8/30 | 87.5%* | 8 |

\* open 對位後 weld 仍抬 = 運氣基線；主宣稱不看 open 升舉率。

### 裁定（`analyze_d4_sm_grasp`）

```
d4_align_tracking:     True   (r ≥ 0.9)
d4_align_beats_blind:  True   (73% vs 40%, Fisher 單尾 p ≈ 0.009)
d4_posture_clean:      True   (0 invalid)
d4_lift_given_align:   報告項（未鎖死過閘）
```

### g0 執行器（負結果，必須保留）

| 條件 | 對位 | 接觸 | lift IK | z_gain | lift success |
|------|------|------|---------|--------|--------------|
| **無 weld** | OK | True | True | **~0** | **0/2** |
| **有 weld** | OK | True | True | ~0.06 | **2/2** |

→ 摩擦-only **不列主路徑**（D4-7）。

### 與 D3 r3

| | D3 r3 closed | D4 n30 closed |
|--|--------------|---------------|
| 對位 | 80% vs blind 33% | 73% vs 40% |
| r | 0.978 | 0.976 |
| 方向 | 聲學閉環贏盲走 | 一致 |

走廊/seed 不同，數字不可逐點等同，**因果方向一致**。

---

## 3. Track B — PPO 接近 + 合爪

### 3.1 任務定義

- **Env**：`Isaac-Ur10RtxAcousticGrasp-Direct-v0`  
- **Obs（8-D 正典）**：energy, peak, gmo_valid, d_hat, gripper, ee_x, prev_a₀, prev_a₁ — **無 true_range / 無 xyz**  
- **Act**：Δrange（移目標，TCP 固定）+ gripper  
- **評測**：episode-level **oracle** `true_range ≤ standoff+0.05` 且合爪  

### 3.2 訓練路徑（簡表）

| 階段 | 觀測 | Reward | 結果（eval n=20） |
|------|------|--------|-------------------|
| d_hat 卡死初訓 | 聲學 | d_hat | true ~0%（估距廢） |
| d_hat 修復後 | 聲學 | d_hat | log 假近；true ~1% |
| scaffold `rl_tune` | **true+聲學** | true | final success **55%** |
| scaffold `close_ft` | true+聲學 | hold/close | **100%** |
| 聲學 obs 從零 | 8-D | true | near 100%，success **0%**（不合爪） |
| **`acoustic_close_ft`** | **8-D** | true + close_ft | **near 100% / success 100%** ← **B 正典** |

正典權重：  
`runtime/outputs/v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt`

### 3.3 關鍵修復（方法論）

1. **d_hat**：禁止振幅當 peak index；gated sample-index peak + 距離閘。  
2. **評測改 oracle**：`success_true`；d_hat success 僅診斷。  
3. **credit**：true 進 reward（scaffold）才能學接近；只進 reward 不進 obs 仍難（geom_rew50）。  
4. **合爪**：從已會接近的 ckpt **close fine-tune**，勿從零加重 hold（會只走不合爪）。

---

## 4. 消融 ②③（必須誠實）

Episode eval n=20，deterministic：

| 配方 | obs | train reward | true near | **true success** | d_hat success |
|------|-----|--------------|-----------|------------------|---------------|
| **acoustic_close_ft** | 聲學 8-D | **true** | 100% | **100%** | ~85% |
| **② BLIND + true** | 全 0 | **true** | 100% | **100%** | ~95% |
| **③a pure acoustic** | 聲學 8-D | **d_hat only** | **0%** | **0%** | **90%** |
| **③b pure BLIND** | 全 0 | **d_hat only** | **0%** | **0%** | **90%** |

### 解讀

1. **有 true reward**：有聲 / 盲都能 100% → 1-DOF 走廊 + 特權距離獎勵，**開環時序**可過；**不能**主張「必須聽音」。  
2. **純 d_hat reward**：true **全 0**，d_hat success 卻 90% → **假近合爪刷分**。  
3. 瓶頸在 **d_hat 偏差 / 假近**，不是 PPO 迭代不夠。  
4. B 正典宣稱上限：**「聲學-only policy obs +（訓練時）true scaffold reward 下的接近與合爪」**，不是 pure acoustic reward。

---

## 5. ④ SM + policy 掛接

### 5.1 協議（非同進程插權重）

```
B policy                    A SM (n30)
REST → APPROACH → ALIGN
     → CLOSE → LIFT_HANDOFF ──► weld-on-stall → LIFT → HOLD
```

- B 棧：Lab fixed-TCP（本報告 ④ 所跑）  
- A 棧：`d3_grasp_runner` 物理臂 + Robotiq + weld  
- **④ 不在 Lab env 執行物理升舉**；handoff ≠ lift success  

入口：

```bash
bash lab/run_d4_sm_policy_hookup.sh
python3 scripts/analyze_d4_sm_policy_hookup.py
```

### 5.2 結果（n=20，model_49）

| 指標 | 值 |
|------|-----|
| final true near | **100%** |
| final true success | **100%** |
| **LIFT_HANDOFF ready** | **100%** |
| mean handoff step | **5.5** |

典型 trace：`REST→ACOUSTIC_APPROACH→ALIGN→CLOSE→LIFT_HANDOFF→DONE`

### 5.3 分層合併（offline，勿乘成單一 e2e）

| 段 | 來源 | 率 |
|----|------|-----|
| B 接近+合爪 handoff | ④ n=20 | **100%** |
| A closed 對位 | n30 | **73.3%** |
| A P(升舉\|對位) weld | n30 | **86.4%** |

`runtime/outputs/v2_d4_sm_policy_hookup/sm_policy_hookup_combined.json`

---

## 5.4 ⑤ 同場景串聯（正式 n=90，已完成）

**定義**：同一 d3 物理 episode 內——B actor 驅動接近 Δx 與合爪意圖；停靠距離用 **d3 經典 argmax peak → d_horiz**（避免 gated 假近）；末端 `_grasp_and_lift`（descend / close / weld-on-stall / lift）。

```bash
bash runtime/run_v2_d4_same_scene_policy.sh   # 預設 N_EP=90
# 產物：runtime/outputs/v2_d4_same_scene_policy_n90/
```

| 設定 | 值 |
|------|-----|
| n | **90** |
| seed | 20260718 |
| ckpt | `acoustic_close_ft/model_49.pt` |
| weld | 開，`lift_up_step=0.002` |
| 走廊 | target x ∈ [1.00, 1.15] m |
| 牆鐘 | ~1.5 h（01:09–02:35） |
| 停靠原因 | **90/90 `standoff_est`** |
| 姿態／感測器違規 | **0** |

### 主表

| 指標 | 同場景 policy n=90 | 規則 A closed n=30 |
|------|--------------------|--------------------|
| **對位 (±2 cm)** | **69/90 = 76.7%** | 22/30 = 73.3% |
| **升舉全率** | **67/90 = 74.4%** | 24/30 = 80.0% |
| **P(升舉\|對位)** | **76.8%** | 86.4% |
| weld / contact | 74.4% | 80.0% / — |
| mean \|align_err\| | **1.46 cm** | — |

Smoke n=2（同 seed 前兩 target）：對位 2/2、升舉 1/2。

### 解讀

1. 對位與規則臂**同級甚至略高** → 同場景串聯不是「策略完全不會對位」。  
2. \(P(\text{升舉}\mid\text{對位})\) 低於規則臂 → 停點／domain gap（Lab 固定 TCP 訓練 vs 桌面臂載）可預期，**非再訓 PPO 主解**。  
3. 全 standoff_est 停靠 + weld 路徑 → 仍是**接觸觸發附著**升舉，不是摩擦。  
4. 論文主對位正典仍是 **D3 r3**；本表為 D4 延伸。

`same_scene_summary.json`、`closed/episodes.csv`。

---

## 6. 論文可宣稱措辭（上限）

### 可寫

> 在 Isaac Sim 6 設定下：（1）規則聲學閉環對位在夾取狀態機中仍顯著優於盲走（D4-A：73% vs 40%，Fisher p≈0.009；r≈0.98）；（2）對位後以接觸觸發之 weld 附著升舉可分層報告（規則臂 P(升舉|對位)≈86%；無 weld 摩擦升舉 g0 失敗）；（3）在**無目標 xyz** 的策略觀測下，可學會接近與合爪時機（Lab 評測，訓練獎勵可用距離 scaffold）；（4）該策略可於**同一物理場景**驅動接近並接狀態機升舉（n=90：對位 76.7%，升舉 74.4%）。論文主對位敘事仍以 **D3 r3** 為準。

### 不可寫

- 「純聲學 reward 端到端夾取成功」  
- 「證明必須使用聲學觀測」（BLIND+true 反例）  
- 「無附著機制的物理摩擦夾持成功」  
- 將 Lab handoff 與 A lift **跨場景相乘**成未跑同場景的 e2e（同場景請直接報 n=90 分層數字）  
- 用 D4 n=90 或 Lab 100% **取代** D3 r3 正典對位率  

---

## 7. 產物與重現

| 項目 | 路徑 |
|------|------|
| 計畫 | `docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md` |
| 決策 / 風險 | `docs/plan_v2/d4/{decisions,risks,notes}.md` |
| A 三臂 | `runtime/outputs/v2_d4_sm_grasp_n30/` |
| A 入口 | `bash runtime/run_v2_d4_sm_grasp.sh` |
| B 正典 ckpt | `.../v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt` |
| B 訓練 | `bash lab/run_d4_ppo_train.sh`（`ACOUSTIC_ONLY=1` 等 flag 見 notes） |
| B eval | `bash lab/run_d4_ppo_eval.sh` |
| ④ hookup | `bash lab/run_d4_sm_policy_hookup.sh` |
| ⑤ 同場景 | `bash runtime/run_v2_d4_same_scene_policy.sh` |
| 同場景 n=90 | `runtime/outputs/v2_d4_same_scene_policy_n90/` |
| 論文 §5.3 草稿 | `thesis/THESIS_CH5_3_D4_SUPPLEMENT_DRAFT.md` |
| 本報告 | `docs/plan_v2/reports/D4_sm_grasp_report.md` |

---

## 8. 誠實記錄與限制

1. **B Lab vs A/d3 物理**：B 訓練移目標不移臂；同場景串聯已在 d3 跑 n=90，但觀測分布仍有 domain gap。  
2. **true scaffold 訓練**：acoustic_close_ft 的 reward 用 true_range；policy 推理時 obs 無 true。  
3. **d_hat 假近**：pure reward 路徑失敗的主因；若要 pure acoustic 宣稱，需先修估距。  
4. **BLIND 反例**：削弱「聲學必要」全稱；1-DOF + 特權距離獎勵下開環可過。  
5. **weld**：與 D3 相同——附著模擬，非摩擦保持宣稱。  
6. **停靠**：同場景控制距離用 argmax peak（d3 經典），非僅 gated peak。  

---

## 9. 下一步候選

| 優先 | 內容 |
|------|------|
| P0 論文 | 將 `THESIS_CH5_3_D4_SUPPLEMENT_DRAFT.md` 貼入 docx §5.3；§6.2 增限制列 |
| P1 | （可選）修 d_hat 後再試 pure reward |
| P2 | （可選）摩擦資產更換——僅當要挑戰 weld 邊界 |
| ~~P1 同場景~~ | ✅ n=90 完成 |

---

## 10. 一句話

> **D4 = 聲學仍負責「走到窗內」；A 用狀態機 + weld 驗證對位與升舉；B 學接近／合爪時機；同場景 n=90 證明策略可接升舉（對位 76.7%、升舉 74.4%）。D3 r3 仍是對位正典；摩擦升舉與 pure-reward 不宣稱。**
