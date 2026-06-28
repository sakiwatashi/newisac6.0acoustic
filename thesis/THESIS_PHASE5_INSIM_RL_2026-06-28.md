# 論文正文素材：Phase 5 in-sim RSL-RL（§3.10、§4.7.1）

**狀態：** 可貼入 Word 初稿；v5（500 iter, shaped reward）訓練與 eval 已完成（2026-06-29）
**定位：** 口試加分／方法延伸；**非主貢獻**（主貢獻仍為 Sim Phase 3 + Lab §4.5–§4.6）  
**Canonical 輸出：**
- v3：`runtime/outputs/lab_rl_distance_in_sim_long_v3/`
- v4：`runtime/outputs/lab_rl_distance_in_sim_long_v4/`
- v5：`runtime/outputs/lab_rl_distance_in_sim_long_v5/`（訓練中／待填）

---

## 摘要增補句（可併入既有 Lab/SL 段之後）

**中文：**

> 進一步地，本研究以 Isaac Lab `DirectRLEnv` 搭配 RSL-RL PPO，於模擬器內閉環訓練距離估計策略（in-sim RL），直接以 RTX GMO 觀測驅動策略更新；在修正 GMO 擷取管線後，策略於 hold-out 評估達趨勢級追蹤（deterministic MAE 約 0.11–0.13 m，Pearson r 約 0.10–0.33），惟聲學特徵對距離之變異解釋量仍有限（raw early_energy 變化 <0.5%），故僅作訓練迴路可行性示範，不宣稱優於 §4.6 監督基線。

**英文：**

> An in-simulation closed-loop extension was implemented with Isaac Lab `DirectRLEnv` and RSL-RL PPO, training a distance-estimation policy directly from RTX GMO observations. After fixing the GMO capture pipeline, hold-out evaluation showed trend-level tracking (deterministic MAE ≈0.11–0.13 m, Pearson r ≈0.10–0.33), while acoustic features still exhibited very weak distance sensitivity (raw early_energy range <0.5%). This demonstrates a feasible training loop rather than superiority over the supervised baseline in §4.6.

---

## 第三章 §3.10 In-sim 強化學習環境（DirectRLEnv + RSL-RL）

### 3.10.1 動機與與離線 RL smoke 之差異

§4.6 與 Phase 5 v1 離線 REINFORCE smoke 均在**已記錄之 GMO 軌跡**上更新策略，環境動態不隨 policy 互動而重算 RTX。為驗證 **Isaac Lab + RSL-RL 閉環**，本節改採 `DirectRLEnv`：每一步 policy 輸出距離預測，模擬器同步推進目標軌跡、觸發 GMO 擷取並回傳 reward。

### 3.10.2 環境規格

| 項目 | 設定 |
|------|------|
| 任務 ID | `Isaac-Ur10RtxAcousticDistance-Direct-v0` |
| 實作 | `lab/isaaclab_tasks_ext/ur10_rtx_acoustic_distance/ur10_rtx_acoustic_direct_env.py` |
| 場景 bootstrap | `lab/scene_bootstrap.py`（重用 Phase 4 Geometry Passport） |
| 觀測（6 維） | `early_energy×1e-4`, `peak×1e-2`, `gmo_valid`, `sensor_x,y,z` |
| 動作（1 維） | 連續值 ∈ [−1,1] → 距離 [1.0, 2.0] m |
| 目標運動 | `d(t)=1.5+0.5·sin(2π·step/64)` m（與 §4.5 一致） |
| Episode | 32 policy steps（decimation=4，physics dt=0.01 s） |
| GMO | 每 2 policy steps 擷取；`timeline.play()` + `SimulationApp.update()` |
| 啟動 | `AppLauncher` + `isaacsim.exp.base.python.kit`（**非** `./isaaclab.sh train`） |

### 3.10.3 獎勵設計演進

**基線（v3/v4）：** `r = −|pred − gt|`

