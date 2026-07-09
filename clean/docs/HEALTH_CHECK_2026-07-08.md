# 專案健檢報告 — 2026-07-08

**範圍**:全 repo 唯讀審計(未修改任何程式/設定/資料)。
**對照基準**:`docs/WPM_EXPERIMENT_RULES.md`(規則文本)、`REPRODUCIBILITY_AUDIT.md`、claim boundary(7/1 權威敘事)。
**動機**:過去曾發生「基於錯誤參數繼續實驗,最後才發現問題」(如 GRASP_SKIP_LIFT DynamicCuboid 污染、z 軸當時間軸)。本次健檢針對同類風險做系統掃描。
**每條發現附驗證方式,可獨立重現。**

---

## 總覽

| 嚴重度 | 數量 | 摘要 |
|--------|------|------|
| 🔴 高(結論有效性) | 4 | F1 approach_sweep_v4 指標無效、F2 死門檻、F3 能量方向矛盾、F4 測試失敗 |
| 🟡 中(一致性/世系) | 5 | F5–F9:校正表雙源、TOF 假值、early_energy 雙定義、文件數字漂移、grasp sweep 旗標 |
| 🟢 低(清理) | 3 | F10–F12:重複腳本、孤兒模組、硬編碼路徑 |
| ✅ 通過項 | 6 | 見「通過項」一節 |

---

## 🔴 高嚴重度

### F1:approach_sweep_v4「30/30 = 100%」不是聲學閉環的證據(本報告最重要發現)

**現象**(從 `runtime/outputs/approach_sweep_v4/` 原始數據直接計算):

- wrench 隨機分布於 x = 0.717–1.288 m(跨度 0.57 m),但 **30 個 episode 的最終 sensor_x 全部 = 0.958 m,零變異**。停止位置與目標位置完全無關。
- 停止時 `fused_distance_m` = 0.61–0.73 m(貼近校正表上限 0.728,飽和),而真實 oracle 距離 = 0.30–0.46 m。**控制器的距離估計與真實距離脫鉤**。
- 聲學 standoff 觸發條件(fused ≤ GRASP_STANDOFF_M = 0.35)在巡航中**從未生效**:對最近的 wrench(0.717 m),理想聲學停止點約 sensor_x ≈ 0.45,實際卻一路開到 0.958(超過目標 0.24 m)。
- 停止機制是 **IK 可達上限**(tool0_x ≈ 0.878 → sensor_x = 0.958):13/30 episode 直接標為 `standoff_reached_ik_limit`,其餘 `descend_ready` 也停在同一位置。
- 「oracle 距離 ≤ 0.45 m:29/30」是**走廊幾何的必然結果**:wrench 生成範圍(`WRENCH_X_MIN_M`–`WRENCH_X_MAX_M`,`grasp_passport_v1.py:115-119`)的設計本身保證「開到 IK 上限」就落在 0.30–0.46 m 內。任何「無感測、直接開到底」的開環策略會得到**完全相同的 30/30**。
- v4 sweep **沒有 open-loop 對照組**(`runtime/run_closed_loop_approach_sweep.sh` 只跑 closed_loop)。

**與 committed 敘事的關係**:v9 資料集(84% vs 開環 29%)有對照組、幾何不同,其結論**不受本發現影響**。受影響的是 7/6–7/8 的 v4 敘事(`runtime/SESSION_SUMMARY_2026-07-08.md` 稱「接近成功率 30/30 = 100%」)以及以它為前提的 Phase C。

**與規則文本的印證**:規則 2-2(手臂 mesh 主導信號)、規則 2-4(有 UR10e 手臂的距離回歸 R²≈0,5+ 次實驗)早已預言 arm+table 場景的能量→距離不可靠;v4 數據證實 fused 距離確實無資訊量。

