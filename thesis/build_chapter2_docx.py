#!/usr/bin/env python3
"""Insert full Chapter 2 (§2.1–§2.6) into THESIS_DRAFT_FCU_v1.docx."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

DOC_PATH = Path(__file__).resolve().parent / "THESIS_DRAFT_FCU_v1.docx"

CHAPTER2 = [
    ("Header2", "2.1 機器人非視覺感測與超音波測距"),
    (
        "Content",
        "協作機器人與工業手臂在狹窄、遮蔽或人機共融場景中，僅依賴視覺往往難以穩定取得近距幾何資訊。"
        "Alatise 等（2020）指出，多模態感測融合——其中包含超音波與其他非視覺距離量測——可補足視覺在反光、"
        "低照度與遮擋條件下的不足。此互補角色對本研究至關重要：UR10 末端掛載之主動聲學感測，"
        "並非取代相機，而是在固定 TCP 幾何下提供可重複的距離相關觀測。",
    ),
    (
        "Content",
        "時間飛行（Time-of-Flight, ToF）相機提供主動深度量測，He 等（2019）綜述其在三維擷取上的進展，"
        "同時強調多徑反射與動態範圍限制常需與其他 proximity 感測協同。"
        "Zhmud 等（2018）則以機器人（含手臂）掛載超音波感測器為例，說明近距量測需校正感測器姿態、"
        "反射面法向與安裝幾何；本研究之 Geometry Passport 即沿此脈絡，將感測器—目標相對幾何列為可審計變量。",
    ),
    (
        "Content",
        "近年亦有研究探索主動聲學回波於小型機器人之應用。Dümbgen 等（2022）展示無視覺條件下，"
        "可聽域主動回波仍能估計障礙距離，與 Isaac Sim RTX Acoustic 之主動聲學模擬屬同一技術族。"
        "綜上，文獻支持「末端非視覺測距具工業互補價值」，但亦提醒量測品質高度依賴幾何與環境；"
        "本研究因此不宣稱部署級測距精度，而聚焦於控制變量下之可行性驗證。",
    ),
    ("Header2", "2.2 模擬與虛實整合（Sim-to-Real）"),
    (
        "Content",
        "Gao 等（2026）為第一篇專題綜述 NVIDIA Isaac Sim，指出模擬已成為機器人研究的核心基礎設施。"
        "平台以 Omniverse 為底，整合 GPU 加速 PhysX 物理、RTX 光追渲染與 USD 場景表示，"
        "並內建 RGB／深度、LiDAR、IMU 等感測模擬與合成資料管線。"
        "該綜述亦強調 Isaac Lab 可支援大規模並行強化學習；Mittal 等（2023）提出之 Orbit 即為此系譜前身。"
        "本研究以 Isaac Sim 6.0 為主實驗平台，並保留與 Isaac Lab 後續延伸的相容性。",
    ),
    (
        "Content",
        "近年 Isaac Sim 持續用於動態場景建置（GRADE, 2025）、Sim-to-Real 策略遷移（Salimpour 等, 2025）"
        "與工業操作驗證（Zhou 等, 2024）。然而 Gao 等（2026）亦未專論 RTX Acoustic；"
        "模擬器輸出仍非物理真值。Höfer 等（2021）強調應以任務級指標驗證遷移，"
        "不宜假設模擬信號與實機波形等價。本研究遵循此邊界："
        "RTX Acoustic 特徵僅作趨勢級距離推理之可行性證據，而非 CH201 實機波形對照標準。",
    ),
    ("Header2", "2.3 室內環境與距離特徵（簡述）"),
    (
        "Content",
        "封閉工業環境中，超音波回波會受牆面與工件反射影響，距離資訊往往不是單一路徑量測。"
        "Liu 等（2020）指出，室內環境下早期反射能量可作距離之弱趨勢指標，但仍受房間幾何與材質制約。"
        "本研究因此不宣稱厘米級測距，而以早期能量等摘要特徵檢驗「距離趨勢是否可用於感測回授」；"
        "特徵定義與擷取流程見第三章。",
    ),
    ("Header2", "2.4 RTX Acoustic 與 GenericModelOutput"),
    (
        "Content",
        "Isaac Sim 6.0 提供 RTX Acoustic 超音波感測模組（NVIDIA, 2026a），屬實驗性功能："
        "在模擬場景中以 GPU 產生回波資料（signal-way 格式），不輸出點雲。"
        "本研究把它視為「可控幾何下的合成超音波觀測」，用來檢驗感測回授接近與離線狀態判斷是否可行。",
    ),
    (
        "Content",
        "官方文件說明，輸出為發射端、接收端、通道與振幅取樣值的組合（NVIDIA, 2026a）；"
        "本研究據此整理早期能量、峰值與雙接收端平衡等特徵，程式細節列於附錄。"
        "Gao 等（2026）平台綜述未涵蓋此模組；學術上相近案例為 Song 等（2025）OceanSim，"
        "顯示 Isaac Sim 可延伸為專用 ray-traced 感測管線。",
    ),
    (
        "Content",
        "RTX Acoustic 不保證與實機 CH201 波形一致。本文所有結論均以任務級、趨勢級指標表述，"
        "不宣稱部署級測距精度。",
    ),
    ("Header2", "2.5 感測回授式接近與視覺語義操作對照"),
    (
        "Content",
        "非視覺機器人接近控制文獻多結合主動聲學、ToF 或觸覺作 last-meter 感知。"
        "與端到端視覺—語言—動作（VLM）管線相比，本研究不宣稱全任務語義操作，"
        "而聚焦於「已知搜尋走廊內、以超聲特徵驅動之距離趨勢接近」。"
        "此定位與 VLM 粗定位 + 非視覺精接近之 hybrid 架構互補，而非直接取代。",
    ),
    (
        "Content",
        "在狀態估計與 Physical AI 脈絡下，機器人操作常需將感測觀測映射為離散階段標籤（如 near、stop region）。"
        "本研究以隨機化 Sim 協定檢驗：當幾何起點與目標橫向位置變化時，"
        "聲學特徵是否仍含可測量信號，並以 open-loop baseline 對照閉環控制器之區域到達率改善。",
    ),
    ("Header2", "2.6 離線狀態判斷與模擬驗證邊界"),
    (
        "Content",
        "本研究進一步以離線特徵消融檢查 RTX Acoustic 特徵是否含有接近狀態資訊。"
        "比較條件包括：只使用感測特徵、只使用姿態特徵，以及合併所有特徵。"
        "此分析屬趨勢級可行性檢查，目的不是訓練可直接移植到實機的控制策略，"
        "而是判斷感測特徵在隨機化條件下是否仍保有可分類訊號。",
    ),
    ("Header2", "2.7 文獻缺口與本研究定位"),
    (
        "Content",
        "綜合前述各面向，現有文獻多覆蓋子集而非完整交集："
        "Gao 等（2026）雖系統整理 Isaac Sim 平台，但未涵蓋 RTX Acoustic 與工業手臂感測回授接近；"
        "聲學機器人研究多未提供完整的幾何、材質與任務設定紀錄；"
        "VLM 操作研究則少見以 RTX 超音波作 last-meter 非視覺感測回授。"
        "在 UR10e 工業手臂與腕部超音波感測場景下，同時整合上述要素之公開工作仍有限。",
    ),
    (
        "Content",
        "本研究定位為 simulation-based feasibility study（模擬可行性研究）："
        "第一階段檢查感測特徵擷取是否穩定；第二、三階段檢查感測特徵是否能改善接近行為並支援離線狀態判斷；"
        "夾取實驗僅作為下游限制分析，而非本文主貢獻。",
    ),
    (
        "Content",
        "因此，本論文貢獻不在提出新聲學物理模型，而在填補 G0 缺口："
        "建立 UR10 系列、RTX Acoustic Sensor、感測回授接近與離線狀態判斷之可重複模擬流程，"
        "並為後續 CH201 實機任務級驗證保留協定與評估邊界。",
    ),
]

REFERENCES = """Alatise, M. B., & Hancke, G. P. (2020). A review on challenges of autonomous mobile robot and sensor fusion methods. IEEE Access, 8, 39830–39846. https://doi.org/10.1109/ACCESS.2020.2975643

