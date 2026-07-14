# 實驗步驟 × 數學 × 文獻原文對照（詳版）

| 欄位 | 內容 |
|------|------|
| **建立日期** | 2026-07-15 |
| **用途** | 口試／外部審稿：說明「從第一次用到數學開始，每一步對照哪篇論文、原文怎麼說、我們自己補了什麼」 |
| **權威實驗／論文** | `docs/plan_v2/PROGRESS.md`；`thesis/rebuild_thesis_v2.py` → `THESIS_DRAFT_FCU_v2*.docx` |
| **精簡表** | `docs/plan_v2/METHOD_LITERATURE_MAP.md`（標題對照）；本檔為**展開＋原文** |
| **D2 專檔** | `docs/plan_v2/D2V2_LITERATURE_GROUNDING.md` |
| **PDF 包** | `thesis/literature_key_papers/`（見同目錄 `README.md`、`MISSING_PAPERS_TO_DOWNLOAD.md`） |

---

## 0. 先講清楚邊界（避免口試被問倒）

### 0.1 我們**沒有**「整本論文抄一套實驗」

本論文是 **simulation-based feasibility study** 的方法**組合**：

- 每個**組件**（ToF 測距、自校、消融、預註冊、多點定位、移動感測譜系……）都能掛到成熟文獻／教科書程序；
- **完整交集**（Isaac Sim 6.0 RTX Acoustic + UR10e 腕載超聲閉環接近／夾取 + 包絡優先 + 三臂效度）在公開文獻中稀疏——那是貢獻所在，不是某篇 paper 的復現。

### 0.2 三層回答模板（對每一個有數學的步驟都適用）

1. **方法族**：對照哪類問題／哪幾篇；
2. **原文／標準形式**：作者實際寫了什麼（本檔引用）；
3. **自有部分**：操作定義、門檻數字、場景、runner 預註冊——**不是**該論文給的數字。

### 0.3 原文引用慣例

- **「原文（英）」**：自本機 PDF `pdftotext` 摘錄，保留原文；排版換行已略整理。
- **「PDF 狀態」**：`HAVE` = 已在 `thesis/literature_key_papers/`；`MISSING` = 見 MISSING 清單，僅能依論文正文轉述＋公開摘要，**口試前宜補 PDF**。
- 文中標號 **[n]** 以當前論文參考文獻為準（重建後以文末為權威）；本檔以**作者—年份**為主鍵。

### 0.4 資料鏈總覽（有數學的步驟依此順序出現）

```
GMO 波形
  → [1] peak = argmax |W|
  → [2] ToF 距離 d̂ = peak·T·c/2  或  (peak−b)/a     ← Zhmud / He
  → [3] OLS 自校 peak = a d + b                      ← Zhmud 校正脈絡；OLS 教科書
  → [4] S1 配對移除 + 操作型 SNR                     ← Valin / Tsuchiya / Liu 動機；SNR 式自有
  → [5] S2 Pearson r / RMSE 量化                     ← 教科書指標；包絡內再量化 = 自有
  → [6] 側向四重證偽（Spearman / 互相關）            ← 對照 Kerstens 陣列路線（證偽後放棄）
  → [7] 三臂消融 + 預註冊判準                        ← Meyes / Nosek
  → [8] D1/D1.5/D3 閉環控制律 + r/RMSE/Welch/Fisher ← ToF 譜系 + 自有控制；統計教科書
  → [9] D2 五點 Gauss–Newton 多點定位               ← Kapoor + Hayes 譜系
```

---

## 1. 第一次用到數學：從波形到距離（全管線共用，論文 3.1／3.5）

### 1.1 步驟內容

| 項目 | 內容 |
|------|------|
| **實驗出現點** | 任何讀 GMO 的量測（S1 起）；正式定義在 CH3 |
| **程式／特徵** | 多幀平均波形；`peak_sample_idx = argmax |mean|` |
| **公式** | \(\displaystyle \mathrm{peak}=\arg\max_n |W[n]|\) |

**物理意義**：最強回波到達對應的樣本索引；在 Isaac Sim 6.0 中 `timeOffsetNs` 恆為 0，**不能**當飛行時間，故以 peak 當時間代理。