**驗證方式**:
```bash
python3 - <<'EOF'
import csv, json, math
eps = json.load(open('runtime/outputs/approach_sweep_v4/episodes_summary.json'))['episodes']
wx = {e['trial_id']: e['wrench_oracle_position_m'][0] for e in eps}
rows = list(csv.DictReader(open('runtime/outputs/approach_sweep_v4/ultrasonic_closed_loop_grasp_history.csv')))
stop = {}
for r in rows:
    try: sx = float(r['sensor_x_m'])
    except: continue
    if math.isfinite(sx):
        t = int(r['trial_id']); stop[t] = max(stop.get(t, -9), sx)
print('stop_x 範圍:', min(stop.values()), '-', max(stop.values()))
print('wrench_x 範圍:', min(wx.values()), '-', max(wx.values()))
EOF
# 預期輸出:stop_x 範圍 0.958–0.958(恆定);wrench_x 範圍 0.717–1.288
```

**建議**(未執行,僅建議):v4 需補跑同幾何的 open-loop 對照(預測:同樣 30/30 → 證明指標無效);接近成功的主指標應改為「停止位置 vs 目標位置的相關性/誤差」,而非 reason 集合成員資格。**在此之前,Phase C 不應把 v4 的 100% 當作「接近已解決」的前提。**

### F2:最終接近的 0.14 m 門檻是死碼(數學上不可能觸發)

- `FINAL_APPROACH_STANDOFF_M = 0.14`(`grasp_passport_v1.py:174`)。
- 但控制距離 `fused_distance_m` 來自 tier_b 能量表插值,表的距離下限 = **0.256 m**(clamp,見 `runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json`);fallback `DEFAULT_CALIBRATION` 下限 0.10 m,但 sweep 實際載入 JSON。
- 因此 `_final_approach_decision` 的 `distance_m <= 0.14`(`ultrasonic_closed_loop_controller.py`)**永遠為假**,最終接近一律以 `descend_final_limit`(固定 8 步開環前進)結束。
- **影響**:「final acoustic creep」實際上是開環定步數推進,不是聲學閉環;這也可能是 Phase C 夾取對位不準的成因之一。

**驗證**:`python3 -c "import json; t=json.load(open('runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json'))['energy_calibration']; print('表距離下限:', min(d for _,d in t))"` → 0.256 > 0.14。

### F3:能量→距離校正表方向與 Phase A 趨勢相反,且世系可疑

- Phase A 結論(論文地基):early energy 與距離**負相關**(ρ≈−0.66)→ 越近能量越高。材質敏感度數據同向(0.5 m:165.4 > 3.0 m:157.1)。
- 但 `tier_b_calibration.json` 與 `DEFAULT_CALIBRATION`(`grasp_passport_v1.py:145-155`)都是**越近能量越低**(153.8→0.728 m、133.0→0.256 m)。
- 兩者不能同時代表「目標回波」。合理解釋(與規則 2-2 一致):arm+table 場景的能量變化由手臂自身姿態/桌面幾何主導,校正表學到的是「手臂伸展程度」而非目標距離——這與 F1 的實證(fused 與 oracle 脫鉤)吻合。
- 世系:tier_b JSON 生成於 **6/30**,單一 trial(trial_id=9)、n=19 樣本、單一 wrench 位置;JSON 內自帶 `claim_boundary: "Tables built from oracle_distance_m for offline labeling only."`,但 `ultrasonic_grasp_common.py:242` 將它用於**線上控制**——與自己宣告的用途矛盾(口試防線漏洞)。

**驗證**:對照 `runtime/outputs/phase3_material_sensitivity_sgw/material_cross_condition_features.csv`(近=高能量)與 tier_b JSON(近=低能量)。

### F4:單元測試失敗 — 測試與實作已漂移

