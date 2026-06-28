# Citation Bank（論文用 · 待補 DOI/頁碼）

**格式目標：** 逢甲 fcuformat APA；英文 A–Z、中文筆劃  
**狀態：** 占位引用；口試前逐條核對官方文件版本號

---

## 軟體與平台（必引）

| Key | 建議引用 | 用途 |
|-----|----------|------|
| `isaac_sim_60` | NVIDIA Isaac Sim 6.0 Documentation / Release Notes | RTX Acoustic、SimulationApp |
| `isaac_lab` | NVIDIA Isaac Lab v3.0.0-beta2 docs | DirectRLEnv、AppLauncher |
| `rsl_rl` | RSL-RL library (rsl-rl-lib 5.x) | PPO 實作 |
| `ur10_official` | Universal Robots UR10 + Isaac Sim robot asset | 機器人模型 |
| `omniverse_rtx` | NVIDIA Omniverse RTX / RTX Sensor docs | 感測渲染語境 |

## 機器人非視覺感測

| Key | 主題 | 備註 |
|-----|------|------|
| `robot_sonar_review` | 機器人超音波測距綜述 | §2.1 占位 |
| `tof_robot` | ToF 於機器人感知 | §2.1 占位 |
| `sensor_fusion_nonvisual` | 非視覺與視覺互補 | §2.1 占位 |

## Sim-to-Real / 數位雙生

| Key | 主題 | 備註 |
|-----|------|------|
| `sim2real_survey` | 模擬到實機遷移綜述 | §2.2 |
| `domain_gap_robot` | 領域差距與任務級驗證 | claim boundary |
| `isaac_sim_robot_learning` | Isaac 生態之機器人學習案例 | §2.2 |

## 房間聲學與模擬

| Key | 主題 | 備註 |
|-----|------|------|
| `pyroomacoustics` | PyRoomAcoustics 套件文獻 | §2.5、§3.8 |
| `room_acoustics_multipath` | 多徑與早期能量 | §2.3 |
| `rir_early_energy` | RIR 早期能量定義 | 對齊本研究特徵 |

## 強化學習（Phase 5）

| Key | 主題 | 備註 |
|-----|------|------|
| `ppo_schulman` | PPO 原始論文 | §3.10 |
| `rl_robot_sim` | 模擬器中機器人 RL | §2.2 / §5.2 |

---

## BibTeX 占位（LaTeX 若需要）

```bibtex
@misc{isaac_sim_60,
  author = {{NVIDIA}},
  title  = {Isaac Sim 6.0 Documentation},
  year   = {2026},
  note   = {Version 6.0.0-rc.59, accessed 2026-06-28}
}

@misc{isaac_lab_beta,
  author = {{NVIDIA}},
  title  = {Isaac Lab},
  year   = {2026},
  note   = {v3.0.0-beta2}
}

@article{schulman2017ppo,
  author  = {Schulman, John and Wolski, Filip and Dhariwal, Prafulla and Radford, Alec and Klimov, Oleg},
  title   = {Proximal Policy Optimization Algorithms},
  journal = {arXiv preprint arXiv:1707.06347},
  year    = {2017}
}

@inproceedings{scheibler2018pyroom,
  author    = {Scheibler, Robin and Bechwati, Fatima and Dietz, Martin and others},
  title     = {PyRoomAcoustics: A Python package for audio room simulations and array processing algorithms},
  booktitle = {ICASSP},
  year      = {2018}
}
```

---

## 正文引用對照（撰寫時用）

| 章節 | 建議引用 |
|------|----------|
| §1.1 | `robot_sonar_review`, `isaac_sim_60` |
| §2.4 | `isaac_sim_60`, `omniverse_rtx` |
| §3.6–3.7 | `isaac_sim_60` |
| §3.8 | `pyroomacoustics` |
| §3.9–3.10 | `isaac_lab_beta`, `rsl_rl`, `ppo_schulman` |
| §4.7.1 | `ppo_schulman` |