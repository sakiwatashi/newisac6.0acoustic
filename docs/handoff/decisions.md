# decisions.md — 健檢後續行動的關鍵決策(2026-07-08)

> 交接包一部分。每個決策附「為什麼」與「捨棄的替代方案」。前置閱讀:`docs/HEALTH_CHECK_2026-07-08.md`(發現編號 F1–F12 沿用該文件)。

---

## D1:F1 裁定實驗採「感測器致盲」對照,不用現有 open_loop_baseline

**決策**:新增環境變數 `GRASP_BLIND_APPROACH=1`(`scripts/ultrasonic_grasp_common.py`,`_acoustic_features_from_capture` 內把 `fused_distance_m` / `estimated_distance_energy_m` 強制為 `+inf`),在 v4 完全相同的幾何與 trial ids 下跑 30 episodes 盲走對照(E1)。

**為什麼**:
- 裁定 F1 需要的對照是「沒有聲學資訊的策略能否得到同樣的接近結果」。`+inf` 保證 `math.isfinite()` 守門失敗 → 聲學 standoff 觸發在數學上不可能生效,是最乾淨的致盲方式。
- `gmo_valid` 保持 True,不會誤觸 `NO_GMO` 失敗路徑,其餘管線(IK、走廊、記錄)與 v4 完全一致——唯一變因就是聲學資訊。

**捨棄的替代方案**:
1. **現有 `--control-mode open_loop_baseline`**:查證後(`official_asset_ur10_ultrasonic_closed_loop_grasp.py:146`)它是「oracle wrench pose 導航」,不是盲走——用它會把「oracle 導航 vs 聲學導航」和「有無資訊」混在一起,答不了 F1 的問題。
2. **純分析、不跑實驗**:v4 數據已證明停止位置恆定(0.958 m),分析上已可推論;但「盲走跑出一樣的結果」是口試上最無可辯駁的形式,且成本只有 ~5 分鐘 GPU 時間。
3. **寫獨立 POC 腳本重刻走廊運動**:重複造輪、且無法保證與 v4 管線逐位一致,對照力反而弱。

**風險**:此改動落在共用檔 `ultrasonic_grasp_common.py`(該檔已有大量未提交修改)。已控制為:預設關閉、旗標命名明確、模組載入時印告示行(run.log 可稽核)、diff 極小(~15 行)。

## D2:F2(死門檻 0.14 m)本輪不改碼,記為已知死碼

**決策**:`FINAL_APPROACH_STANDOFF_M = 0.14` 與 tier_b 表 clamp 下限 0.256 的矛盾,本輪只記錄、不修。

**為什麼**:實測(health check)顯示接近末段的 fused 讀值停在 0.61–0.73(表上限飽和),即使把門檻改成 0.30 也一樣達不到——問題根源是能量→距離映射在 arm+table 場景無資訊量(F3),不是門檻數字。改門檻是無效修補,還會擾動 diff。真正的修法(重校/換特徵)依 E1 裁定結果再決定方向。

**捨棄的替代方案**:把 0.14 調成 0.30 後重跑 v4——預測結果不變(fused 從未 ≤0.47),白費一輪。

## D3:E2(Phase C 重跑)直接走 Robotiq,不再投入 SurfaceGripper

**決策**:新 sweep `runtime/run_closed_loop_grasp_sweep_robotiq.sh`(輸出 `grasp_sweep_v4_robotiq`),移除 `--final-gripper surface`,其餘與 grasp_sweep_v3 相同,30 episodes、`--enable-lift`。

**為什麼**:7/8 session 已確認 Robotiq finger-joint 路徑完整實作且與官方 tutorial_9 一致;SurfaceGripper 修了 5 個問題後仍 0/30。此決策沿用 session summary 的結論,無新資訊推翻它。

**判讀前提(重要)**:E2 結果必須與 F1 一起解讀——接近段停止位置是固定的,所以 grasp 成功預期集中在「wrench 恰好落在固定停止點附近」的 trials。E2 的產出除成功率外,必附 `analyze_stop_position.py` 的 per-trial 對照(wrench_x vs 成功)。**若成功 trials 的 wrench_x 呈窄帶分布,不可把成功率宣稱為「聲學閉環夾取」能力。**

## D4:論文主數據錨定回 v9,v4 的 100% 敘事棄用(待 E1 確認後生效)

**決策**:若 E1 盲走得到與 v4 相同的接近結果(預測如此),則:論文 Phase B 主數據 = `physical_ai_v9_skip_lift_clean`(84% vs 29%,有對照組、已 committed);v4 改述為「走廊幾何上限實驗 + 指標失效分析」,可作為 limitation/負結果素材(有學術價值:展示了如何用停止位置變異數偵測指標失效)。

**為什麼**:v9 有 open-loop 對照組且幾何不同(開環只到 29%,證明該幾何下接近非平凡);v4 無對照組且停止位置與目標零相關。用戶亦明示可回錨 v9 乾淨數據。

**捨棄的替代方案**:修好校正表後重建 v4 敘事——受規則 2-4(arm 場景距離回歸 R²≈0,5+ 次實驗)壓制,成功機率低,不值得在口試時程內投入。列為未來工作。

