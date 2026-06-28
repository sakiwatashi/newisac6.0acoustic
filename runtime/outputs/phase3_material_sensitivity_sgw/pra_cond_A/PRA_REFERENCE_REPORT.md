# Experiment 4 PyRoomAcoustics Reference Report

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: run
- Verification Status: GENERATED
- Version Label: exp_result_v1

## Scope

This batch provides an interpretable PyRoomAcoustics RIR/RT60 reference under a documented shared geometry. It is not ground truth for RTX Acoustic.

## Outputs

- `/home/lab109/song/isaacsim6.0/runtime/outputs/phase3_material_sensitivity_sgw/pra_cond_A/pra_reference_features.csv`

## Configuration

- external backend path: `/home/lab109/下載/ai-pyroomacoustics-main/backend/server.py`
- geometry policy: `formal_ur10_fixed_tcp_reference_cond_A`
- room dim: `4.5x3x2.8`
- mic position: `[0.8, 0.16, 0.65]`
- absorption: `low_absorption` = `0.1`
- geometry note: the default 4.5 m x-dimension keeps the formal UR10 RTX receiver at x=1.08 m and the 3.0 m target inside the room; rerun with `--room-dim` and `--mic-position` for a strict 4.0 m proposal geometry.

## Rows

| Distance m | RIR abs peak | RIR peak index | Direct delay samples | RT60 | Early energy 50 ms |
|---:|---:|---:|---:|---:|---:|
| 0.5 | 1.96512413 | 180 | 140 | 0.867717896 | 10.6480528 |
| 1 | 0.947796991 | 320 | 280 | 0.882514598 | 6.0405619 |
| 1.5 | 0.598144047 | 460 | 420 | 0.88211432 | 4.52107344 |
| 2 | 0.442403591 | 600 | 560 | 0.890048529 | 4.19631133 |
| 2.5 | 0.413687571 | 2441 | 700 | 0.919560921 | 3.80922477 |
| 3 | 0.292328847 | 4109 | 840 | 0.914288677 | 3.51415116 |
