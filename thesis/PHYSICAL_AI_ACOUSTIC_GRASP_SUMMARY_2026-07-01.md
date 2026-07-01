# RTX Acoustic Physical AI Grasp Experiment Summary

Date: 2026-07-01

## 1. Current Thesis Position

The defensible thesis direction is not "stable ultrasonic robotic grasping." The current results support a narrower and stronger claim:

> RTX Acoustic ultrasonic features can support closed-loop robotic approach and pre-grasp state estimation in Isaac Sim. Final grasp/contact execution remains the limiting factor.

Recommended thesis title:

> 基於 RTX Acoustic 超音波感測之機械手臂閉迴路接近控制與 Physical AI 狀態判斷

Possible English title:

> RTX Acoustic-Based Closed-Loop Robotic Approach Control and Physical-AI State Estimation in Isaac Sim

The grasp component should be framed as a downstream evaluation stage, not the primary contribution.

## 2. System Built

The project now contains a complete Isaac Sim pipeline for:

- UR10e + Robotiq 2F-85 official asset loading.
- Wrist-mounted RTX Acoustic sensor.
- Dynamic randomized target spawning.
- Acoustic closed-loop approach.
- Open-loop oracle baseline.
- Contact-only stable proxy mode.
- Offline Physical AI dataset extraction.
- Threshold baselines and machine-learning ablation.
- Trial-level success audit and anomaly reporting.

Important scripts added or modified:

- `scripts/official_asset_ur10_ultrasonic_closed_loop_grasp.py`
- `scripts/ultrasonic_grasp_common.py`
- `scripts/grasp_passport_v1.py`
- `scripts/run_host_ultrasonic_closed_loop_grasp_smoke.sh`
- `scripts/run_host_open_loop_grasp_baseline_smoke.sh`
- `scripts/run_physical_ai_v8_randomized_pipeline.py`
- `scripts/build_physical_ai_acoustic_dataset.py`
- `scripts/train_physical_ai_acoustic_policy.py`

## 3. Key Engineering Fixes

### 3.1 PhysX Instability Isolation

Earlier runs repeatedly showed:

```text
PhysX error: Illegal BroadPhaseUpdateData - non-finite bounds
Invalid PhysX transform detected
```

This was not caused by RTX Acoustic. It was mainly caused by unstable final grasp/contact physics and repeated manipulation of articulated/non-root links.

A major bug was found:

- The wrapper printed `GRASP_SKIP_LIFT=1`.
- But in headless mode the main script still created `DynamicCuboid`.
- This meant the supposedly contact-only experiments were still entering the physics-lift path.

Fix applied:

- Added explicit `--skip-lift` and `--enable-lift`.
- `--skip-lift` now creates `FixedCuboid` in both GUI and headless modes.
- Wrappers now pass the explicit flag instead of relying only on environment variables.

Verified log:

```text
Contact-only proxy: wrench=FixedCuboid (GRASP_SKIP_LIFT=1 / --skip-lift; no physics lift)
```

This made the contact-only dataset cleaner and reduced contamination from unstable lift physics.

### 3.2 Randomized Dataset Pipeline

The v8/v9 pipeline randomizes:

- Search start X.
- Search start Y.
- Target Y.
- Trial IDs and seeds by config.

Purpose:

- Break the simple `sensor_x_m` / `sensor_y_m` shortcut.
- Test whether acoustic features still provide state information under randomized geometry.

## 4. Main Experimental Results

The most useful run is:

```text
runtime/outputs/physical_ai_v9_skip_lift_clean
```

Dataset:

```text
trial_dir_count = 49
step_row_count = 284
closed_loop trials = 25
open_loop_baseline trials = 24
```

### 4.1 Approach Success

Stage-level audit:

```text
closed_loop:
  approach <= 0.45 m: 21/25 = 84.0%
  near <= 0.35 m:     21/25 = 84.0%
  final success:       5/25 = 20.0%

open_loop_baseline:
  approach <= 0.45 m: 7/24 = 29.2%
  near <= 0.35 m:     1/24 = 4.2%
  final success:       5/24 = 20.8%
```

Interpretation:

- Closed-loop acoustic approach substantially improves reaching the target region.
- Final grasp success does not improve because downstream contact/gripper execution is still weak.
- Therefore the strongest claim is about approach-zone arrival, not final grasp.

### 4.2 Physical AI Ablation Results

From:

```text
runtime/outputs/physical_ai_v9_skip_lift_clean_ablation/feature_ablation_summary.csv
```

Important metrics:

```text
all_features, stop_region_label:
  F1 = 0.684
  balanced_accuracy = 0.665

acoustic_only, stop_region_label:
  F1 = 0.598
  balanced_accuracy = 0.590

pose_only, stop_region_label:
  F1 = 0.533
  balanced_accuracy = 0.650
```

