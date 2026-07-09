# WPM 聲學實驗規則文本
**版本**: 1.0 | **日期**: 2026-07-06 | **基於**: 10+ 次實驗的教訓

---

## 第一章：GMO 資料結構（最常犯錯的地方）

### 規則 1-1：`z` 欄位不是時間軸

```
GMO 各欄位正確含義：
  gmo.x[i]           → TX 感測器掛載 ID（發射器編號）
  gmo.y[i]           → RX 感測器掛載 ID（接收器編號）
  gmo.z[i]           → Channel ID（發射序列的通道編號）← 不是時間！
  gmo.scalar[i]      → 振幅值
  gmo.timeOffsetNs[i]→ 永遠是 0（Isaac Sim 6.0 已知 bug，不可使用）
```

**❌ 錯誤**：`waveform[z_idx] = amplitude`（把 channel ID 當 sample index）
**✅ 正確**：用 `numSamplesPerSgw` 做時間軸

---

### 規則 1-2：用 `numSamplesPerSgw` 重建時間波形

GMO buffer 的排列方式：
```
[sgw_0 樣本0, sgw_0 樣本1, ..., sgw_0 樣本(N-1),
 sgw_1 樣本0, sgw_1 樣本1, ..., sgw_1 樣本(N-1), ...]
```

正確重建第一個 signal way 的時間波形：
```python
num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
# num_spsgw > 0 才能用 stride 方法
amps = amp_all[0 : num_spsgw]     # 第一個 signal way，時間由小到大
peak_idx = int(np.argmax(amps))   # 時間峰值位置（正確！）
```

**驗證**：若 `num_spsgw == 0`，改用 fallback（按 tx/rx/ch 分組）。

---

### 規則 1-3：`timeOffsetNs` 在 Isaac Sim 6.0 全是 0

```python
# 驗證 code（每次新實驗加這行）：
tof_first = float(tof_all[0])
assert tof_first == 0.0, "timeOffsetNs 不是 0？需要重新確認"
```

不要用 `timeOffsetNs` 做任何距離計算。用 `peak_sample_idx * T_US * V / 2`。

---

### 規則 1-4：樣本週期 T_US = 132.5 µs（已校正值）

```python
T_US = 132.5e-6    # 秒/樣本（從實驗反推，非 schema default 的 102.4 µs）
V_SOUND = 343.0    # m/s
# 距離換算：dist_m = peak_sample_idx * T_US * V_SOUND / 2
```

從實驗數據驗證（dist=0.6m, peak=22）：`22 × 132.5e-6 × 343 / 2 = 0.50m ✓`

---

## 第二章：WPM 物理特性（已實驗確認）

### 規則 2-1：WPM 是真正的 Ray Tracer

WPM **確實追蹤幾何聲波路徑**，包括 `UsdGeom.Cube` prim。
- 有 Cube 目標在 (dist, 0, 0)：peak_sample_idx = dist / (T_US × V / 2)，r = +0.9998
- WPM 的 `azSpanDeg`、`elSpanDeg`、`traceTreeDepth` 是真正的 ray tracing 參數

**官方描述**（`acoustic_extension.rst`）：
> "high-fidelity acoustic wave propagation modeling with support for multiple ray bounces, material interactions"

---

### 規則 2-2：USD Mesh 資產優先於 Cube prim

| 場景幾何 | WPM 可見性 | 備註 |
|---------|-----------|------|
| UR10e URDF mesh | ✅ 高優先 | 主導信號，遮蓋 Cube |
| `UsdGeom.Cube` | ✅ 可見 | 但會被 USD Mesh 蓋掉 |
| 房間牆壁（Cube） | ✅ 可見 | 但被 arm mesh 和参數化模型蓋掉 |

**核心教訓**：UR10e 手臂的 USD mesh 訊號強度遠大於 Cube prim，只要手臂在場景中，Cube 目標的距離信號就被完全掩蓋。

---

### 規則 2-3：Close Range 參數化模型的作用

`closeDirectAmpl`、`closeIndirectAmpl` 等參數是**疊加**在幾何 ray tracing 之上的近場放大器，不是替代品。它們影響振幅大小，但 **peak_sample_idx（飛行時間）仍由幾何決定**。

---

### 規則 2-4：已確認無效的方法

以下方法已經過多次實驗確認無效，**不要重複嘗試**：

| 方法 | 結果 | 實驗次數 |
|------|------|---------|
| NonVisualMaterial (A/B/C/D) 條件改變 | 對 Acoustic 無效（對 Lidar/Radar 有效） | 4 次 |
| 移除天花板/後牆（open_space） | 零效果（byte-for-byte identical） | 1 次 |
| closeIndirectAmpl=0.1、closeDirectAmpl=30 | 零效果（byte-for-byte identical） | 1 次 |
| azSpanDeg=45、elSpanDeg=45 | 零效果 | 1 次 |
| 有 UR10e 手臂的距離回歸 | R² ≈ 0 | 5+ 次 |

---

## 第三章：實驗設計規則

### 規則 3-1：arm-free 場景設計

無手臂實驗的標準場景：
```
感測器：固定於 (0, 0, 0)，TX at (0,0,0)，RX at (mount_spacing, 0, 0)
目標  ：Cube 沿 +X 軸，中心於 (dist, 0, 0)
禁止  ：UR10e 或任何 USD Mesh（只保留 Cube 目標）
```

---