- `python3 scripts/test_ultrasonic_closed_loop_controller.py` → **FAILED (failures=1)**。
- 原因:未提交的修改把 `DistanceCalibration.estimate_distance_m()` 的語意從「early_energy 查表」改成「peak_sample_idx × T_US × V/2 公式」(git diff `ultrasonic_closed_loop_controller.py`),但 `test_calibration_interpolation` 仍餵能量值 160 並期望 < 3.0 m;新公式回傳 160 × 132.5e-6 × 343 / 2 = 3.636 m。
- 這正是「語意改了、下游沒跟上」的模式。同語意的欄位 `estimated_distance_m` 在 history CSV 中前後兩批數據(v9 vs v4)含義不同,跨批比較時會踩雷。
- 其餘測試:`test_acoustic_calibration_v1.py` ✅、`test_acoustic_features.py` ✅、`test_grasp_passport_reach.py` ✅(4 檔中 3 過 1 敗)。

---

## 🟡 中嚴重度

### F5:校正表雙源並存,shell 註解與實際不符

- 舊接近腳本 `official_asset_ur10_ultrasonic_closed_loop_approach.py:417` 用 baked-in `DEFAULT_CALIBRATION` — 該常數自己的註解寫著 **[DEPRECATED]**。
- 兩個 sweep(approach v4 / grasp v3)其實都跑 `official_asset_ur10_ultrasonic_closed_loop_grasp.py`,經 `_tier_b_calibration_tables()` 載入 **tier_b JSON**。
- 但兩個 sweep shell 的註解與 log 都寫「`DEFAULT_CALIBRATION`」——**與實際載入的表不符**。兩表的 clamp 範圍不同(0.10–0.90 vs 0.256–0.728),重現實驗時會誤導。

### F6:TOF 相關的殘留假值

- `timeOffsetNs` 恆為 0(已知 Isaac Sim 6.0 限制,規則 1-3),tier_b JSON 的 `tof_calibration` 為空 → runtime 回退到 `DEFAULT_TOF_CALIBRATION`(`grasp_passport_v1.py:160-168`)——這組值(0.72e6–1.28e6 ns)**沒有任何實測來源**(校正 sweep 的 19 筆 TOF 全為 0)。
- 融合有雙重防護(`reject_zero` + `min_valid_tof_ns=1e5`),實際 fused = 純能量 ✅。但:
  - `acoustic_features_from_summary`(管線實際使用的路徑)建 `tof_ns` 時**沒有** `reject_zero`,與 `acoustic_features_from_gmo`(有 `reject_zero=True`)行為不一致;
  - `estimated_distance_tof_m` 因此以 0 ns 插值出 **0.22 m 的假值**寫進 history/dataset;它也在 `train_physical_ai_acoustic_policy.py` 的 all_features 欄位裡(常數欄,無害但污染)。
- 論文措辭風險:「Tier B = energy + TOF 融合」實際上是**純能量**;`REPRODUCIBILITY_AUDIT.md` 未提交的修改已記錄此事(good),論文正文需同步。

### F7:early_energy 有兩種不相容定義並存

- 管線家族(`rtx_acoustic_factory.py:163`):前 **25%** 樣本(fraction=0.25,樣本數隨 numSamplesPerSgw 浮動)。
- armfree 家族(4 支腳本)與規則文本:固定 **N_EARLY=20** 樣本。
- 規則 4-3 自稱範本「與 rtx_acoustic_factory.py 相容」,但範本用 N_EARLY=20——**規則文本自我矛盾**。
- 影響:論文若同時引用 Phase A/v9(fraction 定義)與 armfree 圖表(N_EARLY 定義)的 "early energy" 數字,兩者不可直接比較,需在文中標明。

### F8:文件數字與最新數據漂移(多套敘事並存)

- `README.md` / `REPRODUCIBILITY_AUDIT.md` / 論文統整稿停留在 v9(84% vs 29%);
- `SESSION_SUMMARY_2026-07-08.md` 主張 v4 = 100%(依 F1,此指標無效);
- `grasp_sweep_v3` = 0/30(SurfaceGripper 路徑)。
- 三套數字沒有任何一份文件同時交代。**若 F1 成立,建議明確棄用 v4 的 100% 敘事,論文主數據回錨 v9**(v9 有對照組、且已 committed)。

### F9:`run_closed_loop_grasp_sweep.sh` 仍帶 `--final-gripper surface`

