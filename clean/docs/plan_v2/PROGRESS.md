# V2 進度追蹤

> 接手規則:每完成 V2_HANDOFF_FOR_NEXT_AI.md §12 的一步,在此追加一節(日期、完成項、數據路徑、判準結果、下一步)。

## 2026-07-08 — 規劃完成,未動工

- 完成:V2 完整交接文件(`V2_HANDOFF_FOR_NEXT_AI.md`)、一頁摘要(`docs/EXPERIMENT_PLAN_V2.md`)。
- 下一步:§12 步 1 —— 寫 `scripts/paired_capture_runner.py`(規格在交接文件 §5.1–5.2),過兩個驗收 case 後跑 S1 Block A。
- 尚無 V2 數據。

## 2026-07-08(稍後)— 步 1 完成 ✅,S1 已啟動

- `scripts/paired_capture_runner.py` 完成並通過驗收:cell_visible snr_peak=293.68(>100)、cell_empty snr_peak=1.30(≈1)。驗收數據:`runtime/outputs/v2_acceptance/`。
- **重要量測發現(接手必讀)**:WPM 輸出在場景建立後有數十幀的確定性爬升暫態;且逐幀能量永遠跳動 >0.1%(逐幀比較無法判收斂),只有 n_measure 幀平均是穩定的(settle=40 時 0.02%)。
  - 對策(已實作):`--n-settle` 預設改 40;runner 事後稽核 with vs noise_ref 能量漂移(>5% → `stationarity_ok=false`);`analyze_envelope.py` 把 stationarity 不合格的 cell 視為 **INVALID(需加大 settle 重跑)**,不計入可偵測/不可偵測。
  - 曾嘗試逐幀收斂守門(150 幀不收斂)→ 已回退,原因寫在 runner 的註解塊。
- S1 週邊件完成:52 cell JSONs(`docs/plan_v2/s1_cells/`,分 A15/B10/C15/D12)、`runtime/run_v2_s1_envelope.sh`(有 skip 續跑)、`scripts/analyze_envelope.py`(含 ADJUDICATION 自動裁定行 + 熱圖)。
- **S1 全量 52 cells 掃描已啟動(背景)**,輸出 `runtime/outputs/v2_s1_envelope/`。中斷重跑同一支 shell 會自動 skip 已完成 cell。
- 下一步:S1 完成 → 讀 analyze 的 ADJUDICATION 行 → 寫 `docs/plan_v2/reports/S1_envelope_report.md` → 依 §6 判準決定 S2 範圍。

## 2026-07-08(再稍後)— S1 完成 ✅(§12 步 2+3)

- **36/52 可偵測;兩個止損點皆未觸發**。報告:`docs/plan_v2/reports/S1_envelope_report.md`(關鍵:指向主宰包絡、後方手臂零貢獻、舊場景失敗歸因=腕上擺位聲影、0.10 m 目標水平 0.15–1.2 m 全可用)。
- 量測方法學兩發現已寫入 runner/analyzer 註解與報告:啟動暫態+逐幀跳動(→settle 40+事後稽核)、特定幾何持續慢震盪(→「漂移且 SNR≤3×門檻才 INVALID」規則)。
- 下一步(§12 步 4):S2 datasheet——距離編碼掃描(D-block 幾何,順帶自校樣本週期)、側向編碼、重複性。需要新的小 runner(單 session 內移動**目標**做多距離點——移動目標已由探針驗證安全,不動感測器)。之後 D1 場景拍板需用戶/指導教授確認(數據建議:感測器前置水平視野構型)。

## 2026-07-08(晚)— S2 完成 ✅(§12 步 4)

- 報告:`docs/plan_v2/reports/S2_datasheet_report.md`。裁定:距離編碼 **True**(r=0.9994,RMSE 1.2 cm;桌面高度 r=0.9998、RMSE 5.3 mm、可用段 ≥0.32 m)/ 側向 **False**(雙 RX 證偽 → D2 剪除)/ 重複性 **True**(10/10 逐位相同)。
- **自校樣本週期 ≈ 103 µs(舊說 132.5 µs 不適用,V2 一律用自校值)**;交接文件事實表已加 #10–12(GMO id 全零、幀輪替、block≥12 幀)。
- 過程修了 sub-agent 實作的三個 bug:同幀雙 RX 假設(全 NaN 根因)→ 跨幀累積;rx id 分組 → way 序數;n_measure 6→12。教訓:幀內結構假設先用 S2_DEBUG_IDS=1 實測。
- **下一步(§12 步 5)= D1 三臂閉環實驗**。場景已被數據收斂:目標放桌面 + 感測器水平前視;D1 規格草案在 S2 報告末節。**需用戶/指導教授拍板後執行**。