**自有／工程**：40 影格 settle + 24 影格平均、前後 12 幀能量差 >5% 剔除——**無單一必引論文**。

### 1.2 距離公式（第一條物理式）

\[
\hat{d}=\frac{\mathrm{peak}\times T\times c}{2}
\]

或經自校後等價：

\[
\hat{d}=\frac{\mathrm{peak}-b}{a}
\]

其中 \(T\) 為樣本週期，\(c\) 為聲速，\(a,b\) 為 OLS 斜率／截距。

---

### 1.3 文獻：Zhmud et al. (2018) — 機器人超聲測距與公式

| 欄位 | 內容 |
|------|------|
| **完整書目** | Zhmud, V. A., et al. (2018). Application of ultrasonic sensor for measuring distances in robotics. *J. Phys.: Conf. Ser.*, 1015, 032189. |
| **論文標號（約）** | **[7]** |
| **PDF** | `HAVE` → `thesis/literature_key_papers/06_Zhmud_2018_ultrasonic_distances_robotics_JPCS.pdf` |
| **我們對它的用法** | **方法族**：超聲 ToF 測距標準形式；安裝／入射角／校正意識。**不是**復現 HC-SR04 硬體實驗。 |

**原文 — 回波與時間（感測原理）：**

> The rangefinder generates sound waves at a frequency of 40 kHz. The sound waves reflects from the object and returns to the receiver, the sensor gives the information about the time, which was demanded to sound waves for propagation from the sensor to the object and back.

**原文 — 距離公式（與我們 peak×T×c/2 同構）：**

> Next, let us calculate the distance from the sensor to the object.  
> \(S = vt;\quad t = T/2 \Rightarrow S = vT/2.\)  (1)  
> Here, υ is speed of sound (≈ 340 m/s); t is time of motion of the wave from the sensor to the object; T is time of motion of the wave from the sensor to the object and back.

（同一節亦寫 timer 形式 \(S = v\,\mathrm{Tim}\cdot 10^{-6}/2\) 等，本質仍是往返時間 × 聲速 / 2。）

**原文 — 入射角／指向敏感（與我們 S1「指向主宰」敘事同方向）：**

> … the readings are affected by the angle of incidence of the wave. If the sensor is directed perpendicular to the object, the measurements will be most accurate. In addition, if, the angle of incidence is too large, then the wave, reflected from the object, does not enter the receiver, which will lead to an incorrect measurement.

**原文 — 提高精度須考慮多因素／溫度（校正脈絡）：**

> The above formulas are sufficient for a correct measurement of the distance, but if there is a need to improve the accuracy of the measurement, it is necessary to take into account a number of factors.  
> First, it is desirable to take into account the ambient temperature… the speed of sound in gases increases with increasing temperature.

**我們接住什麼／不接什麼**

| 接住 | 不接（自有或環境差異） |
|------|------------------------|
| \(S=vT/2\) 往返 ToF | 固定 340 m/s 或 HC-SR04 的 Tim/58.8 |
| 指向／入射角會壞測距 | 他們的具體 15° 波束角數值 |
| 要考慮校正因素 | 我們改成**每批 OLS 自校 peak–d**，而非只加溫度感測器 |

---

### 1.4 文獻：He et al. (2019) — 主動 ToF／深度脈絡

| 欄位 | 內容 |
|------|------|
| **書目** | He, Y., et al. (2019). Recent advances in 3D data acquisition and processing by time-of-flight camera. *IEEE Access*. |
| **標號（約）** | **[9]** |
| **PDF** | `MISSING`（`09_He_2019_…`，見 MISSING 清單） |
| **用法** | **學科脈絡**：主動打光／ToF 深度、多徑與動態範圍限制——支持「ToF 族測距」與「不能假設單峰＝完美距離」。**不是** ToF 相機硬體或演算法復現。 |

**可引用立場（論文正文已寫；補 PDF 後請換正式原文）：**  
時間飛行相機以主動打光量測深度；文獻提醒多徑反射與動態範圍等限制，近距常需其他感測互補。本研究將超聲 peak 索引解釋為 ToF 族距離推理，與 He 等主動深度脈絡並列，而非抄其相機 pipeline。

