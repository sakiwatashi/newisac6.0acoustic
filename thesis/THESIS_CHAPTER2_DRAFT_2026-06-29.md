# 第二章、文獻探討（完整初稿）

**依據：** `citation_support_bank.md` Recommended final 20  
**格式：** 逢甲 13b 內文（可貼入 Word `Content` 樣式）

---

## 2.1 機器人非視覺感測與超音波測距

協作機器人與工業手臂在狹窄、遮蔽或人機共融場景中，僅依賴視覺往往難以穩定取得近距幾何資訊。Alatise 等（2020）指出，多模態感測融合——其中包含超音波與其他非視覺距離量測——可補足視覺在反光、低照度與遮擋條件下的不足。此互補角色對本研究至關重要：UR10 末端掛載之主動聲學感測，並非取代相機，而是在固定 TCP 幾何下提供可重複的距離相關觀測。

時間飛行（Time-of-Flight, ToF）相機提供主動深度量測，He 等（2019）綜述其在三維擷取上的進展，同時強調多徑反射與動態範圍限制常需與其他 proximity 感測協同。Zhmud 等（2018）則以機器人（含手臂）掛載超音波感測器為例，說明近距量測需校正感測器姿態、反射面法向與安裝幾何；本研究之 Geometry Passport 即沿此脈絡，將感測器—目標相對幾何列為可審計變量。

近年亦有研究探索主動聲學回波於小型機器人之應用。Dümbgen 等（2022）展示無視覺條件下，可聽域主動回波仍能估計障礙距離，與 Isaac Sim RTX Acoustic 之主動聲學模擬屬同一技術族。綜上，文獻支持「末端非視覺測距具工業互補價值」，但亦提醒量測品質高度依賴幾何與環境；本研究因此不宣稱部署級測距精度，而聚焦於控制變量下之可行性驗證。

## 2.2 模擬與虛實整合（Sim-to-Real）

Gao 等（2026）指出，模擬已成為機器人研究的核心基礎設施；NVIDIA Isaac Sim 整合 GPU 加速物理、RTX 渲染與感測模擬於 USD 場景圖，並支援大規模機器人學習實驗。Mittal 等（2023）提出 Orbit（Isaac Lab 前身），以 GPU 並行模擬支撐互動式機器人學習環境；本研究 Phase 4–5 之 DirectRLEnv 延伸即建立於此平台系譜。

近年 Isaac Sim 生態持續擴充：GRADE（2025）示範以 Isaac Sim 生成動態室內場景，與本研究移動目標設定同類；Salimpour 等（2025）將 Isaac Sim 訓練之強化學習策略銜接 Gazebo 與 ROS 2，說明模擬器可作為 Sim-to-Real 鏈路起點；Zhou 等（2024）則將 Isaac Sim 用於工業 CPS 操作基準，呼應智能製造數位驗證需求。

然而，模擬器輸出並非物理真值。Höfer 等（2021）強調 Sim-to-Real 應以任務級指標驗證遷移成效，不宜假設模擬信號與實機波形等價。本研究遵循此認識論邊界：RTX GMO 特徵僅作趨勢級距離推理之可行性證據，而非 CH201 實機部署之波形對照標準。

## 2.3 聲學模擬與多徑效應

室內聲學定位與測距長期受多徑傳播與殘響影響。Liu 等（2020）綜述室內聲學定位文獻，指出早期反射能量（early energy）常作為距離或位置之弱代理變量（proxy），其可解釋變異量受房間幾何、材質吸收與收發配置制約。

Valin 等（2017）回顧機器人聲源定位，說明殘響環境下需區分直接徑與反射徑貢獻；主動聲學（感測器發射、接收回波）可提供額外距離線索，但仍非 ToF 雷射之單一路徑量測。Tsuchiya 等（2022）進一步示範，單通道聲學感測亦可利用多徑到達時間進行室內自我定位，顯示聲學—距離之間存在可利用但非線性、非單調的關聯。

上述文獻為本研究選用 primary_sgw_early_energy 提供理論動機：在封閉工業房間中，早期信號能量隨距離呈趨勢性變化，但不宜將其直接等同物理 ToF 或宣稱厘米級精度。此設定與後文 PyRoomAcoustics 趨勢對照及 claim boundary 一致。

## 2.4 RTX Acoustic 與 GenericModelOutput

Isaac Sim 6.0 提供 RTX Acoustic 實驗性感測模組（NVIDIA, 2026a），以 GPU 路徑追蹤模擬聲波傳播，輸出 Generic Model Output（GMO）之 signal-way 張量。相較傳統幾何聲學套件（如 image-source 模型），RTX 路徑與材質互動方式不同，NVIDIA（2026c）亦將 RTX 感測與註解器（annotators）定位為可擴充之合成感測管線。

GMO 欄位語義（NVIDIA, 2026b）定義 tx／rx／channel 維度與振幅取樣序列，為本研究 rtx_acoustic_factory 特徵萃取之依據。由於學術文獻中直接結合「RTX Acoustic + 工業手臂」之公開研究極少，平台鄰近工作如 Song 等（2025）之 OceanSim 示範：Isaac Sim 可擴充為專用 ray-traced 感測管線，支撐本研究以官方 API 建構可重現擷取流程之合理性。

需再次強調：RTX Acoustic 目前標示為 experimental，文件亦未保證與實機 CH201 或 PRA 波形一致。本研究將其視為「可控幾何下之合成觀測來源」，而非物理 ground truth。

## 2.5 PyRoomAcoustics 房間聲學基線

為避免單一模擬器之模型偏差，本研究引入 PyRoomAcoustics（Scheibler 等, 2018）作為幾何聲學基線。Brinkmann 等（2019）之 round-robin 研究顯示，不同房間聲學模擬器對 RIR 之預測存在系統性差異，故跨模擬器比較應限於趨勢級（trend-level）對照，而非波形級等價檢定。

在特徵—距離推理文獻方面，dEchorate 資料集（2021）提供標定 RIR 與回波特徵，支撐以聲學摘要特徵進行距離相關學習之可行性。本研究 Phase 3 以 PRA 萃取 early energy、RT60 等與 RTX 同幾何對齊，實證兩者於距離軸上具一致趨勢（Spearman ρ≈0.66），但振幅尺度與飽和行為不同，再次印證「趨勢可對、波形不等」之 claim boundary。

## 2.6 文獻缺口與本研究定位

綜合前述各面向，現有文獻多覆蓋子集而非完整交集：Isaac Sim 平台研究（F2）鮮少同時處理 RTX Acoustic 距離可重複性；聲學機器人研究（F4/F6）多未提供 Isaac／Omniverse 可審計管線；Isaac Lab 閉環 RL（F7）亦少見以 RTX GMO 為觀測源之距離估計實驗。在工業固定 TCP 手臂場景下，同時整合上述要素之公開工作仍屬稀疏。

Xu 等（2024）論述製造數位雙生需可重現模擬管線，呼應本學程之智能製造脈絡。本研究定位為 simulation-based feasibility pipeline（模擬可行性管線）與 methodological bridge（Sim 靜態校準 → Lab 動態觀測 → 可選 in-sim RL）：以 Geometry／Material Passport、30/30 可重複性協定與 replication package 提供可審計證據，並以監督學習（§4.6, r≈0.47）示範趨勢級距離推理，而非宣稱部署級測距或波形等價。

因此，本論文貢獻不在提出新聲學物理模型，而在填補 G0 缺口：建立 UR10 固定 TCP + RTX Acoustic + Isaac Lab 延伸之端到端可重現工作流程，為後續 CH201 實機 task-level 驗證預留協定與評估邊界。