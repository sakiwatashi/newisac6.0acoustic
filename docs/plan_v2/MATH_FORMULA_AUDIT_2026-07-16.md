# 數學／公式獨立審計報告（S1→D3）

| 欄位 | 內容 |
|------|------|
| **日期** | 2026-07-16 |
| **範圍** | V2 正典鏈：S1 包絡 → S2 特性 → D1 → D1.5 → D2 → D3(r3) |
| **方法** | 自 raw CSV／npy 重算；scipy 教科書對照；論文 `rebuild_thesis_v2.py` 數字交叉 |
| **結論摘要** | **公式結構正確、數值與論文主宣稱一致、裁定可重現。** 無推翻結果的數學錯誤。有 4 項「口試用語／透明度」強化建議（非錯公式）。 |

---

## 0. 審計範圍與不做什麼

**做：**

- 每條物理／統計公式的代數正確性與文獻同構
- 自原始數據獨立重算，與 official analyzer 及論文四捨五入數字比對
- Gauss–Newton 多點定位與 scipy `least_squares` 對照
- Fisher／McNemar／Welch 與 scipy 對照

**不做：**

- 重跑 GPU 模擬（信任已落盤 npy／csv 為正典）
- 舊 v4／v9 管線
- 放寬或改寫任何預註冊門檻

**一鍵官方重算（已於審計日執行，全過）：**

```bash
bash runtime/verify_all.sh
# 另逐支：analyze_envelope / analyze_s2_datasheet / analyze_d1|d15 / analyze_d2v2 / analyze_d3_grasp
```

---

## 1. 共用基礎公式（全鏈）

### 1.1 峰值索引

\[
\mathrm{peak}=\arg\max_n W[n]
\]

| 項目 | 結果 |
|------|------|
| **程式** | 全 runner：`np.argmax(wf)`（非 `argmax|W|`） |
| **實測** | S1/S2/D2 波形 **全域非負** → `argmax(W)=argmax|W|`，與文獻寫法等價 |
| **文獻** | ToF 族「最強回波時間代理」；Zhmud 等用往返時間，此處用樣本索引 |
| **自有** | 多幀平均後再 argmax；Isaac `timeOffsetNs≡0` 故不能當 ToF |

**判定：OK。** 論文若寫 \(\arg\max|W|\)，在本引擎輸出下與實作一致；建議維持「非負振幅」一句，避免委員挑 `abs`。

### 1.2 飛行時間距離（Zhmud 同構）

Zhmud (2018)：\(S=vT/2\)（\(T\)＝往返時間）。

本管線兩種等價寫法：

\[
\hat{d}_{\text{phys}}=\frac{\mathrm{peak}\cdot T_{\mathrm{sample}}\cdot c}{2},
\qquad
\hat{d}=\frac{\mathrm{peak}-b}{a}
\quad\text{（OLS 自校，控制用）}
\]

由 \(\mathrm{peak}=a\,d+b\) 且 \(a=2/(T_{\mathrm{sample}}\,c)\) 得：

\[
T_{\mathrm{sample}}=\frac{2}{a\cdot c},\quad c=343\,\mathrm{m/s}
\]

**獨立驗算（S2 combined p1–p3）：**

| 量 | 重算值 | 論文／宣稱 |
|----|--------|------------|
| \(a\) | 56.562414 smp/m | — |
| \(b\) | −4.070 smp | — |
| \(r\) | **0.999413** | **0.9994** |
| RMSE | **1.208 cm** | **1.21 cm** |
| \(T_{\mathrm{cal}}\) | **103.088 µs** | **103.09 µs** |

**截距不可丟：** \(b/a \approx -7.20\,\mathrm{cm}\)。若誤用 \(\mathrm{peak}\cdot T\cdot c/2\) 而無截距，會有固定偏差。控制律全程用 \((\mathrm{peak}-b)/a\)。

**判定：OK。** 與 Zhmud 同構；校正協議為自有操作（非抄 HC-SR04 常數）。

### 1.3 水平距離（畢氏）

\[
\hat{d}_{xy}=\sqrt{\max\big(\hat{d}_{3D}^{2}-h^{2},\,10^{-6}\big)}
\]

| 實驗 | \(h\) | 來源 |
|------|-------|------|
| D1 / D1.5 | **0.20 m** | sensor \(z=0.65\) − target \(z=0.45\) |
| D2 / D3 夾爪構型 | **0.19 m** | `TOOL_Z − BAR_Z`（Robotiq 幾何） |

\(\varepsilon=10^{-6}\)：當 \(\hat{d}_{3D}<h\) 時夾到 \(\approx 1\,\mathrm{mm}\)，屬近場工程地板，**不是**物理奇異。

