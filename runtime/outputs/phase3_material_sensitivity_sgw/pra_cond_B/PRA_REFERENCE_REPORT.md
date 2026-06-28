# Experiment 4 PyRoomAcoustics Reference Report

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: run
- Verification Status: GENERATED
- Version Label: exp_result_v1

## Scope

This batch provides an interpretable PyRoomAcoustics RIR/RT60 reference under a documented shared geometry. It is not ground truth for RTX Acoustic.

## Outputs

- `/home/lab109/song/isaacsim6.0/runtime/outputs/phase3_material_sensitivity_sgw/pra_cond_B/pra_reference_features.csv`

## Configuration

- external backend path: `/home/lab109/下載/ai-pyroomacoustics-main/backend/server.py`
- geometry policy: `formal_ur10_fixed_tcp_reference_cond_B`
- room dim: `4.5x3x2.8`
- mic position: `[0.8, 0.16, 0.65]`
- absorption: `medium_absorption` = `0.35`
- geometry note: the default 4.5 m x-dimension keeps the formal UR10 RTX receiver at x=1.08 m and the 3.0 m target inside the room; rerun with `--room-dim` and `--mic-position` for a strict 4.0 m proposal geometry.

## Rows

| Distance m | RIR abs peak | RIR peak index | Direct delay samples | RT60 | Early energy 50 ms |
|---:|---:|---:|---:|---:|---:|
| 0.5 | 1.96599607 | 180 | 140 | 0.20978151 | 7.3126822 |
| 1 | 0.950090035 | 320 | 280 | 0.205109077 | 2.98271812 |
| 1.5 | 0.601598356 | 460 | 420 | 0.205622668 | 1.85568585 |
| 2 | 0.442989801 | 600 | 560 | 0.218900556 | 1.49934545 |
| 2.5 | 0.312663811 | 740 | 700 | 0.219325789 | 1.29511126 |
| 3 | 0.27132087 | 880 | 840 | 0.220873214 | 1.14311596 |
