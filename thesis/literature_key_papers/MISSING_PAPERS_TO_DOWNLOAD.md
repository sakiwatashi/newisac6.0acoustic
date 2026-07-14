# 尚未下載的論文／文件（請手動補齊）

> **2026-07-15 更新：** Nosek 2018 已補入  
> `02_Nosek_2018_The_preregistration_revolution_PNAS.pdf`（OSF 開放稿）。  
> **實驗×數學×原文詳版對照：** `docs/plan_v2/EXPERIMENT_MATH_LITERATURE_GROUNDING.md`

本檔列出**本包尚未收錄 PDF**、但論文方法／口試仍重要的文獻。  
已下載的檔案見同資料夾內 `01_…`～`14_…` 與 `README.md`。

下載後建議命名：`作者年_短題名.pdf`，放進本資料夾後可重打 zip：

```bash
cd /home/lab109/song/isaacsim6.0/thesis
zip -r -9 literature_key_papers.zip literature_key_papers
```

---

## 最優先（方法主幹，強烈建議補）

### 1. Nosek et al. (2018) — 預註冊  ✅ **已下載（2026-07-15）**

- **題名：** The preregistration revolution  
- **出處：** *Proceedings of the National Academy of Sciences*, 115(11), 2600–2606  
- **DOI：** https://doi.org/10.1073/pnas.1708274114  
- **建議直連（若可開）：** https://www.pnas.org/content/pnas/115/11/2600.full.pdf  
- **對應你的實驗：** 判準先寫後跑、D3 失敗不放寬／新目錄複驗  
- **建議檔名：** `02_Nosek_2018_The_preregistration_revolution_PNAS.pdf`

### 2. Hayes & Gough (2009) — 合成孔徑／移動感測譜系

- **題名：** Synthetic aperture sonar: A review of current status  
- **出處：** *IEEE Journal of Oceanic Engineering*, 34(3), 207–224  
- **DOI：** https://doi.org/10.1109/JOE.2009.2020853  
- **對應你的實驗：** D2「手臂移動多視點量測」的文獻譜系（非完整 SAS 成像）  
- **建議檔名：** `15_Hayes_2009_Synthetic_aperture_sonar_review.pdf`  
- **備註：** IEEE 常需學校權限

### 3. Valin, Michaud & Rouat (2017) — 機器人聲源定位綜述

- **題名：** Localization of sound sources in robotics: A review  
- **出處：** *Robotics and Autonomous Systems*, 96, 184–210  
- **DOI：** https://doi.org/10.1016/j.robot.2017.07.011  
- **對應你的實驗：** 配對移除／多路徑動機（包絡、不能整條波形當真理）  
- **建議檔名：** `16_Valin_2017_Localization_of_sound_sources_in_robotics_review.pdf`

### 4. Höfer et al. (2021) — Sim2Real 邊界

- **題名：** Sim2Real in robotics and automation: Applications and challenges  
- **出處：** *IEEE Transactions on Automation Science and Engineering*  
- **DOI：** https://doi.org/10.1109/TASE.2021.3064065（若 DOI 有異以論文參考文獻為準）  
- **對應你的實驗：** 只談任務級／模擬可行性，不宣稱波形＝實機  
- **建議檔名：** `17_Hoefer_2021_Sim2Real_in_robotics_and_automation.pdf`

### 5. Kerstens, Laurijssen & Steckel (2019) — 陣列 3D 聲納（對照路線）

- **題名：** eRTIS: A fully embedded real time 3D imaging sonar sensor for robotic applications  
- **出處：** *2019 IEEE International Conference on Robotics and Automation (ICRA)*, pp. 1438–1443  
- **DOI / IEEE：** 搜尋 “eRTIS ICRA 2019”  
- **對應你的實驗：** 文獻上可用陣列做左右；本文四重證偽後**不走**這條，改多點定位  
- **建議檔名：** `18_Kerstens_2019_eRTIS_embedded_3D_imaging_sonar_ICRA.pdf`

---

## 次優先（背景／ complementary，有空再補）

### 6. Alatise & Hancke (2020)

- **題名：** A review on challenges of autonomous mobile robot and sensor fusion methods  
- **出處：** *IEEE Access*, 8, 39830–39846  
- **DOI：** https://doi.org/10.1109/ACCESS.2020.2975643  
- **用途：** 非視覺／多模態感測融合  
- **建議檔名：** `08_Alatise_2020_AMR_sensor_fusion_review_IEEE_Access.pdf`

### 7. He et al. (2019)

