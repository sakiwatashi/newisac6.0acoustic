# Citation Support Bank (Facet-Curated)

**Version:** v2 — reorganized by `research_taxonomy.md` facets  
**Total curated entries:** 38 (was 53; removed off-topic / duplicate)  
**Target for thesis §2:** pick **~20** from「Recommended final 20」below  
**Rule:** Every §2 sentence maps to **one facet** → cite from that facet block only.

---

## Study classification (reminder)

| Primary type | Methodological bridge |
|--------------|----------------------|
| Simulation-based feasibility pipeline | Sim → Lab → optional in-sim RL, with claim boundaries |

**Gap (G0):** F2 ∩ F5 ∩ F8 ∩ fixed-TCP industrial manipulator — sparse in literature.

---

## Recommended final 20 (thesis §2 reference set)

| # | ID | Facet | § | Reference (short) |
|---|-----|-------|---|-------------------|
| 1 | F2-01 | F2 | 2.2 | Gao et al. (2026) Isaac Sim survey |
| 2 | F3-01 | F3 | 2.2 | Höfer et al. (2021) Sim2Real challenges |
| 3 | F2-02 | F2 | 2.2 | Mittal et al. (2023) Orbit / Isaac Lab |
| 4 | F2-03 | F2 | 2.2 | GRADE (2025) dynamic Isaac Sim envs |
| 5 | F2-04 | F2 | 2.2 | Salimpour et al. (2025) Isaac Sim→ROS2 RL |
| 6 | F2-05 | F2 | 2.2 | Zhou et al. (2024) Isaac Sim industrial CPS |
| 7 | F1-01 | F1 | 2.1 | Alatise et al. (2020) sensor fusion / non-visual |
| 8 | F1-02 | F1 | 2.1 | He et al. (2019) ToF advances |
| 9 | F1-03 | F1 | 2.1 | Zhmud et al. (2018) ultrasonic on robots |
| 10 | F1-04 | F1 | 2.1 | Dümbgen et al. (2022) robot echolocation |
| 11 | F4-01 | F4 | 2.3 | Liu et al. (2020) indoor acoustic localization survey |
| 12 | F4-02 | F4 | 2.3 | Valin et al. (2017) sound localization in robotics |
| 13 | F4-03 | F4 | 2.3 | Tsuchiya et al. (2022) multipath acoustic ranging |
| 14 | F5-01 | F5 | 2.4 | NVIDIA RTX Acoustic docs |
| 15 | F5-02 | F5 | 2.4 | NVIDIA RTX annotators / GMO |
| 16 | F5-03 | F5 | 2.4 | OceanSim (2025) Isaac Sim sensor extension |
| 17 | F4-04 | F4 | 2.5 | Brinkmann et al. (2019) room sim round robin |
| 18 | F4-05 | F4 | 2.5 | Scheibler et al. (2018) PyRoomAcoustics |
| 19 | F6-01 | F6 | 2.5–2.6 | dEchorate RIR dataset (2021) |
| 20 | G0-01 | G0 | 2.6 | Gap statement + Xu et al. (2024) digital twin manufacturing |

---

## F1 — Non-visual robot ranging & proximity sensing

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| F1-01 | Alatise, M. B., et al. (2020). A Review on Challenges of Autonomous Mobile Robot and Sensor Fusion Methods. *IEEE Access*. https://doi.org/10.1109/access.2020.2975643 | 2020 | 多模態感測（含超音波／距離）用於補足視覺在遮蔽、反光環境下的不足。 | yes |
| F1-02 | He, Y., et al. (2019). Recent Advances in 3D Data Acquisition and Processing by Time-of-Flight Camera. *IEEE Access*. https://doi.org/10.1109/access.2019.2891693 | 2019 | ToF 提供主動深度量測，但在多徑與動態範圍上常需與其他 proximity 感測互補。 | yes |
| F1-03 | Zhmud, V., et al. (2018). Application of ultrasonic sensor for measuring distances in robotics. https://doi.org/10.1088/1742-6596/1015/3/032189 | 2018 | 機器人（含手臂）可掛載超音波進行近距量測，需校正姿態與反射面。 | yes |
| F1-04 | Dümbgen, F., et al. (2022). Blind as a Bat: Audible Echolocation on Small Robots. *IEEE RA-L*. https://doi.org/10.1109/lra.2022.3194669 | 2022 | 主動聲學回波可在無視覺下估計障礙距離，與 RTX 主動聲學模擬同族。 | yes |
| F1-05 | Villani, V., et al. (2018). Survey on human–robot collaboration in industrial settings. *Mechatronics*. https://doi.org/10.1016/j.mechatronics.2018.02.009 | 2018 | 協作機器人需近距離感知保障安全；非視覺測距具工業互補價值。（可選） | yes |