## D5:不開 git branch、不 commit;交接物全部為新增檔案

**決策**:所有產出(docs/handoff/、新 shell、新分析腳本)為新檔;既有檔案只動兩處:`ultrasonic_grasp_common.py`(D1 致盲旗標)與 `test_ultrasonic_closed_loop_controller.py`(F4 過期測試對齊)。不建 branch、不 commit。

**為什麼**:工作樹已有大量用戶未提交的修改(12 個 modified 檔),此時建 branch/commit 會把不屬於本輪的變更攪進版本歷史;邊界要求不動 main。commit 決策留給用戶。

**捨棄的替代方案**:開 spike branch 提交本輪產出——在乾淨樹上是對的,在目前的髒樹上會製造歸屬混亂。

## D6:不回頭改舊 sweep shell 的錯誤註解(F5)

**決策**:`run_closed_loop_approach_sweep.sh` / `run_closed_loop_grasp_sweep.sh` 裡「DEFAULT_CALIBRATION」的錯誤註解不改。

**為什麼**:這兩支腳本是「已執行實驗的紀錄」,回頭改寫會讓 run.log 與腳本內容對不上。正確做法:新腳本寫正確註解(已做),差異記錄在 health check F5 與本文件。

## D8:E3(接近段目標追蹤)先做機制驗證,再做配對差分

**決策**:E3 拆兩步。E3a:armfree 探針驗證 `set_prim_visibility` 是否真的把 prim 從 WPM ray tracing 移除(四條件:可見/visibility off/translate 移遠/RemovePrim)。E3b:依 E3a 選定的移除機制,做 7 trials 的配對式 per-trial 無扳手基準差分 + early-window matched filter(7/5 每日總結明列的兩個「尚待實作」)。

**為什麼**:7/4–7/5 的全局差分結果(diff ≈ 1e-5、相關 r≈0.1 且方向錯)有兩種互斥解釋:(a) 扳手在 arm+table 場景聲學不可見;(b) visibility 旗標不影響 WPM BVH → baseline 裡扳手根本還在,差分測到的只是 session 間浮點雜訊。兩者對論文的結論完全不同,而規則 2-4「移除後牆 byte-identical」的異常結果與 (b) 一致性很高。不先分辨 (a)/(b) 就跑 E3b,會重蹈「基於錯誤參數繼續做」的覆轍。

**捨棄的替代方案**:直接跑配對差分(若 visibility 無效,結果又是一批不可解釋的雜訊,浪費一輪);直接翻 Isaac Sim 原始碼確認 BVH 行為(RTX sensor 插件是閉源 C++,查不到就變成空轉;實驗 2 分鐘就有答案)。

**判準(判讀前預寫)**:條件 B(visibility off)的波形變化 > 10× session 內雜訊(A2 對照)→ visibility 有效;否則無效,7/4–7/5 baseline 數據全部作廢,E3b 改用 translate/RemovePrim 機制。

## D9:E3b 取消——既有數據已含完美配對實驗,答案是零訊號

**決策**:原計畫的配對差分 sweep + early-window matched filter 不跑。

**為什麼**:E3a 證明 visibility 機制有效後,`global_baseline_diff_v1` 的 trial_16(與無扳手 baseline 同軌跡)就是現成的完美配對實驗——結果:0.39–0.81 m 全程差分 ≤ 2e-5(浮點雜訊),無趨勢。訊號不存在,任何特徵工程(early-window MF 等)都是在雜訊上雕花。

**捨棄的替代方案**:照原計畫跑 7×2 配對 sweep——只會用 10 分鐘 GPU 再確認一次已知答案。

## D10:D4 修正——v9 也不能宣稱聲學閉環;論文敘事需與用戶/指導教授重新對齊

**決策**:v9 再審計證實其閉環 trials 為 `claim_mode: scaffold`(oracle 前進上限 + oracle 出口,21/25 靠 forward_cap 停止)。**撤回 D4「錨定 v9 作為聲學閉環證據」的建議**;v9 可作為 scaffold 模式系統整合數據,但不能支持「不將目標座標作為控制輸入」的敘述。論文敘事重構方向見 E3 報告第「對論文的建議」節——此為架構級決策,**保留給用戶與指導教授**,本輪不動論文文件。

**為什麼**:三段證據(E3a 探針、trial_16 配對差分、v9 claim_mode 實錄)互相咬合,結論不依賴單一實驗。仍然成立的資產:Phase A、armfree 測距、Robotiq 管線、負結果機制分析。

**捨棄的替代方案**:繼續尋找「能追蹤目標的特徵」——證據 2 顯示無物理基礎,除非改變場景/感測器幾何(列為 N2 診斷方向,非本輪範圍)。

## D7:sub-agent 分工

- SA1(haiku):F4 測試修復 + 跑 4 個純 Python 測試 — 機械性,規格已含完整目標程式碼。
- SA2(sonnet):兩支新 sweep shell + `analyze_stop_position.py` — 機械性,規格含逐項行為定義與驗收(對 approach_sweep_v4 跑出 stop_x≈0.958 恆定才算過)。
- 本體保留:D1 致盲改碼(POC 核心,錯了整個 E1 無效)、E1/E2 執行與判讀、所有決策文件。
