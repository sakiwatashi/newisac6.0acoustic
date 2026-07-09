# Session Summary — 2026-07-08
# Isaac Sim 6.0 閉環抓取 Phase C：SurfaceGripper 死路 + Robotiq 解法確認

---

## 1. 本 Session 的目標

接續 approach_sweep_v4（接近成功率 30/30 = 100%）的成果，進入 **Phase C**：

- 執行 `run_closed_loop_grasp_sweep.sh`（grasp_sweep_v3，30 episodes）
- 使用 SurfaceGripper 做物理夾持 + 升舉
- 目標：grasp success > 0%，確認閉環接近 → 夾取管線全通

---

## 2. 執行環境

```
Script:    scripts/official_asset_ur10_ultrasonic_closed_loop_grasp.py
Sweep:     runtime/run_closed_loop_grasp_sweep.sh
Output:    runtime/outputs/grasp_sweep_v3/
Robot:     UR10e + Robotiq 2F-85 (Isaac/Robots/UniversalRobots/ur10e/ur10e.usd)
Gripper:   --final-gripper surface (SurfaceGripper)
Episodes:  30 (trial_id 0–29)
Claim:     acoustic_only（無 oracle 輔助控制）
```

---

## 3. 遭遇的所有問題、錯誤、修復嘗試（按時間順序）

### 問題 A：`Gripper not found: /World/ur10/wrist_3_link/SurfaceGripper`

**錯誤訊息**：
```
[Error] [isaacsim.robot.surface_gripper] Gripper not found: /World/ur10/wrist_3_link/SurfaceGripper
```

**根本原因**：`ultrasonic_grasp_common.py` 的 `setup_surface_gripper()` 被呼叫時傳入了 `sensor_mount_path`（wrist_3_link）而不是 `ee_path`（ee_link）。SurfaceGripper 被建立在 `/World/ur10/wrist_3_link/SurfaceGripper`，但 SurfaceGripper C++ 插件在內部期待的是 ee_link 路徑。

**修復**：改成傳 `ee_path` → Gripper 路徑變為 `/World/ur10/ee_link/SurfaceGripper`。

**結果**：錯誤訊息路徑改了，但仍 `Gripper not found`。

---

### 問題 B：`Gripper not found: /World/ur10/ee_link/SurfaceGripper`（仍然）

**根本原因**（深層）：SurfaceGripper 的 C++ 插件（`omni.physx.surface_gripper`）**只在 `world.reset()` 時掃描並登記** stage 上的 SurfaceGripper prim。`setup_surface_gripper()` 在 `world.reset()` 之後才被呼叫，所以 C++ 插件對新建立的 prim 一無所知。

**修復嘗試 1**：在 `setup_surface_gripper()` 之後再呼叫一次 `world.reset()`，讓插件重新掃描。

**結果**：引發新的崩潰 → 問題 C。

---

### 問題 C：`ValueError: current_arm_q contains non-finite joint values: [nan nan nan nan nan nan]`

**錯誤訊息**：
```
ValueError: current_arm_q contains non-finite joint values: [nan nan nan nan nan nan]
```

**根本原因**：第二次 `world.reset()` 把機械臂重置到「未初始化」狀態（所有 joint = 0 或 NaN），而 `bootstrap_arm_after_world_reset()` 只在第一次 `world.reset()` 後被呼叫，第二次之後沒有再呼叫。IK 讀到 NaN joint 就炸了。

**修復**：放棄「reset 後呼叫 setup」策略。改用 **pre-creation 策略**：在 `World()` 建立之前就把 SurfaceGripper prim 寫進 stage。

---

### 問題 D：`UnboundLocalError: cannot access local variable 'final_gripper'`

**錯誤訊息**：
```
UnboundLocalError: cannot access local variable 'final_gripper'
```

**根本原因**：Pre-creation 程式碼被插在 `main()` 函式的早期，但 `final_gripper = str(args.final_gripper)` 這行在函式後面才執行（line ~478）。Pre-creation block 用了尚未賦值的 `final_gripper` 變數。

**修復**：改用 `str(args.final_gripper)` 直接讀 argparse namespace，不依賴後面的變數賦值。