Interpretation:

- Acoustic-only features contain measurable signal.
- Pose-only remains a confound.
- All-features performs best overall.
- Current results support "offline Physical AI state/action dataset and policy baseline," not a deployable learned controller yet.

### 4.3 Threshold Baseline

The best simple threshold rules were weak for `near_label`:

```text
top threshold near_label:
  feature = amplitude_mean
  F1 approximately 0.50
  precision low, recall high
```

Interpretation:

- Single acoustic scalar thresholds are insufficient.
- Multi-feature policy or temporal filtering is needed.

## 5. SurfaceGripper Attempt

Question investigated:

> Can an official-style Isaac Sim SurfaceGripper provide a stable final grasp baseline?

Changes attempted:

- Added `--final-gripper surface`.
- Created SurfaceGripper prim.
- Added attachment point.
- Tried parent under `ee_link`.
- Tried parent under `wrist_3_link`.
- Tried world-root `/World/SurfaceGripper`.
- Switched from low-level `iface.close_gripper()` to official `GripperView.apply_gripper_action([0.5])`.
- Increased `max_grip_distance` for diagnosis.

Observed issue:

```text
[isaacsim.robot.surface_gripper.plugin] Gripper not found: /World/SurfaceGripper
```

Conclusion:

- The SurfaceGripper USD prim can be created.
- But the SurfaceGripper runtime manager does not register it correctly in the current UR10e + Robotiq scene flow.
- This is an integration issue with Isaac Sim SurfaceGripper runtime registration, not an RTX Acoustic issue.

Current SurfaceGripper status:

- Not ready for thesis result table.
- Can be mentioned only as an attempted official baseline.
- Next step should be an isolated official SurfaceGripper smoke test before integrating it back into UR10.

## 6. What Can Be Claimed

Strong claim:

> Acoustic-guided closed-loop control substantially improved target-region approach under randomized target poses compared with an open-loop baseline.

Supported by:

```text
closed_loop approach <= 0.45 m: 84.0%
open_loop approach <= 0.45 m:   29.2%
```

Moderate claim:

> Acoustic features provide measurable state information for stop-region classification under randomized simulation conditions.

Supported by:

```text
acoustic_only stop_region_label F1 = 0.598
```

Weak / not yet defensible claim:

> The system achieves stable final grasping.

This should not be claimed. Final success remains about 20%.

## 7. Recommended Thesis Framing

Use a staged evaluation:

1. Acoustic signal acquisition.
2. Closed-loop approach.
3. Approach-zone arrival.
4. Offline Physical AI state estimation.
5. Final grasp/contact as limitation.

Suggested result table:

| Metric | Closed-loop | Open-loop |
|---|---:|---:|
| Approach <= 0.45 m | 84.0% | 29.2% |
| Near <= 0.35 m | 84.0% | 4.2% |
| Final success | 20.0% | 20.8% |

Suggested ablation table:

| Feature Set | Label | F1 | Balanced Accuracy |
|---|---|---:|---:|
| All features | stop_region | 0.684 | 0.665 |
| Acoustic only | stop_region | 0.598 | 0.590 |
| Pose only | stop_region | 0.533 | 0.650 |

## 8. Limitations

Current limitations:

- Final grasp/contact stage is unstable.
- Robotiq articulated contact physics can still trigger non-finite PhysX states when true lift is enabled.
- SurfaceGripper is not yet integrated successfully.
- Current learned policy is offline only.
- Some oracle information is used for safety/supervision in scaffold mode.
- Acoustic-only mode remains weaker and needs more randomized data.

## 9. Next Technical Steps

Priority order:

1. Keep v9 as the clean pilot dataset.
2. Do not rerun random batches blindly.
3. Add an isolated official SurfaceGripper smoke test:
   - no UR10;
   - simple moving parent;
   - dynamic cube;
   - verify `GripperView.get_surface_gripper_status()` becomes `Closed`;
   - verify `get_gripped_objects()` returns cube path.
4. If isolated SurfaceGripper works, integrate it back into UR10.
5. If SurfaceGripper remains unreliable, keep final grasp as a limitation and focus thesis on approach/state estimation.
6. Expand randomized data only after final evaluation metrics are separated into:
   - approach success;
   - contact success;
   - lift success;
   - policy prediction performance.

## 10. Bottom Line

The project is thesis-usable if framed correctly.

The result is not:

> We built a fully successful ultrasonic grasping robot.

The result is:

> We built an RTX Acoustic-based closed-loop robotic approach and Physical AI state-estimation pipeline, demonstrated strong improvement in approach-zone arrival under randomized target poses, and identified final contact/grasp execution as the primary remaining bottleneck.

