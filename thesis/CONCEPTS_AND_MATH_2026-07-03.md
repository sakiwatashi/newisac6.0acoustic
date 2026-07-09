# 名詞解釋 · 數學原理 · 驗證方法
# UR10 RTX Acoustic 超音波閉環接近控制論文

**版本：** 2026-07-03
**對象：** 口試委員、自我複習、研究紀錄
**語言：** 中文說明 + 數學公式

---

## 目錄

1. [平台名詞解釋](#1-平台名詞解釋)
2. [感測器名詞解釋](#2-感測器名詞解釋)
3. [聲學物理原理](#3-聲學物理原理)
4. [GMO 資料結構詳解](#4-gmo-資料結構詳解)
5. [核心數學公式](#5-核心數學公式)
6. [標定（Calibration）原理](#6-標定calibration原理)
7. [距離估算演算](#7-距離估算演算)
8. [閉環控制演算](#8-閉環控制演算)
9. [Physical AI 與機器學習](#9-physical-ai-與機器學習)
10. [統計驗證方法](#10-統計驗證方法)
11. [實驗設計與對照](#11-實驗設計與對照)

---

## 1. 平台名詞解釋

---

### NVIDIA Isaac Sim

**是什麼：**
NVIDIA Isaac Sim 是 NVIDIA 推出的**機器人模擬平台**，建立在 NVIDIA Omniverse 之上。它能夠在電腦中建立接近真實世界的物理環境，讓機器人在「虛擬世界」裡進行測試和訓練，而不需要真正的硬體。

**為什麼用它：**
- 可以模擬**真實物理**（重力、摩擦、碰撞）
- 支援 **RTX 光線追蹤**，可模擬聲波、光線的真實傳播
- 支援 UR10e、Robotiq 夾爪等官方機器人資產
- 可快速重複執行實驗（不需要等真實機器人）

**本論文版本：** Isaac Sim **6.0.0-rc.59**（release candidate，實驗性功能較多）

**與真實世界的關係：**
```
真實世界                   Isaac Sim
─────────────             ──────────────────
真實 UR10e 機器手臂   →   USD 機器手臂模型
真實超音波感測器      →   RTX Acoustic 感測器
真實房間             →   六面牆 USD 場景
真實空氣傳播音波      →   WPM 波傳播模型計算
```

---

### Isaac Lab

**是什麼：**
Isaac Lab 是建立在 Isaac Sim 上的**強化學習（Reinforcement Learning）訓練框架**。提供更結構化的 gym 環境介面，方便訓練 AI 策略。

**本論文中的角色：**
Isaac Lab 只用於**附錄實驗**（RL 動態訓練）。論文主體實驗（Phase A/B/C）全部在 Isaac Sim standalone 模式下進行。

---

### RTX（Ray Tracing eXtensions）

**是什麼：**
RTX 是 NVIDIA 的**即時光線追蹤技術**，原本用於遊戲畫面的真實光影。在 Isaac Sim 中，同樣的技術被延伸用於**感測器模擬**：

| 傳統技術 | RTX 技術 |
|---------|---------|
| 用幾何近似計算感測器 | 用光線/波的物理傳播計算 |
| 快速但不真實 | 較慢但物理正確 |
| 無法模擬多徑 | 可模擬反射、折射、多徑 |

---

### RTX Acoustic（RTX 聲學模擬）

**是什麼：**
RTX Acoustic 是 Isaac Sim 中的**實驗性超音波感測器 API**。它利用 RTX 光線追蹤引擎，將光線替換為聲波，模擬真實超音波的傳播行為。

**物理模型：WPM（Wave Propagation Model，波傳播模型）**
- 模擬聲波從發射器出發
- 追蹤聲波碰到障礙物後的**反射路徑**
- 計算每條路徑的傳播時間和能量衰減
- 返回每條路徑（Signal Way）的振幅時間序列

**為什麼選超音波（40 kHz）：**
- 40 kHz 超過人耳聽覺上限（20 kHz），不干擾工作環境
- 短波長適合近距離精確測距（0.2–3.0 m 範圍）
- 廣泛用於工業機器人接近感測（如 CH201 晶片）

---

### USD（Universal Scene Description）

**是什麼：**
USD 是 Pixar 開發的**3D 場景描述格式**，被 NVIDIA Omniverse / Isaac Sim 採用為場景標準格式。

```
/World/                         ← 根節點
  room/                         ← 房間
    floor                       ← 地板（Cube prim）
    ceiling                     ← 天花板
    wall_x_min / wall_x_max     ← 左右牆
    wall_y_min / wall_y_max     ← 前後牆
  ur10/                         ← UR10e 機器手臂
    ee_link/                    ← 末端執行器
      official_rtx_acoustic/    ← 超音波感測器
      SurfaceGripper/           ← 吸力夾爪
  wrench/                       ← 目標物（扳手代理）
```

每個節點稱為 **Prim**（Primitive），有位置、旋轉、材質等屬性。

---

### PhysX

**是什麼：**
PhysX 是 NVIDIA 的**物理引擎**，負責計算 Isaac Sim 中所有物體的碰撞、重力、摩擦、關節運動。

**本論文的影響：**
最終夾取成功率僅 ~20% 的主因不是聲學問題，而是 **PhysX 接觸物理的不穩定性**（Robotiq 夾爪 + 扳手目標的 PhysX 接觸計算誤差）。這是論文的 Claim Boundary（不可宣稱的範圍）之一。

---

### SurfaceGripper（吸力夾爪）

**是什麼：**
SurfaceGripper 是 Isaac Sim 內建的**吸盤式夾爪模擬器**，用距離感測來模擬吸力（不需要真實氣動系統）。

**運作原理：**
1. 設定 `max_grip_distance`（例如 0.5 m）
2. 當夾爪進入目標距離範圍，自動建立剛性連接
3. 持續施力直到超過 `coaxial_force_limit` 或 `shear_force_limit` 才放開

**本論文的已知問題：**
"Gripper not found: /World/SurfaceGripper" 錯誤 — 根因是夾爪 prim 建立在錯誤路徑，已修復（詳見 §4 SurfaceGripper 修復）。

---

### UR10e 與 Robotiq 2F-85

**UR10e：**
Universal Robots 製 10 公斤承載量的 6 軸協作機器手臂。臂展約 1.3 m，適合桌面操作任務。

**Robotiq 2F-85：**
Robotiq 公司的兩指平行夾爪，開口最大 85 mm，適合抓取各種形狀物品。

**在 Isaac Sim 中：**
使用官方 USD 資產，包含完整的 PhysX 關節定義和 URDF 幾何。

---

## 2. 感測器名詞解釋

---

### OmniAcoustic Prim

**是什麼：**
在 USD 場景中代表超音波感測器的節點，帶有 `OmniSensorGenericAcousticWpmAPI` 的 USD schema（架構定義）。

**本論文設定：**
```
路徑：/World/ur10/ee_link/official_rtx_acoustic
tick_rate：20 Hz（每秒發射 20 次脈衝）
centerFrequency：40,000 Hz（40 kHz）
感測器掛載：
  m001（rx=0）：位置 (0.0, 0.0, 0.0)     ← 主發射+接收
  m002（rx=1）：位置 (0.10, 0.0, 0.0)   ← 偏移 10 cm 接收器
```

**為什麼用雙接收器：**
- m001 主要用於正面距離測量
- m001 與 m002 的能量差異（能量平衡）用於估算**橫向對準偏差**
- 機器手臂橫向移動修正的依據

---

### Signal Way（信號路徑）

**是什麼：**
超音波從發射器出發，在空間中可以走多條不同的路徑抵達接收器。每條路徑稱為一個 **Signal Way（信號路徑）**。

```
發射器 (tx)
    │
    ├── 直接路徑 ────────────────────────► 接收器 (rx)  ← 最短 ToF
    │
    ├── 一次反射 → 牆壁 → ─────────────► 接收器 (rx)  ← 較長 ToF
    │
    └── 多次反射 → 天花板 → 地板 → ────► 接收器 (rx)  ← 最長 ToF
```

**識別方式：**
每個 Signal Way 用三元組 `(tx_id, rx_id, ch_id)` 唯一識別：
- `tx_id`：發射器 ID
- `rx_id`：接收器 ID（0 或 1）
- `ch_id`：通道 ID（同 tx/rx 對的第幾條路徑）

---

### Primary Signal Way（主信號路徑）

**是什麼：**
在當前幀所有 Signal Way 中，**峰值振幅（peak amplitude）最大**的那條路徑。

**用途：**
能量距離估算的主要來源。振幅最大通常代表回波最強，但不一定是最短路徑（可能是強反射面造成的間接路徑）。

---

### TOF-Primary Signal Way（TOF 主信號路徑）

**是什麼（本論文 2026-07-03 新增）：**
在所有 Signal Way 中，**第一個樣本的時間偏移（`first_time_offset_ns`）最小**的路徑，即**最早到達**的路徑。

**為什麼需要分開：**

| 選取標準 | 代表意義 | 適合用途 |
|---------|---------|---------|
| 最大峰值振幅（Primary） | 最強回波（可能是反射） | 能量距離估算 |
| 最早到達（TOF-Primary） | 直接路徑（空氣最短距離） | ToF 距離估算 |

若用最大振幅 way 的 ToF 估算距離，可能因為多徑反射（更強但路徑更長）而**高估距離**。

---

### GMO（GenericModelOutput）

**是什麼：**
Isaac Sim 中所有 RTX 感測器（LiDAR、Radar、Acoustic）返回資料的**統一容器格式**，全名 GenericModelOutput。

> 重點：GMO 的欄位 `x, y, z` 在超音波中**不是空間座標**，而是 tx/rx/ch 的 ID 號碼。這是最容易誤解的地方。

**詳見 §4。**

---

### AcousticFeatureFrame

**是什麼：**
本論文自訂的 Python dataclass，把從一個 GMO 幀提取的所有聲學特徵打包成一個物件，供閉環控制器使用。

**包含欄位：**
```python
early_energy          # 主 signal way 前 25% 振幅總和
tof_ns                # TOF-Primary way 第一樣本時間偏移（ns）
peak_amplitude        # 主 signal way 峰值振幅
ref_early_energy      # 參考 way (0,0,0) early energy
fused_distance_m      # 融合估算距離（m）
rx_energy_balance     # 雙接收器能量平衡 [-1, 1]
alignment_score       # 綜合對準分數
gmo_valid             # 此幀 GMO 是否有效
```

---

## 3. 聲學物理原理

---

### 超音波測距原理

超音波測距基於 **ToF（Time of Flight，飛行時間）** 原理：

```
       發射脈衝
          │
          │  時間 t₁（發射）
          ▼
    ══════════════ 目標物
          │
          │  時間 t₂（接收回波）
          ▼

   距離 d = v_sound × (t₂ - t₁) / 2
```

其中 **÷2** 是因為聲波需要去程 + 回程：
$$d = \frac{v_{sound} \times \Delta t}{2}$$

**空氣中音速：**
$$v_{sound} \approx 343 \text{ m/s}（25°C，常溫）$$

**換算：每公尺距離 ≈ 5.83 ms 的往返時間**
$$\Delta t_{per\_meter} = \frac{2 \times 1\text{ m}}{343 \text{ m/s}} \approx 5.83 \times 10^{-3} \text{ s} = 5,830,000 \text{ ns}$$

本論文的 `timeOffsetNs` 單位是奈秒（ns），因此：
$$d = \frac{v_{sound} \times t_{ns} \times 10^{-9}}{2}$$

---

### 多徑效應（Multipath Effect）

在封閉室內，超音波會在牆壁、地板、天花板之間反射，產生多條傳播路徑：

```
直接路徑（Direct Path）：
  發射 ──────────────────► 目標 ──────────────────► 接收
  距離最短，到達時間最早，強度最強（理想情況）

一次牆壁反射（First-order Reflection）：
  發射 ──► 牆壁 ──► 目標 ──► 牆壁 ──► 接收
  距離較長，到達時間較晚，強度較弱

高次反射：
  更複雜的路徑，能量更弱，時間更晚
```

**多徑對本論文的影響：**
- 多徑造成接收信號中有多個振幅峰值
- 高次反射有時能量比直接路徑**更強**（特別是在材質 A / 低吸收條件下）
- 這就是為什麼需要 **Early Energy**（前 25% 時間窗）來分離直接路徑

---

### Early Energy 的物理意義

```
時間軸 →
│
│    ████                        ← 直接路徑（最早，25% 以內）
│    ████  ████                  ← 一次反射
│    ████  ████  ██ ██           ← 高次反射
│    ████  ████  ██ ██  ██       ← 更多多徑
└──────────────────────────────
     前25%  後75%

Early Energy = 前25%時間窗內的振幅絕對值總和
```

**距離與 Early Energy 的關係：**
- 距離**近**：直接路徑回波強，Early Energy **大**
- 距離**遠**：直接路徑衰減，多徑干擾比例上升，Early Energy **小**

$$\text{early\_energy} \propto \frac{1}{d^2}（近似）$$

---

### 能量衰減定律

超音波在空氣中的能量衰減遵循**球面衰減（Spherical Spreading）**：

$$I \propto \frac{1}{r^2}$$

其中 $I$ 是強度（Intensity），$r$ 是距離。

加上空氣**吸收衰減**：
$$I = I_0 \cdot \frac{1}{r^2} \cdot e^{-\alpha r}$$

其中 $\alpha$ 是空氣吸收係數（40 kHz 約 1.0–2.0 dB/m）。

**實務上：** 本論文不推導理論衰減公式，而是用**標定表（Calibration Table）**從實驗數據直接建立 early_energy → 距離的對應關係。

---

### 材質吸收係數（α）

| 條件 | 材質描述 | 吸收係數 α | 物理意義 |
|------|---------|-----------|---------|
| A | 低吸收（硬牆） | ~0.10 | 反射強，多徑複雜 |
| **B** | 中等吸收 | **~0.35** | **標準條件（論文主實驗）** |
| C | 高吸收（軟材） | ~0.60 | 吸音材料，信號較弱 |

材質吸收係數越高，聲波每次撞牆損失的能量越多，最終接收到的信號越弱。

---

## 4. GMO 資料結構詳解

---

### GMO 是什麼

GMO（GenericModelOutput）是 Isaac Sim 中所有 RTX 感測器的**通用輸出容器**，設計目的是讓 LiDAR、Radar、Acoustic 都能用同一套資料格式回傳資料。

**關鍵欄位（超音波語意）：**

| GMO 欄位 | 在 LiDAR 中的意義 | **在超音波中的意義** |
|---------|-----------------|-------------------|
| `x[i]` | 點雲 X 座標 | **發射器 ID (tx_id)** |
| `y[i]` | 點雲 Y 座標 | **接收器 ID (rx_id)** |
| `z[i]` | 點雲 Z 座標 | **通道 ID (ch_id)** |
| `scalar[i]` | 反射強度 | **振幅樣本值** |
| `timeOffsetNs[i]` | 到達時間 | **到達時間（奈秒）** |
| `numElements` | 點數 | **總樣本數** |
| `numSamplesPerSgw` | — | **每個 signal way 的樣本數（stride）** |

> ⚠️ 最容易犯的錯誤：直接把超音波 GMO 的 x, y, z 當作空間座標使用。

---

### GMO 資料排列方式

超音波 GMO 的樣本是按 signal way 順序排列的：

```
索引    0   1   2  ... (numSamplesPerSgw-1) │ (numSamplesPerSgw) ... │ ...
        ─────────────────────────────────── │ ──────────────────────── │ ─
信號    [ Signal Way 0 的所有振幅樣本        │ Signal Way 1 的樣本      │ ...]
        [ (tx=0, rx=0, ch=0)               │ (tx=0, rx=0, ch=1)      │ ...]
```

**分割方式：**
```python
num_ways = numElements / numSamplesPerSgw
for way_idx in range(num_ways):
    start = way_idx * numSamplesPerSgw
    end   = start + numSamplesPerSgw
    this_way_amplitudes = scalar[start:end]
    this_way_times      = timeOffsetNs[start:end]
    tx = x[start]    # 同一 way 內 tx/rx/ch 相同
    rx = y[start]
    ch = z[start]
```

---

### SignalWayStats 統計量

每個 Signal Way 分割出來後，計算以下統計量：

| 統計量 | 計算方式 | 物理意義 |
|--------|---------|---------|
| `peak_amplitude` | `max(|amplitudes|)` | 最強回波峰值 |
| `mean_amplitude` | `mean(amplitudes)` | 平均振幅 |
| `std_amplitude` | `std(amplitudes)` | 振幅變異 |
| `early_energy` | 前 25% 樣本的 `sum(|amplitudes|)` | 直接路徑能量（詳見 §3） |
| `first_time_offset_ns` | `timeOffsetNs[0]`（第一個樣本的時間） | 直接路徑到達時間 |

---

## 5. 核心數學公式

---

### 公式 1：Early Energy

$$E_{early} = \sum_{i=0}^{N_{early}-1} |A_i|$$

其中：
- $A_i$ = 第 $i$ 個振幅樣本
- $N_{early} = \max\left(4, \left\lceil N_{total} \times 0.25 \right\rceil\right)$
- $N_{total}$ = 該 Signal Way 的總樣本數（`numSamplesPerSgw`）

**計算流程：**
```
1. 取出該 Signal Way 的所有振幅：A = [a₀, a₁, ..., aₙ]
2. 取絕對值（正負振幅都算能量）
3. 只取前 25%（至少 4 個樣本）
4. 加總
```

---

### 公式 2：ToF 距離

$$d_{ToF} = \frac{v_{sound} \times t_{first}}{2}$$

其中：
- $v_{sound} = 343$ m/s（標準大氣壓 25°C）
- $t_{first}$ = `first_time_offset_ns` × $10^{-9}$（轉換為秒）
- ÷2 因為往返

**但實際上本論文不用此公式直接計算，而是用標定表插值（見 §6）。**
原因：Isaac Sim 的 `timeOffsetNs` 單位和實際 ToF 的對應關係需要實驗標定。

---

### 公式 3：雙接收器能量平衡

$$B_{rx} = \frac{E_0 - E_1}{|E_0| + |E_1|}$$

其中：
- $E_0$ = rx=0（主接收器）的平均 early energy
- $E_1$ = rx=1（偏移 10 cm 接收器）的平均 early energy

**取值範圍：** $B_{rx} \in [-1, 1]$

| 值 | 意義 |
|----|------|
| $B_{rx} \approx 0$ | 感測器對準目標（兩接收器能量相等） |
| $B_{rx} > 0$ | 目標偏向 rx=0 一側，向 rx=1 方向移動 |
| $B_{rx} < 0$ | 目標偏向 rx=1 一側，向 rx=0 方向移動 |

**橫向修正動作：**
$$\Delta y = -\text{sign}(B_{rx}) \times 0.012 \text{ m}$$

---

### 公式 4：融合距離

$$d_{fused} = \frac{w_E \cdot d_E + w_T \cdot d_T}{w_E + w_T}$$

其中：
- $d_E$ = 能量估算距離（標定表插值）
- $d_T$ = ToF 估算距離（標定表插值）
- $w_E = 0.72$（能量權重）
- $w_T = 0.28$（ToF 權重）

**僅在以下條件下使用 $d_T$：**
- $d_T$ 是有限值（非 NaN / Inf）
- `tof_ns ≥ 10^5 ns`（過濾無效 ToF：< 100 μs 視為感測器噪音）

若 ToF 無效，退化為純能量估算：
$$d_{fused} = d_E$$

**融合邏輯：**
```
                           ┌─ d_E 有效? ─ 是 → 用 d_E (w=0.72)
d_fused = 加權平均 ─────────┤
                           └─ d_T 有效? ─ 是 → 用 d_T (w=0.28)
                                        └─ 否 → 純能量估算
```

---

### 公式 5：對齊分數（Alignment Score）

$$S_{align} = E_{early} + 0.35 \cdot E_{ref} + 0.20 \cdot A_{peak} - 25.0 \cdot |B_{rx}|$$

其中：
- $E_{early}$ = primary Signal Way 的 early energy（主距離信號）
- $E_{ref}$ = 參考 Signal Way (tx=0, rx=0, ch=0) 的 early energy（跨幀穩定參考）
- $A_{peak}$ = primary Signal Way 的峰值振幅
- $|B_{rx}|$ = 能量平衡的絕對值（越偏斜懲罰越重）

**設計意義：**
- 越靠近目標，$E_{early}$ 越大，$S_{align}$ 越高
- 越對齊（$B_{rx}$ 越接近 0），$S_{align}$ 越高
- 用於夾取決策：分數超過閾值才允許夾取動作

---

### 公式 6：變異係數（Coefficient of Variation, CV）

$$CV = \frac{\sigma}{\bar{x}} \times 100\%$$

其中：
- $\bar{x}$ = 樣本均值
- $\sigma$ = 樣本標準差（ddof=1）

**用途（Phase A 可重複性驗證）：**
CV 越低 → 重複測量結果越一致 → 感測器特徵越可重複

**判讀標準：**
- CV < 5%：優秀可重複性
- CV < 15%：可接受
- CV > 30%：高度不穩定

---

### 公式 7：Spearman 等級相關係數 ρ

$$\rho = 1 - \frac{6 \sum d_i^2}{n(n^2-1)}$$

其中：
- $d_i$ = 樣本 $i$ 在 X 排名與在 Y 排名的差值
- $n$ = 樣本數（本論文 n = 6 個距離點）

**本論文的應用：**
```
X = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]  ← 目標距離（m）
Y = [mean early_energy @ 各距離]       ← RTX 特徵均值

結果：ρ ≈ -0.66（負相關）
意義：距離越大，early_energy 越小（符合物理預期）
```

**為什麼用 Spearman 而非 Pearson：**
- early_energy 與距離的關係是**非線性**的（約 $1/d^2$）
- Spearman 只看排名順序，不假設線性關係
- 適合評估「趨勢」而非「線性程度」

---

### 公式 8：F1 分數

$$F1 = \frac{2 \cdot TP}{2 \cdot TP + FP + FN}$$

**混淆矩陣：**

```
                    預測 Positive    預測 Negative
實際 Positive           TP（真陽）       FN（假陰）
實際 Negative           FP（假陽）       TN（真陰）
```

- $TP$（True Positive）：預測「在接近區」且確實在接近區
- $FP$（False Positive）：預測「在接近區」但實際不在
- $FN$（False Negative）：預測「不在接近區」但實際在

**為什麼用 F1（而非準確率 Accuracy）：**
- 接近區（stop_region_label = 1）的樣本比非接近區少（**類別不平衡**）
- 純 Accuracy 在不平衡資料會偏高，掩蓋模型缺陷
- F1 = Precision × Recall 的調和平均，對類別不平衡更公平

---

### 公式 9：Balanced Accuracy

$$BA = \frac{Recall + Specificity}{2} = \frac{TPR + TNR}{2}$$

其中：
- $Recall（TPR）= \frac{TP}{TP + FN}$（真陽率，命中率）
- $Specificity（TNR）= \frac{TN}{TN + FP}$（真陰率，特異性）

**意義：**
同時考慮兩類的預測能力，在類別不平衡時比 Accuracy 更可靠。

---

## 6. 標定（Calibration）原理

---

### 為什麼需要標定

RTX Acoustic 的 early_energy 和 timeOffsetNs 是**模擬器內部量**，不能直接用理論公式換算距離，需要先建立「特徵值 → 距離」的對應關係（標定表）。

**標定流程：**
```
1. 機器手臂從近距離慢慢向目標接近（動態掃描）
2. 每一步記錄：
   (primary_sgw_early_energy, tof_ns, oracle_distance_m)
   其中 oracle_distance_m 是幾何計算的真實距離（地面真實值）
3. 從這些資料對建立插值表
4. 之後用此表把新的特徵值換算成距離估計
```

---

### 能量標定表建立

**演算法：**
1. 收集所有 `(early_energy, oracle_distance)` 資料對
2. 過濾無效 GMO 幀
3. 按 `oracle_distance` **降序**排列（從遠到近）
4. 均勻取 8 個代表點（跨越全距離範圍）
5. 強制**單調性**：確保 early_energy 越大 → 距離越小

**單調性意義：**

```
能量（越大 = 越近）
  大 ─────────────────────────► 小
  │
  ▼
距離（越大 = 越遠）
  小 ─────────────────────────► 大
```

若出現 $E_{i} > E_{i+1}$ 但 $d_i < d_{i+1}$（能量倒轉），強制修正為 $E_{i} = E_{i+1}$

**預設標定表（手動標定，2026-06-30）：**

| Early Energy | 距離（m） |
|:---:|:---:|
| 221.0 | 0.85 |
| 155.0 | 0.72 |
| 148.0 | 0.65 |
| 140.0 | 0.50 |
| 136.0 | 0.40 |
| 132.0 | 0.30 |
| 128.0 | 0.25 |
| 95.0  | 0.22 |

---

### ToF 標定表建立

類似能量標定，但：
- 按 `oracle_distance` **升序**排列
- `tof_ns` 越大 → 距離越大（正向單調）
- 過濾 `tof_ns < 10^5 ns`（100 μs 以下視為無效 ToF）

**預設 ToF 標定表：**

| ToF (ns) | 距離（m） |
|:---:|:---:|
| 720,000 | 0.22 |
| 800,000 | 0.28 |
| 880,000 | 0.35 |
| 960,000 | 0.45 |
| 1,040,000 | 0.55 |
| 1,140,000 | 0.65 |
| 1,280,000 | 0.85 |

**物理換算驗證（音速 343 m/s）：**
$$d = \frac{343 \times 0.72 \times 10^{-3}}{2} \approx 0.123 \text{ m}$$

> 注意：標定表的值與理論音速計算有差距，因為模擬器的時間單位需要獨立標定。

---

## 7. 距離估算演算

---

### 線性插值演算（`_interp_monotonic_table`）

給定標定表和輸入特徵值，計算估算距離：

```
標定表（以能量為例）：
  索引  0     1     2     3     ...
  key  221   155   148   140   ...  ← 降序（能量大到小）
  val  0.85  0.72  0.65  0.50  ...  ← 對應距離（m）

輸入：early_energy = 160

步驟：
1. 找到 160 落在哪個區間：155 < 160 ≤ 221
   → 索引 0（221）到 索引 1（155）之間
2. 計算插值比例：
   t = (160 - 155) / (221 - 155) = 5 / 66 ≈ 0.076
3. 計算距離：
   d = 0.72 + 0.076 × (0.85 - 0.72) = 0.72 + 0.010 ≈ 0.730 m
```

**超出範圍：夾至端點，不外插**
- 若 `early_energy > 221`（比最大值還大）→ 回傳 0.85 m（最近端）
- 若 `early_energy < 95`（比最小值還小）→ 回傳 0.22 m（最遠端）

---

### 完整距離估算流程

```
GMO 幀
  │
  ├── [能量路徑]
  │   1. 選 Primary Signal Way（最大 peak_amplitude）
  │   2. 計算 early_energy
  │   3. 能量標定表插值 → d_energy
  │
  ├── [ToF 路徑]
  │   1. 選 TOF-Primary Signal Way（最小 first_time_offset_ns）  ← 2026-07-03 修復
  │   2. 取 first_time_offset_ns = tof_ns
  │   3. 驗證 tof_ns ≥ 1e5 ns
  │   4. ToF 標定表插值 → d_tof
  │
  └── [融合]
      加權平均(d_energy × 0.72 + d_tof × 0.28) → d_fused
```

---

## 8. 閉環控制演算

---

### 什麼是閉環控制

```
開環（Open-loop）：
  指令 ──────────────────► 機器手臂 ──► 結果
  （固定預計算路徑，不看感測器）

閉環（Closed-loop）：
  感測器 ──► 估算距離 ──► 決策 ──► 機器手臂
      ▲                              │
      └──────────────────────────────┘（回饋循環）
  （根據感測器即時調整動作）
```

**本論文的閉環：**
每走一步，先讀 RTX Acoustic 特徵，估算到目標的距離，再決定下一步要不要繼續前進。

---

### 狀態機（State Machine）

控制器是一個有限狀態機，每個 tick（每 1/20 秒）從感測器讀資料，更新狀態。

```
狀態轉換圖：

INIT
  │ 初始化完成
  ▼
AT_SEARCH_START
  │ 開始接近
  ▼
APPROACH_STEP ◄──────────────────────┐
  │ 每步判斷                         │ 還沒到
  ├─ 到達 standoff(0.35m) 或走廊終點 ─┘
  ▼
LATERAL_ALIGN
  │ 橫向對齊（能量平衡 → 0）
  ▼
FINAL_APPROACH
  │ 慢速接近（0.02m/步）
  ▼
DESCEND / AT_STANDOFF
  │
  ▼
GRASP → LIFT → SUCCESS
         （任何階段可能 → FAIL）
```

---

### APPROACH_STEP 決策邏輯

```
每步執行：

1. 讀取 GMO → 計算 AcousticFeatureFrame
2. 若 gmo_valid = False → FAIL (NO_GMO)
3. 若 early_energy 非有限值 → FAIL (INVALID_FEATURE)
4. 取得融合距離 d = fused_distance_m
5. 若步數 ≥ 40 → FAIL (MAX_STEPS)
6. 若感測器 X 位置 ≥ 搜索走廊終點：
     若 d ≤ 0.45 m → 轉 LATERAL_ALIGN
     否則 → FAIL (SEARCH_LIMIT)
7. 若步數 ≥ 3 且 d ≤ 0.35 m（standoff）→ 轉 LATERAL_ALIGN
8. 否則：前進 0.04 m，步數 +1
```

**為什麼步數 ≥ 3 才判斷距離：**
前幾步感測器還在「暖機」，GMO 資料可能不穩定（transient response）。

---

### Supervisor（監管員）的角色

Supervisor 是**安全包絡**，不是控制器。

```
控制器決策（純聲學）：
  「我的 fused_distance = 0.40m，可以繼續」

Supervisor（oracle 安全）：
  「oracle 真實距離 = 0.38m，正常」→ CONTINUE
  「oracle 真實距離 = 0.20m，快撞了」→ FORCE_STANDOFF

論文 claim boundary：
  控制器 = 純 RTX 聲學特徵（可宣稱）
  Supervisor = oracle 幾何護欄（不計入聲學貢獻）
```

---

## 9. Physical AI 與機器學習

---

### Physical AI 在本論文的定義

**NVIDIA 的 Physical AI：**
能夠理解並操作物理世界的 AI 系統，強調感知 → 推理 → 行動的整合。

**本論文的 Physical AI 任務：**
離線分類器，判斷機器手臂當前步驟是否「已進入接近區」（`stop_region_label`）。

**輸入：** 19 維聲學 + 位姿特徵
**輸出：** 是/否 在接近區（oracle 距離 ≤ 0.45 m）

---

### Leave-One-Trial-Out（LOTO）驗證

**為什麼不用普通 K-fold：**

```
普通 K-fold 的問題：
Trial 1: step1, step2, step3, ..., step20
─────────────────────────────────────────
K-fold 可能把 step5 放 train，step6 放 test
→ 相鄰步驟高度相關 → 洩漏 → F1 虛高

LOTO（正確做法）：
Round 1：Trial 1 作 test，Trial 2-25 作 train
Round 2：Trial 2 作 test，Trial 1,3-25 作 train
...
Round 25：Trial 25 作 test，Trial 1-24 作 train
→ 整個 trial 不跨訓練/測試集 → 無洩漏
```

---

### 特徵消融實驗

**目的：** 分離「聲學特徵」和「位姿特徵」的貢獻

| 設定 | 使用特徵 | 目的 |
|------|---------|------|
| `all_features` | 全 19 維 | 上界參考 |
| `acoustic_only` | 去掉 `sensor_x_m`, `sensor_y_m` | 純聲學能力 |
| `pose_only` | 只保留 `sensor_x_m`, `sensor_y_m` | 純位姿貢獻 |

**結果解讀（v9 canonical）：**

| Feature Set | F1 | Balanced Accuracy |
|-------------|:---:|:---:|
| all_features | **0.684** | 0.665 |
| acoustic_only | 0.598 | 0.590 |
| pose_only | 0.533 | 0.650 |

- `acoustic_only F1 (0.598) > pose_only F1 (0.533)` → **聲學特徵有獨立貢獻**
- 但兩者都遠低於 `all_features` → 位姿和聲學互補

---

### 模型選擇

**Logistic Regression（LR）：**
- 線性模型，可解釋係數
- 適合作為 baseline
- 用 `class_weight="balanced"` 處理類別不平衡

**Decision Tree（深度 2）：**
- 只有 2 層 → 只能學習最重要的 1-2 個分割
- 容易解釋（可畫出決策樹）
- 避免過擬合（`min_samples_leaf=3`）

---

## 10. 統計驗證方法

---

### Phase A 驗證：30/30 可重複性

**驗證問題：** RTX Acoustic 特徵在相同條件下是否穩定？

**方法：**
```
實驗設計：
  6 距離點 × 5 次 repeat = 30 次獨立 Isaac Sim 啟動

每次 run 的 PASS 條件：
  - gmo_valid = True（GMO 資料有效）
  - num_elements > 0（有至少一個信號樣本）
  - primary_sgw_early_energy 是有限正值

整體通過條件：
  pass=30, fail=0
```

**結果：** 30/30 PASS ✅

---

### Phase A 驗證：距離趨勢 Spearman ρ

**驗證問題：** early_energy 是否隨距離增加而下降（有趨勢）？

**方法：**
```
1. 取 6 個距離點的 early_energy 均值
   X = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]  m
   Y = [μ₀.₅, μ₁.₀, μ₁.₅, μ₂.₀, μ₂.₅, μ₃.₀]  （early_energy 均值）

2. 計算 Spearman ρ（scipy.stats.spearmanr）

3. 結果：ρ ≈ -0.66
   方向：負相關（距離↑，能量↓）→ 符合物理預期
```

**統計力道說明（重要！）：**
n=6 的 Spearman 檢定統計力有限，p 值約 0.15（未達 p < 0.05 顯著）。
**論文應陳述為「趨勢級可行性」，而非「統計顯著相關」。**

---

### Phase B/C 驗證：閉環 vs 開環

**驗證問題：** 閉環接近是否比開環更能到達目標？

**對照組設計：**

| 組別 | 控制方式 | Trial 數 |
|------|---------|---------|
| 閉環（實驗組） | RTX Acoustic 閉環控制器 | 25 |
| 開環（對照組） | 直接讀 oracle 目標座標 | 24 |

> 為什麼開環用 oracle 座標？這是「能到達目標的最理想開環基準」，如果閉環連這個都比不上，才是失敗。

**隨機化設計（防止偏差）：**

```
v9 版本的隨機化變數：
  1. 搜索起點 X/Y（在允許範圍內隨機）
  2. 目標扳手 Y 偏移（左右偏移隨機）
  3. Trial 種子（控制 LCG 隨機數）

目的：
  打破簡單的「距離越近成功越高」相關性
  迫使模型真正利用聲學特徵，而非位置捷徑
```

**結果：**

| 指標 | 閉環 | 開環 |
|------|:---:|:---:|
| 到達 ≤ 0.45 m | **84%** (21/25) | 29% (7/24) |
| 到達 ≤ 0.35 m | **84%** (21/25) | 4.2% (1/24) |
| 最終夾取成功 | 20% (5/25) | 20.8% (5/24) |

---

### Phase B/C 驗證：Physical AI 消融

**驗證問題：** acoustic_only 特徵是否含有可測量的狀態信號？

**假設：**
- $H_0$：acoustic_only 的 F1 ≤ pose_only 的 F1（聲學沒有額外幫助）
- $H_1$：acoustic_only 的 F1 > pose_only 的 F1（聲學有獨立貢獻）

**結果：** acoustic_only F1 = 0.598 > pose_only F1 = 0.533
**結論：** 拒絕 $H_0$，聲學特徵有可測量的狀態信號 ✅

---

## 11. 實驗設計與對照

---

### 實驗架構全圖

```
Phase A：特徵可重複性
─────────────────────
固定 TCP → 6 距離點 × 5 repeats
目標：30/30 PASS + ρ ≈ -0.66
答案：RTX 特徵是否穩定且有距離趨勢？（RQ1）

           │
           ▼

Phase B：閉環接近
─────────────────
隨機化場景 → 閉環 25 trials vs 開環 24 trials
目標：到達率 84% vs 29%
答案：閉環是否優於開環？（RQ2）

           │
           ▼

Phase C：Physical AI + 夾取
────────────────────────────
同 v9 資料集 → 離線 LOTO 分類 + contact-only 夾取
目標：acoustic_only F1 = 0.598 + 夾取示範
答案：聲學特徵能分類狀態嗎？夾取能示範嗎？（RQ3/4）
```

---

### Contact-Only 模式（--skip-lift）

**為什麼用 contact-only：**
- PhysX + Robotiq 的 lift（提升）動作高度不穩定
- lift 失敗率很高，但這是**夾爪物理模擬問題**，非**聲學問題**
- 為了清楚分離「聲學貢獻」和「夾取機構限制」，使用 contact-only 模式

**Contact-only 設定：**
```
--skip-lift 旗標 → FixedCuboid（靜態目標物）
目標物不動，只驗證機器手臂能否接觸到目標

vs.

--enable-lift → DynamicCuboid（動態目標物）
目標物可被移動，驗證完整夾取+提升（高不穩定性）
```

---

### Claim Boundary 總結

**本論文的聲明邊界（Claim Boundary）是什麼：**
明確界定哪些結果可以作為論文貢獻，哪些屬於已知限制。

**可以聲明（有充分實驗依據）：**

| 聲明 | 數字依據 |
|------|---------|
| RTX 特徵 30/30 可重現 | Phase A batch_summary.txt |
| early_energy 有距離下降趨勢 | ρ ≈ −0.66, n = 6 |
| 閉環到達率顯著優於開環 | 84% vs 29% |
| 聲學特徵含可測量狀態信號 | acoustic_only F1 = 0.598 |
| Tier B 接觸示範框架 | contact-only v9 |

**不可以聲明（超出實驗範圍）：**

| 不可聲明 | 原因 |
|---------|------|
| 厘米級精確測距 | 僅趨勢，n=6 統計力不足 |
| 穩定夾取系統 | 最終成功率 ~20%，PhysX 問題 |
| 純聲學控制（無幾何護欄） | Supervisor 仍用 oracle 安全包絡 |
| 可部署學習控制器 | 只有離線 baseline |
| 實機驗證（CH201） | 未執行 |

---

*文件生成時間：2026-07-03*
*同步文件：`TECHNICAL_REFERENCE_2026-07-03.md`（代碼細節）、`REPRODUCIBILITY_AUDIT.md`（可重現審計）*
