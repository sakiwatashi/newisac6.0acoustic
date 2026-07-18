# D4 決策紀錄

> 上游：`docs/plan_v2/ACOUSTIC_GRASP_DUAL_TRACK_PLAN.md`

## D4-1：雙軌並行，D3 r3 只讀

- **決策**：新實驗一律 `runtime/outputs/v2_d4_*`；不修改 `v2_d3_grasp_r3` 判準或數據。
- **原因**：正典對位結果不可被後驗污染。

## D4-2：g0 允許短暫 oracle（僅閘門）

- **決策**：`d4_g0_executor_smoke` 可用 bar 真值把工具送進窗，只測 close+lift 物理。
- **原因**：分離「執行器能否抬」與「聲學能否進窗」。
- **邊界**：g0 產出標 `debug_scaffold: true`；正式 A/B 控制禁止 oracle。

## D4-3：主指標分層

- **決策**：對位 / 升舉 / P(升舉|對位) 分欄；禁止單一總成功率當唯一宣稱。
- **對位容差**：預設沿用 D3 `TOL_ALIGN_X_M=0.02`；若 g0 量出新窗再鎖 D4 版並寫入 runner header。

## D4-4：摩擦優先，weld 僅對照

- **決策**：A/B 預設嘗試真摩擦保持；`--weld-on-stall` 僅對照臂或 g0 失敗後的 fallback 欄。
- **宣稱**：無摩擦保持實證前，不可宣稱物理摩擦夾持。

## D4-5：Track B 觀測禁物體 xyz

- **決策**：policy obs 僅聲學特徵 + 本體（關節/爪）；單元測試鎖定。
- **原因**：否則訓成 privileged grasp，不是聲學。

## D4-6：執行順序 A 冒煙 → B 骨架 → A 三臂 → B 訓練

- **決策**：見計畫 §5；B 長訓不得早於 g0 執行器方向判定。

## D4-7：g0 無 weld 升舉 FAIL → 摩擦不列主路徑（2026-07-16）

- **證據**：`v2_d4_g0_executor` g3 smoke 2/2：對位≈0、接觸 True、lift_ik True、z_gain≈0、lift success 0/2、weld_applied False。
- **決策**：
  1. **不**以「無 weld 升舉率」作為 Track A 主過閘條件。
  2. Track A 主表繼續分層：對位（聲學）+ P(升舉|對位) 在 **weld-on-stall 或日後新執行器** 下報告。
  3. 無 weld 結果保留為 **負結果／限制**：模擬器指墊摩擦不足以拖動 0.15 kg bar（與 D3 D-13 一致）。
  4. Track B 不阻塞於摩擦升舉；obs 仍禁 oracle。
- **不做**：為抬起而放寬對位容差或把 oracle 塞進正式臂。