---

## 2. S2（與每批閉環前）：OLS 樣本週期／距離自校（論文 3.2）

### 2.1 步驟與公式

1. 感測器固定；目標沿視軸（或桌高）放到約 20 個**已知**距離 \(d_i\)（約 0.15–1.20 m）。  
2. 每點：settle 40 + 平均 24 幀 → \(\mathrm{peak}_i\)。  
3. OLS：

\[
\mathrm{peak}_i = a\, d_i + b + \varepsilon_i
\]

4. 樣本週期：\(T = 2/(a\cdot c)\)。  
5. 控制用：\(\hat{d}=(\mathrm{peak}-b)/a\)。  
6. **重要效度**：自校用已知距離；進入控制回合後，目標真值**只進記錄欄、不進控制**。

### 2.2 文獻對照

| 層次 | 來源 |
|------|------|
| 「近距超聲要校正／不能死套常數」 | **Zhmud (2018)** 校正與誤差因素討論（見 §1.3 原文） |
| OLS 本身 | **教科書級**迴歸，通常不強制掛「發明文獻」 |
| 20 點、兩幾何交叉、當輪不用舊斜率 | **本研究操作協議** |

**與 Zhmud 的差別（口試必講）**  
Zhmud 強調溫度、TX–RX 基線幾何修正 \(h^2=a^2-(b/2)^2\) 等；我們在**模擬確定性引擎**裡，用**已知距離掃描**直接估 peak–d 線性模型，吸收引擎取樣週期與路徑效應，而不是抄他們的溫度表。

### 2.3 S2 量化指標（仍屬「有數學」）

- Pearson \(r(\mathrm{peak}, d)\)、RMSE（例：視軸 \(r=0.9994\)，RMSE 1.21 cm）。  
- **文獻**：相關／RMSE＝標準指標；「只在 S1 可偵測包絡內做 datasheet」＝**envelope-first 自有方法論**。

---

## 3. S1：配對移除與操作型 SNR（論文 3.3 支柱一、第四章）

### 3.1 實驗設計（數學前的因果設計）

同場景、同姿態：

1. \(W_{\mathrm{tgt}}\)：有目標  
2. \(W_{\mathrm{bg}}\)：物理移除目標（背景／多路徑）  
3. \(W_{\mathrm{noise}}\)：緊接重複量測（雜訊底）

**可偵測判準（本研究操作定義）：**

\[
\mathrm{SNR}_{\mathrm{op}}
=\frac{\max|W_{\mathrm{tgt}}-W_{\mathrm{bg}}|}{\max|W_{\mathrm{tgt}}-W_{\mathrm{noise}}|}
,\qquad
\text{可偵測} \Leftrightarrow \mathrm{SNR}_{\mathrm{op}}>10
\]

**重要聲明（論文已寫）**：此 SNR **不是**通訊工程功率譜 SNR；是配對差分偵測比。

### 3.2 文獻：Liu et al. (2020) — 室內聲學定位與多路徑

| 欄位 | 內容 |
|------|------|
| **書目** | Liu, M., et al. (2020). Indoor acoustic localization: a survey. *Human-centric Computing and Information Sciences*（以 PDF／論文參考文獻為準）. |
| **標號（約）** | **[13]** |
| **PDF** | `HAVE` → `07_Liu_2020_Indoor_acoustic_localization_survey.pdf` |
| **用法** | 支持「室內不能假設單一路徑」；ToF 是測距常見物理量；兩階段：先量距離／角度，再幾何定位。 |

**原文 — 兩階段定位（與我們 S 測距 → D2 交會同構）：**

> Generally, localization algorithms can be described as a two-stage procedure [41]. In the first step, geographic information such as distances and angles are measured. In the second step, the target is located using those data. Physical phenomena such as Time of Flight (ToF) [9, 40, 50, 51], Doppler Effect … and phase shift … assist in the first step. Geometric knowledge … and optimization methods … are common choices for the second step.

**原文 — 多路徑挑戰（支持配對移除動機）：**

> Multipath effect is another common issue [50]. We hope to detect the signal reflected by the target or coming from the direct path. Due to the complex environment, the received signal is the superposition of signals reflected by different objects. … Still, methods are in need to distinguish the target.

