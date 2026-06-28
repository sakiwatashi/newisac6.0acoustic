# Research Taxonomy — UR10 RTX Acoustic Thesis

**Purpose:** Define *what kind of research this is* (in English facets) before literature search.  
**Not a copy of chapter outline** — a cross-cutting classification for query design.

---

## 1. Primary study type

| Label | Definition | What we are NOT |
|-------|------------|-----------------|
| **Simulation-based feasibility pipeline** | End-to-end, auditable workflow in Isaac Sim/Lab that asks whether RTX acoustic *features* can support *trend-level* distance reasoning under controlled geometry. | Hardware ranging product; waveform-faithful digital twin |
| **Methodological bridge study** | Connects Sim static calibration → Lab dynamic obs → optional in-sim RL loop, with explicit **claim boundaries**. | Pure algorithm paper; pure simulator benchmark |

**One-line positioning (English):**  
*A reproducible Isaac Sim–Lab pipeline for fixed-TCP UR10 RTX acoustic distance feasibility, evaluated with trend-level metrics rather than deployment-grade ranging.*

---

## 2. Facet taxonomy (search axes)

Each facet is an **independent literature lane**. Papers may sit in multiple facets.

### F1 — Non-visual robot ranging & proximity sensing
- Scope: ultrasonic, ToF, active echo, arm-mounted ranging, occlusion-robust cues
- Thesis link: motivates why vision-only fails and why distance proxies matter

### F2 — Robotics simulation platforms (GPU / Omniverse / Isaac)
- Scope: Isaac Sim survey, Isaac Lab, Orbit, digital twin in manufacturing, environment authoring
- Thesis link: §2.2 platform legitimacy; justifies tool choice

### F3 — Sim-to-real transfer & evaluation epistemology
- Scope: domain gap, domain randomization, *task-level* vs *signal-level* validation
- Thesis link: claim boundary — trend OK, waveform equivalence NOT OK

### F4 — Indoor room acoustics & multipath observables
- Scope: RIR, early reflections, early energy, material absorption, enclosed industrial rooms
- Thesis link: why `primary_sgw_early_energy` is a plausible but weak distance proxy

### F5 — Simulated / ray-traced acoustic & multimodal sensing
- Scope: RTX sensors, acoustic rendering, synthetic sensor data for robotics, sim sensor fidelity
- Thesis link: closest technical neighbor to RTX Acoustic (still sparse in literature)

### F6 — Distance / geometry inference from acoustic features
- Scope: regression, learning from echo/RIR summaries, SLAM-with-acoustics (feature level)
- Thesis link: relates to §4.6 SL and §4.7 RL as estimators, not localizers

### F7 — In-simulation RL for perception / state estimation
- Scope: DirectRLEnv, PPO smoke, closed-loop GMO capture, weak-signal policies
- Thesis link: Phase 5 — loop viability, not beating SL

### F8 — Reproducible experimental infrastructure
- Scope: repeatability protocols, open pipelines, geometry/material passports, benchmark design
- Thesis link: 30/30 PASS, passports, replication package

---

## 3. Gap facet (G0) — intersection not found in literature

**G0 = F2 ∩ F5 ∩ F8 ∩ (industrial manipulator fixed-TCP)**  
Public work often has:
- Isaac Sim **without** RTX acoustic distance repeatability, or
- Acoustic robotics **without** Isaac/Omniverse audit trail, or
- RL in Isaac Lab **without** RTX GMO closed loop.

Our contribution sits in this **sparse intersection** as feasibility + methodology.

---

## 4. Facet → thesis chapter map

| Facet | Primary chapter |
|-------|-----------------|
| F1 | §2.1 |
| F2, F3 | §2.2 |
| F4 | §2.3, §2.5 |
| F5 | §2.4 |
| F6 | §2.6, §4.6 |
| F7 | §3.10, §4.7 |
| F8 | §3.4–3.7, §4.1 |
| G0 | §2.6, §5.1 |

---

## 5. Search query templates (English)

Used in `facet_literature_search.md` (OpenAlex, 2020+ unless foundational).

