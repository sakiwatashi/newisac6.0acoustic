# notes.md — 工作筆記(隨做隨寫)

## 2026-07-08

### 健檢階段(詳見 docs/HEALTH_CHECK_2026-07-08.md)
- **意外發現**:approach_sweep_v4 全部 30 episodes 停在恆定 sensor_x=0.958(IK 上限),與 wrench 位置(0.717–1.288)零相關;fused 距離飽和在 0.61–0.73,真實距離 0.30–0.46。→ F1。
- **死路確認**:`open_loop_baseline` 模式是 oracle 導航(help 文字自己寫的),不能當「無資訊」對照組——差點誤用,設計 E1 前先查了實作才發現。
- **成本驚喜**:v4 sweep 30 episodes 只要 ~4 分鐘(19:55:16→19:59:04);grasp_sweep_v3 ~5 分鐘。實驗迭代成本遠低於預期,裁定實驗可以放心跑全量 n=30。
- v4 的 `standoff_reached_ik_limit`(13/30)其實來自兩個不同的程式路徑(approach 段有 fused≤0.47 門檻;final_approach 段無門檻直接給標籤)——同一個 reason 字串、兩種語意,reason 標籤不可作為分析依據。分析一律用停止位置+oracle 距離。
- 學到:`AcousticFeatureFrame` 是 frozen dataclass → 覆寫要用 `dataclasses.replace`,已離線驗證。
- tier_b JSON 內嵌 `claim_boundary: "offline labeling only"` 但被線上控制使用——文件與程式互相矛盾的例子,健檢時 grep JSON 內容才發現。

### 執行階段
- 步 1 致盲改碼:完成。離線驗證 output:`before fused=0.5705 / after fused=inf / standoff trigger=False`。
- SA1(haiku)完成:17/17 測試全綠(F4 修畢)。
- SA2(sonnet)完成:3 個新檔全數通過驗收;分析腳本對 approach_sweep_v4 重現手算值(stop_x mean 0.95797、stdev 0.00017、29/30≤0.45)。
- **SA2 附帶發現**:approach_sweep_v4 的 terminal_reason 是 `contact_only_failed`×30、success_count=0——v4 其實連 contact-only 階段也全敗(先前只看 approach_reason 沒注意到)。與 F1 一致:停在固定位置,多數 trial 的 wrench 不在夾爪下方。
- E1 已啟動(背景),以 run.log 中 BLIND_APPROACH=1 告示行確認致盲生效。
- **E1 裁定完成(03:24)**:盲走 30/30 ≤0.45(閉環 29/30)、≤0.35 20/30(閉環 16/30)、stop_x 同樣恆定 0.958。**F1 CONFIRMED——v4 的 100% 與聲學無關**。盲走甚至「略優」的原因:閉環組有 4 個 episode 在 lateral/final 階段多繞了幾步,停止時 Y 略偏;不是聲學有負貢獻的證據,是雜訊級差異。詳見 F1_adjudication_report.md。
- 意外印證:盲走每 episode 只要 5.1 秒(v4 閉環 ~7 秒)——閉環多出來的時間就是那些無效的 lateral/final 步驟。
- E2(Robotiq grasp sweep)已啟動,監看 log 等 Robotiq banner 確認路徑。
- **E2 完成(03:44)**:12/30 = 40% `grasp_lift_success`(含物理升舉)。Robotiq 路徑一次打通(v3 SurfaceGripper 0/30)。每 episode ~35 秒(升舉物理使成本比 skip-lift 高 7 倍)。
- **E2 交叉分析**:成功帶 wx∈[0.944,1.258](帶內 12/17≈71%);wx≤0.914 全滅 0/12(手臂開過頭)。成功由「wrench 是否落在固定停止點前方甜蜜帶」決定,印證 F1。40% 不可宣稱為聲學閉環能力。
- 死路備忘(給下個接手者):(1) open_loop_baseline 是 oracle 導航,不能當盲走對照;(2) reason 標籤不可作分析依據(同字串兩種語意);(3) 別再試 SurfaceGripper;(4) arm+table 場景的 energy→距離映射無資訊量,重校前先跑特徵-距離掃描驗證。
- 交接包完成:decisions.md / plan.md / notes.md / risks.md / F1_adjudication_report.md / E2_grasp_report.md + HEALTH_CHECK_2026-07-08.md。

## 2026-07-08(第二輪:E3 接近段目標追蹤)
- 開工前先挖舊數據:7/4–7/5 校正戰役已跑過差分實驗(differential_calibration_v1、global_baseline_diff_v1),DAILY_SUMMARY_2026-07-05.md 明列兩個尚待實作:per-trial 配對無扳手基準、early-window matched filter。**省掉一輪重複設計**。
- **發現疑點**:全局差分僅 ~1e-5(能量 ~117 的 1e-7 倍,浮點雜訊級)。兩種解釋:扳手真的聲學不可見 vs `set_prim_visibility` 不影響 WPM BVH(baseline 裡扳手還在)。規則 2-4「移除後牆 byte-identical」與後者高度一致——當年那個實驗可能也是用 visibility 做的「移除」。
- 決策 D8:先跑 E3a 機制探針(armfree 四條件),判準預寫。sonnet 撰寫探針中。
- **旁證查核**:open_space 實驗的「移除牆」是 create_six_wall_room 直接**不建立** prim(geometry_passport_v1.py:315),不是 visibility——所以「byte-identical」是真的物理移除後仍無變化。含意:arm+table 場景的回波不是牆面幾何反射貢獻的;參數化近場模型 + 手臂/桌 mesh 主導。「扳手聲學不可見」解釋的先驗權重上升。
- 連帶疑點(未驗證):規則 2-4 的三個「零效果」結論(牆移除、closeAmpl 參數、材質)若共享同一成因(WPM 輸出由參數化模型主導、幾何只在近距離大反射體時起作用),那 armfree 的強訊號(r=0.999)與 arm+table 的無訊號並不矛盾——目標 cube 的幾何回波只有在無遮蔽、近距離時才浮得出參數化背景。E3a/E3b 會直接檢驗。
- **E3a 結果(當日)**:visibility/translate/delete 三機制皆有效(Δ=251.6 vs 雜訊 0.62)。7/4–7/5 baseline 數據有效。armfree cube 訊號/背景 = 124,000/20。
- **意外紅利**:global baseline 用 trial_16 軌跡錄 → trial_16 的 global_diff 欄 = 現成完美配對實驗。免跑 E3b。
- **證據 2 定案**:扳手聲學貢獻全程(0.39–0.81 m)≤ 2e-5 = 浮點雜訊,最近兩步精確 0.0。目標不可見。
- **證據 3(v9 再審計)**:r(stop_x, wrench_x)=+0.926 表面漂亮,但 21/25 是 standoff_reached_forward_cap(oracle 出口),episodes_summary 實錄 claim_mode='scaffold'。v9 的追蹤 = oracle 前進上限。**84% vs 29% 是運動策略對比,不是聲學對比**。
- 教訓(給下個接手者):看到「漂亮的相關性」先查 reason 分布與 claim_mode,再信。這專案三層數字(v4 100%、v9 84%、r=0.926)全是不同機制的假象,每層都要用對照組或模式實錄戳穿。
- 死路清單更新:standoff 距離的目標追蹤特徵工程(能量/差分/MF)在現有場景幾何下全部無物理基礎,別再試;要救只能動場景/感測器幾何(N2)。