**我們怎麼落地**  
不實作 Liu 綜述裡某一套商用／手機聲學系統；把「需要區分目標 vs 疊加回波」落成**物理移除目標的配對差分**，再用 \(\mathrm{SNR}_{\mathrm{op}}\) 畫包絡。

### 3.3 文獻：Valin et al. (2017)；Tsuchiya et al. (2022)

| 文獻 | PDF | 角色 |
|------|-----|------|
| Valin, Michaud & Rouat (2017). Localization of sound sources in robotics: A review. *RAS*. | `MISSING` | 機器人聲源定位：陣列幾何、多路徑、殘響為共同挑戰 → 配對／包絡動機 |
| Tsuchiya et al. (2022). Indoor self-localization using multipath arrival time of sound. *JJAP*. | `MISSING` | 室內多路徑到達時間仍可含空間資訊 → 時間域特徵有意義，但不能把混響當「乾淨單峰」 |

**論文正文已固定的轉述（補 PDF 後換原文）：**  
Valin 等指出陣列幾何、多路徑與殘響是距離與方位估計的共同挑戰；Tsuchiya 等以室內多路徑到達時間做無地圖自我定位。二者共同支持以配對移除分離目標回波與背景多路徑。

### 3.4 什麼是「我們的」

| 項目 | 歸屬 |
|------|------|
| \(\mathrm{SNR}_{\mathrm{op}}\) 公式與門檻 10 | **自有操作定義** |
| 52 格四因子（距離×尺寸×俯仰×干擾區） | **自有實驗設計** |
| 「包絡優先再放任務」四支柱命名 | **本研究方法論主張** |

---

## 4. 第四章側向四重證偽：統計數學 + 陣列路線對照

### 4.1 用到的數學／統計

| 檢驗 | 用意 | 結果意象 |
|------|------|----------|
| 能量差 vs 橫移：Spearman \(\rho\) | 單調左右線索？ | 遠低於預設 \(\rho\ge 0.9\) |
| 互相關時差 vs 橫移：Pearson \(r\) | 左右 ToA 差？ | \(r\approx 0.002\) |
| 其餘兩項 | 頻率／通道可分性等 | 全未過預設判準 |

相關／門檻數字＝**教科書統計 + 自有預註冊**。

### 4.2 文獻：Kerstens et al. (2019) eRTIS — **對照路線（證偽後放棄）**

| 欄位 | 內容 |
|------|------|
| **書目** | Kerstens, R., Laurijssen, D., & Steckel, J. (2019). eRTIS: A fully embedded real time 3D imaging sonar… *ICRA*. |
| **標號（約）** | **[10]** |
| **PDF** | `MISSING` |
| **用法** | 文獻上「多元件陣列／成像聲納可解 3D／方位」的代表。我們**沒有實作 eRTIS**；用四重實驗證明**本模擬單次 GMO 輸出不提供可用左右**，故**不能**走這條，改走 §9 多點定位。 |

**口試一句**  
「Kerstens 告訴我們文獻上陣列能做什麼；第四章告訴我們**這個引擎輸出做不到**，所以 D2 換運動合成。」

---

## 5. 貫穿閉環：三臂資訊消融（Meyes）與預註冊（Nosek）

### 5.1 三臂定義（資訊層的「數學」）

| 臂 | 估距進控制？ |
|----|----------------|
| 聲學 | \(\hat{d}\) 真實來自 peak→OLS |
| 盲走 | 量測管線相同，\(\hat{d}\leftarrow +\infty\)（聲學停止永不成立） |
| 開環 | 不量測，固定行程 |

主指標：停止位置與目標的 Pearson \(r\)、RMSE；**刻意**不以單純到達率為主（窄走廊開環也會「看起來常到」）。

### 5.2 文獻：Meyes et al. (2019) — Ablation