- 已知問題(session summary 有記錄),此處列入以完整化:該旗標強制走已證實不工作的 SurfaceGripper 路徑;Robotiq 預設路徑已實作未啟用。
- 注意:即使改用 Robotiq 重跑,**F1/F2 的接近品質問題仍在**——夾取成功率可能受「停在固定位置而非目標前」拖累,兩者需一併解讀。

---

## 🟢 低嚴重度(清理項)

### F10:四支重疊的校正分析腳本

`calibration_analysis.py`、`calibration_analysis_output.py`、`recalibrate_energy_from_dataset.py`、`test_recalibration.py` 功能高度重疊(都在做 v9 能量→距離重校),且輸出路徑指向 `scripts/*.txt`(報告寫進原始碼目錄;目前檔案不存在,表示從未成功跑完或輸出已刪)。其重校結果**沒有接回**任何 runtime 表。

### F11:`vector_utils.py` 為零引用的孤兒模組

自述「口試前不強制替換」——狀態如實,但需知道它目前沒有任何腳本 import。

### F12:絕對路徑硬編碼

`acoustic_calibration_v1.py:12`(`DEFAULT_CALIBRATION_JSON`)、`recalibrate_energy_from_dataset.py` 等寫死 `/home/lab109/song/isaacsim6.0/...`,與 README 的「或你的 clone 路徑」承諾衝突(重現性風險,口試搬機器會炸)。

---

## ✅ 通過項(明確驗證無問題)

1. **規則 1-1/1-2(GMO stride)**:`rtx_acoustic_factory.py` 正確以 `gmo.z` 為 channel ID、以 `numSamplesPerSgw` stride 重建波形;無「z 當時間軸」殘留。
2. **規則 1-4(T_US)**:全庫一致使用 132.5e-6;無 102.4e-6 殘留。
3. **規則 4-1(argparse 順序)**:抽查 4 支新 sim 腳本,argparse 均在 `SimulationApp` 之前。
4. **acoustic_only 特徵集無 oracle 洩漏**:`run_physical_ai_v8_randomized_pipeline.py:23-37` 的 `ACOUSTIC_ONLY_FEATURES` 不含 `estimated_distance_*`、`fused_distance_m`、`sensor_x/y` → **F1≈0.598 的 claim 乾淨** ✅。
5. **acoustic_only 模式的 oracle 出口正確關閉**:`_check_approach_proximity_exit` / `_cap_tool0_target_for_spawn` 均在 `if not _acoustic_only_claim(runtime)` 之內 → v4 的問題不是 oracle 作弊,而是指標定義(F1)。
6. **材質條件已知無效並有記錄**:規則 2-4 + 實測數據(條件 A/B 特徵至小數第 4 位相同)一致;論文中「材質條件 B」只能作為協定標註,不能作為實驗變因宣稱(口試需能回答)。

---

## 驗收對照

| 驗收條件 | 狀態 |
|----------|------|
| 1. 滿足原先規則要求 | 逐條對照 `WPM_EXPERIMENT_RULES.md` 完成:規則 1-1/1-2/1-3/1-4/4-1 合規;規則 4-3 發現文本自我矛盾(F7);規則 2-2/2-4 的預言被 v4 數據證實(F1/F3) |
| 2. 輸出可驗證報告 | 本檔;每條發現附 file:line 或可執行驗證指令 |
| 3. 過程未詢問/未要求確認 | 是;全程唯讀,未修改任何程式、設定、main branch,未做無關重構,未加功能 |

## 建議處理順序(供決策,本次未動手)

1. **先裁定 F1**:補跑 v4 幾何的 open-loop 對照(一條 sweep 即可)。若開環同樣 30/30,正式棄用 v4 敘事,回錨 v9。
2. 修 F4 測試(對齊新語意)——一行級修改。
3. Phase C 重跑前先解 F2(門檻 0.14 vs clamp 0.256 擇一修正),否則 Robotiq 版重跑仍會在「開環 creep 8 步」的對位品質上受限。
4. F5/F8 文件同步可在數據裁定後一次做。