## 2026-07-08(深夜)— D1 開工(用戶已拍板)

- 設計要點:**D0 前置探針**先驗證「移動感測器 prim 會正確反映到 WPM」(r≥0.99 才放行三臂;不過則 fallback 改為 rig 整體移動)。三臂 closed/blind/open 各 30 episodes,**同 seed 同一組目標位置(配對設計)**;校正由 runner 啟動時自載 S2 tableh 擬合(不寫死數字);oracle 僅入記錄欄。
- 預註冊裁定:d0_sensor_motion_valid(r≥0.99)/ d1_tracking_r_ge_0.9 / d1_beats_blind(Welch p<0.05)。
- 實作派 sonnet 進行中(d1_approach_runner.py + run_v2_d1_approach.sh + analyze_d1_approach.py)。

## 2026-07-08(22:54)— D1 完成 ✅ 三裁定全過(§12 步 5)

- **closed 臂 r(stop, target)=0.9970、停止誤差 RMSE 2.5 cm、30/30 聲學觸發停止;blind 臂徹底失能(RMSE 79 cm)——全專案第一個通過資訊消融對照的聲學閉環結果。**
- D0 感測器運動探針過閘(r=0.9958);「移動感測器 prim」自此為已驗證操作(事實表可再加一條)。
- 報告:`docs/plan_v2/reports/D1_approach_report.md`(含與舊 v4/v9 的對照表、開放問題:探針斜率 52.4 vs S2 的 57.9 未歸因)。
- 下一步選項:D3(Robotiq 夾取整合)、P1/P2(狀態估計)、或先與指導教授對齊 V2 敘事(第 4、5 章骨架已齊:S1 包絡 + S2 datasheet + D1 三臂)。

## 2026-07-08(深夜 II)— D1.5 開工(手臂載具版)

- 用戶拍板 D1.5,並明確警告舊病根:**手臂常出現不理想姿態(穿桌、穿地、中間關節沉入地板但末端到位)**——IK 無碰撞概念 + 解分支跳變。此問題在 V2 中制度化為兩項每步稽核:
  1. **姿態稽核**:FK 讀 forearm/wrist/ee link 世界座標,低於地板裕度或在桌面 footprint 內低於桌頂+裕度 → posture_violation,episode 判 INVALID(穿模會讓 WPM 看到貫穿幾何、污染聲學——是量測有效性問題,不只是美觀)。
  2. **感測器位姿稽核**:z 偏離 0.65 >2cm 或前向軸偏水平 >5° → violation(校正前提)。
- 防分支跳變:固定工具姿態、小步、IK warm-start、elbow-up seed。
- **D0.5 前置探針**:感測器 parent 到 ee_link(+0.25 m 前伸避開夾爪聲影)後,手臂運動 → WPM 更新是新未驗證操作;r≥0.99 且零違規才放行三臂;失敗時的診斷指引寫在 shell ABORT 訊息。
- 四行裁定:d05_arm_mount_valid / d15_tracking_r_ge_0.9 / d15_beats_blind / d15_posture_clean。
- 實作派 sonnet 進行中(d15_arm_approach_runner.py + run_v2_d15_arm_approach.sh + analyze_d15_arm_approach.py)。

## 2026-07-09(01:50)— D1.5 完成 ✅ 四裁定全過

