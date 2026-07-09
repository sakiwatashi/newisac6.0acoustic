# 技術完整統整文件
# UR10 RTX Acoustic 超音波閉環接近控制 · Isaac Sim Pipeline

**版本：** 2026-07-03
**論文：** 基於 RTX Acoustic 超音波感測之機械手臂閉迴路接近控制與 Physical AI 狀態判斷
**學校：** 逢甲大學電聲碩士學位學程

---

## 目錄

1. [環境與平台](#1-環境與平台)
2. [RTX Acoustic API 完整說明](#2-rtx-acoustic-api-完整說明)
3. [GMO 資料結構與解析計算](#3-gmo-資料結構與解析計算)
4. [SurfaceGripper API](#4-surfacegripper-api)
5. [場景幾何 Passport 系統](#5-場景幾何-passport-系統)
6. [實驗設計 — Phase A 特徵可重複性](#6-實驗設計--phase-a-特徵可重複性)
7. [實驗設計 — Phase B/C 閉環接近與夾取](#7-實驗設計--phase-bc-閉環接近與夾取)
8. [閉環控制器狀態機](#8-閉環控制器狀態機)
9. [Approach Supervisor v1 監管邏輯](#9-approach-supervisor-v1-監管邏輯)
10. [標定系統 (Calibration)](#10-標定系統-calibration)
11. [距離估算計算方式](#11-距離估算計算方式)
12. [Physical AI 資料集建立](#12-physical-ai-資料集建立)
13. [Physical AI 模型訓練與評估](#13-physical-ai-模型訓練與評估)
14. [特徵提取計算 (Phase A)](#14-特徵提取計算-phase-a)
15. [Spearman 趨勢分析](#15-spearman-趨勢分析)
16. [材質系統 (RTX NonVisualMaterial)](#16-材質系統-rtx-nonvisualmaterial)
17. [檔案結構與腳本清單](#17-檔案結構與腳本清單)
18. [Claim Boundary 表](#18-claim-boundary-表)

---

## 1. 環境與平台

### 軟體版本

| 元件 | 版本 |
|------|------|
| NVIDIA Isaac Sim | **6.0.0-rc.59** host standalone |
| Isaac Lab | 3.0.0-beta2（附錄實驗） |
| rsl-rl-lib | 5.0.1（附錄 RL） |
| Python | 3.12（Isaac Sim 內建） |
| Isaac Sim Experience | `apps/isaacsim.exp.base.python.kit` |
| NumPy | Isaac Sim 內建 |
| SciPy | Isaac Sim 內建（`scipy.stats.spearmanr`） |
| scikit-learn | `sklearn`（offline policy training） |

### 硬體需求

- NVIDIA GPU（RTX Acoustic 需 RTX 光線追蹤）
- 建議：DGX 或具 RTX 能力的 GPU
- 作業系統：Linux（Ubuntu）

### 關鍵路徑

```text
REPO_ROOT=/home/lab109/song/isaacsim6.0
APP_ROOT=$REPO_ROOT/app
SCRIPTS=$REPO_ROOT/scripts
OUTPUTS=$REPO_ROOT/runtime/outputs
```

### 環境設定

```bash
source scripts/env_host_isolated.sh
```

---

## 2. RTX Acoustic API 完整說明

### 來源

```
app/standalone_examples/api/isaacsim.sensors.experimental.rtx/
  create_acoustic_basic.py
  inspect_acoustic_gmo.py

app/exts/isaacsim.sensors.experimental.rtx/
  tests/test_acoustic_sensor.py
```

### 核心 Import

```python
from isaacsim.sensors.experimental.rtx import (
    Acoustic,
    AcousticSensor,
    parse_generic_model_output_data,
)
import omni.replicator.core as rep
from omni.replicator.core import Writer
```

### Step 1：建立 OmniAcoustic Prim（`Acoustic`）

```python
acoustic = Acoustic(
    "/World/ur10/ee_link/official_rtx_acoustic",   # USD 路徑
    tick_rate=20.0,                                 # Hz：每秒傳送脈衝次數
    aux_output_level="BASIC",                       # 輸出等級
    translations=np.array([0.08, 0.0, 0.0]),       # 相對父 prim 的偏移（m）
    attributes={
        # 中心頻率（Hz）
        "omni:sensor:WpmAcoustic:centerFrequency": 40000.0,
        # 雙接收器安裝（Dual Mount）
        "omni:sensor:WpmAcoustic:sensorMount:m001:position": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m001:rotation": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:position": (0.10, 0.0, 0.0),  # 間距 10 cm
        "omni:sensor:WpmAcoustic:sensorMount:m002:rotation": (0.0, 0.0, 0.0),
        # 接收器群組（包含 m001, m002 兩個接收器）
        "omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices": [0, 1],
    },
)
```

**關鍵參數說明：**

| 參數 | 值 | 說明 |
|------|-----|------|
| `tick_rate` | 20.0 Hz | 超音波脈衝發射頻率 |
| `centerFrequency` | 40,000 Hz | 40 kHz 超音波中心頻率 |
| `sensorMount:m001` | (0,0,0) | 第一接收器（發射+接收） |
| `sensorMount:m002` | (0.10,0,0) | 第二接收器（間距 10 cm，用於橫向對齊） |
| `translations` | (0.08, 0, 0) | 感測器相對 ee_link 的前向偏移 8 cm |
| `aux_output_level` | "BASIC" | Writer 模式下不需要 FULL aux data |

**USD Schema：**
`OmniSensorGenericAcousticWpmAPI` — WPM（Wave Propagation Model）聲學模型

### Step 2：建立 Runtime Wrapper（`AcousticSensor`）

```python
# 模式 A：Writer 模式（Writer 自帶 annotator）
sensor = AcousticSensor(acoustic, annotators=[])

# 模式 B：直接 annotator 模式
sensor = AcousticSensor(
    acoustic,
    annotators=["generic-model-output"],
    render_vars=["GenericModelOutput"],
)
```

### Step 3：自訂 Writer 接收 GMO

```python
class AcousticGmoWriter(Writer):
    def __init__(self):
        self.data_structure = "renderProduct"
        self.annotators = [rep.annotators.get("GenericModelOutput")]
        self._frame_count = 0

    def write(self, data):
        if "renderProducts" not in data:
            return
        for _rp_name, rp_data in data["renderProducts"].items():
            gmo_raw = rp_data.get("GenericModelOutput")
            if isinstance(gmo_raw, dict):
                gmo_raw = gmo_raw.get("data")
            gmo = parse_generic_model_output_data(gmo_raw)
            if gmo.numElements > 0:
                # 處理 gmo 資料
                pass
        self._frame_count += 1

rep.WriterRegistry.register(AcousticGmoWriter)
sensor.attach_writer("AcousticGmoWriter")
```

### Step 4：模擬運行

```python
timeline = omni.timeline.get_timeline_interface()
timeline.play()

for _ in range(settle_steps):
    simulation_app.update()   # 每次 update 推進一個物理步

timeline.stop()
```

### 本專案感測器掛載方式

```text
/World/ur10/ee_link/                    ← UR10e 末端執行器（隨機械臂運動）
    official_rtx_acoustic/              ← OmniAcoustic prim
        visual_rx_mount_0               ← 橙色球體視覺標記（無渲染的感測器標示）
        visual_rx_mount_1
```

---

## 3. GMO 資料結構與解析計算

### GenericModelOutput (GMO) 欄位語意

RTX Acoustic 的 GMO 與 LiDAR/Radar 不同，欄位語意如下：

| GMO 欄位 | 超音波語意 | 資料型別 |
|-----------|-----------|---------|
| `x[i]` | 發射器 sensor mount ID (tx_id) | int32 |
| `y[i]` | 接收器 sensor mount ID (rx_id) | int32 |
| `z[i]` | 通道 ID (ch_id) | int32 |
| `scalar[i]` | 振幅樣本值 | float32 |
| `timeOffsetNs[i]` | 時間偏移（奈秒，用於 ToF） | float64 |
| `numElements` | 總樣本數 | int |
| `numSamplesPerSgw` | 每個 signal way 的樣本數 | int |
| `timestampNs` | 幀時間戳記（奈秒） | int64 |
| `frameStart.timestampNs` | 幀起始時間戳 | int64 |
| `frameEnd.timestampNs` | 幀結束時間戳 | int64 |
| `modality` | 感測器模態（應為 "ACOUSTIC"） | enum |

### Signal Way（信號路徑）概念

一個 **Signal Way** 是一條「發射器 → 反射面 → 接收器」路徑，由 `(tx_id, rx_id, ch_id)` 唯一識別。每個 signal way 包含 `numSamplesPerSgw` 個振幅樣本，按時間排列。

**本專案的雙接收器設定下：**
- m001（rx=0）：直接接收 + 自發自收
- m002（rx=1）：偏移 10 cm 的接收器（用於橫向能量平衡）

### GMO 驗證（`validate_acoustic_gmo`）

```python
def validate_acoustic_gmo(gmo, np) -> dict:
    n = gmo.numElements
    issues = []
    if n <= 0:
        issues.append("numElements<=0")
    if gmo.numSamplesPerSgw <= 0:
        issues.append("numSamplesPerSgw<=0")
    if n > 0 and n % gmo.numSamplesPerSgw != 0:
        issues.append("numElements not multiple of numSamplesPerSgw")
    if gmo.frameEnd.timestampNs <= gmo.frameStart.timestampNs:
        issues.append("invalid frame timestamps")
    if n > 0:
        scalars = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
        if not np.all(np.isfinite(scalars)):
            issues.append("non-finite scalar samples")
    return {"valid": len(issues)==0, "issues": issues, ...}
```

### Signal Way 解析（`parse_signal_ways`）

```python
def parse_signal_ways(gmo, np) -> list[SignalWayStats]:
    n = gmo.numElements
    tx_ids = np.ctypeslib.as_array(gmo.x, shape=(n,))
    rx_ids = np.ctypeslib.as_array(gmo.y, shape=(n,))
    ch_ids = np.ctypeslib.as_array(gmo.z, shape=(n,))
    amplitudes = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
    time_offsets = np.ctypeslib.as_array(gmo.timeOffsetNs, shape=(n,))

    num_samples_per_sgw = gmo.numSamplesPerSgw
    # 主要路徑：按 stride 分割
    if num_samples_per_sgw > 0 and n % num_samples_per_sgw == 0:
        for sgw_index in range(n // num_samples_per_sgw):
            start = sgw_index * num_samples_per_sgw
            end = start + num_samples_per_sgw
            amps = amplitudes[start:end]
            # 計算每個 signal way 的統計量
            ...
    # Fallback：按 (tx, rx, ch) 分組
    else:
        ...
```

### 每個 Signal Way 的統計量（`SignalWayStats`）

```python
@dataclass(frozen=True)
class SignalWayStats:
    tx_id: int
    rx_id: int
    ch_id: int
    sample_count: int
    peak_amplitude: float    # max(|amplitudes|)，過濾 inf/nan 後
    mean_amplitude: float    # mean(amplitudes)
    std_amplitude: float     # std(amplitudes)
    early_energy: float      # sum(|amplitudes[:count]|)，前 25%
    first_time_offset_ns: float  # timeOffsetNs[0]（第一個樣本的 ToF）
```

### Early Energy 計算

```python
def _early_energy(amplitudes, np, fraction=0.25, min_samples=4) -> float:
    arr = np.abs(np.asarray(amplitudes, dtype=float))
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return nan
    # 取前 25% 樣本（至少 4 個）
    count = max(min_samples, int(ceil(arr.size * fraction)))
    count = min(count, arr.size)
    return float(np.sum(arr[:count]))
```

**Early Energy 物理意義：**
前 25% 時間窗口的振幅總和，主要捕捉**直接路徑回波能量**，減少後期多徑干擾的影響。距離越近，直接路徑能量越強 → early energy 越大。

### Primary / TOF-Primary / Reference Signal Way 選取

```python
# 振幅最大的 signal way（用於能量距離估算）
def _pick_primary_way(ways) -> SignalWayStats:
    return max(ways, key=lambda w: w.peak_amplitude if isfinite(w.peak_amplitude) else -inf)

# 最早到達的 signal way（用於 ToF 距離估算）★ 2026-07-03 新增
def _pick_tof_primary_way(ways) -> SignalWayStats:
    valid = [w for w in ways if isfinite(w.first_time_offset_ns) and w.first_time_offset_ns > 0]
    if not valid:
        return _pick_primary_way(ways)
    return min(valid, key=lambda w: w.first_time_offset_ns)

# 參考 signal way：固定 (tx=0, rx=0, ch=0)，用於跨幀歸一化
def _pick_reference_way(ways) -> SignalWayStats:
    for w in ways:
        if w.key == (0, 0, 0):
            return w
    return _pick_primary_way(ways)   # fallback
```

### 雙接收器橫向統計（`_rx_channel_stats`）

```python
def _rx_channel_stats(ways) -> tuple:
    # 依 rx_id 分組，計算各接收器的平均 early_energy 和 ToF
    rx_energy = {}  # rx_id -> [early_energy]
    rx_tof = {}     # rx_id -> [first_time_offset_ns]
    for w in ways:
        rx_energy.setdefault(w.rx_id, []).append(w.early_energy)
        rx_tof.setdefault(w.rx_id, []).append(w.first_time_offset_ns)

    e0 = mean(rx_energy.get(0, []))   # rx=0 平均能量
    e1 = mean(rx_energy.get(1, []))   # rx=1 平均能量
    t0 = mean(rx_tof.get(0, []))      # rx=0 平均 ToF
    t1 = mean(rx_tof.get(1, []))      # rx=1 平均 ToF

    # 橫向能量平衡：[-1, 1]，0 = 完美對齊
    denom = abs(e0) + abs(e1)
    balance = (e0 - e1) / denom if denom > 1e-9 else 0.0

    # ToF 差異（用於橫向偏移估算）
    tof_delta = t0 - t1

    return e0, e1, t0, t1, balance, tof_delta
```

### 波形早期能量比例（`_waveform_early_fraction`）

```python
def _waveform_early_fraction(gmo, np, fraction=0.25) -> float:
    # 整個 GMO 的前 25% 振幅佔總振幅的比例
    amps = np.abs(np.ctypeslib.as_array(gmo.scalar, shape=(n,)))
    total = sum(amps)
    count = max(4, ceil(amps.size * fraction))
    return float(sum(amps[:count]) / total)
```

**物理意義：** 越接近目標，直接路徑能量佔比越高，比例越大。

### summarize_gmo_frame 完整輸出欄位

| 欄位 | 說明 |
|------|------|
| `timestamp_ns` | 幀時間戳（奈秒） |
| `num_elements` | GMO 總樣本數 |
| `num_signal_ways` | 偵測到的 signal way 數量 |
| `num_samples_per_sgw` | 每個 signal way 的樣本數 |
| `gmo_valid` | 驗證通過？（布林） |
| `gmo_modality` | 應為 "ACOUSTIC" |
| `gmo_validation_issues` | 問題清單（分號分隔） |
| `amplitude_min/max/mean/std` | 全幀振幅統計 |
| `all_sgw_peak_mean` | 所有 signal way 峰值的平均 |
| `all_sgw_peak_std` | 所有 signal way 峰值的標準差 |
| `signal_way_keys` | 所有 (tx,rx,ch) key 列表 |
| `primary_sgw_{tx,rx,ch,peak,mean,early_energy,first_time_offset_ns}` | 振幅最大 way |
| `tof_primary_sgw_{tx,rx,ch,peak,mean,early_energy,first_time_offset_ns}` | 最早到達 way ★新 |
| `ref_sgw_{tx,rx,ch,peak,mean,early_energy,first_time_offset_ns}` | 參考 (0,0,0) way |
| `rx_early_energy_0/1` | 雙接收器各自平均能量 |
| `rx_tof_ns_0/1` | 雙接收器各自平均 ToF |
| `rx_energy_balance` | 能量平衡 (e0-e1)/(e0+e1) |
| `rx_tof_delta_ns` | ToF 差異 t0-t1 |
| `waveform_early_fraction` | 全幀前 25% 能量比例 |

---

## 4. SurfaceGripper API

### Import

```python
from isaacsim.robot.surface_gripper import GripperView, create_surface_gripper
from isaacsim.robot.surface_gripper.bindings._surface_gripper import (
    acquire_surface_gripper_interface,
    GripperStatus,
)
from usd.schema.isaac import robot_schema
```

### 建立步驟（正確版本 — 2026-07-03 修復）

```python
def setup_surface_gripper(stage, ee_path, *, GripperView, create_surface_gripper):
    # Step 1：在 ee_link 下建立 gripper prim（路徑對齊 surface_gripper_path()）
    gripper_prim = create_surface_gripper(stage, ee_path)
    # → 建立於 /World/ur10/ee_link/SurfaceGripper
    path = str(gripper_prim.GetPath())

    # Step 2：建立 attachment point（定義接觸幾何）
    from pxr import Gf, Sdf, UsdPhysics
    from usd.schema.isaac import robot_schema

    joint_path = f"{path}/attachment_point_0"
    joint = UsdPhysics.Joint.Define(stage, joint_path)
    joint.CreateBody0Rel().SetTargets([ee_path])          # ee_link 作為 Body0
    joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.03, 0.0, -0.06))  # 接觸點位置
    joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    robot_schema.ApplyAttachmentPointAPI(joint.GetPrim())
    joint.GetPrim().GetAttribute(robot_schema.Attributes.FORWARD_AXIS.name).Set(UsdPhysics.Tokens.x)
    stage.GetPrimAtPath(path).GetRelationship(
        robot_schema.Relations.ATTACHMENT_POINTS.name
    ).SetTargets([Sdf.Path(joint_path)])

    # Step 3：建立 GripperView 並設定屬性
    view = GripperView(paths=path)
    view.set_surface_gripper_properties(
        max_grip_distance=[0.50],       # 最大夾取距離（m）
        coaxial_force_limit=[5000.0],   # 軸向力限制（N）
        shear_force_limit=[5000.0],     # 剪力限制（N）
        retry_interval=[0.05],          # 重試間隔（s）
    )

    # Step 4：取得底層介面並開啟夾爪
    iface = acquire_surface_gripper_interface()
    iface.open_gripper(path)

    return path, iface, view
```

### 操作方式

```python
# 夾取（值 > 0 = 關閉）
view.apply_gripper_action([0.5])

# 開啟
view.apply_gripper_action([-0.5])

# 查詢狀態
status = view.get_surface_gripper_status()
# 返回：["Open"] / ["Closing"] / ["Closed"]

# 查詢抓到的物件
gripped = view.get_gripped_objects()
```

### 已知問題

**"Gripper not found" 根本原因**（2026-07-03 已修復路徑問題）：
- 舊版：`gripper_parent = "/World"` → 建在 `/World/SurfaceGripper`（與 `surface_gripper_path()` 預期的 `/World/ur10/ee_link/SurfaceGripper` 不符）
- 修復：`create_surface_gripper(stage, ee_path)` → 建在 `/World/ur10/ee_link/SurfaceGripper`

**殘留風險**：C++ plugin 在 PhysX 場景初始化時掃描 gripper prim。若 `setup_surface_gripper` 在 `world.reset()` 之後呼叫，可能仍需手動觸發 scene rebuild。

---

## 5. 場景幾何 Passport 系統

### 設計原則

Passport 系統確保所有腳本使用相同的幾何常數，避免硬寫數字散落各處。

### geometry_passport_v1.py — 基礎場景

| 常數 | 值 | 說明 |
|------|-----|------|
| `ROOM_DIM_M` | (4.5, 3.0, 2.8) m | 房間長×寬×高 |
| `ROOM_CENTER_M` | (2.0, 0.0, 0.0) m | 房間中心 |
| `WALL_THICKNESS_M` | 0.05 m | 牆壁厚度 |
| `ROBOT_PRIM_PATH` | `/World/ur10` | UR10e USD 路徑 |
| `EE_FRAME` | `ee_link` | 末端執行器鏈結名稱 |
| `SENSOR_PRIM_NAME` | `official_rtx_acoustic` | 感測器 prim 名稱 |
| `SENSOR_LOCAL_OFFSET_M` | (0.08, 0.0, 0.0) m | 感測器相對 ee_link 前向偏移 |
| `SENSOR_MOUNT_SPACING_M` | 0.10 m | 雙接收器間距 |
| `CENTER_FREQUENCY_HZ` | 40,000 Hz | 超音波中心頻率 |
| `TICK_RATE_HZ` | 20.0 Hz | 脈衝率 |
| `TCP_RADIUS_M` | 0.80 m | TCP 工作半徑 |
| `TCP_HEIGHT_M` | 0.65 m | TCP 工作高度 |
| `TCP_Y_M` | 0.16 m | TCP Y 偏移 |
| `DISTANCE_WAYPOINTS_M` | (0.5, 1.0, 1.5, 2.0, 2.5, 3.0) m | Phase A 距離點 |
| `DEFAULT_MATERIAL_CONDITION` | "B" | 材質條件（medium absorption） |

### 六面牆房間建立

```python
def create_six_wall_room(Cube, np) -> list[str]:
    # 按 ROOM_DIM_M 和 ROOM_CENTER_M 建立：
    # floor, ceiling, wall_x_min, wall_x_max, wall_y_min, wall_y_max
    # 每面牆是厚度 WALL_THICKNESS_M 的 Cube prim
    return ["/World/room/floor", "/World/room/ceiling", ...]
```

**六面牆的必要性：** RTX Acoustic 需要封閉房間產生正確的多徑反射，模擬真實室內聲學環境。

### grasp_passport_v1.py — 夾取任務幾何

| 常數 | 值 | 說明 |
|------|-----|------|
| `TABLE_TOP_Z_M` | 0.40 m | 工作台高度 |
| `WRENCH_SCALE_M` | (0.18, 0.04, 0.04) m | 目標物（扳手代理）尺寸 |
| `WRENCH_PHYSICS_MASS_KG` | 0.15 kg | 目標物質量 |
| `GRASP_STANDOFF_M` | 0.35 m | 閉環停止距離（感測器到目標） |
| `SEARCH_START_X_M` | 0.55 m（可被 env 覆蓋） | 搜索走廊起點 |
| `SEARCH_END_X_M` | `EE_X_MAX + 0.05` m | 搜索走廊終點（含 +5 cm 走廊 slack） |
| `APPROACH_STEP_M` | 0.04 m | 每步接近距離 |
| `MAX_APPROACH_STEPS` | 40 | 最大接近步數 |
| `LATERAL_ALIGN_STEP_M` | 0.012 m | 橫向對齊步長 |
| `FINAL_APPROACH_STEP_M` | 0.02 m | 最終接近步長 |
| `FINAL_APPROACH_STANDOFF_M` | 0.14 m | 最終接近停止距離 |
| `EE_X_MAX_REACH_M` | 1.28 m | UR10e 末端 X 最大到達 |
| `SENSOR_X_MAX_REACH_M` | `EE_X_MAX + 0.08` = 1.36 m | 感測器最大到達 |

### 目標物隨機生成（`spawn_wrench_position`）

```python
def spawn_wrench_position(trial_id: int, seed: int) -> WrenchSpawn:
    x_min, x_max = wrench_spawn_x_bounds_m()
    span = x_max - x_min
    # LCG（線性同餘偽隨機）
    frac = ((trial_id + 1) * 1103515245 + seed) % 10000 / 10000.0
    x = x_min + span * frac
    return WrenchSpawn(trial_id, seed, wrench_x_m=x, wrench_y_m=WRENCH_Y_M, wrench_z_m=WRENCH_CENTER_Z_M)
```

---

## 6. 實驗設計 — Phase A 特徵可重複性

### 實驗目的

**RQ1：** RTX Acoustic 特徵在固定 TCP 下是否可重現？是否有距離趨勢？

### 場景設定

- 機器手臂：UR10（官方 USD 資產），固定 TCP（hand不動）
- 感測器掛載：`/World/ur10/ee_link/official_rtx_acoustic`
- 房間：六面牆，材質條件 B（medium absorption, α≈0.35）
- 目標物：`/World/fixed_target`（Cube, 8×8×2 cm）

### 實驗協定

- **距離點：** 0.5, 1.0, 1.5, 2.0, 2.5, 3.0 m（6 個）
- **每距離 settle 步數：** 30 步（確保 GMO 穩定）
- **GMO substeps：** 每步擷取 2 次 GMO
- **Repeat 次數：** 5（repeat_001 ~ repeat_005）
- **總 run 數：** 6 距離 × 5 repeats = **30 runs**

```bash
bash scripts/run_phase3_repeatability_and_analysis.sh
# → 執行 run_host_fixed_tcp_repeatability_batch.sh（30 次 Isaac Sim）
# → 執行 extract_fixed_tcp_rtx_features.py（特徵聚合）
# → 執行 run_phase3_rtx_pra_comparison.sh（趨勢圖表）
```

### PASS/FAIL 條件

```text
batch_summary.txt 中：
  pass=30
  fail=0
```

FAIL 條件：任一 run 的 `gmo_valid=False` 或 `num_elements=0`

### 輸出資料

| 層級 | 路徑 | git？ |
|------|------|-------|
| Raw repeat | `runtime/outputs/fixed_tcp_repeatability_v1/` | ❌ |
| 特徵 CSV | `runtime/outputs/phase3_rtx_features/fixed_tcp_repeatability_v1_distance_features.csv` | ❌ |
| Canonical 摘要 | `runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/` | ✅ |

---

## 7. 實驗設計 — Phase B/C 閉環接近與夾取

### 實驗目的

**RQ2：** 閉環超聲特徵能否改善機器手臂到達目標區域的成功率？
**RQ3：** 離線 Physical AI 能否從聲學特徵分類目標接近狀態？

### Canonical 資料集

```text
runtime/outputs/physical_ai_v9_skip_lift_clean/
  trial_dir_count = 49
  step_row_count = 284
  closed_loop trials = 25
  open_loop_baseline trials = 24
```

### 隨機化設定（v8/v9 pipeline）

隨機化目的：打破簡單的 `sensor_x_m` / `sensor_y_m` 位置捷徑，迫使模型真正使用聲學特徵。

```bash
# 環境變數覆蓋（由 run_physical_ai_v8_randomized_pipeline.py 注入）
GRASP_SEARCH_START_X_M   # 搜索起點 X（隨機）
GRASP_SEARCH_START_Y_M   # 搜索起點 Y（隨機）
GRASP_WRENCH_Y_M         # 目標 Y 偏移（隨機）
GRASP_SPAWN_SEED         # 生成種子
```

### 實驗控制

```python
# 控制器（closed-loop）：不讀 target world pose
controller = UltrasonicClosedLoopController(config=ControllerConfig(
    grasp_standoff_m=0.35,
    approach_step_m=0.04,
    max_approach_steps=40,
))

# Baseline（open-loop）：直接讀 oracle target pose
open_loop_pregrasp_ee_position = open_loop_pregrasp_candidates_m(wrench_position)
```

### --skip-lift 設定（contact-only 模式）

```python
# --skip-lift：建立 FixedCuboid（靜態），避免 PhysX lift 不穩定
# --enable-lift：建立 DynamicCuboid（動態），執行真實夾取+提升

# 正確記錄（v9 驗證）：
# Contact-only proxy: wrench=FixedCuboid (GRASP_SKIP_LIFT=1 / --skip-lift; no physics lift)
```

**Bug 歷史（已修復）：** 舊版 headless 模式下 `GRASP_SKIP_LIFT=1` 環境變數存在但 Python 腳本仍建立 `DynamicCuboid`，導致 physics lift 污染資料。v9 改為明確傳入 `--skip-lift` 旗標。

### 成功率定義

| 指標 | 定義 | Closed-loop | Open-loop |
|------|------|-------------|-----------|
| Approach ≤ 0.45 m | 最終感測器到目標距離 ≤ 0.45 m | **84.0%** (21/25) | **29.2%** (7/24) |
| Near ≤ 0.35 m | 最終距離 ≤ 0.35 m（進入 standoff） | **84.0%** (21/25) | **4.2%** (1/24) |
| Final success | 夾取+接觸成功 | 20.0% (5/25) | 20.8% (5/24) |

### 階段化評估框架

```text
Stage 1: 聲學信號擷取（RTX GMO valid）
Stage 2: 閉環接近（controller state machine）
Stage 3: 到達接近區（≤ 0.45 m）← 主要貢獻
Stage 4: 離線 Physical AI 狀態估計
Stage 5: 夾取接觸（← 下游限制，非主貢獻）
```

---

## 8. 閉環控制器狀態機

### 檔案

`scripts/ultrasonic_closed_loop_controller.py`

### 狀態定義（`ControllerState`）

```
INIT → AT_SEARCH_START → APPROACH_STEP → LATERAL_ALIGN → FINAL_APPROACH → AT_STANDOFF
                                                                              ↓
                                                                           DESCEND → GRASP → LIFT → SUCCESS
FAIL（隨時可能發生）
```

### 狀態轉換邏輯

**APPROACH_STEP（主接近）：**
```python
def _approach_decision(self, features):
    distance_m = self._distance_for_control(features)

    # 超過最大步數 → FAIL
    if step_index >= max_approach_steps:
        return FAIL

    # 到達搜索走廊終點
    if sensor_x_m >= search_end_x_m:
        if step_index >= 3 and distance_m <= standoff + 0.10:
            return → LATERAL_ALIGN   # 允許進入對齊
        return FAIL (SEARCH_LIMIT)

    # 到達 standoff
    if step_index >= 3 and distance_m <= grasp_standoff_m:
        return → LATERAL_ALIGN

    # 繼續前進
    step_index += 1
    return APPROACH_STEP
```

**LATERAL_ALIGN（橫向對齊）：**
```python
def _lateral_decision(self, features):
    # 能量平衡在容忍範圍內 → 進入最終接近
    if abs(rx_energy_balance) <= lateral_rx_balance_tolerance:   # 0.12
        return → FINAL_APPROACH

    # 超過最大橫向步數 → 強制進入最終接近
    if lateral_step_index >= max_lateral_align_steps:   # 6
        return → FINAL_APPROACH

    # 繼續橫向移動
    delta_y = -sign(rx_energy_balance) * lateral_align_step_m   # 0.012 m
    return LATERAL_ALIGN
```

**FINAL_APPROACH（最終接近）：**
```python
def _final_approach_decision(self, features):
    distance_m = self._distance_for_control(features)

    # 到達最終 standoff（0.14 m）→ DESCEND
    if distance_m <= final_approach_standoff_m:
        return DESCEND

    # 超過最大步數 → 強制 DESCEND
    if final_step_index >= max_final_approach_steps:   # 8
        return DESCEND

    # 繼續接近（步長 0.02 m）
    return FINAL_APPROACH
```

### 距離選取策略

```python
def _distance_for_control(self, features) -> float:
    # 優先使用融合距離（能量+ToF 加權平均）
    if isfinite(features.fused_distance_m):
        return features.fused_distance_m
    # fallback：只用能量標定表
    return self.calibration.estimate_distance_m(features.early_energy)
```

### 動作輸出

| 方法 | 返回值 | 說明 |
|------|--------|------|
| `should_step_forward()` | bool | 是否執行前進動作 |
| `step_forward_delta_x_m()` | 0.04 m | 前進步長 |
| `should_step_lateral_y()` | bool | 是否執行橫向動作 |
| `step_lateral_delta_y_m()` | ±0.012 m | 橫向步長（方向由 balance 決定） |
| `should_step_final_forward()` | bool | 是否執行最終接近動作 |
| `step_final_forward_delta_x_m()` | 0.02 m | 最終接近步長 |

### Fail 原因（`FailReason`）

| 原因 | 觸發條件 |
|------|---------|
| `NO_GMO` | `gmo_valid=False` |
| `INVALID_FEATURE` | `early_energy` 不是有限值 |
| `MAX_STEPS` | 超過 40 步 |
| `SEARCH_LIMIT` | 到達走廊終點且距離太遠 |
| `LATERAL_LIMIT` | 橫向對齊步數超限（不會 FAIL，繼續前進） |

---

## 9. Approach Supervisor v1 監管邏輯

### 檔案

`scripts/approach_supervisor_v1.py`

### Claim Boundary

> Supervisor 使用 oracle 距離作為安全包絡（`oracle_slack_m=0.12`），**不**用於生成控制動作。控制器只使用 RTX GMO 特徵。

### 監管動作（`SupervisorAction`）

| 動作 | 觸發條件 |
|------|---------|
| `CONTINUE` | 正常繼續 |
| `HOLD` | 等待感測器穩定 |
| `FORCE_STANDOFF` | 到達前向上限且 oracle 距離在容忍範圍 → 強制停止 |
| `WARN_FUSION_SATURATED` | 融合距離飽和（比 oracle 高 >0.20 m）|
| `WARN_REACH_CAP` | 接近 UR10 reach 上限 |

```python
def evaluate(self, obs, features, controller_state, tool0_x_m, wrench_x_m, step_index):
    oracle_m = obs["oracle_distance_m"]
    fused_m = features.fused_distance_m
    max_x = max_tool0_x_before_wrench_center_m(wrench_x_m)
    at_cap = tool0_x_m >= max_x - 0.01   # 到達前向上限

    # 融合飽和判斷
    fusion_saturated = (at_cap and oracle_m <= standoff + 0.08
                        and fused_m > oracle_m + 0.20)

    # Oracle 接近判斷
    oracle_close = oracle_m <= standoff + oracle_slack_m   # 0.35 + 0.12 = 0.47 m

    if at_cap and oracle_close:
        return FORCE_STANDOFF
    if at_cap and fusion_saturated:
        return WARN_FUSION_SATURATED
    return CONTINUE
```

---

## 10. 標定系統 (Calibration)

### 標定來源

從動態接近掃描（`ur10e_dynamic_approach_calibration_v1`）獲得的資料，用 oracle 距離標記。

```text
runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json
```

### 能量標定表（`build_energy_calibration_points`）

**建立方式：**
1. 收集動態接近時所有 `(primary_sgw_early_energy, oracle_distance_m)` 資料對
2. 過濾無效 GMO
3. 依 oracle_distance 降序排列，均勻取 8 個代表點
4. 按 early_energy 降序排列（能量大 = 距離近）
5. 強制單調性（較大能量不能對應較大距離）

**預設值（`DEFAULT_CALIBRATION`，手動標定 trial-9 sweep 2026-06-30）：**

```python
DEFAULT_CALIBRATION = (
    (221.0, 0.85),  # 高能量 = 近距離
    (155.0, 0.72),
    (148.0, 0.65),
    (140.0, 0.50),
    (136.0, 0.40),
    (132.0, 0.30),
    (128.0, 0.25),
    (95.0,  0.22),  # 低能量 = 遠距離
)
```

### TOF 標定表（`build_tof_calibration_points`）

**建立方式：**
1. 過濾 `first_time_offset_ns < 1e5 ns`（無效 ToF）
2. 依 oracle_distance 降序排列，均勻取 8 個點
3. 確保 `tof_ns` 單調遞增（ToF 大 = 距離遠）

**預設值（`DEFAULT_TOF_CALIBRATION`）：**

```python
DEFAULT_TOF_CALIBRATION = (
    (0.72e6, 0.22),  # 720,000 ns → 0.22 m
    (0.80e6, 0.28),
    (0.88e6, 0.35),
    (0.96e6, 0.45),
    (1.04e6, 0.55),
    (1.14e6, 0.65),
    (1.28e6, 0.85),
)
```

---

## 11. 距離估算計算方式

### 能量距離估算（`estimate_distance_from_energy`）

```python
def estimate_distance_from_energy(early_energy, calibration_points) -> float:
    # 對 early_energy（降序 key）做線性插值
    # early_energy 大 → 距離小（反向單調）
    return _interp_monotonic_table(early_energy, calibration_points, ascending_key=False)
```

**原理：** 超音波能量隨距離增加而衰減（近似 1/r² 法則）。early_energy 越大表示距離越近。

### TOF 距離估算（`estimate_distance_from_tof`）

```python
def estimate_distance_from_tof(tof_ns, calibration_points) -> float:
    # 對 tof_ns（升序 key）做線性插值
    # tof_ns 大 → 距離大（正向單調）
    return _interp_monotonic_table(tof_ns, calibration_points, ascending_key=True)
```

**原理：** `distance = speed_of_sound × time / 2`（來回）
空氣中音速 ≈ 343 m/s，ToF 每 1 m 距離 ≈ 2920 μs（2.92×10⁶ ns）

### 線性插值（`_interp_monotonic_table`）

```python
def _interp_monotonic_table(value, points, *, ascending_key) -> float:
    # 對有序 lookup table 做分段線性插值
    # 超出範圍時夾至端點值（不外插）
    for (k_lo, d_lo), (k_hi, d_hi) in zip(ordered, ordered[1:]):
        if k_lo <= value <= k_hi:
            t = (value - k_lo) / (k_hi - k_lo)
            return d_lo + t * (d_hi - d_lo)
```

### 融合距離估算（`fuse_distance_estimates`）

```python
def fuse_distance_estimates(d_energy, d_tof, *, energy_weight=0.72, tof_ns=None) -> float:
    # 加權平均，能量權重 0.72，ToF 權重 0.28
    # ToF 需通過有效性檢查（tof_ns >= 1e5 ns）

    values = []
    if isfinite(d_energy):
        values.append((d_energy, energy_weight))

    tof_usable = isfinite(d_tof) and (tof_ns is None or tof_ns >= 1e5)
    if tof_usable:
        values.append((d_tof, 1.0 - energy_weight))

    denom = sum(w for _, w in values)
    return sum(d * w for d, w in values) / denom
```

**融合權重選擇：**
能量距離的穩定性優於 ToF（在 sim 中），設 `energy_weight=0.72`，ToF 作輔助修正。

### Alignment Score（對齊分數）

```python
alignment_score = (
    early_energy                              # 主信號能量（直接路徑）
    + 0.35 * ref_early_energy                 # 參考 way 加成（跨幀穩定性）
    + 0.20 * peak_amplitude                   # 峰值振幅加成
    - 25.0 * abs(rx_energy_balance)           # 橫向不平衡懲罰
)
```

**意義：** 分數越高表示感測器對準目標越好，越適合進入夾取。

---

## 12. Physical AI 資料集建立

### 檔案

`scripts/build_physical_ai_acoustic_dataset.py`

### 資料來源

每個 trial 目錄下的 `ultrasonic_closed_loop_grasp_history.csv`，每行是一個控制步驟。

### 標籤定義

| 標籤 | 定義 | 閾值 |
|------|------|------|
| `near_label` | oracle 距離是否 ≤ 0.35 m | `near_threshold_m=0.35` |
| `stop_region_label` | oracle 距離是否 ≤ 0.45 m | `stop_threshold_m=0.45` |
| `terminal_step_label` | 是否為 episode 最後一步 | — |
| `episode_success` | 此 trial 最終是否成功 | from summary JSON |

**重要：** 這些標籤使用 **oracle 距離**（地面真實值），只用於**離線訓練評估**，不作為控制器輸入。

### 特徵欄位（19 維）

```python
FEATURE_COLUMNS = [
    # RTX 聲學特徵
    "early_energy",                  # AcousticFeatureFrame.early_energy（primary way）
    "primary_sgw_early_energy",      # 同上（冗餘欄，保留相容性）
    "ref_early_energy",              # 參考 way (0,0,0) early energy
    "tof_ns",                        # primary TOF（奈秒）★ v9後改用最早到達
    "ref_tof_ns",                    # 參考 way TOF
    "peak_amplitude",                # primary way 峰值振幅
    "amplitude_mean",                # 全幀振幅平均
    "amplitude_std",                 # 全幀振幅標準差
    "all_sgw_peak_std",              # 所有 signal way 峰值的標準差
    "rx_energy_balance",             # 雙接收器能量平衡 (e0-e1)/(e0+e1)
    "rx_tof_delta_ns",               # 雙接收器 ToF 差
    "waveform_early_fraction",       # 全幀前 25% 能量占比
    # 推導特徵
    "estimated_distance_energy_m",   # 能量標定表推算距離
    "estimated_distance_tof_m",      # ToF 標定表推算距離
    "fused_distance_m",              # 融合距離（主要控制用）
    "alignment_score",               # 對齊分數（綜合評分）
    # 位姿特徵（幾何資訊）
    "sensor_x_m",                   # 感測器世界 X 座標
    "sensor_y_m",                   # 感測器世界 Y 座標
    "num_signal_ways",               # 偵測到的 signal way 數量
]
```

---

## 13. Physical AI 模型訓練與評估

### 檔案

`scripts/train_physical_ai_acoustic_policy.py`

### 驗證策略：Leave-One-Trial-Out (LOTO)

```python
def leave_one_trial_out(rows, features, label):
    groups = sorted({row["source_dir"] for row in rows})
    for test_group in groups:
        train_rows = [r for r in rows if r["source_dir"] != test_group]
        test_rows  = [r for r in rows if r["source_dir"] == test_group]
        # 在 train 上訓練，在 test 上預測
        # 彙總所有 test 預測 → 整體指標
```

**選擇 LOTO 而非 K-fold 的原因：** 每個 trial 的樣本點高度相關（同一 episode 的連續步驟），若同一 trial 跨 train/test 則洩漏。LOTO 確保完整 trial 不跨集合。

### 模型規格

**Logistic Regression：**
```python
Pipeline([
    ("impute", SimpleImputer(strategy="median")),   # NaN 填補
    ("scale", StandardScaler()),                     # 標準化
    ("model", LogisticRegression(
        class_weight="balanced",   # 處理類別不平衡
        max_iter=2000,
        random_state=0,
    )),
])
```

**Decision Tree（深度 2）：**
```python
Pipeline([
    ("impute", SimpleImputer(strategy="median")),
    ("model", DecisionTreeClassifier(
        max_depth=2,               # 淺層，避免過擬合
        class_weight="balanced",
        min_samples_leaf=3,        # 最小葉節點樣本數
        random_state=0,
    )),
])
```

### 評估指標

```python
def metrics(y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    specificity = tn / (tn + fp)
    recall = tp / (tp + fn)
    return {
        "accuracy":          (tp + tn) / n,
        "balanced_accuracy": (recall + specificity) / 2.0,  # 主要指標
        "precision":         tp / (tp + fp),
        "recall":            recall,            # sensitivity
        "specificity":       specificity,
        "f1":                2*tp / (2*tp + fp + fn),  # 主要指標
    }
```

### 消融實驗（Feature Ablation）設定

| Feature Set | 欄位 | 目的 |
|-------------|------|------|
| `all_features` | 全 19 維 | 上界 |
| `acoustic_only` | 去掉 `sensor_x_m`, `sensor_y_m` | 純聲學訊號是否足夠 |
| `pose_only` | 只保留 `sensor_x_m`, `sensor_y_m` | 幾何資訊的貢獻 |

### Canonical 結果（physical_ai_v9_skip_lift_clean）

| Feature Set | Label | F1 | Balanced Accuracy |
|-------------|-------|----|-------------------|
| all_features | stop_region_label | **0.684** | 0.665 |
| acoustic_only | stop_region_label | **0.598** | 0.590 |
| pose_only | stop_region_label | 0.533 | 0.650 |

**解讀：**
- `acoustic_only > pose_only`（F1 0.598 > 0.533）→ 聲學特徵有獨立信息量
- `all_features > acoustic_only` → 位姿資訊補充聲學特徵
- `pose_only` 的 balanced_accuracy > acoustic_only → 幾何對平衡精度更穩定
- 但 `pose_only` 在 F1 上輸給 `acoustic_only` → 聲學提供更好的 precision/recall 平衡

---

## 14. 特徵提取計算 (Phase A)

### 檔案

`scripts/extract_fixed_tcp_rtx_features.py`

### 流程

1. 讀取所有 `*_timeseries.csv`（30 個 runs）
2. 依 `(repeat_id, material_condition, target_distance_m)` 分組
3. 計算每組的統計量

### 距離組統計量計算

```python
def mean_std_cv(values: list[float]) -> tuple[float, float, float]:
    arr = np.asarray(values)[np.isfinite(values)]
    mean = np.mean(arr)
    std = np.std(arr, ddof=1)    # 樣本標準差（ddof=1）
    cv = std / abs(mean)         # 變異係數（Coefficient of Variation）
    return mean, std, cv
```

**對每個 signal way 指標計算 mean/std/CV：**

| 來源欄位 | 計算欄位 |
|---------|---------|
| `primary_sgw_early_energy` | `_mean`, `_std`, `_cv` |
| `primary_sgw_peak` | `_mean`, `_std`, `_cv` |
| `primary_sgw_first_time_offset_ns` | `_mean`, `_std`, `_cv` |
| `ref_sgw_early_energy` | `_mean`, `_std`, `_cv` |
| `all_sgw_peak_mean` | `_mean`, `_std`, `_cv` |

### 論文主要可重複性指標

- **CV（變異係數）：** `CV = std / mean × 100%` — 越低越可重複
- **30/30 PASS：** 所有 run 的 `gmo_valid=True`
- **結果：** `primary_sgw_early_energy` CV 低（5 次 repeat 間穩定）

---

## 15. Spearman 趨勢分析

### 檔案

`scripts/analyze_fixed_tcp_rtx_pra.py`

### Spearman ρ 計算

```python
from scipy.stats import spearmanr

def spearman(x: list[float], y: list[float]) -> tuple[float, float]:
    result = spearmanr(x, y)
    return float(result.correlation), float(result.pvalue)
```

### 分析的 RTX 特徵 × 距離

```python
RTX_METRICS = [
    "amplitude_max_mean",              # 全幀最大振幅均值
    "amplitude_mean_mean",             # 全幀平均振幅均值
    "primary_sgw_peak_mean",           # primary way 峰值均值
    "primary_sgw_early_energy_mean",   # ★ 主要論文指標
    "ref_sgw_peak_mean",               # 參考 way 峰值均值
    "all_sgw_peak_mean_mean",          # 所有 way 峰值均值的均值
]
```

### 論文主要結果

```
primary_sgw_early_energy vs target_distance_m：
  Spearman ρ ≈ -0.66
  n = 6（距離點）
  方向：負相關（距離越大，early energy 越小）
```

**注意事項：** n=6 的 Spearman 相關統計力道有限（p 值約 0.15），論文中應陳述為「趨勢級可行性」而非「統計顯著相關」。

### 單調性標記

```python
def monotonic_label(rho: float) -> str:
    if abs(rho) < 0.7:  return "non-monotonic"
    if rho > 0:         return "positive"
    return "negative"
```

---

## 16. 材質系統 (RTX NonVisualMaterial)

### 材質條件

| 條件 | 標記 | 吸收係數 α | 說明 |
|------|------|-----------|------|
| A | low_absorption | ~0.10 | 硬牆（強反射） |
| **B** | medium_absorption | **~0.35** | **標準條件（論文主實驗）** |
| C | high_absorption | ~0.60 | 軟材（弱反射） |

### 材質設定方式

使用 Isaac Sim `Acoustic NonVisualMaterial`（非視覺材質，只影響聲學計算）：
```python
# rtx_material_passport_v1.py
apply_room_and_target_materials(stage, condition="B")
```

---

## 17. 檔案結構與腳本清單

### 腳本目錄（`scripts/`）

**核心 Library（被其他腳本 import）：**

| 檔案 | 功能 |
|------|------|
| `rtx_acoustic_factory.py` | RTX GMO 解析、特徵計算、信號路徑分析 |
| `ultrasonic_closed_loop_controller.py` | 閉環狀態機 |
| `approach_supervisor_v1.py` | 接近監管邏輯 |
| `geometry_passport_v1.py` | Phase A/B/C 場景幾何常數 |
| `grasp_passport_v1.py` | 夾取任務幾何常數與標定表 |
| `ur10e_robotiq_common.py` | UR10e+Robotiq 機器人控制 helper |
| `ur10e_robotiq_passport_v1.py` | UR10e IK 設定與常數 |
| `rtx_material_passport_v1.py` | RTX 材質設定 |
| `ultrasonic_grasp_common.py` | Phase C 共用 helper（含 SurfaceGripper setup） |
| `acoustic_calibration_v1.py` | 標定表建立與載入 |
| `grasp_passport_v1.py` | 夾取 Passport（含 WrenchSpawn、距離計算） |

**實驗腳本：**

| 檔案 | 功能 |
|------|------|
| `official_asset_ur10_fixed_tcp_distance_sweep.py` | Phase A：固定 TCP 距離掃描 |
| `official_asset_ur10_ultrasonic_closed_loop_grasp.py` | Phase C：閉環接近+夾取 |
| `run_physical_ai_v8_randomized_pipeline.py` | Phase B/C 批次隨機化管線 |
| `extract_fixed_tcp_rtx_features.py` | Phase A 特徵提取 |
| `analyze_fixed_tcp_rtx_pra.py` | RTX × PRA 趨勢分析 |
| `build_physical_ai_acoustic_dataset.py` | Physical AI 資料集建立 |
| `train_physical_ai_acoustic_policy.py` | 離線模型訓練評估 |
| `acoustic_calibration_v1.py` | 標定表管理 |

**Shell 腳本（`scripts/*.sh`）：**

| 腳本 | 功能 |
|------|------|
| `env_host_isolated.sh` | 環境變數設定 |
| `run_phase3_repeatability_and_analysis.sh` | Phase A 完整流程 |
| `run_host_ultrasonic_closed_loop_grasp_smoke.sh` | Phase C smoke |
| `run_host_open_loop_grasp_baseline_smoke.sh` | Open-loop baseline smoke |
| `run_host_fixed_tcp_repeatability_batch.sh` | 30 次 batch |

### 輸出目錄（`runtime/outputs/`）

| 目錄 | 內容 | git？ |
|------|------|-------|
| `fixed_tcp_repeatability_v1/` | Phase A raw（30 × json+csv） | ❌ |
| `phase3_rtx_features/` | 特徵提取 CSV | ❌ |
| `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/` | **Canonical 摘要** | ✅ |
| `physical_ai_v9_skip_lift_clean/` | Phase B/C 49 trials | ❌ |
| `physical_ai_v9_skip_lift_clean_ablation/` | 消融 CSV | ✅ |
| `ur10e_dynamic_approach_calibration_v1/` | 標定 JSON | ✅ |

---

## 18. Claim Boundary 表

### 可宣稱（論文可寫）

| Claim | 依據 | 量化數字 |
|-------|------|---------|
| RTX 特徵 30/30 可重現 | `batch_summary.txt: pass=30` | 100% |
| `primary_sgw_early_energy` 有距離下降趨勢 | `fixed_tcp_rtx_pra_correlations.csv` | ρ≈−0.66 (n=6) |
| 閉環接近到達率顯著優於 open-loop | `physical_ai_v9` audit | **84% vs 29%** |
| 閉環近距（≤0.35m）顯著優於 open-loop | 同上 | **84% vs 4.2%** |
| acoustic_only 含可測量狀態信號 | ablation CSV | **F1≈0.598** |
| Tier B contact-only 示範 | v9 experiments | 階段化評估框架 |

### 不可宣稱（論文不可寫）

| 不可宣稱 | 原因 |
|----------|------|
| 厘米級部署測距 | 僅趨勢級 feasibility，n=6 距離點 |
| 穩定最終夾取 | ~20% 兩組相近，下游 PhysX 問題 |
| 純超音波端到端夾取（零幾何護欄） | Supervisor 仍用 oracle 安全包絡 |
| 可部署學習控制器 | 離線 baseline only，未 online 閉環 |
| CH201 實機驗證 | 未執行 |
| RTX 與 PRA 波形等價 | 已移出論文主線 |

---

*文件生成時間：2026-07-03*
*對應版本：`physical_ai_v9_skip_lift_clean`、`rtx_acoustic_factory.py v1.0`（含 TOF-primary fix）*
