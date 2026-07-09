# E3 報告 — 目標聲學不可見性 + v9 主數據再審計(2026-07-08)

> 本報告是三段證據的匯合點,結論影響論文核心敘事。每段證據附獨立驗證方式。

## 證據 1:visibility 機制有效(E3a 探針)

`scripts/visibility_wpm_probe.py`(armfree,cube@0.5m,四條件):

| 條件 | early_energy | max\|Δ vs 可見\| |
|------|-------------:|------------------:|
| A 可見 | 124,001.7 | — |
| B visibility off | 19.7 | 251.6 |
| A2 恢復可見(session 雜訊參考) | 123,946.9 | **0.62** |
| C translate 移遠 | 19.8 | 252.1 |
| D RemovePrim | 20.8 | 251.8 |

**三種移除機制等效且有效**(Δ 是雜訊的 400 倍)→ 7/4–7/5 的 baseline-mode 數據**有效**。
重現:`./app/python.sh scripts/visibility_wpm_probe.py`;JSON 在 `runtime/outputs/visibility_wpm_probe_v1/`。

## 證據 2:扳手在 arm+table 場景聲學貢獻為零(既有配對數據)

`global_baseline_diff_v1` 的全局基準用 trial_16 軌跡錄製 → trial_16 自身的 global_diff 欄位就是**完美配對**的有/無扳手差分。結果:oracle 距離從 0.814 m 接近到 0.394 m 的全程 19 步,`global_diff_early_energy` ≤ 2.2e-5(背景能量 ~135 的 1e-7 量級 = E3a 實測的跨 session 浮點雜訊),最近兩步精確為 0.0,**無任何距離趨勢**。其餘 6 個 trial 同量級。

對照:armfree 場景同尺寸量級的 cube 貢獻 124,000 能量單位(信號/背景 = 6000:1)。**同一顆目標,在 arm+table 場景信號歸零**——candidate 機制(未逐一驗證):腕上感測器指向、夾爪/手臂 mesh 遮蔽、參數化近場模型主導。與規則 2-2/2-4、open_space byte-identical(牆是物理不建立,非 visibility)互相印證。

**直接後果**:任何以「能量/差分/matched filter 特徵在 standoff 距離追蹤目標」為目標的方案,在目前場景幾何下**沒有物理基礎**。E3b(配對差分 sweep + early-window MF)取消——既有數據已給出答案:無訊號可萃取。

## 證據 3:v9 主數據的「閉環追蹤」來自 oracle scaffold(再審計)

v9 閉環 25 trials 離線分析(`physical_ai_v9_skip_lift_clean`):

- r(stop_x, wrench_x) = **+0.926** —— 停止位置確實追蹤目標,但:
- 21/25 trials 的 approach_reason = `standoff_reached_forward_cap`——這是 **oracle 出口**(`_check_approach_proximity_exit` 要求 `_oracle_proximity_ok(oracle_m)`),且前進被 `_cap_tool0_target_for_spawn(runtime.spawn.wrench_x_m)` 用**真實 wrench 座標**設上限;
- **`episodes_summary.json` 實錄 `claim_mode: 'scaffold'`**(全部 v9 closed_loop trials)。

也就是說:v9 的 84% vs 29% 比較的是「oracle 上限爬行」vs「oracle 直接 IK」,**兩邊都有目標座標參與,差異來自運動策略,不是聲學資訊**。配合證據 2(聲學特徵物理上不可能含目標資訊),v9 的閉環接近數字**不能**作為聲學閉環控制的證據。

論文統整稿中「閉環:不將目標世界座標作為控制輸入」的敘述,對 v9 **不成立**——這正是本輪健檢要抓的「基於錯誤前提繼續做」模式,只是它埋得比 F1 深一層。

驗證:`python3 -c "import json; print(json.load(open('runtime/outputs/physical_ai_v9_skip_lift_clean/closed_loop_trial_1/episodes_summary.json'))['claim_mode'])"` → `scaffold`。

## 全鏈總結(三輪裁定合併)

| 宣稱 | 狀態 | 依據 |
|------|------|------|
| v4 閉環接近 100% | ❌ 幾何人工產物 | F1 盲走對照 |
| v9 閉環 84% vs 29% | ❌ oracle scaffold,非聲學 | 證據 3 |
| standoff 距離聲學追蹤目標(任何特徵) | ❌ 目標聲學不可見 | 證據 1+2 |
| Phase A 特徵-距離趨勢(ρ≈−0.66) | ✅ 仍成立 | 該場景目標移動時特徵確實變化(材質敏感度 CSV 可獨立驗證 0.5m vs 3.0m 有差) |
| armfree ToF 測距(r≈0.999) | ✅ 仍成立 | 7/6 掃描,n=280 |
| Robotiq 夾取管線(帶內 71%) | ✅ 仍成立 | E2 |
| Physical AI acoustic_only F1≈0.598 | ⚠️ 需重新詮釋 | 扳手不可見 → 特徵編碼的是**手臂自身姿態**(自體回波),不是目標;0.598 > pose_only 0.533 可解釋為聲學對姿態的編碼比 2 維座標更豐富。**未做直接驗證**,列為待辦 |

## 對論文的建議(僅建議,敘事決策屬於用戶/指導教授)

誠實且仍有份量的重構方向:

1. **正結果**:armfree WPM 超聲測距特性化(r≈0.999、T_US 校正、GMO 解析規則)+ Phase A 可重複性——這部分紮實。
2. **負結果 + 機制分析**(有學術價值):arm+table 場景目標回波被遮蔽/淹沒的系統性證據(配對差分、E3a 探針、open_space、材質無效),以及「指標失效偵測方法學」(停止位置變異數、盲走對照、oracle scaffold 審計)——這一章等於一套 sim-based 感測驗證的 audit protocol,是本輪最原創的貢獻。
3. **系統整合**:oracle-scaffold 閉環 + Robotiq 夾取管線照實標註(scaffold 模式),作為工程貢獻。
4. **Physical AI 重新定位**:聲學自體狀態估計(ego-state / acoustic proprioception)——需先補一個直接驗證實驗(用 arm pose 回歸聲學特徵,若 R² 高則定案)。

## 下一步候選(依價值排序,未執行)

- N1:Physical AI 重詮釋的直接驗證(離線,免 GPU:聲學特徵 → sensor pose 回歸)。
- N2:感測器指向/遮蔽診斷(在 grasp 場景 standoff 姿態下放大 cube + 感測器姿態掃描)——回答「為什麼不可見」,補機制分析章。
- N3:與指導教授對齊新敘事後,批次更新 README/audit/docx。