---

### 問題 E：`PhysicsUSD: CreateJoint - no bodies defined at body0 and body1`

**錯誤訊息**：
```
[Warning] [omni.physx.plugin] PhysicsUSD: CreateJoint - no bodies defined at body0 and body1
```

**根本原因**：SurfaceGripper 的 C++ 插件需要一個 `IsaacAttachmentPointAPI` joint 來定義「吸附點」。這個 joint 的 `body0` 必須是一個 PhysX **standalone rigid body**（有 `UsdPhysics.RigidBodyAPI`）。

問題在於：
1. `ee_link` 是 articulation 的一個 link，不是 standalone rigid body，PhysX 拒絕它作為 joint body。
2. Attachment joint 建立時機在 `world.reset()` 之後，PhysX 不理會後來才建立的 joint。

**修復嘗試**：在 `World()` 建立前（甚至在 `world.reset()` 前）就建立 attachment joint，並用 `wrist_3_link` 作為 `body0`，加上 `physics:excludeFromArticulation = true`（讓 PhysX 把這個 joint 當成 standalone constraint，不歸入 articulation 管理）。

**程式碼（插在 `world = World()` 之前）**：
```python
_pre_sg_path = ""
if str(args.final_gripper) == "surface":
    from isaacsim.robot.surface_gripper import create_surface_gripper as _pre_csg
    from pxr import Gf, Sdf, UsdPhysics
    from usd.schema.isaac import robot_schema as _pre_rs
    _pre_ee = resolve_ee_path(robot_path, stage)
    _pre_mount = resolve_sensor_mount_path(robot_path, stage)  # wrist_3_link
    _pre_sg_prim = _pre_csg(stage, _pre_ee)
    _pre_sg_path = str(_pre_sg_prim.GetPath())
    try:
        _joint_path = f"{_pre_sg_path}/attachment_point_0"
        _joint = UsdPhysics.Joint.Define(stage, _joint_path)
        _joint.CreateBody0Rel().SetTargets([_pre_mount])
        _joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.03, 0.0, -0.06))
        _joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        _joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        _joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        _pre_rs.ApplyAttachmentPointAPI(_joint.GetPrim())
        _joint.GetPrim().GetAttribute(_pre_rs.Attributes.FORWARD_AXIS.name).Set(UsdPhysics.Tokens.x)
        _joint.GetPrim().CreateAttribute(
            "physics:excludeFromArticulation", Sdf.ValueTypeNames.Bool, True
        ).Set(True)
        _pre_sg_prim.GetRelationship(_pre_rs.Relations.ATTACHMENT_POINTS.name).SetTargets(
            [Sdf.Path(_joint_path)]
        )
    except Exception as _pre_exc:
        print(f"SurfaceGripper pre-setup failed: {_pre_exc}", flush=True)
```

**結果**：`no bodies defined` 警告消失。C++ 插件不再說 "Gripper not found"。但 30 episodes 全部 `grasp_contact_failed`。

---

### 問題 F：30/30 `grasp_contact_failed`（SurfaceGripper 不吸）

**現象**：插件已登記，attachment joint 已建立，但 `gripper_view.get_gripped_objects()` 永遠回傳空列表。`apply_gripper_action([0.5])` 觸發 "Closing" 狀態，但實際上沒有 attach 到任何物體。

**可能原因（未完全診斷）**：
1. `apply_gripper_action([0.5])` 可能不夠強——官方測試用 `[1.0]`。
2. Attachment joint 的幾何參數（`localPos0`、`forwardAxis`）可能對不到夾爪實際接觸面。
3. 物理模擬中 SurfaceGripper 的 proximity zone 可能沒有覆蓋到 wrench 表面。

**解決**：**尚未解決**。卡太久，用戶決定停止 SurfaceGripper 方向。

---

## 4. 最終關鍵發現（本 Session 最重要的結論）

### 研究官方範例後的發現

查閱：
- `app/standalone_examples/tutorials/manipulation/tutorial_9_pick_place_pink.py`
- `app/standalone_examples/tutorials/manipulation/tutorial_9_gripper_control.py`
- `scripts/ur10e_robotiq_common.py`
- `scripts/official_asset_ur10_ultrasonic_closed_loop_grasp.py`