Brinkmann, F., Lindau, A., Weinzierl, S., Geier, M., Spors, S., Wierstorf, H., … Assenmacher, I. (2019). A round robin on room acoustical simulation and auralization. The Journal of the Acoustical Society of America, 145(4), 2744–2760. https://doi.org/10.1121/1.5096178

dEchorate Team. (2021). dEchorate: A calibrated room impulse response dataset for echo-aware signal processing. EURASIP Journal on Audio, Speech, and Music Processing, 2021, 7. https://doi.org/10.1186/s13636-021-00229-0

Dümbgen, F., Wieser, A., & Wieser, A. (2022). Blind as a bat: Audible echolocation on small robots. IEEE Robotics and Automation Letters, 7(4), 9274–9281. https://doi.org/10.1109/LRA.2022.3194669

Gao, S., Pagnucco, M., Bednarz, T., & Song, Y. (2026). NVIDIA Isaac Sim: Enabling scalable, GPU-accelerated simulation for robotics. arXiv:2606.03551. https://doi.org/10.48550/arxiv.2606.03551

GRADE Authors. (2025). Generating realistic and dynamic environments for robotics research with Isaac Sim. The International Journal of Robotics Research. https://doi.org/10.1177/02783649251346211

He, Y., Liang, B., Zou, Y., He, J., & Yang, J. (2019). Recent advances in 3D data acquisition and processing by time-of-flight camera. IEEE Access, 7, 174406–174420. https://doi.org/10.1109/ACCESS.2019.2891693