**逐步重算：** D1 closed 267 步、D1.5 closed 151 步，\(d_{3D}\) 與 \(d_{xy}\) 與公式 **誤差 0**。

**判定：OK。** 口試須能講清 D1 用 0.20、D2 用 0.19 的幾何原因。

### 1.4 操作型 SNR（S1，自有定義）

\[
\mathrm{SNR}_{\mathrm{op}}
=\frac{\max|W_{\mathrm{with}}-W_{\mathrm{without}}|}
{\max|W_{\mathrm{with}}-W_{\mathrm{noise}}|},
\qquad
\text{可偵測}\iff \mathrm{SNR}_{\mathrm{op}}>10
\]

| 項目 | 結果 |
|------|------|
| **52/52 cell** 自 `with.npy` / `without.npy` / `noise_ref.npy` 重算 | **與 `snr_peak` 相對誤差 0** |
| early_energy \(=\sum_{n=0}^{19} W[n]^2\) | **52/52 一致** |
| peak_idx | **52/52 一致** |
| 可偵測 | **36/52**，與論文一致 |
| 止損 | `block_D_all_fail=False`，`all_cells_fail=False` |

**文獻邊界：**

- Liu / Valin / Tsuchiya：支持「多路徑需分離目標 vs 背景」→ 配對移除的**動機**
- **門檻 10、公式本身：本研究操作定義**，**不是**通訊功率譜 SNR，論文 3.3 已聲明

**判定：OK。** 不可對委員說「標準 SNR 定義來自某 IEEE 標準」。

### 1.5 OLS / Pearson / Spearman / RMSE / CV

| 指標 | 實作 | scipy 對照 |
|------|------|------------|
| OLS + Pearson | 手算 / numpy | **一致** |
| Spearman（平均結秩） | 手算 | **一致** |
| RMSE | \(\sqrt{\mathrm{mean}(e^2)}\) | 標準 |
| 重複 CV | `std(ddof=1)/|mean|` | 標準 |

**判定：OK。**

---

## 2. 分實驗結果（重算 vs 論文）

### 2.1 S1 包絡

| 判準 | 重算 | 論文 |
|------|------|------|
| 可偵測 | 36/52 | 36/52 |
| Block 止損 | 未觸發 | 未觸發 |
| 主宰因子敘事 | 指向 > clutter（數據支持） | 同 |

**數學角色：** 因果設計（配對）+ 操作閾值；無爭議物理常數。

### 2.2 S2 特性

| 項目 | 重算 | 論文 | 預註冊 |
|------|------|------|--------|
| 視軸 \(r\) | 0.999413 | 0.9994 | ≥0.95 → **True** |
| 視軸 RMSE | 1.208 cm | 1.21 cm | — |
| \(T_{\mathrm{cal}}\) | 103.088 µs | 103.09 µs | — |
| 桌高 \(r\) | 0.999822 | 0.9998 | 資訊項 |
| 桌高 RMSE | 0.534 cm | 5.3 mm | 資訊項 |
| 側向 Spearman \(\rho\) | 0.3571 | 能量線索弱 | \(\lvert\rho\rvert\ge0.9\) → **False（預定證偽）** |
| 重複 CV | 0.0 | 10/10 peak 相同 | CV\<5% → **True** |
| balance 定義 | \((E_0-E_1)/(E_0+E_1)\) | — | 13/13 點與 CSV 一致 |

**文獻：** 測距＝Zhmud 族 + OLS；側向負結果對照 Kerstens 陣列路線（證偽後改 D2）。

### 2.3 D1 飛行閉環

控制律：

1. \(\hat{d}_{3D}=(\mathrm{peak}-b)/a\)（S2 tableh 校正）
2. \(\hat{d}_{xy}=\sqrt{\hat{d}_{3D}^2-h^2}\)，\(h=0.20\)
3. \(\hat{d}_{xy}\le 0.35\,\mathrm{m}\) → 停；否則前進一步 0.05 m

| 臂 | \(r(\mathrm{stop},\mathrm{target})\) | stop_error RMSE | 論文 |
|----|--------------------------------------|-----------------|------|
| closed | **0.997020** | **2.456 cm** | 0.9970 / 2.5 cm |
| blind | 0（走廊末端固定） | 79.273 cm | 失能 |
| open | 0（固定行程） | 16.921 cm | — |

| 檢定 | 重算 | 論文 |
|------|------|------|
| Welch \(t\)（兩側，closed vs blind 誤差） | **−25.1317** | （D1 正文著重 r/RMSE；D1.5 寫 t） |
| scipy 精確 Student-t \(p\) | \(2.12\times10^{-21}\) | ≪0.05 |
| 常態近似 \(p\)（analyzer） | ≈0 | 與 exact **同判** at α=0.05 |

