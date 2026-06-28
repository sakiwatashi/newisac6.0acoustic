# Experiment 4 PyRoomAcoustics Reference Report

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: run
- Verification Status: GENERATED
- Version Label: exp_result_v1

## Scope

This batch provides an interpretable PyRoomAcoustics RIR/RT60 reference under a documented shared geometry. It is not ground truth for RTX Acoustic.

## Outputs

- `/home/lab109/song/isaacsim6.0/runtime/outputs/phase3_material_sensitivity_sgw/pra_cond_C/pra_reference_features.csv`

## Configuration

- external backend path: `/home/lab109/下載/ai-pyroomacoustics-main/backend/server.py`
- geometry policy: `formal_ur10_fixed_tcp_reference_cond_C`
- room dim: `4.5x3x2.8`
- mic position: `[0.8, 0.16, 0.65]`
- absorption: `high_absorption` = `0.7`
- geometry note: the default 4.5 m x-dimension keeps the formal UR10 RTX receiver at x=1.08 m and the 3.0 m target inside the room; rerun with `--room-dim` and `--mic-position` for a strict 4.0 m proposal geometry.

## Rows

| Distance m | RIR abs peak | RIR peak index | Direct delay samples | RT60 | Early energy 50 ms |
|---:|---:|---:|---:|---:|---:|
| 0.5 | 1.96655153 | 180 | 140 | 0.108190868 | 5.11632692 |
| 1 | 0.953057273 | 320 | 280 | 0.112212359 | 1.50724331 |
| 1.5 | 0.60650816 | 460 | 420 | 0.114326896 | 0.745018417 |
| 2 | 0.442481146 | 600 | 560 | 0.116535176 | 0.479571093 |
| 2.5 | 0.319210944 | 740 | 700 | 0.11920032 | 0.345141118 |
| 3 | 0.267276898 | 880 | 840 | 0.120540839 | 0.282430306 |
