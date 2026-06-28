# Isaac Lab Phase 5 — 強化學習規劃（2026-06-28）

**定位：** 口試加分／未來工作；**非碩論必達項**。  
**前置：** Phase 4 smoke ✅、Phase 4.6 SL ✅、**Phase 5 v1 offline PG ✅**（`lab_rl_distance_smoke_v1`）

### Phase 5 v1 已完成（2026-06-28，offline）

- 腳本：`lab/train_rl_distance_smoke.py`、`run_rl_distance_smoke.sh`
- 方法：REINFORCE 線性高斯 policy，在 Lab GMO 軌跡上訓練（**非 in-sim RSL-RL**）
- 結果：MAE **0.27 m**，r **0.47**（與 SL 相當）
- 產出：`rl_reward_curve.png`、`rl_pred_vs_gt.png`
- 論文定位：「RL 訓練迴路 smoke」；下一階 in-sim RSL-RL 見任務 A 原規劃

---

## 1. 為什麼現在才做 RL？

| 階段 | 已完成 | 證明了什麼 |
|------|--------|------------|
| Sim Phase 3 | 30/30 靜態掃描 | 特徵科學有效 |
| Lab Phase 4 | 128-step 動態 smoke | 管線可連續出 obs |
| Lab Phase 4.6 | Sim→Lab 線性 SL | 趨勢可遷移 |
| **Phase 5 RL** | 待做 | **Lab 訓練迴圈可跑**（非精度突破） |

SL 已用 offline 方式證明特徵→距離可行；RL 的價值是展示 **Isaac Lab + RSL-RL 閉環**，不是取代 SL 當主結果。

---

## 2. 建議的 RL 任務（最小可行）

### 任務 A（推薦，1–2 天）：距離估計 RL smoke

與 SL 同構，但放進 Gym 迴圈，用 reward 驅動 policy。

| 項目 | 設計 |
|------|------|
| Env 名稱 | `Ur10RtxAcousticDistance-v0` |
| 基底 | 重構 `lab/ur10_rtx_acoustic_env.py` → `lab/ur10_rtx_acoustic_direct_env.py`（`DirectRLEnv`） |
| 觀測 | `[early_energy, peak, gmo_valid, sensor_x,y,z]`（6–8 維） |
| 動作 | 1 維連續：預測距離 ∈ [1.0, 2.0] m |
| 環境動態 | 目標正弦運動（同 Phase 4） |
| Reward | `r = -|a_0 - d_gt|`（可選 shaping：`-0.01` 每步） |
| Episode | 128 steps |
| 演算法 | RSL-RL PPO（已隨 Lab 安裝） |

**成功標準（smoke）：**
- 訓練 2k–5k env steps 不崩潰
- Tensorboard 有 reward 曲線
- 最終 policy 在 Lab 測試 r ≥ 0.3（不必優於 SL 0.47）

**論文可寫：** 「示範 RSL-RL 閉環；policy 達趨勢級追蹤，未宣稱優於監督基線。」

### 任務 B（進階，碩論可不做的 Phase 5+）：採樣策略

| 項目 | 設計 |
|------|------|
| 動作 | 2D：目標 lateral offset (y,z) 或下一採樣距離偏好 |
| Reward | 資訊增益 proxy（例如 early_energy 變化量、估計誤差下降） |
| 難點 | 需更多 GMO/step；訓練慢 |

留作博士或專題延伸。

### 任務 C（不建議碩論現在做）：6-DOF 手臂控制

- 需 Experimental UR10 + IK + 碰撞
- 與 fixed TCP 敘事衝突
- 見 `ISAAC_LAB_PHASE4_SPEC.md` Phase 5 原註

---

## 3. 實作步驟（任務 A）

```text
Step 1  lab/ur10_rtx_acoustic_direct_env.py
        - 繼承 isaaclab.envs.DirectRLEnv
        - 重用 scene bootstrap（從 ur10_rtx_acoustic_env 抽函式到 lab/scene_bootstrap.py）

Step 2  lab/register_env.py 或 isaaclab_tasks 風格 task 註冊
        - gym.register("Ur10RtxAcousticDistance-v0", ...)

Step 3  lab/train_rl_distance_smoke.sh
        - cd IsaacLab
        - ./isaaclab.sh -p lab/train_rl_distance.py \
            --task Ur10RtxAcousticDistance-v0 \
            --headless --experience isaacsim.exp.base.python.kit \
            --max_iterations 200

Step 4  輸出
        - runtime/outputs/lab_rl_distance_smoke_v1/
        - logs, exported policy, eval CSV vs SL baseline

Step 5  論文（可選 §4.7 末段或 §5.2）
        - 一張 reward curve + 與 SL 的 r 對照表
```

---

## 4. 檔案規劃

```
isaacsim6.0/lab/
  scene_bootstrap.py              # 共用：房間、UR10、RTX、writer（從 env 抽出）
  ur10_rtx_acoustic_env.py        # Phase 4 smoke（保留）
  ur10_rtx_acoustic_direct_env.py # Phase 5 DirectRLEnv
  train_rl_distance.py            # RSL-RL 訓練入口
  run_rl_distance_smoke.sh
  configs/
    ur10_rtx_acoustic_distance_env_cfg.py
```

---

## 5. 技術風險與對策

| 風險 | 對策 |
|------|------|
| GMO 每 step 太慢 | `decimation=4`；episode 縮為 64 steps 訓練版 |
| headless kit 缺 replicator | 固定 `--experience isaacsim.exp.base.python.kit` |
| DirectRLEnv 與 Writer 非同步 | capture step 內多 `simulation_app.update()`；不 per-step `orchestrator.wait`（太慢） |
| policy 不收敛 | smoke 只要求「跑通」；論文對照 SL baseline |
| GB10 PyTorch capability 警告 | 已知，不阻擋 smoke |

---

## 6. 論文 claim boundary（RL 專用）

| 可宣稱 | 不可宣稱 |
|--------|----------|
| 曾以 RSL-RL 跑通 Lab 閉環 | RL 優於 SL / 已部署 |
| reward 設計為 GT 距離監督之代理 | reward 等於實機任務目標 |
| 與 SL 使用相同 obs 定義 | 端到端聲學 RL 已成熟 |

---

## 7. 時程估計

| 工作項 | 時間 |
|--------|------|
| DirectRLEnv 重構 + 註冊 | 4–8 h |
| RSL-RL smoke 調通 | 4–8 h |
| 評估圖 + 論文一段 | 2 h |
| **合計** | **1–2 工作天** |

建議時序：**Word §4.5/§4.6 定稿後** 再做 RL smoke，避免口試前分散。

---

## 8. 與 SL 的對照（論文用表）

| 方法 | 訓練資料 | 測試 | r | MAE |
|------|----------|------|---|-----|
| SL 線性（§4.6） | Sim 125 | Lab 27 | 0.47 | 0.41 m |
| RL PPO（Phase 5 目標） | Lab 線上 | 同 env | ≥0.3（smoke） | 待填 |

若 RL 未優於 SL，結論寫：「線性特徵映射已足夠趨勢任務；RL 證明管線可擴展至更複雜策略。」

---

*Phase 5 的價值是「閉環跑通」，不是「beat SL」。*