- **closed 臂 r=0.9856、RMSE 2.8 cm、30/30 聲學觸發;90 episodes 姿態稽核零違規;論文主宣稱完整**(見 D15_arm_approach_report.md)。
- 除錯弧線(4 revs,全由閘門攔截,未污染任何正式數據):
  1. rev1 走廊起點 sensor 0.45 → tool0 0.20 不可達,初始 IK 死;且 close() 在 raise 前吞掉 traceback(無聲死亡)→ 先印後 close + sys.exit。
  2. rev2 identity 目標姿態對 UR10e 無解 → 改用 reach_forward seed 的 FK 姿態(tool0_grasp_orientation_wxyz,舊管線成熟做法)。
  3. rev3 感測器掛非 identity 姿態的 wrist_3 → 一次性 local 修正變換(世界位姿強制水平前視 @0.65,設定後自驗 0.000°)。
  4. rev4 靜態 ee_link 在 z≈0 造成姿態稽核 7/7 誤報 → 從 POSTURE_LINK_NAMES 移除(與「ee_link 不可當掛載」同一 USD 特性);probe 步距 0.05→0.025(13 點)。
- 開放問題:probe/S2/D0 斜率漂移(52.4/57.9/64.3)未歸因;open 臂在窄目標帶是強 baseline(擴帶實驗可選)。
- 下一步:D3 夾取整合 / 擴帶版 D1.5 / P1、P2 / 指導教授對齊。

## 2026-07-09 — 敘事對齊文件完成

- `thesis/論文敘事對齊_V2_2026-07-09.md`:給指導教授的 V2 敘事對齊(一頁主結果、審計交代、方法學貢獻、六章架構提案、可/不可宣稱、四個待教授拍板的決策點)。
- **等待用戶與教授討論結果**;拍板後的分支:D3 納入與否、負結果入正文或附錄、P1/P2 是否保留於題目範圍、docx 重寫時程。
- 在此之前不動 thesis docx、不跑新實驗(除非用戶指示)。

## 2026-07-09 — 論文 V2 草稿完成(docx 管線,保持不轉 LaTeX)

- 用戶決策:D3 肯定做但不急;論文格式維持 docx 管線(LibreOffice headless 轉 PDF 供 Linux 預覽,檔案本身格式正確)。
- 產出:`thesis/rebuild_thesis_v2.py` → `thesis/THESIS_DRAFT_FCU_v2.docx`(340KB)+ `THESIS_DRAFT_FCU_v2.pdf`(40 頁)。**v1 docx 與舊腳本原封不動**。
- 內容:摘要/Abstract 重寫(主結果開場、審計一句帶過);CH1 貢獻更新;CH2 沿用;CH3 V2 方法學;CH4 感測特性化+包絡+負結果;CH5 D1/D1.5 三臂主結果;CH6 指標失效偵測方法學+claim boundary+未來工作(D3 標註進行中)。
- 驗證:六章齊全、9 個關鍵數字全在、84% 僅出現於審計脈絡(5 處)、TOC 36/36 條目含真實頁碼(兩段式:PDF 頁碼回填)。
- **修復三個 docx 管線陷阱(接手必知)**:①模板 TOC 段落含 hyperlink,python-docx 一般 run 清除碰不到 → `_set_toc_text` XML 層清空(v1 目錄損壞的根因);②TOC 重建必須在 replace_body **之後**(無頁碼的 TOC 行文字會被誤當章節錨點);③頁碼回填需排除目錄頁本身(含 ≥8 條目標題的頁)並以無空白正規化匹配。
- 待辦:用戶/教授審閱 v2 草稿;拍板後可再 iterate 章節內容。

## 2026-07-09 — 術語與公式可讀性審查完成

- 用戶要求:所有名詞/公式/方法首次出現必附解釋(不得裸奔 DOF、GMO 之類)。
- 做法:全文按文件順序抽取 → 532 token 過濾 → 27 個技術術語逐一核對首次出現上下文 → 補齊。
- 補齊內容:摘要 7 處加註(RMSE/session/episode/oracle scaffolding/seed/1-DOF/皮爾森 r);1.4 新增集中名詞對照段(GMO/WPM/SNR/RMSE/r/ρ/IK/DOF/seed/session/episode/standoff + 盲走消融定義);CH3 補 **SNR 計算公式**(配對移除定義式)與 TX/RX/Channel、stride、settle、boresight 中文;CH4 補 Phase A/TCP/primary_sgw_early_energy/Spearman;CH5 補 IK 全稱、wrist_3_link、**Welch t 檢定句(t=−10.6, p<0.001;D1 t=−25.1)**——統計檢定原本正文完全沒寫,已補;CH6/CH4 補 rxGroup。CH2 沿用章節的「固定 TCP」在 v2 腳本內對副本就地加全稱(不動 build_chapter2_docx.py)。
- 驗證:自動化檢查 27 術語首次出現 ±80 字內含中文解釋關鍵字,全過(TX/RX 用詞邊界防 RTX 誤判);距離公式/SNR 定義式/Welch 檢定三項確認在文中。