- **題名：** Recent advances in 3D data acquisition and processing by time-of-flight camera  
- **出處：** *IEEE Access*, 7, 174406–174420  
- **DOI：** https://doi.org/10.1109/ACCESS.2019.2891693  
- **用途：** ToF／主動深度脈絡（與超聲距離互補）  
- **建議檔名：** `09_He_2019_ToF_camera_IEEE_Access.pdf`

### 8. Tsuchiya et al. (2022)

- **題名：** Indoor self-localization using multipath arrival time of sound  
- **出處：** *Japanese Journal of Applied Physics*, 61(SG), SG1005  
- **DOI：** https://doi.org/10.35848/1347-4065/ac506c  
- **用途：** 室內多路徑到達時間 → 配對移除動機  
- **建議檔名：** `19_Tsuchiya_2022_Indoor_self_localization_multipath_arrival_time.pdf`

### 9. Brinkmann et al. (2019)

- **題名：** A round robin on room acoustical simulation and auralization  
- **出處：** *Journal of the Acoustical Society of America*, 145(4), 2744–2760  
- **DOI：** https://doi.org/10.1121/1.5096178  
- **用途：** 聲學模擬跨引擎差異 → 模擬≠實機  
- **建議檔名：** `11_Brinkmann_2019_round_robin_room_acoustics_JASA.pdf`

### 10. Xu et al. (2024)（緒論背景，可選）

- **題名：** Collaborative robotics, digital twins, human–machine interfaces and AI in smart manufacturing: A review  
- **出處：** *Robotics and Computer-Integrated Manufacturing*（見論文參考文獻）  
- **用途：** 智慧製造／協作臂背景  
- **建議檔名：** `20_Xu_2024_collaborative_robotics_digital_twins_review.pdf`

---

## 官方文件（通常是網頁，不一定有單一 PDF）

| 名稱 | 用途 | 連結 |
|------|------|------|
| NVIDIA — RTX Acoustic Sensor | 平台超音波模組 | https://docs.isaacsim.omniverse.nvidia.com/latest/sensors/isaacsim_sensors_rtx_acoustic.html |
| NVIDIA — RTX Annotators / GMO | 原始輸出結構 | https://docs.isaacsim.omniverse.nvidia.com/6.0.0/sensors/isaacsim_sensors_rtx_annotators.html |
| NVIDIA — Isaac Sim Documentation | 模擬平台 | https://docs.isaacsim.omniverse.nvidia.com/latest/index.html |
| NVIDIA — Isaac Lab docs | 未來 RL 路徑 | https://isaac-sim.github.io/IsaacLab/ |
| Universal Robots — UR10e product factsheet | 手臂規格 | 見論文參考文獻 PDF 網址 |
| Robotiq — 2F-85 instruction manual | 夾爪規格 | 見論文參考文獻 PDF 網址 |

---

## 對照：本包「已有 PDF」一覽（不必再下）

| 檔名 | 題名關鍵字 |
|------|------------|
| `01_Meyes_2019_Ablation_studies_in_ANNs.pdf` | Ablation studies in ANNs |
| `03_Kapoor_2016_3D_multilateration_ultrasonic_beacons_Sensors.pdf` | 3D multilateration ultrasonic beacons |
| `04_Gao_2026_NVIDIA_Isaac_Sim_arXiv.pdf` | NVIDIA Isaac Sim scalable simulation |
| `05_Schulman_2017_PPO_algorithms.pdf` | Proximal policy optimization |
| `06_Zhmud_2018_ultrasonic_distances_robotics_JPCS.pdf` | Ultrasonic distances in robotics |
| `07_Liu_2020_Indoor_acoustic_localization_survey.pdf` | Indoor acoustic localization survey |
| `10_Dumbgen_2022_Blind_as_a_bat.pdf` | Blind as a bat echolocation |
| `12_Scheibler_PyRoomAcoustics_arxiv.pdf` | PyRoomAcoustics |
| `13_Rudin_2022_Learning_to_walk_minutes_parallel_RL.pdf` | Learning to walk in minutes |
| `14_Salimpour_2025_Sim2Real_Isaac_Gazebo.pdf` | Sim-to-Real Isaac Sim |

---

## 補檔建議順序（時間少只抓這五個）

1. Nosek 2018（預註冊）  
2. Valin 2017（聲源定位綜述）  
3. Hayes 2009（合成孔徑）  
4. Höfer 2021（Sim2Real）  
5. Kerstens 2019（eRTIS 對照）  

（Kapoor 多點定位已在本包；Meyes 消融已在本包。）
