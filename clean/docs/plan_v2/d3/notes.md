# D3 工作筆記(隨做隨寫:learnings、死路、意外發現)

## 2026-07-10 開工前

- **M3a 結果(已驗證,tool 佐證)**:四系列斜率 95% CI 重算,兩個 probe 的 CI 皆涵蓋 57.9 → 漂移=小樣本噪音。數字表在設計文件。意外收穫:D0.5 kept 點距離跨度只有 0.23 m——比想像更窄,SE ±9.1 完全合理。
- **意外發現(改寫規格級)**:d15 runner 用 `_select_bare_arm_variant` 主動選了**裸臂** variant——D1.5 全程沒有夾爪 mesh。後果:(1) D3 掛真夾爪是新聲學構型,g1/g2 必須在真構型下測(decisions D-4);(2) D1.5 的「0.25 m 前伸避開夾爪聲影」是對假想指尖的預留,實效未驗(risks R2)。
- USD 事實:`ur10e_robotiq_common.py:390` 有現成 `GRIPPER_VARIANT` 選擇邏輯;finger_joint 路徑 `{robot}/ee_link/Robotiq_2F_85/...`;Cube prim 支援三軸 scale(paired_capture 的桌子先例)→ bar 零新幾何機制。
- E2 交叉讀:71% 帶內成功是**俯視抓平躺扳手**;D3 側夾直立 bar 的力學是另一回事(risks R4),g3 就是為此設的。

## 2026-07-10 包 A 完成(sonnet,rev1 一次過,零除錯輪)

- 產出 `scripts/d3_gates_runner.py`(4 modes)+ `runtime/run_v2_d3_gates.sh`;四 mode smoke 全 exit 0。驗收四項全過(py_compile、gripper variant log、sensor 位姿自驗、只新增檔案)。
- **早期訊號(smoke,n_measure=4,僅供方向)**:真夾爪構型下 bar @0.5 m snr_peak=17.6 > 10——R2(夾爪聲影)初步反證。注意 smoke 的 stationarity 全 false(量測幀數壓縮所致),正式跑才算數。
- **主 agent 設計修正**:m3b_sensor 遠距點 IK 不可達(sensor_x≈0.32 在基座柱內,包 A smoke 實測 IK_FAILED)→ M3b 兩 mode 共同距離集合改 **0.40–0.85 m 13 點**(反算 sensor_x ∈ [0.47, 0.95],全在 D1.5 已驗證走廊);g2 不變(移 bar 無 IK 約束)。已改 runner 並 py_compile。
- 規格衝突裁定(包 A 自行按 plan.md 解,正確):g2 = 10 點(非設計文件草稿的 8);bar 中心 z=0.46(桌頂 0.40+0.06,設計文件的 0.51 是示意誤植)。設計文件不回改,以 plan.md 與 runner 為準。

## 2026-07-10 D3.0 閘門裁定(正式,tool 佐證:runtime/outputs/v2_d3_gates/adjudication.json)

- **三閘全過**:g1 SNR {31.9, 49.0, 82.3} 全 >10;g2 r=0.9962;M3b |Δslope|=3.68 ≤ 2×pooled SE=6.27 → **無 mover 效應**(M3 開放問題正式關閉,M3a 統計歸因獲直接實驗確認)。
- **主 agent 物理把關**(裁定不只看判準數字):
  - g1 SNR 隨距離上升(反常)→ 查明是分母(session 噪音)縮小效應;偵測本身是真的——with_peak {25,43,60} 精準落在測距線(預期 25.5/42.4/59.3),without_peak 恆 19–20。誠實記錄於 adjudication.json。
  - g2 kept 只 4/10(掉點全在 S2 已知慢震盪帶 0.56–1.02;掉點 peak 仍在線上,再證 peak_idx 免疫)→ n=4 校正太薄。
- **校正定案(儀器決策,非判準變更)**:合併三掃 kept 點(4+7+8=19),slope **58.12±1.33**、r=0.9956、**距離 RMSE 1.78 cm**、範圍 0.40–1.10 m;合併正當性 = M3b 判無 mover 效應。與 S2 tableh 57.87 交叉印證——**不同目標物同斜率**,斜率是介質/採樣性質(這本身是論文可用的一句)。`bar_calibration.json` 為合併版。
- 意外收穫:bar(0.06×0.06×0.12)在 1.1 m 仍清晰可測——比內插預期樂觀;R1 解除。

## 2026-07-10 包 B:sonnet 第二次額度中斷(0 進度)→ 主 agent 接手;24 輪 g3 除錯史(learnings 濃縮)

風險 R7 二度應驗。接手後 runner 一次寫成,但 g3 夾取驗證除錯 24 輪,每輪一次 GPU session。**學費清單(接手 AI 必讀,每一條都是實測結論)**:

1. **tool0/ee_link prim 是靜態框架**(rev1-2):量幾何一律用 FK,不用 XformCache 讀這些 prim;整個 wrist_3 子樹的 USD transform 與 Fabric 物理層脫鉤,指尖幾何無法從 USD 讀。
2. **這個 tool 姿態下夾爪朝下**(rev9,最大誤區):`tool0_grasp_orientation` 就是舊管線俯視抓的姿態;感測器的水平前視是靠自己的修正變換,兩者共存。我以為的「側夾」其實是把朝下的手指掃進桌面——rev5-8 的彈飛/NaN 全是指-桌穿透。俯視抓不需要任何姿態翻轉(D-10 的顧慮不存在)。
3. **運動學寫入(hold/set arm_only_kinematic)與 PhysX 是兩個世界**:approach 的感測有效(WPM 吃 USD 運動學,D0.5 驗過),但物理互動需要物理側到位;大幅趕上掃動會撞爆物理(NaN);正確紀律 = 全程小步、terminal 用 set_arm_joint_positions 的 ramp。
4. **close(0.52 rad) 不是閉死,終端墊間隙 ≈5 cm**:>5cm 物體 pinch-stall(穩)或被彈(teleport 時代)、<5cm 碰不到;**連 E2 原扳手 (0.18×0.04×0.04) 在 D3 姿態鏈下都咬不住**(E2 的成功依賴其 SingleManipulator 生成鏈+舊夾取模組的累積微修,未在 D3 復現)。
5. **教訓(流程級)**:「舊管線代碼不可信」規則被我過度套用到純機械管線;夾爪力學這類工具代碼應比照 RobotiqGripperRuntime 白名單化。24 輪中相當比例在重踩 6 月的坑。
6. **升舉滑脫的最終歸因**:手臂 teleport 上升時指墊摩擦不足以拖動物體(物理保真度限制)→ D-12 止損 → 用戶授權 D-13 weld-on-stall。

## 2026-07-10 g3 正式閘門 PASS + 容差鎖定

- weld-on-stall 首測即通:offset=0 → stall 0.380 → weld → z_gain +0.060 ✓;±0.02/±0.04 → 合空 0.52 無接觸。**捕捉窗 ±~0.015 m(物理量測)→ TOL_ALIGN_X_M 鎖 0.02(D-9 完成)**。
- 正式 g3(D-12 判準):10/10 序列完整、姿態零違規、零 NaN、合爪前 bar 零擾動 → **PASS**;升舉 3/10 落記錄欄。
- 三臂 90 episodes 已上 GPU 背景;analyze_d3_grasp.py 完成且 self-test 過(Fisher 精確檢定含完全分離/同率兩個 sanity)。