| 欄位 | 內容 |
|------|------|
| **書目** | Meyes, R., Lu, M., de Puiseau, C. W., & Meisen, T. (2019). Ablation studies in artificial neural networks. arXiv:1901.08644. |
| **標號（約）** | **[11]** |
| **PDF** | `HAVE` → `01_Meyes_2019_Ablation_studies_in_ANNs.pdf` |
| **用法** | **消融方法學**：系統性移除組件以檢驗貢獻。我們把「可移除的通道」定義為**控制器可用的估距**，不是 ANN 權重。 |

**原文 — Abstract（為何做 ablation）：**

> Ablation studies have been widely used in the field of neuroscience to tackle complex biological systems… considering the growth in size and complexity of state-of-the-art artificial neural networks (ANNs)… the question arises whether ablation studies may be used to investigate these networks for a similar organization of their inner representations.

**原文 — ablation 基本觀念（移除以看貢獻）：**

> The basic idea of an ablation, i.e. removing trainable weights from a trained ANN, is also used when networks are pruned… The idea is that some parameters of a trained network contribute very little or not at all to the output of the network and are therefore negligible and can be removed…

**我們的映射**

| Meyes 語彙 | 本研究 |
|------------|--------|
| 移除某個 unit／權重 | 移除「估距資訊」（盲走：估距作廢） |
| 看整體表現掉多少 | 看 \(r\)/RMSE／對位率是否崩壞 |
| 保留網路其餘結構 | 保留同一量測管線、同一 seed、同一目標序列 |

**不是**：復現他們的 ANN 實驗或 pruning。

### 5.3 文獻：Nosek et al. (2018) — Preregistration

| 欄位 | 內容 |
|------|------|
| **書目** | Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. *PNAS*, 115(11), 2600–2606. |
| **標號（約）** | **[5]** |
| **PDF** | `HAVE`（2026-07-15 補入）→ `02_Nosek_2018_The_preregistration_revolution_PNAS.pdf`（OSF/PNAS 開放稿） |
| **用法** | 先鎖問題與分析計畫再看結果；區分 prediction vs postdiction。本研究：判準寫進 runner header；D3 失敗**不放寬**，改設計新目錄重跑。 |

**原文 — Abstract 核心定義：**

> Mistaking generation of postdictions with testing of predictions reduces the credibility of research findings. … An effective solution is to define the research questions and analysis plan prior to observing the research outcomes–a process called preregistration. Preregistration distinguishes analyses and outcomes that result from predictions from those that result from postdictions.

**原文 — 為何區分 prediction / postdiction：**

> … postdiction is characterized by the use of data to generate hypotheses about why something occurred, and prediction is characterized by the acquisition of data to test ideas about what will occur. In prediction, data are used to confront the possibility that the prediction is wrong. In postdiction, the data are already known and the postdiction is generated to explain why they occurred.

**原文 — 事後包裝的傷害：**

> Failing to appreciate the difference can lead to overconfidence in post hoc explanations (postdictions) and inflate the likelihood of believing that there is evidence for a finding when there is not. Presenting postdictions as predictions can increase the attractiveness and publishability of findings by falsely reducing uncertainty. Ultimately, this decreases reproducibility.

**我們的映射**

| Nosek | 本研究 |
|-------|--------|
| analysis plan prior to outcomes | 預註冊 \(r\)/RMSE/對位率/Welch/Fisher 門檻 |
| 不把 postdiction 當 prediction | D3 r1 如實 False → 走廊修正後 **r3 新規格**，不改寫 r1 過關 |
| 提高 credibility | 主指標用相關性而非可被走廊撐高的到達率 |

**不是**：把 Nosek 的心理／生醫註冊平台整套搬進 Isaac Sim；是**原則落地**。

---

## 6. D1 / D1.5：閉環控制律中的數學（論文 3.5、5.1–5.2）

### 6.1 五步因果鏈（有式處）

1. **量測** \(\mathrm{peak}\)  
2. **預測**  
   \[
   \hat{d}_{3D}=\frac{\mathrm{peak}-b}{a},\quad
   \hat{d}_{xy}=\sqrt{\hat{d}_{3D}^{2}-h^{2}}
   \]  
   （\(h\approx 0.19\)–\(0.20\,\mathrm{m}\) 感測器—桌高差）  