**Removed from F1:** Zhu 2021 DRL navigation, Gai 2021 agriculture — off-topic for fixed-TCP acoustic study.

---

## F2 — Robotics simulation platforms (Isaac / GPU / Omniverse)

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| F2-01 | **Gao, S., Pagnucco, M., Bednarz, T., & Song, Y. (2026).** NVIDIA Isaac Sim: Enabling Scalable, GPU-Accelerated Simulation for Robotics. *arXiv:2606.03551*. https://doi.org/10.48550/arxiv.2606.03551 | 2026 | Simulation has become a core infrastructure for robotics research；綜述 GPU、PhysX、RTX、USD、感測模擬與 robot learning。 | yes |
| F2-02 | Mittal, M., et al. (2023). Orbit: A Unified Simulation Framework for Interactive Robot Learning Environments. *IEEE RA-L*. https://doi.org/10.1109/lra.2023.3270034 | 2023 | Orbit／Isaac Lab 系譜：GPU 並行模擬支撐機器人學習。 | yes |
| F2-03 | GRADE (2025). Generating Realistic and Dynamic Environments for robotics research with Isaac Sim. *IJRR*. https://doi.org/10.1177/02783649251346211 | 2025 | 以 Isaac Sim 建動態室內場景，與本研究移動目標設定同類。 | yes |
| F2-04 | Salimpour, S., Peña-Queralta, J., & Páez-Granados, D. (2025). Sim-to-Real… Isaac Sim to Gazebo and ROS 2. *arXiv:2501.02902*. https://doi.org/10.48550/arxiv.2501.02902 | 2025 | Isaac Sim 推動 RL 機器人研究，並可銜接 Gazebo／實機。 | yes |
| F2-05 | Zhou, Z., et al. (2024). Towards Building AI-CPS with NVIDIA Isaac Sim… *ACM MSEC*. https://doi.org/10.1145/3639477.3639740 | 2024 | Isaac Sim 用於工業操作基準，支撐製造場景數位驗證。 | yes |
| F2-06 | Song, J., et al. (2025). OceanSim… *IROS 2025*. https://doi.org/10.1109/iros60139.2025.11246878 | 2025 | 基於 Isaac Sim 擴充感測模擬（亦列於 F5）。 | yes |
| F2-07 | NVIDIA. Isaac Lab Documentation. https://isaac-sim.github.io/IsaacLab/ | 2026 | DirectRLEnv + RSL-RL 閉環訓練平台。（可選） | yes |
| F2-08 | Kim, Y., et al. (2025). Surgical Robotics Environment in Isaac Sim. *ISMR*. https://doi.org/10.1109/ISMR67322.2025.11025977 | 2025 | 領域任務環境範例。（可選，篇幅緊可刪） | yes |

---

## F3 — Sim-to-real epistemology & claim boundaries

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| F3-01 | Höfer, S., et al. (2021). Sim2Real in Robotics and Automation: Applications and Challenges. *IEEE T-ASE*. https://doi.org/10.1109/tase.2021.3064065 | 2021 | **Sim2Real 應以任務級指標驗證，不宜假設模擬信號與實機等價。** | yes |
| F3-02 | Collins, J., et al. (2021). A Review of Physics Simulators for Robotic Applications. *IEEE Access*. https://doi.org/10.1109/access.2021.3068769 | 2021 | 物理模擬器是學習與驗證工具，非 ground truth。 | yes |
| F3-03 | Horváth, D., et al. (2022). Object Detection Using Sim2Real Domain Randomization. *IEEE T-RO*. https://doi.org/10.1109/tro.2022.3207619 | 2022 | Domain randomization 常用於縮小差距；聲學特徵遷移仍待驗證。 | yes |
| F3-04 | NVIDIA Blog (2024). Closing the Sim-to-Real Gap with Isaac Lab. https://developer.nvidia.com/blog/closing-the-sim-to-real-gap-training-spot-quadruped-locomotion-with-nvidia-isaac-lab/ | 2024 | 官方 Sim2Real 敘事：閉環訓練後可遷移實機。（可選） | yes |

