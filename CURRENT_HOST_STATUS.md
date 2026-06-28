# Host Isaac Sim Current Status

Date: 2026-06-26

Host Isaac Sim 6.0 standalone is installed here. The active research repo is `/home/lab109/song/isaac_acoustic_research`.

Use this thesis-facing official-asset smoke first:

```bash
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_ee_smoke.sh
```

This uses the Isaac Sim 6.0 packaged UR10 asset and places `OmniAcoustic` under `/World/ur10/ee_link/official_rtx_acoustic`. It PASSed on 2026-06-25 with writer GMO data (`num_elements=640`) and target alignment angle `0 deg`.

Current recommended target-placement continuous robot-motion acoustic sweep:

```text
/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_continuous_motion_acoustic_target_x1p6/official_asset_ur10_continuous_motion_acoustic_timeseries.csv
```

Result: PASS on 2026-06-26. Target placement scan selected fixed target `(1.6, 0.16, 0.05)` as the best current safe forward-ish span. Continuous acoustic capture with that target collected 159/160 GMO samples, moved `ee_link` by 1.691826 m, and covered fixed-target distance 0.729489-2.423050 m. This is the strongest current thesis-facing continuous sweep dataset.

GUI command to watch this experiment run:

```bash
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_target_x1p6_gui.sh
```

The continuous capture script now creates a six-surface room by default: `/World/room/floor`, `/World/room/ceiling`, `/World/room/wall_x_min`, `/World/room/wall_x_max`, `/World/room/wall_y_min`, and `/World/room/wall_y_max`. It still creates `/World/fixed_target` as the small visible target marker and keeps the functional `OmniAcoustic` mounted under `/World/ur10/ee_link/official_rtx_acoustic`. A room smoke run PASSed on 2026-06-26 with 12/12 samples and wrote `/home/lab109/song/isaacsim6.0/runtime/scenes/ur10_official_asset_room_smoke.usda`.

Current formal distance-waypoint prototype:

```bash
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_distance_waypoint_gui.sh
```

This runs `/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_distance_waypoint_acoustic_capture.py`. The UR10 base stays fixed, the functional sensor remains under `/World/ur10/ee_link/official_rtx_acoustic`, and a planner selects reachable fixed-base joint waypoints closest to requested distances `0.3, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0 m`. Quick validation PASSed on 2026-06-26 with 30/31 samples, six room surfaces present, and measured distance range `0.692969-2.541782 m`. Out-of-tolerance requested distances were `0.3 m`, `0.5 m`, and `3.0 m`; this is the current gap before claiming a full 0-3 m thesis sweep.

Current IK-based distance-waypoint acoustic prototype:

```bash
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_ik_distance_waypoint_gui.sh
```

This runs `/home/lab109/song/isaacsim6.0/scripts/official_asset_ur10_ik_distance_waypoint_acoustic_capture.py` using Isaac Sim 6.0 `LulaKinematicsSolver`. Dense orientation-constrained validation PASSed on 2026-06-26 for requested distances `0.3, 0.5, 1.0, 1.5, 2.0, 2.5 m`: 14/14 acoustic samples, sensor path `/World/ur10/ee_link/official_rtx_acoustic`, dense IK step `0.20 m`, measured distance range `0.424317-2.517941 m`, `ik_orientation_mode=world_x`, and no out-of-tolerance waypoints under the current 0.20 m tolerance. This is the current best visual/automation prototype. The GUI wrapper now waits 8 seconds before motion and slows each movement sample by 0.08 seconds so the arm movement is visible instead of completing before the user can inspect it. Remaining limitation: it covers the practical `~0.42-2.52 m` range with fixed target x=1.6; full 3.0 m still needs a second target placement, changed geometry, or separate far-range run.

Target placement scan result: `/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_target_placement_scan/official_asset_ur10_target_placement_summary.csv`. Among tested target x values 0.4-2.8 m, x=1.6 gave the widest safe forward-ish span after filtering distance >=0.3 m and angle <=60 deg. Larger target x values can exceed 3 m at the far end but lose the near range; 0.3-3.0 m still needs IK/cartesian path planning or multiple target placements.

Current recommended scan-derived continuous robot-motion acoustic sweep:

```text
/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_continuous_motion_acoustic_scan_path/official_asset_ur10_continuous_motion_acoustic_timeseries.csv
```

Result: PASS on 2026-06-26. A workspace scan found candidate near/far UR10 joint poses, then continuous acoustic capture interpolated between them while `/World/ur10/ee_link/official_rtx_acoustic` stayed active. The scan-derived path captured 119/120 GMO samples, moved `ee_link` by 1.589751 m, and covered fixed-target distance 0.075708-1.636010 m. This is the best current continuous sweep pilot; for thesis analysis, prefer filtering out the unsafe near-field portion below about 0.3 m.

Workspace scan result: `/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_workspace_scan/official_asset_ur10_workspace_scan_summary.json` found raw distance range 0.055010-1.786375 m and forward-ish (angle <= 60 deg) range 0.075708-1.636010 m with the current fixed target. This means 0-3 m is not available under the current target/pose sampling; it needs changed target placement and/or IK/cartesian path planning.

Current recommended continuous robot-motion acoustic pilot:

```bash
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_continuous_motion_acoustic.sh
```

Result: PASS on 2026-06-26. The official UR10 moved continuously by interpolating joint commands from `reach_forward` to `reach_right` while `/World/ur10/ee_link/official_rtx_acoustic` stayed active. Pilot output captured 60/60 GMO samples with `num_elements=640`; ee_link moved 0.403813 m; fixed-target distance ranged from 0.485522 m to 0.585602 m. Output CSV: `/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_continuous_motion_acoustic/official_asset_ur10_continuous_motion_acoustic_timeseries.csv`. This validates continuous capture, but not yet a 0-3 m Cartesian sweep.

Current recommended thesis-facing robot-motion acoustic baseline:

```bash
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_motion_acoustic.sh
```

Result: PASS on 2026-06-26. The official UR10 accepted joint-position commands for 4 poses, `/World/ur10/ee_link` moved by up to 0.777052 m, the functional `OmniAcoustic` remained parented under `/World/ur10/ee_link/official_rtx_acoustic`, and all 4 poses produced GMO acoustic data (`num_elements=640`). Output CSV: `/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_motion_acoustic/official_asset_ur10_motion_acoustic_capture.csv`.

Official UR10 robot-motion probe completed on 2026-06-26:

```bash
/home/lab109/song/isaacsim6.0/scripts/run_host_official_asset_ur10_motion_probe.sh
```

Result: PASS. The official UR10 accepted joint-position commands for 4 poses, and `/World/ur10/ee_link` moved by up to 0.777052 m. Outputs are under `/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_motion_probe/`. This proves the arm is controllable; it is not only a static visual asset.

Full official-asset `ee_link` distance sweep completed on 2026-06-25:

```text
/home/lab109/song/isaacsim6.0/runtime/outputs/ur10_official_asset_ee_sweep_20260625_073310/summary.csv
```

Result: PASS 18/18 over 0.5 m, 1.0 m, 1.5 m, 2.0 m, 2.5 m, and 3.0 m with 3 repeats each. Every run used `/World/ur10/ee_link/official_rtx_acoustic`, reported `num_elements=640`, and had target alignment angle `0 deg`.

The older wrapper `scripts/run_host_ur10_smoke.sh` remains a converted-USD runtime proof, but its sensor is under `wrist_3_link`, not the official `ee_link` end-effector frame. The older host handoff was moved to `/home/lab109/song/abandoned_md/host/`.