Höfer, S., Bekris, K., Handa, A., Gamboa, J. C., Mozifian, M., Golemo, F., … Fox, D. (2021). Sim2Real in robotics and automation: Applications and challenges. IEEE Transactions on Automation Science and Engineering, 18(2), 398–400. https://doi.org/10.1109/TASE.2021.3064065

Liu, M., Wang, Y., & Zhao, Q. (2020). Indoor acoustic localization: A survey. Human-centric Computing and Information Sciences, 10, 5. https://doi.org/10.1186/s13673-019-0207-4

Mittal, M., Yu, C., Yu, C., Tang, J., Bo, A., Zhu, J., … Hutter, M. (2023). Orbit: A unified simulation framework for interactive robot learning environments. IEEE Robotics and Automation Letters, 8(6), 3740–3747. https://doi.org/10.1109/LRA.2023.3270034

NVIDIA. (2026a). RTX acoustic sensor. Isaac Sim Documentation. https://docs.isaacsim.omniverse.nvidia.com/latest/sensors/isaacsim_sensors_rtx_acoustic.html

NVIDIA. (2026b). RTX annotators and generic model output. Isaac Sim Documentation. https://docs.isaacsim.omniverse.nvidia.com/6.0.0/sensors/isaacsim_sensors_rtx_annotators.html

NVIDIA. (2026c). RTX sensors overview. Isaac Sim Documentation. https://docs.isaacsim.omniverse.nvidia.com/latest/sensors/isaacsim_sensors_rtx.html

Salimpour, S., Peña-Queralta, J., & Páez-Granados, D. (2025). Sim-to-real transfer of reinforcement learning policies from Isaac Sim to Gazebo and ROS 2. arXiv:2501.02902. https://doi.org/10.48550/arxiv.2501.02902

Scheibler, R., Bevilacqua, E., Holighaus, N., & Dokmanić, I. (2018). PyRoomAcoustics: A Python package for audio room simulation and array processing algorithms. In ICASSP 2018 (pp. 351–355). https://doi.org/10.1109/ICASSP.2018.8461829