3. **決策** \(\hat{d}_{xy}\le 0.35\,\mathrm{m}\) → 停；否則前進 \(0.05\,\mathrm{m}\)  
4. **執行** IK（暖啟動、單步限幅）—機器人學標準  
5. **稽核** 姿態／位姿；不合格剔除  

### 6.2 文獻掛鉤

| 步驟 | 文獻 |
|------|------|
| \(\hat{d}\) 來自 ToF／自校 | Zhmud §1；He 脈絡 |
| 控制律最簡固定步長 | **自有**（可歸因優先；**不是**抄視覺伺服 PID 或 PPO） |
| 三臂 | Meyes §5 |
| 判準／主指標 | Nosek §5 |

未來學習控制才掛 **Schulman PPO**、**Rudin** 並行 RL、Isaac Lab——屬第六章未來工作，**不是**現行實驗數學。

### 6.3 結果裁定用的統計（教科書）

- Pearson \(r(\mathrm{stop}, \mathrm{target})\)、RMSE  
- Welch \(t\)（組間誤差）、Fisher exact（成敗）  
- 後補：成對置換、McNemar（**不改**預註冊門檻）  

無單一「發明論文」；精神對齊 Nosek（先鎖主檢定）。

---

## 7. D3：同一測距數學 + 夾取幾何（論文 5.3）

- 停止後用**一次**估距推目標位置 → 對位 → 固定夾取序列 → 升舉。  
- 近於校正可用下限（約 0.32 m）不再聲學閉環。  
- weld-on-stall／接觸觸發附著＝**模擬器摩擦不足的工程替代**（METHOD map：不可宣稱真實摩擦夾持）。  

**文獻**：測距仍 Zhmud 族；失敗處理對齊 Nosek（r1 歷史失效、r3 正典複驗）。  
**無新聲學物理式**；數學主要是估距幾何與成功／失敗計數＋Fisher／McNemar。

---

## 8. D2：第二大段「重數學」— 多點定位（論文 5.4）

### 8.1 問題從哪來

第四章：單次輸出**無左右** → 文獻兩條路：

1. 陣列／波束（Kerstens 族）→ 本引擎不可行  
2. **多位置各量距離 → 幾何交會**（本節）

### 8.2 文獻：Kapoor et al. (2016) — 超聲 multilateration

| 欄位 | 內容 |
|------|------|
| **書目** | Kapoor, R., et al. (2016). A novel 3D multilateration sensor using distributed ultrasonic beacons for indoor navigation. *Sensors*, 16(10), 1637. |
| **標號（約）** | **[2]** |
| **PDF** | `HAVE` → `03_Kapoor_2016_3D_multilateration_ultrasonic_beacons_Sensors.pdf` |
| **用法** | **問題族**：用多個已知位置的距離量測解目標／載具座標。我們：手臂帶**單一**感測器移動 = 合成多個 vantage；不是佈建固定 beacon 網。 |

**原文 — Abstract（系統是什麼）：**

> Navigation and guidance systems are a critical part of any autonomous vehicle. In this paper, a novel sensor grid using 40 KHz ultrasonic transmitters is presented for adoption in indoor 3D positioning applications. In the proposed technique, a vehicle measures the arrival time of incoming ultrasonic signals and calculates the position without broadcasting to the grid. … Laboratory experiments were performed… The prototype system is shown to have a 1-sigma position error of about 16 cm…

**原文 — Multilateration 定義（與我們「≥3 距離交會」一致）：**

> Multilateration is a method used to determine the position of an object based on simultaneous range measurements from three or more anchors located at known positions [6]. If the number of anchors used is three, it becomes a case of trilateration. Trilateration has been implemented in ultrasonics-based localization systems like Active Bat [7], Cricket [8], Dolphin [9], and Millibots [10].

**原文 — 過定系統用 multilateration／最小平方更穩（與我們 5 點 LS 同方向）：**

> … included both analytical trilateration and recursive least squares multilateration techniques. Both approaches gave similar results in most of the cases. However, for over determined system configurations, the multilateration algorithms were found to give more accurate and robust positioning solutions.

**我們與 Kapoor 的差異（必講）**