**Removed:** OpenAI Rubik's cube — iconic but not needed; saves space.

---

## F4 — Indoor room acoustics & multipath observables

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| F4-01 | Liu, M., et al. (2020). Indoor acoustic localization: a survey. https://doi.org/10.1186/s13673-019-0207-4 | 2020 | 室內聲學定位受多徑與殘響影響；early energy 常作距離 proxy。 | yes |
| F4-02 | Valin, J.-M., et al. (2017). Localization of sound sources in robotics: A review. https://doi.org/10.1016/j.robot.2017.07.011 | 2017 | 機器人聲學定位需處理殘響；主動聲學可提供距離線索。 | yes |
| F4-03 | Tsuchiya, A., et al. (2022). Indoor self-localization using multipath arrival time… https://doi.org/10.35848/1347-4065/ac506c | 2022 | 單一聲學感測可利用多徑到達時間；聲學—距離存在可利用關聯。 | yes |
| F4-04 | Brinkmann, F., et al. (2019). A round robin on room acoustical simulation… *JASA*. https://doi.org/10.1121/1.5096178 | 2019 | 不同聲學模擬器 RIR 預測有系統差異 → 趨勢級對照合理。 | yes |
| F4-05 | Scheibler, R., et al. (2018). PyRoomAcoustics… *ICASSP*. https://doi.org/10.1109/ICASSP.2018.8461829 | 2018 | 幾何聲學 RIR 基線工具，用於 PRA 對照。 | yes |
| F4-06 | Wang, H., et al. (2020). Time-domain impedance boundary… room acoustics. https://doi.org/10.1121/10.0001128 | 2020 | 材質邊界影響早期反射 → 支撐 Material Passport。（可選） | yes |

**Removed:** Obeidat 2021 WiFi indoor localization — wrong modality (RF not acoustics).

---

## F5 — Ray-traced / RTX sensor simulation

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| F5-01 | NVIDIA. RTX Acoustic Sensor. https://docs.isaacsim.omniverse.nvidia.com/latest/sensors/isaacsim_sensors_rtx_acoustic.html | 2026 | RTX Acoustic 實驗性感測，輸出 GMO signal-way。 | yes |
| F5-02 | NVIDIA. RTX Annotators / GMO. https://docs.isaacsim.omniverse.nvidia.com/6.0.0/sensors/isaacsim_sensors_rtx_annotators.html | 2026 | GenericModelOutput 欄位語義為特徵工廠依據。 | yes |
| F5-03 | NVIDIA. RTX Sensors Overview. https://docs.isaacsim.omniverse.nvidia.com/latest/sensors/isaacsim_sensors_rtx.html | 2026 | GPU 路徑追蹤感測與幾何聲學套件模型假設不同。 | yes |
| F5-04 | Song, J., et al. (2025). OceanSim. *IROS 2025*. (see F2-06) | 2025 | Isaac Sim 可擴充為專用 ray-traced 感測管線。 | yes |
| F5-05 | LiMOX (2024). Point Cloud Lidar Model via NVIDIA OptiX. *Sensors*. https://doi.org/10.3390/s24061846 | 2024 | OptiX/RTX 感測模擬類比（非聲學，但說明 RTX sensor 範式）。（可選） | yes |

**Note:** OpenAlex 幾乎無「RTX Acoustic + robot」同題論文；F5 以 **NVIDIA 官方文件為主**。

---

## F6 — Acoustic feature → distance inference

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| F6-01 | dEchorate (2021). Calibrated RIR dataset. https://doi.org/10.1186/s13636-021-00229-0 | 2021 | 標定 RIR／回波特徵可支撐距離相關學習。 | yes |
| F6-02 | Speaker Distance Estimation in Enclosures From Single-Channel Audio (2024). *IEEE/ACM TASLP*. https://doi.org/10.1109/taslp.2024.3382504 | 2024 | 單通道音訊特徵可估計說話者距離（弱觀測、封閉空間）。 | yes |
| F6-03 | **Internal:** Sim→Lab linear SL (§4.6), r≈0.47, MAE≈0.41 m | 2026 | 本研究證據：趨勢級距離推理可行，非部署精度。 | yes |
| F6-04 | Chen, C., et al. (2018). Acoustic SLAM. *TASLP*. https://doi.org/10.1109/taslp.2018.2828321 | 2018 | 聲學特徵與幾何耦合；本研究只做距離估計、不做 SLAM。（對照用，可選） | yes |