**結論：Robotiq 2F-85 物理夾爪一直都在，從來不需要 SurfaceGripper。**

### 官方推薦做法（tutorial_9_pick_place_pink.py）

```python
_GRIPPER_JOINT = "finger_joint"
_CLOSED_POS: float = 0.5  # radians

finger_idx = dof_names.index("finger_joint")
articulation.set_dof_position_targets(
    wp.array([0.5], dtype=wp.float32), dof_indices=[finger_idx]
)
```

純 DOF position target 控制，完全無需 SurfaceGripper。

### 我們的 codebase 已有完全對應的實作

`ur10e_robotiq_common.py` 的 `RobotiqGripperRuntime` 已實作相同邏輯：
- `close(robot, world)` → 平滑 ramp 關閉 finger_joint
- `hold_closed(robot, world)` → 升舉時保持夾力
- `open(robot, world)` → 開啟

### grasp script 的兩條路徑

`official_asset_ur10_ultrasonic_closed_loop_grasp.py` 內部有兩條路徑：

```python
# 預設路徑（Robotiq finger joints）— 已完整實作
robotiq_gripper = initialize_ur10e_manipulator(robot, world, ...)

if final_gripper == "surface":    # 只有 --final-gripper surface 才走這條
    ...setup SurfaceGripper...
    robotiq_gripper = None        # 放棄 Robotiq！改用 SurfaceGripper
else:
    print(f"Robotiq finger joints: {robotiq_gripper.finger_joint_names}")
```

**結論**：過去整個 session 卡住的原因是 sweep 腳本傳了 `--final-gripper surface`，強制走 SurfaceGripper 路徑，而這條路徑無法工作。Robotiq 路徑（預設）一直存在且已完整實作。

---

## 5. 修改過的檔案

### `scripts/official_asset_ur10_ultrasonic_closed_loop_grasp.py`

以下修改都已寫入（**但這些修改最終被確認為多餘**，因為 Robotiq 才是正確路徑）：

1. `sensor_mount_path` → `ee_path` 傳給 `setup_surface_gripper()`（Fix A）
2. 加入 pre-creation block（在 `World()` 前建立 SurfaceGripper prim + attachment joint）
3. attachment joint body0 改用 `wrist_3_link` + `excludeFromArticulation=true`

這些修改讓 `--final-gripper surface` 模式不再崩潰，但 SurfaceGripper 仍無法實際夾取。

### `scripts/ultrasonic_grasp_common.py`

1. `setup_surface_gripper()` 加入「偵測已存在的 prim 就跳過建立」邏輯：
   ```python
   _expected = f"{ee_path}/SurfaceGripper"
   if stage.GetPrimAtPath(_expected):
       gripper_prim = stage.GetPrimAtPath(_expected)
   else:
       gripper_prim = create_surface_gripper(stage, ee_path)
   ```
2. attachment point 建立也加了「已存在就略過」的判斷。

---

## 6. 未修改、尚未動的部分

`runtime/run_closed_loop_grasp_sweep.sh` — **尚未修改**。仍帶有 `--final-gripper surface`。

---

## 7. 下一步 AI 需要做的事

### 立即可執行的修復（最簡單、最有效）

**修改 `runtime/run_closed_loop_grasp_sweep.sh`**，移除 `--final-gripper surface` 這行：

```bash
# 舊（不工作）：
$ISAACSIM "$SCRIPT" \
    ...
    --final-gripper surface \
    --enable-lift \
    ...

# 新（改用 Robotiq finger joints）：
$ISAACSIM "$SCRIPT" \
    ...
    --enable-lift \       # 保留升舉
    ...                   # 不傳 --final-gripper surface
```

不傳 `--final-gripper surface` → 預設走 Robotiq 路徑 → `runtime.robotiq_gripper` 有效 → `robotiq_gripper.close()` 用 finger_joint 夾取。

### 驗證方式