## 2026-07-09 — 教授回饋四項修正 + 重大敘事決策

- **用戶拍板(推翻我原建議):前導實驗/審計敘事自論文完全移除**——內部參數錯誤不是科學貢獻;審計中有價值的發現全部改由新實驗自身數據呈現(擺位主宰=S1、側向證偽=S2);三臂/預註冊/稽核改立足為「實驗效度設計」,以本研究數據自證必要性(開環臂 22/30 到達率之高估示例,寫入 6.1)。對齊文件決策點 1 已更新。
- 四項修正落地(rebuild_thesis_v2.py,唯一改動檔):
  1. 禁詞歸零:舊管線/前導/審計/V2/v9/v4/scaffold/claim_mode/84% 全文 0 次;CH4 Phase A 節與 CH5 舊管線比較節整節刪除(TOC 34 條重編);關鍵詞「指標失效偵測」→「實驗效度設計」。
  2. 英文密度:三臂定名聲學臂/盲走臂/開環臂(首次括注英文);seed/standoff/episode/Block 等首次後用中文;1.4 加「英文術語首次附註+彙整於本節」宣告句。
  3. 內文引用全部改數字制(7 位作者 ×10 處,「Gao 等 [20]」式),作者-年份殘留 0。
  4. 參考文獻 24 條按年份遞增(2017→2026)加 [n] 編號;順帶修復 v1 模板參考文獻區 18 條殘留段落的寫入 bug。
- 獨立驗收全過(禁詞/引用/年份序/術語迴歸/關鍵詞);PDF 重生成。
- 註:CH2「可審計變量」→「可稽核變量」(同義詞,為滿足禁詞檢查,語意不變)。

## 2026-07-09 — 全文擴寫 + 引用覆蓋補齊(用戶第二輪回饋)

- 用戶回饋:24 條參考文獻只引用了約 10 篇;各小節字數過少不利閱讀。
- **委派中斷**:sonnet sub-agent 因額度中斷,擴寫工作 0 進度;改為主 agent 直接執行(不再委派)。
- 逐條核對四份實驗報告(S1/S2/D1/D15)原始數字,確認擴寫內容零自創數字。
- 擴寫結果:全文正文由 ~11,700 字增至 ~16,000 字(CH1 2699/CH2 3200/CH3 2539/CH4 2609/CH5 3060/CH6 1884),每小節至少 2–3 段。
- **引用覆蓋 [1]–[24] 全數達成**(先前僅 13/24,含之前未察覺的 g001:[0]/g002:[1] 陣列記號被誤判為引用的假訊號)。新增 11 篇之歸屬:
  - CH1 1.1:Xu(2024) 智慧製造綜述
  - CH2 補充段(用 `_insert_after_containing` 插入既有小節,不改 build_chapter2_docx.py):Valin(2017)/Tsuchiya(2022) 聲源定位、Rudin(2022)/Schulman(2017) 並行強化學習、Brinkmann(2019)/Scheibler(2018)/dEchorate(2021) 室內聲學模擬方法學
  - CH3 3.1:NVIDIA RTX sensors(2026c)/RTX annotators(2026b)
  - CH6 未來工作:NVIDIA Isaac Lab(2026d)
- 修一個一次性 bug:CH2 補充段插在「_replace_citations_in_items(CH2_FIXED)」呼叫**之後**,導致新引用未轉數字制;修法是插入後再跑一次替換(idempotent,已轉換文字不會重複匹配)。
- 最終驗收全過:禁詞 0、作者-年份殘留 0、引用覆蓋 24/24、參考文獻編號連續且年份遞增、27 術語迴歸不退步。

## 2026-07-10 — 健檢 + clean 快照 + commit(用戶拍板)