```
F1: "robot ultrasonic distance" OR "time-of-flight" AND manipulator proximity
F2: "NVIDIA Isaac Sim" robotics simulation GPU
F3: sim-to-real robotics task-level validation domain gap
F4: room impulse response early energy distance indoor
F5: ray tracing acoustic simulation robot OR RTX sensor simulation robotics
F6: acoustic distance estimation regression RIR features robot
F7: reinforcement learning perception simulation Isaac OR closed-loop sensor simulation
F8: reproducible robotics experiment pipeline repeatability benchmark
G0: Isaac Sim acoustic sensor OR RTX acoustic robot (expect few hits)
```

---

## 6. Curated picks per facet (human judgment, not raw search dump)

Use these when writing §2.x — each pick matches **our** study type (§1), not generic robotics hits.

| Facet | Pick | Why it fits *this* thesis |
|-------|------|-------------------------|
| **F1** | Liu et al. (2020) indoor acoustic localization survey | Multipath + enclosed space framing |
| **F1** | Zhmud et al. (2018) ultrasonic on robots | Arm-mounted ranging precedent |
| **F1** | Dümbgen et al. (2022) audible echolocation on small robots | Active acoustic proxy for distance |
| **F2** | **Gao et al. (2026)** Isaac Sim survey arXiv:2606.03551 | **Primary platform citation** |
| **F2** | Mittal et al. (2023) Orbit / Isaac Lab lineage | Lab extension justification |
| **F2** | GRADE (2025) IJRR | Dynamic indoor env in Isaac Sim |
| **F2** | Salimpour et al. (2025) Isaac Sim→ROS2 RL | Sim2Real + Isaac Sim ecosystem |
| **F2** | OceanSim (2025) IROS | Sensor-sim extension on Isaac Sim |
| **F3** | Höfer et al. (2021) Sim2Real challenges T-ASE | **Claim boundary anchor** |
| **F3** | Collins et al. (2021) physics simulators review | Simulators ≠ ground truth |
| **F4** | Brinkmann et al. (2019) room acoustics round robin | Cross-simulator RIR differences |
| **F4** | Scheibler et al. (2018) PyRoomAcoustics | PRA baseline tool |
| **F4** | Speaker distance from single-channel audio (2024) TASLP | Feature→distance (weak signal) |
| **F5** | NVIDIA RTX Acoustic docs (Isaac Sim 6.0) | **Only direct RTX acoustic primary source** |
| **F5** | LiMOX OptiX lidar sim (2024) | RTX/OptiX sensor sim analogy (not acoustic) |
| **F6** | dEchorate RIR dataset (2021) | Calibrated echo features |
| **F6** | Our §4.6 SL r≈0.47 | Internal evidence for trend-level inference |
| **F7** | Salimpour (2025) + our Phase 5 in-sim PPO | RL loop viability, not SOTA |
| **F8** | Corke et al. grasping benchmarks editorial (2018) | Repeatability / protocol mindset |
| **F8** | Our 30/30 + passports | **Primary empirical contribution** |
| **G0** | *(sparse)* + Gao (2026) gap paragraph | No audited UR10+RTX acoustic+Lab RL stack found |

### Facet search quality notes

- **F4 automated query** often returns RF/mmWave — use fixed queries: `early reflection room acoustics`, `RIR dataset`.
- **F5 / G0** are sparse in OpenAlex; lean on **NVIDIA docs + Gao survey + OceanSim/GRADE** as platform neighbors.
- **F7** Isaac Lab + RSL-RL papers are new; cite Orbit + our replication package as primary.

---

## 7. 中文摘要（給作者）

這篇論文的分類不是「聲學論文」或「RL 論文」單選，而是：

**主類型：** simulation-based feasibility pipeline（模擬可行性管線）  
**次類型：** methodological bridge（Sim → Lab → 可選 in-sim RL）

八個英文 facet（F1–F8）各自對應不同文獻賽道；**G0** 是你真正的缺口（Isaac Sim + RTX 聲學 + 可審計重複性 + 工業手臂）。  
之後搜文獻、寫 §2 都應先問：這句話屬於哪個 facet？再用該 facet 的英文 query 搜，避免搜到不相干的綜述。