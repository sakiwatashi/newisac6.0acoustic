# runtime/outputs 正典清單（MANIFEST）

> 何者為 primary（論文主數字）、historical（保留之失效／中間輪）、confirmatory（佐證探針）。

| 目錄 | 角色 | 說明 |
|------|------|------|
| `v2_s1_envelope/` | **primary** | S1：52 選定格配對移除 |
| `v2_s2_datasheet/` | **primary** | S2：距離／側向／重複性 |
| `v2_d1_approach/` | **primary** | D1：飛行感測器三臂 |
| `v2_d15_arm_approach/` | **primary** | D1.5：UR10e 主結果三臂 |
| `v2_d3_gates/` | **primary**（閘門） | D3.0 可偵測／測距／mover；含 `bar_calibration.json`（D2 同 bar 幾何沿用） |
| `v2_d3_grasp_r3/` | **primary**（D3 夾取） | 走廊 1.15 m；四判準全綠 |
| `v2_d3_grasp/` | **historical failure** | 首輪 1.20 m；`d3_posture_clean=False`（3/90 升舉 IK） |
| `v2_d3_grasp_r2/` | **historical** | 中間輪 1.18 m；1/90 仍失敗 |
| `v2_d2v2_formal/` | **primary** | D2 正式三臂 |
| `v2_d2v2_probe/` | confirmatory | D2 g2 探針（設計階段） |
| `v2_d2v2_probe_wide/` | confirmatory / 止損 | 2D 再夾取閘門：側向 RMSE 1.84→止損 |
| `rxgroup_probe_v1/` | primary（負結果） | 側向分組證偽 |
| `visibility_wpm_probe_v1/` | confirmatory | 能見度／WPM 探針 |
| `armfree_freq_sweep/` | confirmatory（負結果） | 20–100 kHz 峰值不變 |
| `ml_stage3/` | confirmatory | E1/E2/E3 教學／延伸；非主鏈判準 |
| `v2_acceptance/` | confirmatory | 早期接受度檢查 |

## 驗證入口如何對應

`runtime/verify_all.sh`：

- 重算 primary 鏈（含 D3 **r3** 預期 0 個 False）。
- 另印 D3 **首輪** 分析（預期含 `d3_posture_clean=False`，**不計入失敗**，作為失效案例保留）。
- 側向四重證偽與頻率不變性當場重算。

## 校正資產

| 檔案 | 用途 |
|------|------|
| `v2_d3_gates/bar_calibration.json` | bar 目標、桌高幾何之當輪 peak→距離；D3 與 D2 formal runner 沿用（同掛載／同 bar） |

更乾淨的長期目標可抽成 `runtime/calibration/bar_tableheight_calibration.json`（尚未搬移，避免斷路徑）。