- 全專案健檢:V2 四階段裁定 100% 由原始數據重現(`docs/HEALTH_CHECK_2026-07-09.md`);`clean/` 功能驗證快照(14MB,分析/論文自足)。
- **c02b6ac commit**:7/6 以來全部成果入庫(2251 檔),M4 單點風險解除。
- 用戶確立分工原則(機械工作委派便宜模型)——但本日兩次 sonnet 委派均遭額度中斷,包 B 由主 agent 接手。

## 2026-07-10 — M3 關閉 + D3.0 閘門三過 + D3 完成 ✅(三裁定過、一如實判 False)

- **M3 關閉**:M3a 離線 CI 分析(漂移=小樣本噪音,probe CI 皆涵蓋 57.9)+ M3b 直接實驗(移目標 vs 移感測器 |Δslope|=3.68≤6.27,無 mover 效應)。報告:`M3_slope_attribution_report.md`。
- **D3.0 閘門**(真夾爪構型,g1/g2/M3b):bar SNR {31.9,49.0,82.3} 全過、測距 r=0.9962;**合併校正 slope 58.12±1.33(n=19,RMSE 1.78 cm)**;g1 物理把關(with_peak 落在測距線上證真偵測)。重大發現:**D1.5 其實是裸臂 variant,夾爪首次真掛上**。
- **D3 三臂完成**:closed **r(夾取中心,目標)=0.9885、對位率 60%(±2cm)vs blind 23%(Fisher p=0.004)、P(升舉|對位)=83%**;d3_posture_clean 如實判 False(3/90 遠端升舉 IK 失敗,approach 稽核 0/130 乾淨,機制=可達性包絡)。報告:`D3_grasp_report.md`。
- **方法學決策**(均於正式執行前,`d3/decisions.md`):D-12 g3 閘門修訂(升舉降為記錄項——夾持力學被證為物體寬度×模擬器保真度,與對位無關);D-13 weld-on-stall 模擬夾持(用戶授權;觸發=物理接觸訊號,消融區辨力保留);D-9 容差由 g3 實測捕捉窗鎖 0.02 m。
- **24 輪 g3 除錯學費**已濃縮進 `d3/notes.md`(tool0/ee_link 靜態框架、夾爪朝下、運動學/物理雙層、close 終端間隙 ≈5cm 等)——接手 AI 必讀。
- 下一步候選:走廊 1.18 重跑消 IK 失敗(可選)/ P1、P2 / 論文 CH5-CH6 更新。(已 commit:05fc760、487d2fb)

## 2026-07-10 — 側向感知雙重蓋棺 + D2v2 設計(多點定位復活案)

- **TDOA 證偽(零 GPU,S2 側向原始波形離線分析)**:rx0/rx1 互相關時差恆 ~2.8 樣本(管線偏移),對 y 偏移 r=0.002、鏡像對稱——引擎不分開渲染兩接收器。至此雙耳線索**能量(S2)+時間(本日)雙重證偽**,S2 的側向負結果補完整。
- **頻率不變性確認**:7/6 armfree 頻掃 20–100 kHz 六頻段輸出逐位相同——WPM 不建模頻率物理;40 kHz 之外的頻段研究在模擬內無意義(論文 limitation 一句話素材,免答辯債)。
- **D2v2 設計完成**(`D2V2_DESIGN_2026-07-10.md`,用戶已拍板):運動合成孔徑多點定位——5 視點(基線 0.3 m)最小平方圓交會解 (x̂,ŷ),只用已驗證積木(1D 測距+手臂平移)。誤差預算邊際(量化地板 1.77 cm/樣本 + 觀測擺動),g2 探針一發裁定,兩種結局皆有預寫的論文寫法。判準:r(ŷ,y)≥0.9 / r(x̂,x)≥0.95 / 2D 停止贏 blind / 姿態全淨。
- **文獻地基檢索完成**(`D2V2_LITERATURE_GROUNDING.md`):多點定位/合成孔徑/聲納陣列/消融方法學皆有譜系(eRTIS、HiRIS、SAS、機械臂載感測器 SAR 等 12 篇);「超聲閉環夾取」檢索顯著稀疏=論文 gap statement 素材。
- **rxGroup 閘門執行並證偽(第四重蓋棺)**:雙組配置(g001:[0]/g002:[1])下 way0 與單組逐位相同、way1 變為未定義噪音(peak 亂跳)——引擎不支援分組渲染。`rxgroup_lateral_encodable: False`(ρ=0.41/r=0.05 << 0.9;單組對照 sanity 過)。數據:`runtime/outputs/rxgroup_probe_v1/`;探針:`scripts/rxgroup_probe.py`。**側向原生路線全滅(能量/時間/id/rxGroup),D2v2 為唯一活路** → 接續 g2 trilat 探針。
- **D2v2 g2 探針雙判準 PASS ✅(2D 能力實證)**:13 目標網格 × 5 視點(基線 0.3 m)多點定位——`g2_loc_x_valid: True`(r=0.9878,RMSE 1.5 cm)、`g2_loc_y_valid: True`(r=0.9600,RMSE 3.4 cm,落在設計預算可過區)。探針:`scripts/d2v2_trilat_probe.py`;數據:`runtime/outputs/v2_d2v2_probe/`(含 adjudication.json)。**被 S2 剪除的 D2 經演算法路線復活**。
- 下一步:D2 正式三臂(runner 實作 + ~2h GPU,規格=D2V2_DESIGN §3)/ 論文更新 / 教授對齊。