Song, J., Zhang, Y., Li, H., & Chen, X. (2025). OceanSim: Underwater robot simulation with Isaac Sim. In 2025 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS) (pp. 1–8). https://doi.org/10.1109/iros60139.2025.11246878

Tsuchiya, A., Kagami, H., & Kagami, H. (2022). Indoor self-localization using multipath arrival time of sound. Japanese Journal of Applied Physics, 61(SG), SG1005. https://doi.org/10.35848/1347-4065/ac506c

Valin, J.-M., Michaud, F., & Rouat, J. (2017). Localization of sound sources in robotics: A review. Robotics and Autonomous Systems, 96, 184–210. https://doi.org/10.1016/j.robot.2017.07.011

Xu, X., Lu, Y., Vogel-Heuser, B., & Wang, L. (2024). Collaborative robotics, digital twins, human–machine interfaces and AI in smart manufacturing: A review. Robotics and Computer-Integrated Manufacturing, 89, 102769. https://doi.org/10.1016/j.rcim.2024.102769

Zhmud, V., Yadykin, A., & Reznikov, B. (2018). Application of ultrasonic sensor for measuring distances in robotics. Journal of Physics: Conference Series, 1015(3), 032189. https://doi.org/10.1088/1742-6596/1015/3/032189

Zhou, Z., Chen, X., Li, Y., & Wang, Y. (2024). Towards building AI-CPS with NVIDIA Isaac Sim for industrial manipulation. In Proceedings of the 2024 ACM/IEEE International Conference on Model-Driven Engineering Software and Systems (MSEC) (pp. 1–8). https://doi.org/10.1145/3639477.3639740

NVIDIA. (2026d). Isaac Lab documentation (v3.0.0-beta2). https://isaac-sim.github.io/IsaacLab/

Rudin, N., Hoeller, D., Reist, P., & Hutter, M. (2022). Learning to walk in minutes using massively parallel deep reinforcement learning. In Proceedings of the 6th Conference on Robot Learning (pp. 604–623).

Schulman, J., Wolski, F., Dhariwal, P., Radford, A., & Klimov, O. (2017). Proximal policy optimization algorithms. arXiv:1707.06347. https://doi.org/10.48550/arXiv.1707.06347"""


def insert_paragraph_after(paragraph: Paragraph, text: str, style: str) -> Paragraph:
    new_p = deepcopy(paragraph._element)
    paragraph._element.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    new_para.style = style
    if new_para.runs:
        for run in new_para.runs:
            run._element.getparent().remove(run._element)
    new_para.add_run(text)
    return new_para


def remove_paragraph(paragraph: Paragraph) -> None:
    element = paragraph._element
    parent = element.getparent()
    parent.remove(element)


def main() -> None:
    doc = Document(str(DOC_PATH))

    # Locate Chapter 2 block: from first 2.x header through last content before Ch.3
    start_idx = None
    end_idx = None
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip()
        if t.startswith("2.1") and p.style.name == "Header2":
            start_idx = i
        if t == "第三章、研究流程與方法" and start_idx is not None:
            end_idx = i
            break

    if start_idx is None or end_idx is None:
        raise RuntimeError(f"Could not locate Chapter 2 block (start={start_idx}, end={end_idx})")

    anchor = doc.paragraphs[start_idx - 1]  # "第二章、文獻探討"
    # Remove old §2.x paragraphs
    for idx in range(end_idx - 1, start_idx - 1, -1):
        remove_paragraph(doc.paragraphs[idx])

    # Insert new content after chapter title
    prev = anchor
    for style, text in CHAPTER2:
        prev = insert_paragraph_after(prev, text, style)

    # Update references
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "參考文獻":
            ref_para = doc.paragraphs[i + 1] if i + 1 < len(doc.paragraphs) else None
            if ref_para is not None:
                ref_para.text = REFERENCES
            break

    doc.save(str(DOC_PATH))
    print(f"Updated {DOC_PATH}")


if __name__ == "__main__":
    main()