執行後查看 `runtime/outputs/grasp_sweep_v3/episodes_summary.json`，成功的 episode 應該有：
- `terminal_reason: "grasp_contact_success"` 或 `"grasp_lift_success"`
- `success: true`

注意：`_fingers_near_closed()` 的判斷依賴 `finger_joint` 到達 `ROBOTIQ_FINGER_PHYSICS_CLOSE_RAD = 0.52` rad。同時 `_tool0_grasp_geometry_ok()` 要求 tool0 位置在 wrench 上方正確範圍內。

### 若夾取成功率仍低的可能原因

1. `GRASP_FINGER_PHYSICS_CONTROL` 環境變數：預設為 `False`，手指用 kinematic 控制（不走 PD force）。若 wrench 是 dynamic rigid body，kinematic 手指不會施加接觸力，可能推開 wrench 而不是夾住。可嘗試：
   ```bash
   export GRASP_FINGER_PHYSICS_CONTROL=1
   ```
2. wrench 摩擦力：`apply_wrench_physics_material()` 預設摩擦係數。升舉時可調高。
3. 接近精度：如果 tool0 對不準 wrench 中心，`_tool0_grasp_geometry_ok()` 會判失敗。

---

## 8. 架構速查（給下一個 AI 的 codebase 地圖）

```
scripts/
  official_asset_ur10_ultrasonic_closed_loop_grasp.py   # 主 sweep 腳本
  ultrasonic_grasp_common.py                            # 接近+夾取邏輯（execute_grasp_and_lift 在這）
  ur10e_robotiq_common.py                               # spawn_ur10e_robotiq, RobotiqGripperRuntime
  ur10e_robotiq_passport_v1.py                          # 常數：ROBOT_USD_REL, finger close rad 等
  ultrasonic_closed_loop_controller.py                  # 聲學閉環控制器 state machine
  grasp_passport_v1.py                                  # 場景幾何常數
  rtx_acoustic_factory.py                               # GMO 解析、AcousticFeatureFrame
  acoustic_calibration_v1.py                            # Tier-B 能量校正表

runtime/
  run_closed_loop_grasp_sweep.sh    # Phase C sweep（需修改）
  run_closed_loop_approach_sweep.sh # Phase B sweep（已通過，勿動）
  outputs/
    approach_sweep_v4/              # 接近 30/30=100% 的結果
    grasp_sweep_v3/                 # Phase C 結果（目前全 grasp_contact_failed）
```

### GraspRuntime 的關鍵欄位

```python
@dataclass
class GraspRuntime:
    robotiq_gripper: RobotiqGripperRuntime | None   # Robotiq 路徑（預設）
    gripper_iface: Any | None                        # SurfaceGripper 低階介面
    gripper_view: GripperView | None                 # SurfaceGripper 高階介面
    skip_lift: bool                                  # True = 只測接觸，False = 做升舉
    grasp_contact_only: bool                         # = skip_lift
```

在 `execute_grasp_and_lift()` 的夾取判斷：
```python
if runtime.robotiq_gripper is not None:
    # Robotiq 路徑：用 finger_joint 夾
    runtime.robotiq_gripper.close(...)
    gripped = _fingers_near_closed(runtime)

elif runtime.gripper_iface is not None or runtime.gripper_view is not None:
    # SurfaceGripper 路徑（不工作）
    runtime.gripper_view.apply_gripper_action([0.5])
    ...
```

---

## 9. 本 Session 結論

| 項目 | 狀態 |
|------|------|
| approach_sweep_v4（接近 30/30）| 已完成（上一 session）|
| SurfaceGripper C++ 插件登記 | 修到不再 crash，但吸取仍失敗 |
| grasp_sweep_v3 grasp success | 0/30（全 grasp_contact_failed）|
| 真正解法確認 | Robotiq finger joints（已有實作，只需移除 --final-gripper surface）|
| 修改 sweep 腳本 | **尚未執行** |
| 重跑 grasp_sweep_v3（Robotiq 版）| **尚未執行** |

**下一 AI 的第一件事**：閱讀 `runtime/run_closed_loop_grasp_sweep.sh`，移除 `--final-gripper surface` 那行，重跑 30 episodes，確認 grasp success > 0%。