D0 探針 \(r=0.995823\ge0.99\)。逐步公式誤差 **0**。

**文獻：** Meyes 消融精神；Nosek 預註冊；ToF＝Zhmud。

### 2.4 D1.5 手臂主結果

| 項目 | 重算 | 論文 |
|------|------|------|
| closed \(r\) | **0.985612** | **0.9856** |
| closed RMSE | **2.825 cm** | **2.8 cm** |
| Welch \(t\) | **−10.579** | **−10.6** |
| scipy \(p\) | \(9.35\times10^{-12}\) | \<0.001 |
| 姿態／位姿違規（steps） | **0 / 421** | 零違規 |
| D0.5 探針 \(r\) | 0.991828 | ≥0.99 |

統計僅用 `episode_valid` 回合；位置用 `stop_sensor_x_actual`（實達）。**判定：OK。**

### 2.5 D2 多點定位（Gauss–Newton）

目標函數（圓交會最小平方）：

\[
\min_{x,y}\sum_k\Big(\big\|(x,y)-v_k\big\|-\hat{h}_k\Big)^2
\]

- \(\hat{h}_k=\sqrt{\hat{d}_{3D,k}^2-0.19^2}\)
- 初值 \(x_0=0.60+\overline{\hat{h}}\)，\(y_0=0\)
- 最多 25 步 Gauss–Newton

| 驗證 | 結果 |
|------|------|
| 合成無噪目標 | GN 與 scipy LS **逐位相同**，誤差 0 |
| 自 vantage steps 重解 30 回合 | 與 `x_hat,y_hat` **30/30 誤差 0** |
| \(r(\hat{x},x)\) | **0.9785** ≥0.95 |
| \(r(\hat{y},y)\) | **0.9497** ≥0.9（論文 0.950） |
| 側向 RMSE | 3.34 cm |
| 停止 RMSE 2D | **1.875 cm**（論文 1.9 cm） |
| blind RMSE | 15.004 cm |
| Welch \(t\) | −12.10（論文 −12.1） |
| \(\mathrm{stop\_err\_2d}=\lvert\mathrm{stop\_dist\_2d}-0.35\rvert\) | 30/30 |

**文獻：** Kapoor multilateration **問題族**（非其 beacon 硬體／16 cm 精度）；Hayes SAS **運動合成觀測**精神（非完整成像鏈）。

### 2.6 D3 夾取（正典 r3）

| 項目 | 重算 | 論文 |
|------|------|------|
| closed \(r\) | **0.978059** | **0.978** |
| 對位率 | **24/30 = 80%** | 80% |
| blind 對位 | **10/30 = 33.3%** | 33% |
| \(\lvert\mathrm{err}\rvert\) RMSE | 1.58 cm | ~1.6 cm |
| \(P(\mathrm{lift}\mid\mathrm{align})\) | 19/24 ≈ 79.2% | 79% |
| Fisher exact one-sided | **p = 2.868631×10⁻⁴** | \<0.001；**與 scipy `greater` 逐位相同** |
| McNemar exact（佐證） | **p = 1.288×10⁻³** | 與 scipy `binomtest` 相同 |
| 無效回合 | 0 | 零違規 |

`align_error_x ≈ grasp_center_x − target_x`（最大差 \(1.2\times10^{-6}\,\mathrm{m}\)，浮點）。對位：\(\lvert\mathrm{align\_error\_x}\rvert\le 0.02\,\mathrm{m}\)。

**無新聲學物理式**；統計＝教科書 + Nosek 紀律（r1 如實 False → r3 新目錄）。

---

## 3. 文獻對照是否「挑不出錯」

| 步驟 | 可掛文獻 | 必須自承為自有 | 風險 |
|------|----------|----------------|------|
| ToF \(S=vT/2\) | Zhmud 2018 原文 | 引擎 peak 代理、\(c=343\) | 低：同構清楚 |
| OLS 自校 | 教科書 + Zhmud 校正意識 | 20 點協議、當輪不用舊斜率 | 低 |
| \(\mathrm{SNR}_{\mathrm{op}}\) | Liu 等多路徑動機 | **公式與門檻 10** | 中：用語須鎖「操作型」 |
| 三臂 | Meyes ablation **精神** | 臂＝資訊通道，非 ANN | 低：已映射 |
| 預註冊 | Nosek 2018 | 非正式 OSF 平台註冊 | 低：原則落地 |
| 多點定位 | Kapoor 定義 | 腕載合成 vantage，非 beacon 網 | 低 |
| GN solver | 標準 NLS | 不宣稱抄 Kapoor 方程式編號 | 低 |
| Welch／Fisher | 教科書 | 手算 p 用常態近似 | 見 §4 |