**塑形獎勵（v5，建議論文描述）：**

```text
r = −1.0·|pred−gt|
    −0.35·|pred−d_energy|
    +0.15·𝟙[sign(Δpred)=sign(Δgt) ∧ |Δgt|>0.02]
    −0.25·(1−gmo_valid)
```

其中能量先驗距離（Phase 4 趨勢，ρ≈−0.77）：

```text
d_energy = clamp(1.5 − 0.27·(raw_E − 4290)/50, 1.0, 2.0)  [m]
```

目的：在 L1 距離誤差之外，鼓勵策略與 `early_energy` 隱含距離一致，並獎勵與 GT 同向之預測變化。

### 3.10.4 PPO 設定摘要

| 版本 | 迭代數 | 特點 |
|------|--------|------|
| v3 | 200 | 基線 MLP，無 obs normalization |
| v4 | 200 | `empirical_normalization` + actor/critic obs norm |
| v5 | 500 | v4 + 塑形獎勵 + `entropy_coef=0.08` |

演算法：RSL-RL PPO；`num_steps_per_env=32`；hidden [64,64]。

---

## 第四章 §4.7.1 In-sim RSL-RL 距離估計實驗

### 4.7.1.1 實驗目的

示範 (1) RTX GMO 管線可支撐 in-sim 策略梯度訓練；(2) 修正 writer 生命週期後觀測有效（`gmo_valid=1`）；(3) 與 §4.6 SL 基線對照時，明確劃定 claim boundary。

### 4.7.1.2 關鍵工程修正（方法貢獻之一）

初期長訓練（v1/v2）出現 `pred` 常數化，根因為 GMO writer 於 `sim.reset()` 後失效，且誤用 `omni.kit.app` 物件。修正要點：

1. `simulation_app_ref.set_simulation_app(app_launcher.app)`
2. `rebind_rtx_gmo_writer()` 於 `DirectRLEnv.__init__` 完成後
3. `capture_rtx_gmo()` 採 Phase 4 之 `timeline.play()` 模式

修正後 smoke：`gmo_init_captured=True`，`obs0=[E≈0.43, P≈4.76, valid=1]`。

### 4.7.1.3 評估協定

- Headless play：`lab/eval_rl_distance_in_sim.py`，64 steps
- 指標：MAE、Pearson r(gt, pred)、Pearson r(gt, raw_E)、pred 標準差
- 模式：deterministic（均值動作）與 stochastic（採樣）

### 4.7.1.4 結果（v3/v4，已完成）

**表4.7 In-sim RSL-RL hold-out 評估（64 steps，材質 B，fixed TCP）**

| 訓練 run | Checkpoint | 模式 | MAE (m) | r(gt,pred) | r(gt,raw_E) | pred mean±std (m) | E range % |
|----------|------------|------|---------|------------|-------------|-------------------|-----------|
| long_v3 | model_199 | det | **0.115** | 0.335 | 0.020 | 1.576±0.000 | 0.32 |
| long_v3 | model_100 | det | 0.215 | 0.233 | 0.077 | 1.798±0.000 | 0.41 |
| long_v4 | model_199 | det | 0.132 | −0.308 | 0.020 | 1.513±0.006 | 0.32 |
| long_v4 | model_199 | stoch | 0.126 | **0.247** | −0.042 | 1.534±0.083 | 0.35 |
| long_v5 | model_499 | det | 0.441 | 0.229 | 0.077 | 1.637±0.477 | 0.41 |
| long_v5 | model_499 | stoch | 0.457 | 0.078 | −0.035 | 1.559±0.481 | 0.46 |

**表4.8 與 §4.6 監督基線對照**

| 方法 | MAE (m) | Pearson r | 備註 |
|------|---------|-----------|------|
| Sim→Lab 線性 SL（§4.6） | 0.41 | **0.47** | 主學習基線 |
| 離線 REINFORCE smoke（Phase 5 v1） | 0.27 | 0.47 | 非 in-sim |
| in-sim PPO v3 model_199 | **0.115** | 0.34 | det；pred 近常數 |
| in-sim PPO v4 model_199 stoch | 0.126 | 0.25 | 略有變異 |