---

## F7 — In-simulation RL for perception (smoke / loop viability)

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| F7-01 | Salimpour et al. (2025) — see F2-04 | 2025 | Isaac Sim 上 RL 訓練可銜接實機驗證鏈。 | yes |
| F7-02 | Mittal et al. (2023) Orbit — see F2-02 | 2023 | GPU 模擬支撐高頻 rollout／PPO 類訓練。 | yes |
| F7-03 | **Internal:** Phase 5 in-sim PPO DirectRLEnv + GMO rebind fix | 2026 | 本研究：閉環可跑通；policy 趨勢級追蹤，未優於 SL。 | yes |

**Note:** 專門「Isaac Lab + RTX GMO + RL」文獻極少；F7 以平台文獻 + 本研究結果為主。

---

## F8 — Reproducible experimental infrastructure

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| F8-01 | Corke, P., et al. (2018). Guest Editorial: Open Discussion of Robot Grasping Benchmarks, Protocols, and Metrics. *IEEE T-ASE*. https://doi.org/10.1109/tase.2018.2871354 | 2018 | 機器人實驗需公開協定與可重複指標。 | yes |
| F8-02 | Babel et al. (2022). Reproducibility in Human-Robot Interaction. https://doi.org/10.1007/s43154-022-00094-5 | 2022 | 可重現性為 HRI／機器人實驗可信度基礎。（可選） | yes |
| F8-03 | **Internal:** Geometry/Material Passport, 30/30 PASS, replication package | 2026 | 本研究主要方法貢獻：可審計管線。 | yes |

---

## G0 — Research gap (sparse intersection)

| ID | Reference | Year | Support claim (中文) | Verified |
|----|-----------|------|----------------------|----------|
| G0-01 | **Synthesis (本研究).** No published stack combining: Isaac Sim RTX Acoustic distance repeatability + UR10 fixed-TCP + Isaac Lab closed-loop RL + auditable passports. | 2026 | 現有工作多覆蓋子集；本研究填補 **可行性管線** 缺口，非宣稱物理等價。 | yes |
| G0-02 | Xu, X., et al. (2024). Collaborative robotics, digital twins, HMI and AI. *RCIM*. https://doi.org/10.1016/j.rcim.2024.102769 | 2024 | 製造數位雙生需可重現模擬管線；呼應智能製造學程脈絡。 | yes |
| G0-03 | Universal Robots. UR10 product documentation. https://www.universal-robots.com/products/ur10-robot/ | — | 平台正當性；採官方 USD。 | yes |

---

## §2.x writing map (facet-driven)

| § | Facets to cite | Primary IDs |
|---|----------------|-------------|
| §2.1 | F1 | F1-01, F1-02, F1-03, F1-04 |
| §2.2 | F2 + F3 | **F2-01** lead, F2-02–05, F3-01, F3-02 |
| §2.3 | F4 | F4-01, F4-02, F4-03 |
| §2.4 | F5 | F5-01, F5-02, F5-03, F5-04 |
| §2.5 | F4 + F6 | F4-04, F4-05, F6-01, F6-02 |
| §2.6 | G0 + F6 + F8 | G0-01, G0-02, F8-03, F6-03 |

### §2.2 建議首段（可直接改寫）

> Simulation has become a core infrastructure for robotics research (Gao et al., 2026). NVIDIA Isaac Sim integrates GPU-accelerated physics, RTX rendering, and sensor simulation within a USD scene graph, and has been extended for dynamic environment authoring (GRADE, 2025), cross-platform reinforcement-learning transfer (Salimpour et al., 2025), and domain-specific perception simulation (OceanSim, 2025). Following Höfer et al. (2021), this thesis treats simulation outputs as **task-level feasibility evidence**, not as waveform-equivalent ground truth for deployment-grade ranging.

---

## Removed entries (v1 → v2)

Duplicates, wrong modality, or weak fit: C002, C006, C019, C022, C027, C032, C040, C044, C045, C046, C048, Eliakim duplicate of F1 theme, Pegasus/Jacinto (redundant with OceanSim/GRADE).

---

*Cross-ref: `research_taxonomy.md` · `facet_literature_search.md` · Updated 2026-06-28*