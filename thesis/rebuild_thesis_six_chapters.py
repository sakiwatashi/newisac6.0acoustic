#!/usr/bin/env python3
"""Rebuild thesis docx: six chapters, abstract, fig3.1, claim table, cleanup."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.shared import Inches
from docx.text.paragraph import Paragraph

THESIS = Path(__file__).resolve().parent
ROOT = THESIS.parent
DOC = THESIS / "THESIS_DRAFT_FCU_v1.docx"

FIG = {
    "3.1": THESIS / "figures/fig3_1_research_architecture.png",
    "4.1": ROOT / "runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/rtx_amplitude_max_vs_distance.png",
    "4.2": THESIS / "figures/fig4_2_rtx_early_energy_vs_distance.png",
    "4.3": ROOT / "runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/pra_features_vs_distance.png",
    "4.4": THESIS / "figures/fig4_4_material_early_energy_0p5m.png",
    "5.1": ROOT / "runtime/outputs/lab_dynamic_smoke_v1/lab_target_trajectory_xy.png",
    "5.2": ROOT / "runtime/outputs/lab_dynamic_smoke_v1/lab_obs_vs_gt_distance.png",
    "5.3": ROOT / "runtime/outputs/lab_sl_distance_v1/sl_sim_to_lab_pred_vs_gt.png",
    "5.4": ROOT / "runtime/outputs/lab_sl_distance_v1/sl_sim_to_lab_trajectory.png",
}

ABSTRACT_ZH = (
    "本研究從應用電聲角度，探討室內主動聲學回波特徵能否在可控幾何下支撐趨勢級距離推理。"
    "研究平台為 NVIDIA Isaac Sim 6.0 RTX Acoustic，感測器懸掛於 Universal Robots UR10 末端；"
    "實驗採固定 TCP、移動目標設計，於 0.5–3.0 m 範圍進行 6×5 次正式擷取，全部通過驗證（30/30 PASS）。"
    "結果顯示 primary_sgw_early_energy 優於飽和之振幅峰值作為距離代理（Spearman ρ≈−0.66），"
    "且與 PyRoomAcoustics 幾何聲學基線呈趨勢一致（ρ≈+0.66），惟非波形等價。"
    "延伸實驗將同一 Geometry Passport 與特徵工廠接入 Isaac Lab：動態場景 128 steps 觀測中，"
    "early_energy 與 GT 距離 ρ≈−0.48；Sim 靜態標定訓練之線性回歸於 Lab hold-out 達 MAE≈0.41 m、r≈0.47。"
    "in-sim RSL-RL PPO 閉環示範訓練迴路可行，但 hold-out 未優於監督基線（v5 det MAE≈0.44 m）。"
    "本研究貢獻為可審計模擬可行性管線與明確 claim boundary，非部署級測距或波形級數位雙生。"
)

ABSTRACT_EN = (
    "This thesis examines, from an applied electro-acoustics perspective, whether indoor active acoustic echo "
    "features support trend-level distance reasoning under controlled geometry. Using NVIDIA Isaac Sim 6.0 RTX "
    "Acoustic on a UR10 end-effector with a fixed-TCP, moving-target protocol, all 30 formal captures (6 distances "
    "× 5 repeats) passed validation. primary_sgw_early_energy outperformed saturated amplitude peaks as a distance "
    "proxy (Spearman ρ≈−0.66) and trend-matched PyRoomAcoustics (ρ≈+0.66), without waveform equivalence. "
    "The same geometry passport and feature factory were extended in Isaac Lab: dynamic observations showed "
    "ρ≈−0.48 between early energy and ground-truth distance; Sim-trained linear regression achieved MAE≈0.41 m "
    "and r≈0.47 on Lab hold-out. In-simulation RSL-RL PPO demonstrated a feasible closed loop but did not beat "
    "the supervised baseline (v5 det MAE≈0.44 m). The contribution is an auditable feasibility pipeline with "
    "explicit claim boundaries, not deployment-grade ranging or waveform-faithful digital twins."
)

KEYWORDS_ZH = "關鍵詞：室內聲學；RTX Acoustic；signal-way 特徵；early energy；Isaac Sim；可重複性"
KEYWORDS_EN = "Keywords: indoor acoustics; RTX Acoustic; signal-way features; early energy; Isaac Sim; repeatability"

# Import references from build_chapter2_docx
sys.path.insert(0, str(THESIS))
from build_chapter2_docx import CHAPTER2, REFERENCES  # noqa: E402

# Fix Ch2 §2.6 for 電聲學程
CH2_FIXED = []
for item in CHAPTER2:
    if item[0] == "Content" and "智能製造" in item[1]:
        text = item[1].replace("呼應本學程之智能製造脈絡", "呼應電聲與機器人應用交叉之模擬驗證需求")
        text = text.replace("§4.6", "§5.3")
        CH2_FIXED.append((item[0], text))
    elif item[0] == "Content" and "Zhou" in item[1] and "智能製造" in item[1]:
        text = item[1].replace("呼應智能製造數位驗證需求", "支撐機器人應用場景之模擬驗證")
        CH2_FIXED.append((item[0], text))
    else:
        CH2_FIXED.append(item)

CH1 = [
    ("Header1", "第一章、緒論"),
    ("Header2", "1.1 研究背景與問題意識"),
    (
        "Content",
        "室內主動聲學系統中，多徑傳播與殘響使接收信號同時承載幾何、材質與距離資訊，但各分量往往以弱耦合方式呈現於摘要特徵。"
        "在機器人末端非視覺測距應用中，如何從可控實驗條件下擷取可重現之聲學觀測，並據以判斷距離趨勢是否可被辨識，是應用電聲與機器人感知之交叉問題。"
        "NVIDIA Isaac Sim 6.0 提供 RTX Acoustic 實驗性模組，可輸出 Generic Model Output（GMO）signal-way 序列，"
        "為在模擬環境中系統化檢驗上述問題提供工具。",
    ),
    (
        "Content",
        "本研究之核心問題為：在固定 TCP 與可審計幾何／材質條件下，RTX 聲學特徵（尤其 primary_sgw_early_energy）"
        "能否支撐趨勢級距離推理？此問題之答案應以可重複性與跨模型趨勢對照衡量，"
        "而非假設模擬波形等同實機超音波感測器或 CH201 硬體輸出。",
    ),
    ("Header2", "1.2 研究目的與問題陳述"),
    ("Content", "主問題：Isaac Sim 可審計 RTX 聲學擷取管線是否可行且可重現？"),
    ("Content", "子問題一：early energy 等特徵對距離與材質條件之敏感度為何？"),
    ("Content", "子問題二：同一特徵定義能否遷移至 Isaac Lab 動態場景與學習迴路（監督／強化）？"),
    ("Header2", "1.3 研究範圍與限制"),
    (
        "Content",
        "納入：Isaac Sim 6.0 host standalone、官方 UR10、六面牆房間、sensor→target 0.5–3.0 m（6 點）、"
        "材質 A/B/C、30 次正式實驗、Isaac Lab 動態 smoke 與 Sim→Lab 監督學習、in-sim RL 閉環示範。"
        "排除：CH201 實機量測、波形級 RTX–PRA 等價、移動手臂 IK 舊方案。",
    ),
    (
        "Content",
        "限制：模擬 only；單一 TCP 姿態；early_energy 為啟發式（前 25% samples 能量和）；"
        "RTX Acoustic 為 experimental API；6 距離點旨在可行性而非回歸精度飽和。",
    ),
    ("Header2", "1.4 名詞解釋與研究貢獻"),
    (
        "Content",
        "GMO（Generic Model Output）：RTX 聲學感測輸出之結構化訊息，含 signal-way 振幅序列。"
        "Passport：可版本化之幾何／材質實驗護照。trend-level：趨勢級，允許單調相關但不宣稱絕對誤差達部署規格。"
        "claim boundary：可宣稱與不可宣稱之對照邊界（詳表6.1）。",
    ),
    ("Content", "貢獻一（主）：建立 UR10 固定 TCP 下可審計 RTX 聲學管線，完成 30/30 可重複性與 RTX×PRA 趨勢對照。"),
    ("Content", "貢獻二（次）：延伸至 Isaac Lab 動態觀測與 Sim→Lab 監督遷移（r≈0.47，MAE≈0.41 m）。"),
    ("Content", "貢獻三（附）：示範 in-sim RSL-RL 閉環可跑通；未優於監督基線，僅證訓練迴路可行性。"),
]

CH3 = [
    ("Header1", "第三章、研究方法"),
    ("Header2", "3.1 研究架構"),
    (
        "Content",
        "本研究主線為 Isaac Sim 可審計管線（第三、四章）；Isaac Lab 動態觀測與學習示範為延伸（第五章）。"
        "圖3.1 示固態流程：Passport 定義變量 → RTX 擷取 → 特徵工廠 → PRA 趨勢對照 → Sim 主實驗評估；"
        "虛線為同一 Passport／Factory 接入 Lab 之延伸路徑。",
    ),
    ("Image", "3.1", "圖3.1  研究架構（實線：Sim 主線；虛線：Lab 延伸）"),
    ("Header2", "3.2 實驗平台與可重現執行"),
    (
        "Content",
        "Isaac Sim 6.0 host standalone（6.0.0-rc.59），以 scripts/run_host_python.sh 與 env_host_isolated.sh 隔離執行。"
        "機器人為官方 UR10 USD；RTX Acoustic 掛載於 ee_link/official_rtx_acoustic。",
    ),
    ("Header2", "3.3 實驗設計：fixed_tcp_moving_target"),
    (
        "Content",
        "固定 TCP（xy 半徑≈0.816 m、z≈0.65 m），僅移動 8 cm×8 cm×2 cm 目標板；ee_link 運動量 0 m。"
        "距離 waypoints：0.5–3.0 m（6 點）。設計目的為隔離幾何變量，使重複性與趨勢分析可解釋。",
    ),
    ("Header2", "3.4 Geometry Passport 與 Material Passport"),
    (
        "Content",
        "Geometry Passport v1.0：房間 4.5 m×3.0 m×2.8 m、感測器掛載、目標軌跡。"
        "Material Passport v1.0：NonVisualMaterial 條件 A（低吸收）、B（中吸收，主實驗）、C（高吸收）。",
    ),
    ("Header2", "3.5 RTX GMO 擷取與 signal-way 特徵"),
    (
        "Content",
        "以 Replicator Writer 擷取 GMO；timeline.play() 驅動步進。rtx_acoustic_factory.py 驗證結構並解析 signal-way，"
        "萃取 primary_sgw_early_energy（前 25% samples 能量和）、primary_sgw_peak 等。",
    ),
    ("Header2", "3.6 PyRoomAcoustics 趨勢參考協定"),
    (
        "Content",
        "PyRoomAcoustics v0.10.1 批次產生與 Geometry Passport 對齊之 RIR；萃取 RT60、early energy 等。"
        "PRA 僅作趨勢參考，非 RTX 波形 ground truth。",
    ),
    ("Header2", "3.7 評估指標與 claim boundary"),
    (
        "Content",
        "可重複性：30/30 PASS、gmo_valid_rate、跨 repeat CV。趨勢：Spearman ρ（距離／材質）。"
        "延伸：Lab 動態 ρ、Sim→Lab SL 之 MAE／Pearson r、RL hold-out 對照。"
        "全書以表6.1 集中界定可宣稱與不可宣稱項目。",
    ),
]

CH4 = [
    ("Header1", "第四章、Isaac Sim 實證結果與分析"),
    ("Header2", "4.1 可重複性與管線可行性"),
    (
        "Content",
        "正式實驗 30/30 PASS；gmo_valid_rate=1.0；max_ee_motion_m=0。"
        "2.0–3.0 m 區間 amplitude_max 與 early_energy 之跨 repeat CV 近乎 0，顯示擷取管線穩定。",
    ),
    ("Header2", "4.2 距離趨勢與 RTX×PRA 對照"),
    (
        "Content",
        "材質 B、5 repeats 平均：amplitude_max 於 1.0 m 後飽和；primary_sgw_early_energy 與距離 ρ≈−0.66。"
        "RTX 與 PRA early energy 趨勢一致（ρ≈+0.66），振幅尺度不同，屬趨勢級對照。",
    ),
    ("Image", "4.1", "圖4.1  RTX amplitude_max 與目標距離（材質 B）"),
    ("Image", "4.2", "圖4.2  RTX primary_sgw_early_energy 與目標距離（材質 B）"),
    ("Image", "4.3", "圖4.3  PyRoomAcoustics 特徵與目標距離趨勢對照"),
    ("Header2", "4.3 材質敏感度（A/B/C）"),
    (
        "Content",
        "primary_sgw_peak 於 0.5 m 與 3.0 m 幾乎無差；early_energy @0.5 m 可區分 C（≈190.6）與 A/B（≈165.4）。"
        "PRA RT60 對材質吸收更敏感。",
    ),
    ("Image", "4.4", "圖4.4  材質 A/B/C 於 0.5 m 之 early_energy 比較"),
    ("Header2", "4.4 穩健性驗證（P1）"),
    (
        "Content",
        "P1 smoke 驗證 rtx_acoustic_factory 對 GMO 之結構檢查：signal-way 維度、ACOUSTIC 模態、"
        "primary/ref/all peak 一致性與非平坦波形條件。NonVisualMaterial 條件之 NV ID 解碼與 Passport 登錄一致。"
        "P1 確保特徵萃取前資料有效，屬管線穩健性而非獨立物理假設檢驗。",
    ),
]

CH5 = [
    ("Header1", "第五章、Isaac Lab 延伸與學習示範"),
    ("Header2", "5.1 動態環境與觀測協定"),
    (
        "Content",
        "Ur10RtxAcousticDynamicEnv 重用 Sim 之 Passport 與 Factory；目標正弦運動 "
        "d(t)=1.5+0.5·sin(2π·step/64) m，128 steps，GMO decimation=4。觀測含 early_energy、peak、gmo_valid 與 GT 距離。",
    ),
    ("Header2", "5.2 動態觀測結果"),
    (
        "Content",
        "27 步有效 GMO（gmo_valid_rate=1.0）；max_sensor_position_motion_m=0。"
        "primary_sgw_early_energy 與 GT 距離 Pearson ρ=−0.475（n=27），方向與 Sim 一致。",
    ),
    ("Image", "5.1", "圖5.1  動態場景 GT 距離軌跡（1.0–2.0 m）"),
    ("Image", "5.2", "圖5.2  Lab early_energy 與 GT 距離（ρ≈−0.48）"),
    ("Header2", "5.3 Sim→Lab 監督學習"),
    (
        "Content",
        "Sim n=125 訓練單變量線性回歸（early_energy）；Lab n=27 測試：MAE=0.41 m、RMSE=0.52 m、r=0.47。"
        "加入 peak 之雙特徵模型 MAE 升至 0.44 m（peak 飽和）。此為趨勢級示範，非部署精度。",
    ),
    ("Image", "5.3", "圖5.3  Sim 訓練→Lab 測試：預測 vs GT"),
    ("Image", "5.4", "圖5.4  Sim→Lab 預測與 GT 軌跡對照"),
    ("Header2", "5.4 In-sim RSL-RL 閉環示範"),
    (
        "Content",
        "DirectRLEnv + RSL-RL PPO；修正 GMO writer 生命週期後 gmo_init_captured=True。"
        "v3 det MAE=0.115 m 但 pred 近常數（std≈0），低 MAE 部分來自常數預測，非真實追蹤。"
        "v5 塑形獎勵 500 iter：pred 具變異（std≈0.48 m），惟 det MAE=0.441 m、r=0.229，未優於 §5.3 SL（MAE=0.41 m，r=0.47）。",
    ),
    ("TableCaption", "表5.1  In-sim RSL-RL hold-out 評估（64 steps）"),
    (
        "Table",
        ["Run", "Checkpoint", "模式", "MAE(m)", "r(gt,pred)", "pred mean±std(m)"],
        [
            ["long_v3", "model_199", "det", "0.115", "0.335", "1.576±0.000"],
            ["long_v5", "model_499", "det", "0.441", "0.229", "1.637±0.477"],
            ["long_v5", "model_499", "stoch", "0.457", "0.078", "1.559±0.481"],
        ],
    ),
    ("TableCaption", "表5.2  與 §5.3 監督基線對照"),
    (
        "Table",
        ["方法", "MAE (m)", "Pearson r", "備註"],
        [
            ["Sim→Lab 線性 SL", "0.41", "0.47", "主學習基線"],
            ["in-sim PPO v3 det", "0.115", "0.34", "pred 近常數"],
            ["in-sim PPO v5 det", "0.441", "0.229", "有變異，未優於 SL"],
        ],
    ),
]

CH6 = [
    ("Header1", "第六章、結論與建議"),
    ("Header2", "6.1 研究結論"),
    (
        "Content",
        "（1）主貢獻：固定 TCP 下 RTX 聲學擷取管線具高可重複性（30/30），early_energy 為優於 peak 之距離 proxy。"
        "（2）延伸：同一特徵定義可接入 Lab 動態觀測，Sim→Lab SL 達趨勢級追蹤（r≈0.47）。"
        "（3）附錄級：in-sim RL 閉環可跑通，但未在 hold-out 上優於 SL。",
    ),
    ("Header2", "6.2 綜合討論"),
    (
        "Content",
        "電聲觀點：室內多徑使距離資訊主要體現在早期能量之弱趨勢，而非 peak 飽和區。"
        "模擬觀點：RTX 與 PRA 趨勢可對但模型不同，支持以任務級指標（ρ、CV、PASS）論證可行性。"
        "學習觀點：SL 在弱信號下較穩健；RL 低 MAE 需搭配 pred 變異解讀，避免過度宣稱。",
    ),
    ("Header2", "6.3 研究限制與 claim boundary"),
    ("TableCaption", "表6.1  Claim boundary 總表"),
    (
        "Table",
        ["範疇", "可宣稱", "不可宣稱"],
        [
            ["Sim 主實驗", "30/30 可重複；early_energy 趨勢；RTX×PRA 趨勢一致", "波形等價；厘米級測距"],
            ["Lab / SL", "動態觀測可行；Sim→Lab 趨勢遷移 r≈0.47", "MAE 0.41 m 可部署；高 R² 即物理測距"],
            ["in-sim RL", "DirectRLEnv 閉環可跑通；GMO 修正後有效", "優於 SL；v3 低 MAE 即學會測距"],
            ["整體", "可審計可行性管線", "CH201 實機已驗證；數位雙生完成"],
        ],
    ),
    ("Header2", "6.4 後續建議"),
    (
        "Content",
        "建議：（1）CH201 實機 task-level 協定；（2）擴大距離／離軸點位以增加 early_energy 動態；"
        "（3）特徵工程與不確定性量化；（4）以 replication package 支援口試重現。",
    ),
]

TEMPLATE_PAT = re.compile(r"^\(.*標楷體|^\(.*粗體|^\(22,|請在此寫入|目錄頁內文")


def insert_paragraph_after(paragraph: Paragraph, style: str = "Content") -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._element.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    new_para.style = style
    return new_para


def remove_paragraph(paragraph: Paragraph) -> None:
    paragraph._element.getparent().remove(paragraph._element)


def set_text(p: Paragraph, text: str, style: str, center: bool = False) -> None:
    p.style = style
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in p.runs:
        r._element.getparent().remove(r._element)
    if text:
        p.add_run(text)


def paragraph_after_element(parent, element) -> Paragraph:
    after = OxmlElement("w:p")
    element.addnext(after)
    return Paragraph(after, parent)


def append_items(doc: Document, anchor: Paragraph, items: list[tuple[Any, ...]]) -> Paragraph:
    prev = anchor
    for item in items:
        kind = item[0]
        if kind == "Table":
            _, headers, rows = item
            table = doc.add_table(rows=1 + len(rows), cols=len(headers))
            for j, h in enumerate(headers):
                table.rows[0].cells[j].text = h
            for i, row in enumerate(rows, start=1):
                for j, val in enumerate(row):
                    table.rows[i].cells[j].text = val
            prev._element.addnext(table._element)
            prev = paragraph_after_element(prev._parent, table._element)
            continue
        new_p = insert_paragraph_after(prev)
        if kind == "Header1":
            set_text(new_p, item[1], "Header1")
        elif kind == "Header2":
            set_text(new_p, item[1], "Header2")
        elif kind == "Content":
            set_text(new_p, item[1], "Content")
        elif kind == "Image":
            _, key, caption = item
            path = FIG[key]
            new_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            new_p.add_run().add_picture(str(path), width=Inches(5.2))
            cap = insert_paragraph_after(new_p)
            set_text(cap, caption, "Content", center=True)
            prev = cap
            continue
        elif kind == "TableCaption":
            set_text(new_p, item[1], "Content", center=True)
        prev = new_p
    return prev


def cleanup_front_matter(doc: Document) -> None:
    to_remove = []
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip()
        if TEMPLATE_PAT.search(t) or t in ("(20, 粗體, 置中, 字與字之間空一字元)",):
            to_remove.append(i)
    for i in reversed(to_remove):
        remove_paragraph(doc.paragraphs[i])

    for p in doc.paragraphs:
        t = p.text.strip()
        if t.startswith("本研究評估") or t.startswith("本研究從應用電聲"):
            set_text(p, ABSTRACT_ZH, "Normal")
        elif t.startswith("This study evaluates") or t.startswith("This thesis examines"):
            set_text(p, ABSTRACT_EN, "Normal")
        elif t.startswith("關鍵詞："):
            set_text(p, KEYWORDS_ZH, "Normal")
        elif t.startswith("Keywords:"):
            set_text(p, KEYWORDS_EN, "Normal")
        elif t == "指導教授：蔡鈺鼎 教授":
            # add student line after advisor if missing
            pass

    has_student = any("研究生" in p.text for p in doc.paragraphs)
    if not has_student:
        for p in doc.paragraphs:
            if p.text.strip() == "指導教授：蔡鈺鼎 教授":
                sp = insert_paragraph_after(p, "Normal")
                set_text(sp, "研究生：（請填入姓名）", "Normal")
                break


def replace_body(doc: Document) -> None:
    start = end = None
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip()
        if t == "第一章、緒論" and start is None:
            start = i
        if t == "參考文獻" and start is not None:
            end = i
            break
    if start is None or end is None:
        raise RuntimeError("Cannot find body block")

    anchor = doc.paragraphs[start - 1] if start > 0 else doc.paragraphs[0]
    for idx in range(end - 1, start - 1, -1):
        remove_paragraph(doc.paragraphs[idx])

    body = CH1 + [("Header1", "第二章、文獻探討")] + CH2_FIXED + CH3 + CH4 + CH5 + CH6
    append_items(doc, anchor, body)

    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "參考文獻":
            nxt = doc.paragraphs[i + 1] if i + 1 < len(doc.paragraphs) else None
            if nxt is not None:
                set_text(nxt, REFERENCES, "Content")
            break


def ensure_figures() -> None:
    subprocess.run([sys.executable, str(THESIS / "generate_thesis_figures.py")], check=True)
    subprocess.run([sys.executable, str(THESIS / "generate_fig31.py")], check=True)
    for k, p in FIG.items():
        if not p.exists():
            raise FileNotFoundError(f"Missing figure {k}: {p}")


def main() -> None:
    ensure_figures()
    doc = Document(str(DOC))
    cleanup_front_matter(doc)
    replace_body(doc)
    doc.save(str(DOC))
    print(f"Rebuilt six-chapter thesis: {DOC}")


if __name__ == "__main__":
    main()