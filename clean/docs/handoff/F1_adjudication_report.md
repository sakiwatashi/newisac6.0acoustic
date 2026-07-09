# F1 裁定報告 — approach_sweep_v4 指標有效性(2026-07-08)

## 問題

`approach_sweep_v4`(閉環聲學接近,30/30 = 100%)的成功是否來自聲學資訊?
健檢(`docs/HEALTH_CHECK_2026-07-08.md` F1)從既有數據推論「否」;本實驗以對照組正式裁定。

## 方法

**盲走對照組(E1)**:`GRASP_BLIND_APPROACH=1` 把 `fused_distance_m` / `estimated_distance_energy_m` 強制為 `+inf`(`scripts/ultrasonic_grasp_common.py`,健檢 spike),使聲學 standoff 觸發在數學上不可能生效——控制器等同「沿走廊盲目前進直到 IK 失敗」。幾何、trial ids(0–29)、所有其他參數與 approach_sweep_v4 **完全相同**。

- 執行:`bash runtime/run_blind_forward_baseline.sh`(2026-07-08,30 episodes,exit 0)
- 致盲生效證據:run.log 含告示行 `BLIND_APPROACH=1: fused/energy distance forced to +inf`;所有 episode 的 fused 欄為 nan/inf。
- 判讀規則(判讀前預寫於 `docs/handoff/plan.md` 步 5):盲走 ≤0.45 比率 ≥ v4 − 10% 即 F1 成立。

## 結果

| 指標 | 盲走(無聲學) | 閉環 v4(有聲學) |
|------|---------------|-------------------|
| stop_x mean ± std | **0.958 ± 0.000** | 0.958 ± 0.000 |
| Pearson r(wrench_x, stop_x) | 0.107(退化) | 0.248(退化) |
| oracle 距離@停止 | 0.295–0.442 m | 0.295–0.463 m |
| oracle ≤ 0.45 m | **30/30 = 100%** | 29/30 = 96.7% |
| oracle ≤ 0.35 m | **20/30 = 66.7%** | 16/30 = 53.3% |

(數據:`runtime/outputs/blind_forward_baseline_v1/stop_position_analysis.json` vs `runtime/outputs/approach_sweep_v4/stop_position_analysis.json`;重現:`python3 scripts/analyze_stop_position.py --run-dir runtime/outputs/blind_forward_baseline_v1 --compare runtime/outputs/approach_sweep_v4`)

## 裁定

**F1 成立(CONFIRMED)。** 完全沒有聲學資訊的盲走策略,在相同幾何下得到與閉環相同(甚至略優)的接近結果。因此:

1. `approach_sweep_v4` 的「30/30 = 100%」**不能**作為聲學閉環接近能力的證據;`SESSION_SUMMARY_2026-07-08.md` 中「接近成功率 30/30=100%」的敘事棄用。
2. 該幾何(wrench 生成範圍 × IK 可達上限)使「開到底」策略必然停在任何 wrench 的 0.3–0.46 m 內——成功由走廊設計保證,與控制器無關。
3. 兩組唯一的行為差異是 reason 標籤(v4 因 fused 飽和值恰好通過寬鬆門檻而拿到 success 標籤;盲走拿 `ik_failed`)——標籤差異反映的是守門條件,不是控制能力。
4. **D4 生效**:論文 Phase B 主數據錨定 `physical_ai_v9_skip_lift_clean`(閉環 84% vs 開環 29%,有對照組、已 committed)。v4 + 本盲走實驗可改述為「指標失效偵測」方法學素材(停止位置變異數 + 盲走對照)。

## 對 Phase C 的含意

v4 幾何下的夾取實驗(含 E2)中,接近段實際上是「開到固定位置」;夾取成功與否主要由「wrench 是否恰好落在固定停止點的可夾範圍」決定。E2 結果必須據此解讀,不可宣稱為端到端聲學閉環夾取。