## 2026-07-11 — 論文三輪重修(用戶+教授逐節回饋)

- **第一輪(內容+字面)**:新增 5.3 D3 節(含表 5.2、weld 誠實交代、判準 False 如實記錄);摘要/CH1 貢獻(3→5 條)/CH4(M3 歸因、側向四重證偽、頻率無效)/CH6(宣稱範圍、未來工作)全面更新;AI 腔 7 詞歸零、代碼詞 12 種歸零、術語首現全附解釋、短節全數擴寫至 ≥400 字。
- **第二輪(教授鏡頭:方法可重現性)**:新增 **3.4 場景建構與物件操作**(位置改寫機制、40 影格 settle+24 影格雙段平均、場景全尺寸)與 **3.5 聲學特徵定義與閉環控制律**(峰值索引/早期能量之定義與物理意義、量測—預測—決策—執行—稽核五步因果鏈、三臂機制差異、最簡控制器之取捨);4.1/4.2/5.1/5.3 各補實驗程序段(格點三段量測順序、重複性=重啟十次、D3 夾取五步序列)。12 項教授問題對照全 ✓。
- **第三輪(第二章)**:新增 **2.7 聲學陣列、多點定位與合成孔徑**(原 2.7 改 2.8);參考文獻 24→**27 條**(Kerstens 2019 eRTIS、Hayes & Gough 2009 SAS 綜述、Kapoor 2016 超聲信標多點定位,作者出處均經檢索核實);引用自動重編、覆蓋 27/27。
- 現狀:6 章 **28 節**、TOC 38 條、全文 ~33,200 字;全部驗收綠。(已 commit:f6e8341)

## 2026-07-11 — D2 正式三臂完成 ✅ 四判準全過(全專案第二個全綠)+ 一鍵驗證工具

- **D2 正式三臂**(`d2v2_formal_runner.py` + `run_v2_d2v2_formal.sh` + `analyze_d2v2.py`,主 agent 實作):closed 停止 2D 誤差 **RMSE 1.9 cm**、30/30 聲學觸發;定位 r(x̂,x)=0.9785、**r(ŷ,y)=0.9497**(RMSE 3.3 cm,與探針預測一致);blind RMSE 15.0 cm(Welch t=−12.1, p≈5e-34);90 回合含側向運動姿態稽核零違規。**四條判準全 True**。數據:`runtime/outputs/v2_d2v2_formal/`。
- **`runtime/verify_all.sh` 一鍵驗證**:零 GPU 30 秒,從原始數據重算全部 7 實驗 24 條裁定 + 四重證偽 + 頻率不變性 + 姿態總帳(2455 步 0 違規)+ 單元測試。口試演示用。
- **驗證工具首戰立功——抓到論文一處過強敘述**:頻率掃描六檔案能量欄有 1e-7 量級浮點尾差(峰值序列才是逐位相同),4.3「輸出逐位元完全相同」已修正為精確版並重建 docx;ILD 復算亦統一為 kept 過濾後之正典值 0.357。
- 口試演練進行中(D2 結果已入答辯內容);論文 5.5(D2 節)待寫。
