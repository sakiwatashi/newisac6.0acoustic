# E2 報告 — Robotiq 版 Phase C 夾取 sweep(2026-07-08)

## 設定

- 腳本:`runtime/run_closed_loop_grasp_sweep_robotiq.sh` → `runtime/outputs/grasp_sweep_v4_robotiq/`
- 與 grasp_sweep_v3 唯一差異:**移除 `--final-gripper surface`** → 走 Robotiq 2F-85 finger-joint 預設路徑(run.log banner:`Robotiq finger joints: ('finger_joint', ...)`)
- 30 episodes、`--enable-lift`(真實物理升舉)、acoustic_only、幾何與 v4/E1 相同
- 執行 2026-07-08 03:26–03:44,exit 0,每 episode ~35 秒

## 結果

| 指標 | grasp_sweep_v3(SurfaceGripper) | **grasp_sweep_v4_robotiq** | v9 final(參考) |
|------|-------------------------------|---------------------------|----------------|
| grasp 成功 | 0/30 = 0% | **12/30 = 40%**(全為 `grasp_lift_success`,含升舉) | ~20% |

**Robotiq 路徑確認可用**:session summary 的假設(移除 surface 旗標即可)成立,且一次到位拿到含升舉的成功。

## 關鍵交叉分析:成功由幾何決定,不是聲學

per-trial 成功 vs wrench_x(`episodes_summary.json` 直接計算):

```
成功 12 個:wx ∈ [0.944, 1.258],中心 ≈ 1.089
失敗 18 個:全部 wx ≤ 0.914(12 個)+ 帶內散發 5 個(1.002, 1.141, 1.170, 1.179, 1.229)+ 過遠 1 個(1.288)
```

- 接近段停止位置仍恆定(stop_x = 0.958 ± 0.000,tool0 ≈ 0.878;與 E1/F1 一致)。
- **wrench 在 0.944 以内(手臂會開過頭)的 12 個 trial:0% 成功**;
- **wrench 落在固定停止點前方甜蜜帶 [0.944, 1.258] 的 17 個 trial:12/17 ≈ 71% 成功**。

## 結論

1. **夾爪執行不再是主要瓶頸**:在甜蜜帶內 Robotiq 成功率 ~71%(v3 的 0% 是 SurfaceGripper 死路造成,已繞開)。
2. **瓶頸回到接近段**:依 F1 裁定,接近不追蹤目標(固定停止點),所以整體成功率 40% 完全由「wrench 是否恰好落在甜蜜帶」的先驗機率決定。
3. **論文措辭邊界**:40% **不可**宣稱為「聲學閉環夾取成功率」。可宣稱:(a) Robotiq finger-joint 物理夾取+升舉管線在 Isaac Sim 6.0 打通(對照 SurfaceGripper 0/30);(b) 條件成功率 P(grasp|target in reach band) ≈ 71% 表示接觸/升舉物理已可用;(c) 端到端瓶頸在接近段的目標追蹤(F1)。

## 重現

```bash
bash runtime/run_closed_loop_grasp_sweep_robotiq.sh
python3 scripts/analyze_stop_position.py --run-dir runtime/outputs/grasp_sweep_v4_robotiq
```