**沒有「整本實驗抄一篇 paper」的問題**——這是組合式可行性研究；口試用「方法族／原文／自有」三層模板即可防守。

---

## 4. 非阻塞發現（建議強化，非改結果）

### N1. Welch \(p\) 常態近似（已部分披露）

- D1／D1.5 analyzer：兩側常態近似
- D2：一側 `0.5·erfc(|t|/√2)` + 顯式 RMSE 排序
- **本數據**下 scipy 精確 t 與近似 **同判**（p 皆 ≪ 0.05）
- 論文已寫「常態近似，勿引用其精確極小值」方向——**維持**；可補一句「與 Student-t 精確 p 同側結論」

### N2. D1 兩側 vs D2 一側

預註冊各自寫清 + RMSE 排序門閘 → **決策一致**。口試一句話即可，無需改數據。

### N3. \(\mathrm{SNR}_{\mathrm{op}}\) 門檻 10

完全合法若定位為預註冊操作定義；**禁止**暗示來自某標準。論文已寫——守住即可。

### N4. peak 定義寫法

實作 `argmax(W)`；文獻卡可寫 `argmax|W|`。因波形非負而等價。建議論文或 grounding 加半句：「本引擎 GMO 振幅非負，二者相同。」

### N5. 高度差 0.20 vs 0.19

非錯誤：D1 裸感測器高度 vs D2/D3 夾爪 bar 幾何。建議方法節表格一行對照，防委員以為不一致。

---

## 5. 論文數字交叉表（主宣稱）

| 宣稱 | 獨立重算 | 一致？ |
|------|----------|--------|
| S1 36/52 | 36/52 | ✅ |
| S2 r=0.9994 | 0.999413 | ✅ |
| S2 RMSE 1.21 cm | 1.208 cm | ✅ |
| S2 \(T\) 103.09 µs | 103.088 µs | ✅ |
| 桌高 RMSE 5.3 mm | 5.34 mm | ✅ |
| D1 r=0.9970 | 0.997020 | ✅ |
| D1 RMSE 2.5 cm | 2.456 cm | ✅ |
| D1.5 r=0.9856 | 0.985612 | ✅ |
| D1.5 RMSE 2.8 cm | 2.825 cm | ✅ |
| D1.5 Welch t=−10.6 | −10.579 | ✅ |
| D3 r=0.978 / 80% vs 33% | 0.9781 / 24/30 vs 10/30 | ✅ |
| D3 Fisher p\<0.001 | 2.87×10⁻⁴ | ✅ |
| D2 側向 r=0.950 | 0.9497 | ✅ |
| D2 停止 RMSE 1.9 cm | 1.875 cm | ✅ |
| D2 Welch t=−12.1 | −12.10 | ✅ |

**四捨五入全部落在論文表述精度內。無膨脹宣稱。**

---

## 6. 總裁定

| 維度 | 裁定 |
|------|------|
| 物理公式（ToF、OLS、畢氏、圓交會 LS） | **正確** |
| 操作定義（SNR、門檻、standoff） | **自洽且預註冊**；邊界已聲明 |
| 統計（r、RMSE、Welch、Fisher、McNemar、Spearman） | **與教科書／scipy 一致**；Welch 近似在本數據不翻案 |
| 逐步控制律 | **CSV 可逐步還原，誤差 0** |
| D2 定位 solver | **30/30 自 vantage 還原 x̂,ŷ** |
| 文獻掛鉤 | **方法族正確**；無「假冒復現」；自有部分已標 |
| 論文主數字 | **全部可重算對上** |

**整體：可防守為「無法被挑剔的數學核心」。**  
殘餘挑剔點只在**用語精度**（SNR 名稱、Welch 近似、h=0.19/0.20、peak 絕對值寫法），不在計算錯誤或結果造假。

---

## 7. 建議的口試「公式護盾」三句話（每段實驗）

1. **這是什麼式、從哪來：**「ToF 是 Zhmud \(S=vT/2\) 同構；我們用 peak 當時間代理，再用當輪 OLS 吃掉固定偏差。」
2. **什麼是我們的：**「門檻、格點、三臂、standoff 是預註冊操作協議，不是抄論文數字。」
3. **怎麼證明沒算錯：**「`verify_all.sh` 零 GPU 重算；必要時展示本審計對 scipy 的對照。」

---

## 8. 產物與重現

- 本檔：`docs/plan_v2/MATH_FORMULA_AUDIT_2026-07-16.md`
- 文獻詳版：`docs/plan_v2/EXPERIMENT_MATH_LITERATURE_GROUNDING.md`
- 正典狀態：`STATUS.md`、`docs/HANDOFF_CURRENT.md`

審計執行環境：numpy 2.4.3、scipy 1.17.1；數據根目錄 `runtime/outputs/v2_*`。