**解讀（務必寫進正文）：**

1. in-sim RL 之 MAE 較低，部分來自策略收斂至**窄範圍常數預測**（det 模式 pred_std≈0），並非全面優於 SL。
2. `r(gt, raw_E)≈0` 表示 GMO 能量在 1–2 m 動態區間內變化極小（<0.5%），限制觀測可辨識度。
3. SL 在趨勢相關（r≈0.47）上仍較穩健；RL 價值在**閉環管線驗證**，非精度超越。

### 4.7.1.5 v5 結果（500 iter，塑形獎勵，已完成）

| 項目 | 值 |
|------|-----|
| Checkpoint | `model_499.pt` |
| det MAE / r | **0.441 m / 0.229** |
| stoch MAE / r | 0.457 m / 0.078 |
| pred 動態（det） | 1.637±0.477 m（較 v3 明顯有變異） |
| raw_E range | 0.41%（與 v3 同級，觀測仍弱） |
| 訓練末期 error（log） | iter 499：`distance_error_m=0.358`，`Mean reward≈−19.71` |
| 訓練 log | `logs/lab_rl_distance_in_sim_v1_long_v5.log` |
| eval log | `logs/eval_rl_v5_model499.log` |

**解讀：** v5 塑形獎勵使策略脫離 v3 之近常數預測（pred_std 由 ≈0 升至 ≈0.48 m），但 hold-out MAE 升至 ≈0.44 m，未優於 §4.6 SL（MAE=0.41 m, r=0.47）。此結果支持「RL 價值在閉環可行性，非精度超越」之 claim boundary。

### 4.7.1.6 Claim boundary（§4.7.1 必寫）

| 可宣稱 | 不可宣稱 |
|--------|----------|
| Isaac Lab DirectRLEnv + RSL-RL 閉環可跑通 | in-sim RL 優於 §4.6 SL |
| GMO 管線修正後觀測有效 | MAE 0.11 m 可部署 |
| 塑形獎勵 + 長訓練為後續研究起點 | 策略已學會物理測距 |
| 與 SL 互補：SL 證遷移，RL 證閉環 | early_energy 已足夠支撐高精度 RL |

### 4.7.1.7 圖表建議

| 圖號 | 內容 | 來源 |
|------|------|------|
| 圖4.9 | PPO 訓練 reward / distance_error 曲線 | TensorBoard 或 log grep |
| 圖4.10 | eval：pred vs gt 時序（v3 vs v5） | play 診斷輸出 |

---

## 第五章 §5.2 增補（Phase 5 in-sim 完成後）

### 5.2.3 已完成之 in-sim RL 階段
- DirectRLEnv 註冊與 scene_bootstrap 整合 ✅
- GMO writer 生命週期修正 ✅
- v3 200-iter 長訓練 + hold-out eval ✅
- v4 obs normalization 實驗 ✅
- v5 塑形獎勵 500-iter + hold-out eval ✅（MAE≈0.44 m，趨勢追蹤但未優於 SL）

### 5.2.4 後續建議
- 擴大距離範圍或離軸點位以增加 E 動態
- 多 env 平行（若 GPU 允許）加速 PPO
- CH201 實機 task-level 驗證（協定參考 §4.6）

---

## Word 貼上檢查清單（Phase 5 增補）

- [ ] 摘要中英文各加 in-sim RL 一句（見上）
- [ ] 第三章插入 §3.10
- [ ] 第四章 §4.7 下增 §4.7.1（或獨立 §4.8，與導師確認編號）
- [ ] 插入表4.7、表4.8；v5 完成後補表4.7 最後一列
- [ ] 圖4.9–4.10（可選）
- [ ] §5.2.3 勾選完成項