| Kapoor | 本研究 D2 |
|--------|-----------|
| 固定 40 kHz beacon 網格 | 無 beacon；腕載感測器主動測目標距離 |
| 載具收聽多信標 | 感測器在 5 個已知臂位對**同一目標**測距 |
| 室內導航定位 | 桌面操作空間二維接近閉環 |
| 他們的 16 cm 級精度敘事 | 我們自己的側向 \(r=0.950\)、停止 RMSE 1.9 cm（模擬內） |

### 8.3 文獻：Hayes & Gough (2009) — 合成孔徑／移動感測譜系

| 欄位 | 內容 |
|------|------|
| **書目** | Hayes, M. P., & Gough, P. T. (2009). Synthetic aperture sonar: A review of current status. *IEEE JOE*, 34(3), 207–224. |
| **標號（約）** | **[1]** |
| **PDF** | `MISSING` |
| **用法** | **譜系**：單一感測器在運動中採樣，等效更大孔徑／更多空間觀測。我們只借用「**運動合成觀測基線**」精神，**不做**完整 SAS 成像鏈（匹配濾波、條帶圖等）。 |

**論文正文固定轉述（補 PDF 後換原文）：**  
合成孔徑讓單一感測器在移動中連續量測，等效更大孔徑；Hayes 等回顧其在聲納領域之發展。本研究第五章側向方案屬此一族：手臂本身當移動平台。

### 8.4 本研究實作式（腳本 `scripts/d2v2_*.py`）

已知 vantage \(v_k=(x_k,y_k)\) 與水平估距 \(\hat{h}_k\)（仍由 peak→OLS）：

\[
\min_{x,y}\ \sum_k \Big(\big\|(x,y)-v_k\big\|-\hat{h}_k\Big)^2
\]

**Gauss–Newton** 迭代（純 stdlib，約 25 步；見 `d2v2_trilat_probe.py` 之 `_trilat_solve`）。

- 此為 **圓交會／多點定位最小平方** 的標準數值法；  
- **Kapoor** 給問題族與 RLS multilateration 先例；  
- **solver 細節**不宣稱抄自 Kapoor 某方程式編號。

### 8.5 閉環與消融

- 定位後沿估計方位接近，估距 ≤ standoff 停止。  
- 盲走：進定位前距離作廢 → 無解 → 護欄（Meyes）。  
- 開環：固定名義點。

---

## 9. 模擬宣稱邊界（限制章數學以外的「方法文獻」）

### 9.1 Höfer et al. (2021) — Sim2Real

| PDF | `MISSING` |
| 用法 | 任務級指標談遷移；**不**假設模擬波形＝實機波形 |

**論文正文：** Höfer 等強調應以任務級指標談遷移。本研究：RTX Acoustic 特徵只當趨勢級距離推理的可行性證據，不是 TDK CH201 等實機波形對照標準。

### 9.2 Brinkmann et al. (2019) round-robin；NVIDIA 文件

- 聲學模擬跨引擎可有系統差 → 支持「模擬≠實機」。PDF：`MISSING`（Brinkmann）。  
- WPM／GMO 結構：NVIDIA 官方文件（非學術 paper，但方法上是資料源權威）。

### 9.3 Dümbgen et al. (2022) — Blind as a bat

| PDF | `HAVE` → `10_Dumbgen_2022_Blind_as_a_bat.pdf` |
| 用法 | 背景：機器人主動聲學／回波定位可行且被研究；**不是**我們的控制律來源。 |

**原文 — Abstract 片段：**

> Although robots are often equipped with microphones and speakers, the audio modality is rarely used for these tasks. … We propose an end-to-end pipeline for sound-based localization and mapping that is targeted at, but not limited to, robots equipped with only simple buzzers and low-end microphones. The method is model-based, runs in real time, and requires no prior calibration or training.

（對比：我們在模擬超聲 40 kHz + 每批自校，任務是臂載接近／夾取，不是他們的可聽域 SLAM。）

---

## 10. 總表：步驟 × 公式 × 文獻 × 自有 × PDF

