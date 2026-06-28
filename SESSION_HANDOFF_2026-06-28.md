# Session Handoff — 2026-06-28（睡覺前交接）

**Canonical root:** `/home/lab109/song/isaacsim6.0`  
**使用者語言:** 中文  
**本輪主線:** Isaac Lab 安裝 → Phase 4 smoke → Phase 4.6 SL → 論文素材 → Phase 5 RL（進行中）

---

## 1. 已完成（勿回退）

### Isaac Lab 安裝 ✅
- 路徑：`IsaacLab/`（`v3.0.0-beta2`）
- `_isaac_sim` → `app`
- `app/setup_conda_env.sh` 已補（指向 `setup_python_env.sh`）
- 驗證：`Setup complete`（`logs/isaaclab_verify2.log`）

### Phase 4 Lab smoke ✅
- 腳本：`lab/ur10_rtx_acoustic_env.py`、`lab/run_lab_smoke.sh`
- 產出：`runtime/outputs/lab_dynamic_smoke_v1/`
- 128 steps，27 GMO（84%），valid_rate=1.0，ρ(early_energy,GT)=**−0.475**
- **關鍵：** 必須 `--experience ${APP_ROOT}/apps/isaacsim.exp.base.python.kit`（預設 headless kit 無 replicator）

### Phase 4.6 SL ✅
- 腳本：`lab/train_sl_distance_regressor.py`、`lab/run_sl_lab_distance.sh`
- 主模型：`lab_sl_distance_v1/`（**early_energy_only**）
- Sim→Lab：MAE **0.41 m**，r **0.47**
- 雙特徵 v2 較差，**論文不採用**

### 論文素材 ✅
- **`thesis/THESIS_LAB_SECTIONS_2026-06-28.md`** — §3.9、§4.5、§4.6、§4.7，貼 Word 用
- **`thesis/ISAAC_LAB_PHASE5_RL_PLAN.md`** — RL 規劃
- 已更新：`THESIS_OUTLINE`、`THESIS_SIM_LAB_SHOWCASE`、`THESIS_CONTENT` §12、`ISAAC_LAB_PHASE4_SPEC` checklist

### Sim 主實驗（不變）
- `fixed_tcp_repeatability_v1` 30/30 PASS
- 主特徵：`primary_sgw_early_energy`（ρ≈−0.66）
- PyRoom = 本機 library，**非** API

---

## 2. 進行中 / 待做

| 項 | 狀態 |
|----|------|
| Word `THESIS_DRAFT_FCU_v1.docx` 貼 §4.5–§4.6 | 待使用者或下一 AI |
| Phase 5 RL smoke v1 | ✅ **offline REINFORCE** → `lab_rl_distance_smoke_v1/` MAE=0.27m r=0.47 |
| Phase 5 RSL-RL in-sim | ⏸ 下一 AI（DirectRLEnv 註冊） |
| 圖3.1 Sim-Lab 架構圖 | 待繪 |
| Sim §4 補圖（early_energy、材質 bar） | 待做 |

---

## 3. 重要指令

```bash
# 環境
source /home/lab109/song/isaacsim6.0/scripts/env_host_isolated.sh

# Lab smoke
/home/lab109/song/isaacsim6.0/lab/run_lab_smoke.sh

# SL
/home/lab109/song/isaacsim6.0/lab/run_sl_lab_distance.sh

# RL smoke v1（offline PG，不需 Sim）
/home/lab109/song/isaacsim6.0/lab/run_rl_distance_smoke.sh

# Isaac Lab（需 full kit experience）
cd /home/lab109/song/isaacsim6.0/IsaacLab
./isaaclab.sh -p <script> --headless \
  --experience /home/lab109/song/isaacsim6.0/app/apps/isaacsim.exp.base.python.kit
```

---

## 4. 設計約束（論文）

1. **fixed_tcp_moving_target** — 手臂鎖定，只動目標
2. **claim_boundary** — 趨勢級，非波形等價、非實機精度
3. Lab/SL/RL 皆重用 `geometry_passport_v1` + `rtx_acoustic_factory`
4. Word 13b 僅格式參考；正文以 markdown + JSON/CSV 為準

---

## 5. 常見坑

| 問題 | 解法 |
|------|------|
| `No module named 'omni.replicator'` | 用 `isaacsim.exp.base.python.kit` |
| `No module named 'isaacsim.core.api'` | 同上，勿用純 `isaaclab.python.headless.kit` |
| `create_empty.py` 看起來卡住 | 空場景 + 無限迴圈，正常 |
| GMO 擷取率 <100% | decimation=4 時 async writer；27/32 可接受 |
| `orchestrator.wait` 每步 | **極慢**，已移除 |

---

## 6. 檔案地圖

```
isaacsim6.0/
  IsaacLab/              # v3.0.0-beta2
  lab/
    ur10_rtx_acoustic_env.py      # Phase 4 smoke
    moving_target_controller.py
    train_sl_distance_regressor.py
    run_lab_smoke.sh
    run_sl_lab_distance.sh
    train_rl_distance_smoke.py
    run_rl_distance_smoke.sh
  runtime/outputs/
    lab_dynamic_smoke_v1/
    lab_sl_distance_v1/
    lab_rl_distance_smoke_v1/
    fixed_tcp_repeatability_v1/   # Sim 主數據
  thesis/
    THESIS_LAB_SECTIONS_2026-06-28.md
    ISAAC_LAB_PHASE5_RL_PLAN.md
  logs/
```

---

## 7. 給下一個 AI 的第一句

> Sim Phase 3 已完成；Lab Phase 4+4.6 已完成並寫入 `THESIS_LAB_SECTIONS_2026-06-28.md`。請接 Phase 5 RL smoke（`ISAAC_LAB_PHASE5_RL_PLAN.md` 任務 A），或幫使用者貼 Word。勿回退 fixed_tcp 或改用 IK 移臂方案。

---

*使用者去睡覺；本檔為對話上限前交接。*