### 規則 3-2：距離掃描最小要求

| 項目 | 最小值 | 建議值 |
|------|-------|-------|
| 距離步數 | 10 | 20-30 |
| settle frames / 步 | 8 | 12 |
| measure frames / 步 | 3 | 6 |
| 最小距離 | 0.15m | 0.20m |
| 最大距離 | 0.80m | 1.50m |

---

### 規則 3-3：結果驗收標準

每次實驗必須報告以下項目，才算完整：

```
□ numElements > 0（有資料）
□ numSamplesPerSgw 印出（確認 stride 可用）
□ tof_first_ns 印出（確認仍是 0）
□ peak_sample_idx 是否隨距離線性變化（眼測或 r）
□ Pearson r(peak_sample_idx, distance) 報告
□ inferred_dist_m RMSE 報告
□ 結論：r > 0.95 = 可偵測，r < 0.50 = 不可偵測
```

---

### 規則 3-4：移動目標的正確方式

**不用**：`Cube.set_translations()` 或其他 Isaac Sim 高階 API（可能有 xform op 命名不一致問題）

**使用**：直接操作 USD xform op：
```python
from pxr import Gf, UsdGeom
xformable = UsdGeom.Xformable(stage.GetPrimAtPath("/World/target"))
ops = {op.GetOpName(): op for op in xformable.GetOrderedXformOps()}
if "xformOp:translate" in ops:
    ops["xformOp:translate"].Set(Gf.Vec3d(x, y, z))
```

---

## 第四章：腳本撰寫規則

### 規則 4-1：argparse 必須在 SimulationApp 之前

```python
# ✅ 正確順序
import argparse
parser = argparse.ArgumentParser()
parser.add_argument(...)
args, _ = parser.parse_known_args()  # parse_known_args，不是 parse_args

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
# 之後才 import numpy、omni 等
```

---

### 規則 4-2：Writer 資料共享用 module-level dict

```python
_buf = {"latest": None}   # 模組層級

class MyWriter(Writer):
    def write(self, data):
        _buf["latest"] = parse(data)   # 不用回傳，直接寫 _buf

rep.WriterRegistry.register(MyWriter)
sensor.attach_writer("MyWriter")   # 這會建立新 instance，_buf 仍可存取
```

---

### 規則 4-3：特徵萃取標準函式

每個實驗腳本必須使用**與 `rtx_acoustic_factory.py` 相容**的萃取邏輯：

```python
def extract_features(gmo) -> dict | None:
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0: return None

    amp_all  = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float)
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)

    if num_spsgw > 0 and n % num_spsgw == 0:
        # 找最大峰值的 signal way 作為 primary
        best_start = max(
            range(n // num_spsgw),
            key=lambda w: float(np.max(amp_all[w*num_spsgw:(w+1)*num_spsgw]))
        ) * num_spsgw
        amps = amp_all[best_start : best_start + num_spsgw]
    else:
        amps = amp_all  # fallback

    peak_idx = int(np.argmax(amps))
    peak_amp = float(amps[peak_idx])
    total_e  = float(np.sum(amps ** 2))
    N_EARLY, N_ULTRA = 20, 8
    early_e  = float(np.sum(amps[:N_EARLY] ** 2))
    ultra_e  = float(np.sum(amps[:N_ULTRA] ** 2))
    early_frac = early_e / total_e if total_e > 0 else 0.0

    return {
        "peak_sample_idx":    float(peak_idx),
        "inferred_dist_m":    peak_idx * 132.5e-6 * 343.0 / 2.0,
        "peak_amplitude":     peak_amp,
        "early_energy":       early_e,
        "ultra_early_energy": ultra_e,
        "early_fraction":     early_frac,
        "total_energy":       total_e,
        "n_samples_per_sgw":  float(num_spsgw),
        "n_elements":         float(n),
    }
```

---

## 第五章：常見陷阱速查表

| 症狀 | 原因 | 解法 |
|------|------|------|
| `peak_sample_idx` 永遠是 0 | 用 `z`（channel ID）當時間軸 | 改用 `numSamplesPerSgw` stride |
| 所有距離輸出完全相同 | UR10e arm mesh 主導信號 | 移除手臂，arm-free 場景 |
| `numElements = 0` | 感測器尚未初始化 | warmup 至少 20 frames |
| 改變幾何無效果 | 之前改的是 Cube/Material，不是 mesh | WPM 對 Cube 有響應，確認場景設定 |
| `early_energy` 全部很低 | N_EARLY 太小，peak 在 window 外 | 檢查 peak_idx 和 N_EARLY 的關係 |
| `inferred_dist` 系統性偏低 | 近場（< 0.45m）Close Range 模型放大 | 用 RMSE+bias 回報，不當作 bug |
| Writer 拿不到資料 | 用了 instance 變數而非 module-level dict | 改用 `_buf = {"latest": None}` |

---

## 附錄：關鍵數值常數

```python
T_US      = 132.5e-6   # 秒/樣本（實驗校正值）
V_SOUND   = 343.0      # m/s
N_EARLY   = 20         # early window（約 0.45m 以內）
N_ULTRA   = 8          # ultra-early window（約 0.18m 以內）
CLOSE_RANGE_M = 1.42   # WPM 近場模型的距離門檻（schema default）
CENTER_FREQ_HZ = 40_000.0  # 我們使用的中心頻率
MOUNT_SPACING_M = 0.10    # TX-RX 間距
```