| # | 步驟 | 核心式／統計 | 主文獻（原文見上節） | 自有部分 | PDF |
|---|------|--------------|----------------------|----------|-----|
| 1 | peak 特徵 | \(\arg\max\|W\|\) | Zhmud ToF 時間代理 | settle/avg 參數 | Zhmud HAVE |
| 2 | ToF 距離 | \(d=\mathrm{peak}\,T\,c/2\) | **Zhmud (1)** \(S=vT/2\)；He 脈絡 | 不用 timeOffsetNs | He MISSING |
| 3 | OLS 自校 | \(\mathrm{peak}=ad+b\) | Zhmud 校正意識 | 20 點、當輪、禁真值進控制 | — |
| 4 | S1 SNR | 配對 max 比 >10 | Liu 多路徑；Valin/Tsuchiya 動機 | **整條 SNR 式與門檻** | Liu HAVE；Valin/Tsuchiya MISSING |
| 5 | S2 量化 | Pearson / RMSE | 教科書 | 包絡內 datasheet | — |
| 6 | 側向證偽 | Spearman / 互相關 | **對照** Kerstens | 四重判準 | Kerstens MISSING |
| 7 | 盲走消融 | \(\hat{d}\to\infty\) | **Meyes** ablation | 三臂接到閉環任務 | Meyes HAVE |
| 8 | 預註冊 | 先鎖 \(r\)/RMSE… | **Nosek** preregistration | runner 數字；D3 重跑紀律 | Nosek HAVE |
| 9 | D1–D3 控制 | \(\hat{d}_{xy}\)、standoff | Zhmud 距離 + 自有律 | 0.35 m / 0.05 m 步長 | — |
| 10 | 組間統計 | Welch / Fisher / … | 教科書 + Nosek 精神 | 主檢定不改 | — |
| 11 | D2 定位 | \(\min\sum(\|p-v_k\|-h_k)^2\) | **Kapoor** multilateration；**Hayes** 運動孔徑譜系 | 5 vantage、GN solver、閉環 | Kapoor HAVE；Hayes MISSING |
| 12 | 宣稱邊界 | 任務級 | Höfer；Brinkmann | 不寫波形 sim2real | MISSING |

---

## 11. 口試速答卡（壓縮）

**Q：第一個公式哪來的？**  
A：超聲 ToF 標準形式 \(S=vT/2\)，Zhmud 2018 原文方程式 (1)；我們用 peak 索引當時間，因引擎 timeOffset 不可用。

**Q：SNR 是通訊標準嗎？**  
A：不是。是配對移除操作定義；多路徑動機見 Liu 原文 “superposition of signals reflected by different objects”。

**Q：盲走抄誰？**  
A：消融邏輯 Meyes（remove component to test contribution）；具體三臂是我們的任務設計。

**Q：為什麼能說沒 p-hack？**  
A：Nosek：analysis plan prior to outcomes；我們 runner header 預註冊，D3 失敗改設計重跑不放寬。

**Q：D2 抄 Kapoor 嗎？**  
A：Multilateration 定義與「多距離交會／過定 LS」對齊 Kapoor 原文；場景是臂載移動合成 vantage + 閉環，不是 beacon 導航復現。運動譜系見 Hayes。

**Q：有沒有一篇從頭跟到尾？**  
A：沒有。組件有譜系，組合與 envelope-first 管線是本論文。

---

## 12. 維護說明

| 何時更新本檔 | 動作 |
|--------------|------|
| 補下載 MISSING PDF | 用 `pdftotext` 換上**正式原文**，改 PDF 狀態為 HAVE |
| 論文參考文獻重編號 | 只改「標號（約）」，作者—年份不變 |
| 新實驗加數學步驟 | 依 §0.2 三層模板新增一節，並改 §10 總表 |
| 與精簡表同步 | 改完後掃一眼 `METHOD_LITERATURE_MAP.md` 是否仍一致 |

**相關檔案**

- `docs/plan_v2/METHOD_LITERATURE_MAP.md` — 一頁精簡  
- `docs/plan_v2/D2V2_LITERATURE_GROUNDING.md` — D2 檢索筆記  
- `docs/plan_v2/DEFENSE_QA_PREP.md` — 口試 Q&A  
- `thesis/literature_key_papers/` — PDF 與 MISSING 清單  
- `thesis/rebuild_thesis_v2.py` — 正文實際措辭  

---

*文件結束 — 2026-07-15*
