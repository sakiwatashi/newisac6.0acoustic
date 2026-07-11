#!/usr/bin/env python3
"""Rebuild thesis docx (V2): six chapters aligned with 論文敘事對齊_V2_2026-07-09.md.

Reads THESIS_DRAFT_FCU_v1.docx (never modified) and writes a new
THESIS_DRAFT_FCU_v2.docx. Mechanism (helper functions, Content list format)
is copied from rebuild_thesis_six_chapters.py; that script and the v1 docx
are read-only inputs and are never touched by this script.

All quantitative claims below are sourced from:
  - docs/plan_v2/reports/S1_envelope_report.md
  - docs/plan_v2/reports/S2_datasheet_report.md
  - docs/plan_v2/reports/D1_approach_report.md
  - docs/plan_v2/reports/D15_arm_approach_report.md
  - docs/handoff/E3_target_invisibility_and_v9_audit.md
  - docs/WPM_EXPERIMENT_RULES.md
No number is invented here.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

THESIS = Path(__file__).resolve().parent
ROOT = THESIS.parent
DOC_IN = THESIS / "THESIS_DRAFT_FCU_v1.docx"
DOC_OUT = THESIS / "THESIS_DRAFT_FCU_v2.docx"

FIG: dict[str, Path] = {}  # V2 introduces no new figures; Image items unused.

sys.path.insert(0, str(THESIS))
from build_chapter2_docx import CHAPTER2, REFERENCES  # noqa: E402

# ---------------------------------------------------------------------------
# Front matter: abstract / keywords (V2 narrative)
# ---------------------------------------------------------------------------

ABSTRACT_ZH = (
    "本研究在 NVIDIA Isaac Sim 6.0 之 RTX Acoustic 超音波模擬環境中，建立並驗證一套"
    "「包絡優先」之感測回授接近方法：先量測感測器在何種幾何條件下讀得到目標，"
    "再將機械手臂任務設計於已驗證之可感測包絡內。"
    "首先以 52 格「配對移除」掃描（同場景有目標與移除目標之成對量測）界定可偵測幾何包絡"
    "（36/52 可偵測；指向為主宰因子；感測器後方手臂之背景貢獻精確為零），並建立感測器量化特性"
    "（距離估計方法：取多影格平均回波波形之峰值位置，經已知距離迴歸自校之線性模型換算為距離；"
    "距離編碼之皮爾森相關係數 r=0.9994；桌面高度目標之均方根誤差（RMSE）5.3 mm；"
    "樣本週期自校 103 µs；跨模擬工作階段（session）重複性逐位相同）。"
    "在此包絡內，以三臂配對對照設計（聲學閉環／估距置換之盲走消融／無量測固定行程之開環，"
    "同種子同目標組）驗證：不讀取任何目標世界座標之純聲學控制迴路，"
    "可驅動 UR10e 機械手臂接近隨機擺放之桌面目標——主結果為停止位置與目標位置相關 r=0.9856、"
    "停止誤差 RMSE 2.8 cm、30/30 全數由聲學觸發停止，且 90 個試驗回合（episode）之姿態稽核零違規；"
    "盲走消融組於同一管線完全失能，確認接近行為之因果來自聲學資訊而非幾何巧合。"
    "在接近能力之基礎上，本研究進一步完成端到端夾取整合：機械手臂以聲學估距決定夾取位置，"
    "夾取中心與目標位置之相關係數 r=0.9885、對位（夾爪中心與目標中心之幾何吻合）誤差 RMSE 1.9 cm，"
    "對位成功率 60% 顯著優於盲走對照之 23%（費雪精確檢定，適用小樣本之精確機率檢定，p=0.004），"
    "對位成功後之附著升舉成功率為 83%（夾持以接觸觸發之固定關節模擬，接觸偵測為物理訊號）。"
    "側向感知方面，本研究以四項獨立實驗證實現行感測器輸出不含左右方向資訊（能量差、時間差、"
    "身分欄位、接收器分組四路皆證偽），並提出以手臂運動合成多視點之多點定位演算法作為替代："
    "自 5 個量測位置之距離交會解算目標二維座標，側向估計相關係數 r=0.960、誤差 RMSE 3.4 cm，"
    "證實側向資訊可經演算法自單軸測距恢復。"
    "研究範圍限於單一隨機種子（seed）、確定性模擬；物理摩擦夾持與實機驗證列為未來工作。"
)

ABSTRACT_EN = (
    "This thesis develops and validates an envelope-first methodology for ultrasonic sensor-feedback "
    "robotic approach in NVIDIA Isaac Sim 6.0 with the RTX Acoustic module: the sensor's detectable "
    "geometry is measured before any robot task is designed inside the validated envelope. A 52-cell "
    "paired-removal scan first maps detectability (36/52 detectable; boresight pointing dominates; the "
    "arm's background contribution behind the sensor is exactly zero), followed by a quantitative sensor "
    "datasheet (distance encoding r=0.9994; tabletop-height target RMSE 5.3 mm; self-calibrated sample "
    "period 103 µs; bit-identical repeatability across sessions). Within this envelope, a three-arm "
    "paired design (closed acoustic / blind range-substitution ablation / open fixed-stroke, matched "
    "seeds and targets) shows that a purely acoustic control loop reading no target world coordinates "
    "can drive a UR10e manipulator toward randomly placed tabletop targets: the arm-mounted main result "
    "reaches a stop-position-to-target correlation of r=0.9856 with RMSE 2.8 cm, 30/30 episodes stopped "
    "by the acoustic trigger, and zero posture-audit violations across 90 episodes, while the blind "
    "ablation fails completely on the identical pipeline — establishing acoustic information, not "
    "geometric coincidence, as the cause. "
    "Building on the approach capability, an end-to-end grasp integration is completed: the manipulator "
    "places its grasp from acoustic range estimates alone, reaching a grasp-center-to-target correlation "
    "of r=0.9885 (alignment RMSE 1.9 cm), a 60% alignment rate versus 23% for the blind ablation "
    "(Fisher's exact test, p=0.004), and an 83% attach-and-lift rate given alignment (grasp attachment is "
    "simulated by a contact-triggered fixed joint; contact detection is a physics signal). For lateral "
    "sensing, four independent experiments show the sensor output carries no left-right information "
    "(energy, timing, identity fields, and receiver grouping all falsified); a motion-synthesized "
    "multilateration algorithm recovers 2-D target position from five vantage-point ranges instead "
    "(lateral r=0.960, RMSE 3.4 cm). Scope is limited to a single simulation seed and a deterministic "
    "engine; physical friction grasping and hardware validation remain future work."
)

KEYWORDS_ZH = "關鍵詞：RTX Acoustic；感測包絡；聲學閉環接近；資訊消融對照；實驗效度設計；Isaac Sim"
KEYWORDS_EN = (
    "Keywords: RTX Acoustic; sensing envelope; acoustic closed-loop approach; "
    "ablation control; experimental validity design; Isaac Sim"
)

# ---------------------------------------------------------------------------
# Chapter 2: reused verbatim from build_chapter2_docx (no changes per spec)
# ---------------------------------------------------------------------------

CH2_FIXED = list(CHAPTER2)
# 首次出現術語就地加註(僅改本腳本之副本,不動 build_chapter2_docx.py 原文):
# CH2 之「固定 TCP」先於第四章之全稱解釋出現,於此補全稱。
CH2_FIXED = [
    (item[0], item[1].replace("在固定 TCP 幾何下", "在固定工具中心點（Tool Center Point, TCP）幾何下", 1))
    if len(item) >= 2 and isinstance(item[1], str) and "在固定 TCP 幾何下" in item[1]
    else item
    for item in CH2_FIXED
]
# 「審計」一詞在全文最終檢查中須為 0（見任務規格）；CH2 之「可審計變量」與已移除之
# 舊管線審計敘事無關（純粹指「可稽核之變量」），僅換用同義詞避免誤判，不動原文語意。
CH2_FIXED = [
    (item[0], item[1].replace("列為可審計變量", "列為可稽核變量", 1))
    if len(item) >= 2 and isinstance(item[1], str) and "列為可審計變量" in item[1]
    else item
    for item in CH2_FIXED
]

# 2026-07-10 逐節審查(用戶要求:字數過少之節擴寫、舊敘事殘句更新、名詞白話化;
# 僅改本腳本之 CH2 副本,不動 build_chapter2_docx.py 原文):

# 2.3(原 146 字)追加白話解釋段
_EXP_23 = (
    "所謂多路徑（multipath），指聲波自發射器出發後，除了「直達目標、反射回來」這一條最短路徑外，"
    "還會經由牆面、桌面等其他表面多次反彈後抵達接收器；殘響（reverberation）則是這些較晚抵達之"
    "回波在時間上疊加拖尾之現象。兩者使接收波形中同時混雜多種幾何來源之訊號，"
    "單看波形上之一個峰值並不足以斷定其對應之物理路徑。"
    "基於此，本研究採取保守之量測立場：不宣稱模擬波形具備與實體量測相同之絕對精度，"
    "而是以「配對移除」（同場景下有目標與移除目標之成對量測，兩者之差即為目標本身之貢獻）"
    "隔離目標訊號，並以趨勢性指標（峰值位置隨距離之線性關係）而非單點絕對值建立距離編碼；"
    "完整之量測程序與稽核設計見第三章。"
)
CH2_FIXED = [
    (item[0], item[1] + _EXP_23)
    if len(item) >= 2 and isinstance(item[1], str) and "特徵定義與擷取流程見第三章" in item[1]
    else item
    for item in CH2_FIXED
]

# 2.4(原 374 字)追加:光線追蹤式聲學與參數化模型之差異白話版
_EXP_24 = (
    "此處值得以白話說明兩類模擬取徑之差異：參數化模型以數學公式直接產生「看起來合理」之回波"
    "（例如依距離套用固定之衰減曲線），計算快速但對場景中實際擺放之物體不敏感——"
    "目標移動了、模擬輸出卻可能不變；光線追蹤式模型則實際追蹤聲波與場景幾何（目標、桌面、手臂連桿）"
    "之碰撞與反射路徑，因此輸出會隨物體之位置、大小、角度而變化。"
    "唯有後者，「量測感測器在什麼幾何下讀得到目標」這一問題才有意義——"
    "此為本研究選用 RTX Acoustic 之核心理由，亦是第四章感測包絡量測之技術前提。"
)
CH2_FIXED = [
    (item[0], item[1] + _EXP_24)
    if len(item) >= 2 and isinstance(item[1], str)
       and "用來檢驗感測回授接近與離線狀態判斷是否可行" in item[1]
    else item
    for item in CH2_FIXED
]

# 2.5 第一段(原 150 字)追加:VLM 白話
_EXP_25A = (
    "此處之視覺語言模型（Vision-Language Model, VLM）指同時理解影像與自然語言之大型神經網路模型，"
    "其強項在於「理解場景中有什麼、大致在哪裡」之語義層次；"
    "但其空間定位精度受影像解析度與訓練資料限制，且在低照度、反光或遮蔽下失效。"
    "本研究之超音波感測回授恰好補足此弱點：不依賴光學條件、對「已知方向上之距離」提供公分級之連續回授。"
    "兩者組成之階層式架構中，語義理解與精細接近各司其職，此為本研究「互補而非取代」定位之具體含義。"
)
CH2_FIXED = [
    (item[0], item[1] + _EXP_25A)
    if len(item) >= 2 and isinstance(item[1], str) and "hybrid 架構互補，而非直接取代" in item[1]
    else item
    for item in CH2_FIXED
]

# 2.5 第二段(原 150 字,含過時敘事)整段改寫
_NEW_25B = (
    "在狀態估計脈絡下，機器人操作常需將連續之感測觀測映射為離散之任務狀態"
    "（例如「目標存在與否」「已進入可夾取範圍與否」），再由狀態驅動行為決策。"
    "本研究對此脈絡之立場是：狀態判斷之前提是感測訊號確實含有對應資訊，"
    "故本文先以第四章之包絡量測與第五章之消融對照確立「訊號中有什麼、沒有什麼」"
    "（距離趨勢存在、單次量測之側向資訊不存在），"
    "將學習式狀態估計留待此一因果地基確立之後（第六章未來工作），"
    "避免在訊號是否含資訊尚屬未知時即投入模型訓練、產生難以歸因之結果。"
)
CH2_FIXED = [
    (item[0], _NEW_25B)
    if len(item) >= 2 and isinstance(item[1], str) and "在狀態估計與 Physical AI 脈絡下" in item[1]
    else item
    for item in CH2_FIXED
]

# 2.6(原 133 字,含過時敘事)整段改寫並擴寫
_NEW_26 = (
    "模擬驗證有其明確之能與不能，本研究對此採取「邊界先行」之立場。"
    "模擬環境之獨特價值在於變因之完全可控與量測之完全可重現："
    "研究者可以精確地只移動一個物體、只改變一個角度，並取得逐位元可重複之量測結果，"
    "這使得「拿掉某一項資訊、觀察系統是否失能」之消融式因果檢驗得以嚴格執行——"
    "此類檢驗在實體環境中因雜訊與不可重現性而難以達到相同之嚴格程度。"
    "反之，模擬結論之效力邊界亦須明確劃定：本研究之確定性引擎不含實體感測器之熱雜訊與元件變異，"
    "亦不對頻率相關之聲學物理完整建模（詳見第四章之負結果記錄），"
    "故所有結論皆明確標註為模擬環境內之因果驗證，"
    "其對實體系統之可移轉性須另經實機實驗確認（第六章）。"
    "本文第六章之「可宣稱與不可宣稱範圍界定」即為此一立場之系統性落實。"
)
CH2_FIXED = [
    (item[0], _NEW_26)
    if len(item) >= 2 and isinstance(item[1], str) and "本研究進一步以離線特徵消融檢查" in item[1]
    else item
    for item in CH2_FIXED
]

# ---------------------------------------------------------------------------
# References: numeric citation style (advisor request). REFERENCES (imported
# from build_chapter2_docx) is a single string with entries separated by a
# blank line. We parse entries, sort by (year asc, first-author surname),
# number them [1..N], and rewrite in-text "Surname 等（YYYY）" / "（Author,
# YYYY）" citations to "Surname 等 [n]" / "[n]". No entry text is altered
# beyond prefixing "[n] "; the blank-line separation used by replace_body's
# write mechanism is preserved.
# ---------------------------------------------------------------------------

import re as _re


def _parse_reference_entries(refs: str) -> list[str]:
    return [e.strip() for e in refs.split("\n\n") if e.strip()]


def _ref_author_surname(entry: str) -> str:
    author_seg = entry.split("(")[0].strip(" .,")
    return author_seg.split(",")[0].strip()


def _ref_year_suffix(entry: str) -> str:
    m = _re.search(r"\((\d{4}[a-z]?)\)", entry)
    return m.group(1) if m else ""


def _ref_year_int(entry: str) -> int:
    m = _re.search(r"\((\d{4})", entry)
    return int(m.group(1)) if m else 9999


def _ref_sort_key(entry: str) -> tuple[int, str, str]:
    return (_ref_year_int(entry), _ref_author_surname(entry).lower(), _ref_year_suffix(entry))


# 2026-07-11 新增 3 筆(第二章新增 2.7 節之文獻依據;作者/年份/出處均經檢索核實):
REFERENCES = REFERENCES + "\n\n" + "\n\n".join([
    "Kerstens, R., Laurijssen, D., & Steckel, J. (2019). eRTIS: A fully embedded real time 3D "
    "imaging sonar sensor for robotic applications. In 2019 International Conference on Robotics "
    "and Automation (ICRA) (pp. 1438\u20131443). IEEE.",
    "Hayes, M. P., & Gough, P. T. (2009). Synthetic aperture sonar: A review of current status. "
    "IEEE Journal of Oceanic Engineering, 34(3), 207\u2013224.",
    "Kapoor, R., Ramasamy, S., Gardi, A., Bieber, C., Silverberg, L., & Sabatini, R. (2016). "
    "A novel 3D multilateration sensor using distributed ultrasonic beacons for indoor navigation. "
    "Sensors, 16(10), 1637. https://doi.org/10.3390/s16101637",
])

_REF_ENTRIES = _parse_reference_entries(REFERENCES)
_REF_ENTRIES_SORTED = sorted(_REF_ENTRIES, key=_ref_sort_key)
_REF_NUMBER: dict[str, int] = {e: i for i, e in enumerate(_REF_ENTRIES_SORTED, start=1)}

REFERENCES_NUMBERED = "\n\n".join(f"[{_REF_NUMBER[e]}] {e}" for e in _REF_ENTRIES_SORTED)

# (surname_lower, "YYYY" or "YYYYa") -> number, for citations that include a
# disambiguating letter suffix (e.g. NVIDIA, 2026a).
_CITATION_LOOKUP: dict[tuple[str, str], int] = {}
# (surname_lower, year_int) -> list of candidate entries, to detect and warn
# on genuine ambiguity (same surname + same bare year, multiple references).
_BARE_YEAR_GROUPS: dict[tuple[str, int], list[str]] = {}
for _entry in _REF_ENTRIES_SORTED:
    _surname_full = _ref_author_surname(_entry)
    # Register both the full first-author segment ("GRADE Authors") and its
    # first whitespace token ("GRADE") as lookup keys: some in-text citations
    # abbreviate a group name to its first word (e.g. "（GRADE, 2025）" citing
    # "GRADE Authors. (2025)").
    _surname_keys = {_surname_full.lower(), _surname_full.split()[0].lower()}
    _yr_suffix = _ref_year_suffix(_entry)
    _yr_int = _ref_year_int(_entry)
    for _surname_l in _surname_keys:
        if _yr_suffix:
            _CITATION_LOOKUP[(_surname_l, _yr_suffix)] = _REF_NUMBER[_entry]
        _BARE_YEAR_GROUPS.setdefault((_surname_l, _yr_int), []).append(_entry)
        _bare_key = (_surname_l, str(_yr_int))
        _CITATION_LOOKUP.setdefault(_bare_key, _REF_NUMBER[_entry])

_CITATION_AMBIGUOUS: set[tuple[str, int]] = {
    k for k, v in _BARE_YEAR_GROUPS.items() if len(v) > 1
}

_CITATION_STATS = {"pattern1": 0, "pattern2": 0, "unresolved": []}

_PAT1 = _re.compile(r"([A-Za-zÀ-ÖØ-öø-ÿ]+)\s?(等)?（(\d{4}[a-z]?)）")
# Parenthetical citations: "（Author, YYYY）" and "（Author 等, YYYY）" (the
# author/等/year are all inside the full-width parens together, as opposed to
# _PAT1 where only the year is parenthesized).
_PAT2 = _re.compile(r"（([A-Za-zÀ-ÖØ-öø-ÿ]+)\s?(?:等)?, ?(\d{4}[a-z]?)）")


def _resolve_citation(surname: str, year: str) -> int | None:
    key = (surname.lower(), year)
    if key in _CITATION_LOOKUP:
        # Guard against a bare-year lookup landing on an ambiguous group.
        if not year[-1].isalpha() and (surname.lower(), int(year)) in _CITATION_AMBIGUOUS:
            return None
        return _CITATION_LOOKUP[key]
    return None


def _replace_citations_in_text(text: str) -> str:
    def _sub1(m: _re.Match) -> str:
        surname, deng, year = m.group(1), m.group(2), m.group(3)
        num = _resolve_citation(surname, year)
        if num is None:
            _CITATION_STATS["unresolved"].append(m.group(0))
            print(f"WARNING: could not map citation to a reference entry: {m.group(0)!r}")
            return m.group(0)
        _CITATION_STATS["pattern1"] += 1
        return f"{surname} 等 [{num}]" if deng else f"{surname} [{num}]"

    def _sub2(m: _re.Match) -> str:
        surname, year = m.group(1), m.group(2)
        num = _resolve_citation(surname, year)
        if num is None:
            _CITATION_STATS["unresolved"].append(m.group(0))
            print(f"WARNING: could not map citation to a reference entry: {m.group(0)!r}")
            return m.group(0)
        _CITATION_STATS["pattern2"] += 1
        return f"[{num}]"

    text = _PAT1.sub(_sub1, text)
    text = _PAT2.sub(_sub2, text)
    return text


def _replace_citations_in_items(items: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    new_items = []
    for item in items:
        kind = item[0]
        if kind == "Table":
            _, headers, rows = item
            new_rows = [[_replace_citations_in_text(c) for c in row] for row in rows]
            new_items.append((kind, headers, new_rows))
        elif len(item) >= 2 and isinstance(item[1], str):
            new_items.append((item[0], _replace_citations_in_text(item[1]), *item[2:]))
        else:
            new_items.append(item)
    return new_items


CH2_FIXED = _replace_citations_in_items(CH2_FIXED)


def _insert_after_containing(items: list, needle: str, new_items: list) -> list:
    """Splice new_items into items, right after the first item whose text
    contains `needle`. Raises if no match (fail loud rather than silently
    dropping content in the wrong place)."""
    out = list(items)
    for idx, it in enumerate(out):
        if len(it) >= 2 and isinstance(it[1], str) and needle in it[1]:
            return out[: idx + 1] + list(new_items) + out[idx + 1 :]
    raise RuntimeError(f"anchor text not found in items: {needle!r}")


# 補充引用(第二章原文未涵蓋之 11 篇參考文獻,依主題插入既有小節內):
CH2_FIXED = _insert_after_containing(
    CH2_FIXED,
    "與 Isaac Sim RTX Acoustic 之主動聲學模擬屬同一技術族",
    [
        (
            "Content",
            "聲源與距離定位之機器人文獻脈絡更廣。Valin 等（2017）系統性回顧機器人聲源定位方法，"
            "指出陣列幾何、多路徑與殘響為距離與方位估計之共同挑戰；"
            "Tsuchiya 等（2022）進一步以室內多路徑到達時間實現無地圖自我定位，"
            "顯示即使在強反射室內環境，時間域到達資訊仍可萃取空間資訊。"
            "此二文獻共同支持本研究以「配對移除」量測分離目標回波與場景背景多路徑之設計動機。",
        ),
    ],
)
CH2_FIXED = _insert_after_containing(
    CH2_FIXED,
    "不宜假設模擬信號與實機波形等價",
    [
        (
            "Content",
            "模擬平台之另一價值在於支援大規模強化學習訓練。Rudin 等（2022）展示以 GPU 大量並行模擬"
            "（數千環境同時執行）可將四足機器人行走策略之訓練時間縮短至數分鐘，"
            "此類大規模並行能力所依託之 GPU 加速模擬架構與 Isaac Sim 同源；"
            "策略最佳化演算法方面，Schulman 等（2017）提出之近端策略最佳化"
            "（Proximal Policy Optimization, PPO）為現行機器人強化學習之主流方法之一。"
            "本研究現行控制器為規則式比例步進控制，未涉及學習型策略；"
            "上述基礎設施顯示：若後續以強化學習取代規則式控制器，"
            "Isaac Sim／Isaac Lab 之 GPU 並行模擬能力已提供可行路徑（詳見第六章未來工作）。",
        ),
    ],
)
CH2_FIXED = _insert_after_containing(
    CH2_FIXED,
    "以早期能量等摘要特徵檢驗「距離趨勢是否可用於感測回授」",
    [
        (
            "Content",
            "室內聲學模擬之驗證方法學方面，Brinkmann 等（2019）之跨實驗室輪測（round-robin）"
            "比較多套房間聲學模擬工具，發現不同幾何聲學引擎對早期反射與殘響時間之預測存在系統性差異，"
            "凸顯「模擬—實機」比對須謹慎詮釋，不宜視為等價。"
            "Scheibler 等（2018）之 PyRoomAcoustics 為公開之房間聲學模擬與陣列訊號處理工具，"
            "提供影像來源法（image-source method）之開放實作；"
            "dEchorate 等（2021）建立之資料集則提供已校正之房間脈衝響應，供回聲感知演算法之基準測試。"
            "此三項工作共同顯示：房間聲學模擬之保真度評估已有成熟方法學基礎，"
            "然多聚焦於固定陣列之訊號處理，較少涵蓋機械手臂載具下之動態幾何場景——"
            "此為本研究以配對移除協定系統性量測動態場景可偵測度之切入點。",
        ),
    ],
)

# Re-run numeric-citation replacement: the three insertions above were
# spliced in AFTER CH2_FIXED's first replacement pass (line ~237), so their
# "Surname 等（YYYY）" citations were never converted. Re-running is safe/
# idempotent — already-converted "Surname 等 [n]" text does not match the
# author-year regex again.
# 2026-07-11 新增 2.7 節:聲學陣列、多點定位與合成孔徑(本文第五、六章之
# 側向感知與多點定位內容此前於文獻章無對應;插於 2.6 之後、原 2.7 之前):
CH2_FIXED = _insert_after_containing(
    CH2_FIXED,
    "即為此一立場之系統性落實",
    [
        ("Header2", "2.7 聲學陣列、多點定位與合成孔徑"),
        (
            "Content",
            "單一收發器之超音波感測僅能量測「指向方向上之距離」，無法分辨目標之左右方位；"
            "文獻對此提供兩大類解法。第一類為多元件陣列：以多個接收器同時接收回波，"
            "利用各接收器間之到達時間差或波束成形（beamforming，將多路訊號依幾何延遲相加以合成指向性）"
            "解算方位。Kerstens 等（2019）之嵌入式即時三維成像聲納即為此路線之代表，"
            "以麥克風陣列在空氣中實現三維超音波成像，其研究群並發展出受蝙蝠迴聲定位啟發之一系列仿生聲納系統。"
            "此路線之前提是各接收器之訊號可被獨立取得——本研究第四章之負結果顯示，"
            "現行模擬引擎之輸出不區分接收器身分，故此路線於本研究之模擬環境中不可行，"
            "此為本研究轉向第二類解法之直接原因。",
        ),
        (
            "Content",
            "第二類解法不依賴多接收器，而是以「多個量測位置」取代「多個接收器」："
            "多點定位（multilateration）自多個已知位置分別量測與目標之距離，以幾何交會解算目標座標，"
            "Kapoor 等（2016）以分佈式超音波信標實現室內三維定位即為典型應用；"
            "合成孔徑（synthetic aperture）則更進一步，讓單一感測器在移動中連續量測，"
            "等效合成一具大孔徑陣列，Hayes 等（2009）對此技術在聲納領域之發展有系統性回顧。"
            "本研究第五章之側向定位方案屬此一族系：以機械手臂本身作為感測器之移動平台，"
            "自五個橫向錯開之量測位置各取一次距離，以最小平方交會解算目標之二維座標——"
            "相較於信標方案需在環境中預先佈設多個發射器，"
            "本研究之方案僅需手臂既有之運動自由度，不增加任何硬體元件。",
        ),
    ],
)
CH2_FIXED = [
    (item[0], item[1].replace("2.7 文獻缺口與本研究定位", "2.8 文獻缺口與本研究定位", 1))
    if len(item) >= 2 and isinstance(item[1], str) and item[1].startswith("2.7 文獻缺口")
    else item
    for item in CH2_FIXED
]
CH2_FIXED = _replace_citations_in_items(CH2_FIXED)

# ---------------------------------------------------------------------------
# Chapter 1
# ---------------------------------------------------------------------------

CH1 = [
    ("Header1", "第一章、緒論"),
    ("Header2", "1.1 研究背景與問題意識"),
    (
        "Content",
        "協作機器人與工業手臂之應用場景日益要求人機共融與彈性佈署，"
        "Xu 等（2024）之綜述指出，數位孿生、人機介面與人工智慧之整合已成為智慧製造之共同趨勢，"
        "而其中末端感測之穩健性——尤其在遮蔽、反光或動態變化之近距工作空間——仍是限制彈性佈署之關鍵瓶頸。"
        "室內主動聲學系統中，多徑傳播（multipath，聲波經牆面等表面多次反彈後抵達接收器之傳播現象）"
        "與殘響（較晚抵達之回波在時間上疊加拖尾）使接收信號同時承載幾何、材質與距離資訊，"
        "此一特性既是超音波測距之挑戰，也是其相對相機與雷射感測之互補優勢："
        "超音波不受光學反光、低照度或煙塵遮蔽影響，且感測硬體成本低廉。",
    ),
    (
        "Content",
        "在機器人末端非視覺 last-meter 接近中，如何從可控模擬條件擷取可重現聲學觀測，"
        "並據以驅動閉環運動，是應用電聲與機器人感知之交叉問題。"
        "NVIDIA Isaac Sim 6.0 提供 RTX Acoustic 實驗性模組，可輸出 Generic Model Output（GMO）資料，"
        "其以「信號路徑」（signal way，單一發射器—接收器組合之回波時間序列）為單位紀錄振幅樣本，"
        "為系統化檢驗上述問題提供工具。相較於實體超音波晶片（如 TDK CH201）之量測需搭配實體場地與硬體，"
        "模擬環境可精確控制幾何、材質與感測器擺位等變因，使因果關係得以被系統性隔離與驗證——"
        "這正是本研究選擇以模擬為主要驗證場域之核心理由。",
    ),
    (
        "Content",
        "與相機 + 視覺語言模型（VLM）端到端操作相比，本研究聚焦非視覺超聲閉環接近，"
        "定位為互補而非取代：VLM 擅長語義理解與粗定位，超聲擅長已知搜尋走廊內之距離趨勢接近，"
        "兩者可組成階層式架構——VLM 負責場景理解與大範圍導航，超聲負責最後一段之非視覺精細接近。"
        "本研究不宣稱取代視覺方案，而是為此類混合架構提供一段可驗證、可量化效度之非視覺感測回授元件。",
    ),
    ("Header2", "1.2 研究目的與問題陳述"),
    (
        "Content",
        "本研究以下列四項研究問題（Research Question, RQ）組織全文之實驗設計與驗證邏輯，"
        "各問題對應獨立之實驗與預先寫定之通過判準，避免以事後詮釋合理化任意結果。",
    ),
    (
        "Content",
        "RQ1（感測包絡）：超音波感測器在何種感測器—目標幾何下能穩定偵測目標，其包絡邊界為何？"
        "此問題之動機在於：若不先界定感測器之可偵測範圍，後續任何機器人任務設計皆建立在未經驗證之假設上，"
        "一旦感測失敗，難以判斷根因是控制策略不當，抑或感測器本身在該幾何下即無法擷取有效訊號。",
    ),
    (
        "Content",
        "RQ2（聲學閉環接近）：不讀取目標世界座標之純聲學控制迴路，能否驅動機械手臂接近隨機擺放目標，"
        "且其因果可經資訊消融對照（盲走失能）證實來自聲學？"
        "此為本研究之核心問題：僅有「接近成功」不足以構成因果證據，唯有透過刻意拿掉感測資訊之對照組"
        "仍然失能，方能排除成功來自場景幾何本身之混淆。",
    ),
    (
        "Content",
        "RQ3（實驗效度）：如何以實驗設計確保閉環宣稱之效度——排除成功來自場景幾何或隱含目標資訊之可能？"
        "此問題涉及研究方法本身之嚴謹性，答案並非單一統計檢定，而是一套組合式之對照與稽核設計（詳見第三章）。",
    ),
    (
        "Content",
        "RQ4（範圍邊界）：夾取整合與側向定位之可行邊界為何？"
        "本研究對此問題給出兩項實證答案：夾取整合部分，聲學對位能力已驗證成立，"
        "而夾爪之物理摩擦夾持受模擬器保真度限制，以接觸觸發之附著機制替代並如實標註；"
        "側向定位部分，感測器原生輸出經四項獨立實驗證偽後，"
        "改以手臂運動合成多視點之演算法路徑恢復側向資訊並驗證可行。"
        "兩項答案共同界定本文之誠實限制與未來工作方向。",
    ),
    ("Header2", "1.3 研究範圍與限制"),
    (
        "Content",
        "本研究之實驗範圍分為四個階段，逐層遞進、互相驗證。"
        "納入項目包括：Isaac Sim 6.0 本機獨立執行版（host standalone）、UR10e 官方機械手臂資產、"
        "感測包絡地圖（實驗代號 S1，52 格配對移除掃描）、"
        "感測器量化特性表（datasheet；實驗代號 S2，含距離、桌面高度、側向、重複性四項量測）、"
        "聲學閉環接近三臂對照（實驗代號 D1 為自由移動感測器之隔離驗證、D1.5 為手臂載具版）、"
        "端到端夾取整合三臂對照（實驗代號 D3，含夾取對位與附著升舉）、"
        "側向感知之系統性檢驗與多點定位可行性驗證，"
        "以及貫穿全部實驗之三臂對照與稽核之實驗效度設計。",
    ),
    (
        "Content",
        "排除項目包括：商用超音波測距晶片（如 TDK CH201）之實機量測、"
        "夾爪之物理摩擦夾持宣稱（本研究之夾持以接觸觸發之附著機制模擬，詳見第五章）、"
        "側向多點定位之完整三臂對照實驗（可行性探針已通過，正式對照實驗列為未來工作）、"
        "以及跨隨機種子之穩健性驗證。",
    ),
    (
        "Content",
        "限制：本研究採單一隨機種子（seed）、確定性物理引擎模擬，尚未驗證跨種子之統計穩健性；"
        "控制自由度限於單自由度（1-DOF）前向接近，未涉及側向或姿態調整；"
        "預定停止距離（standoff）固定為 0.35 m；桌面高度目標之距離編碼於 0.32 m 以內失效，"
        "此範圍外之最後一段接近尚未驗證。控制器全程不讀取任何目標世界座標，"
        "然而所有結論僅在模擬環境中驗證，尚未涉及部署級或實機效能評估。",
    ),
    ("Header2", "1.4 名詞解釋與研究貢獻"),
    (
        "Content",
        "本文之英文術語與程式變數名於首次出現時附中文說明，並彙整於本節；"
        "其後行文以中文譯名為主，必要時括注英文以利對照程式與數據。"
        "本文使用之縮寫與符號如下。"
        "GMO（Generic Model Output）：RTX Acoustic 感測器之原始輸出資料結構。"
        "WPM（Wave Propagation Model）：RTX Acoustic 之波傳播模擬模型。"
        "SNR（signal-to-noise ratio，訊噪比）：本文特指配對移除量測中目標貢獻與量測雜訊底之比值（定義見 3.3 節）。"
        "RMSE（root mean square error）：均方根誤差。"
        "r：皮爾森（Pearson）相關係數；ρ：斯皮爾曼（Spearman）等級相關係數。"
        "IK（inverse kinematics）：逆向運動學，由末端目標位姿反解關節角。"
        "DOF（degree of freedom）：自由度。"
        "seed：隨機種子，決定隨機目標位置序列；session：一次模擬器啟動至關閉之工作階段；"
        "episode：一次完整之接近試驗回合。"
        "standoff：預定停止距離，本文設定 0.35 m。"
        "對位（alignment）：夾取動作執行前，夾爪中心與目標中心在水平方向之幾何吻合程度，"
        "本文以兩者之距離是否在預先鎖定之容差內判定。"
        "多點定位（multilateration）：自多個已知量測位置分別取得與目標之距離，"
        "以幾何交會解算目標座標之定位方法。",
    ),
    (
        "Content",
        "感測包絡（sensing envelope）：使目標可被穩定偵測之感測器—目標相對幾何範圍，以配對移除與 SNR 地圖界定。"
        "指標失效（metric failure）：到達率等表面指標可能由場景幾何本身撐出、而非感測資訊所致之混淆現象；"
        "本文以盲走消融與停止位置相關性作為主指標以排除之。"
        "盲走臂（blind）消融：保留完整量測管線、僅將控制器可用之估距置換為無資訊值之對照組，"
        "用以檢驗閉環成功是否真正依賴感測資訊。",
    ),
    (
        "Content",
        "貢獻一（感測包絡量測方法）：以配對移除協定與 SNR 地圖系統性界定 WPM 超音波感測器之可偵測幾何域"
        "（52 格、36/52 可偵測），確立感測器擺位設計規範。",
    ),
    (
        "Content",
        "貢獻二（聲學閉環接近主結果）：於界定包絡內，以三臂資訊消融對照驗證純聲學控制迴路可驅動 UR10e 手臂"
        "接近隨機擺放桌面目標，主結果 r=0.9856、RMSE 2.8 cm、30/30，90 個試驗回合姿態稽核零違規。",
    ),
    (
        "Content",
        "貢獻三（端到端夾取整合）：將聲學閉環自「接近後停止」延伸至「停止後夾取」，"
        "以聲學估距決定夾取位置，夾取中心與目標相關係數 r=0.9885、對位誤差 RMSE 1.9 cm，"
        "對位因果經資訊消融對照確認（費雪精確檢定 p=0.004）。",
    ),
    (
        "Content",
        "貢獻四（側向感知之證偽與演算法恢復）：以四項獨立實驗系統性證偽感測器原生輸出之側向資訊"
        "（能量差、時間差、身分欄位、接收器分組），並以手臂運動合成多視點之多點定位演算法"
        "恢復目標二維座標（側向相關係數 r=0.960），示範「感測器單一能力 × 運動自由度」之演算法補償路徑。",
    ),
    (
        "Content",
        "貢獻五（實驗效度設計）：提出三臂資訊消融對照、預註冊判準、量測與姿態稽核之組合設計，"
        "確保模擬閉環結果之因果可歸屬，可推廣為 sim-based 機器人感測研究之驗證流程。",
    ),
]

# ---------------------------------------------------------------------------
# Chapter 3 (rewritten)
# ---------------------------------------------------------------------------

CH3 = [
    ("Header1", "第三章、研究方法"),
    ("Header2", "3.1 WPM 感測模型與 GMO 資料結構"),
    (
        "Content",
        "RTX Acoustic 之 Wave Propagation Model（WPM）為真正之幾何光線追蹤式聲波傳播模擬"
        "（NVIDIA, 2026c），與僅依賴參數化近場模型之簡化超聲模擬不同，"
        "WPM 會追蹤聲波路徑與場景幾何（如立方體目標、牆面、機械手臂連桿）之交互反射，"
        "使模擬結果對感測器—目標之相對幾何具有物理意義上之敏感性——此為本研究能以配對移除實驗"
        "系統性界定感測包絡之技術前提。",
    ),
    (
        "Content",
        "WPM 之原始輸出資料結構稱為 Generic Model Output（GMO），"
        "其官方格式定義（NVIDIA, 2026b）說明 GMO 以信號路徑（signal way）序列"
        "紀錄各發射器（TX）／接收器（RX）／通道（Channel）組合之振幅樣本。"
        "本研究之感測器組態為雙聲學掛載點（相距 0.10 m）搭配單一接收群組，"
        "中心頻率設定為 40 kHz。正確重建時間波形須以每路徑樣本數欄位 numSamplesPerSgw 對緩衝區做"
        "跨步切分（stride）：buffer 依序排列為每個 signal way 之 N 個樣本，"
        "而非以 GMO 之 z 欄位（channel ID）作時間索引——此為前期實作階段確認之關鍵細節，"
        "誤用 channel ID 作時間軸將使峰值位置恆為零。",
    ),
    (
        "Content",
        "GMO 之 timeOffsetNs 欄位在 Isaac Sim 6.0 恆為 0（已知限制），不可用於距離推算；"
        "距離改以峰值樣本索引（多幀平均波形中振幅最大值所在之樣本位置）× 樣本週期 × 聲速 ÷ 2 換算。"
        "GMO 之發射／接收／通道身分欄位（id 欄位）在本研究之感測器組態下亦不編碼接收器身分"
        "（每幀恆為 (tx, rx, ch) = (0, 0, 0)），此限制經第四章之側向掃描直接以實測資料證偽並記錄，"
        "而非僅憑文件推測。此外，量測前之場景建立會伴隨數十幀之確定性啟動暫態，"
        "且逐幀能量恆有大於 0.1% 之跳動（訊號路徑輪替結構所致），"
        "故本研究之量測程序一律採多幀平均，並輔以支柱四所述之量測稽核（3.3 節）排除暫態污染之量測。",
    ),
    ("Header2", "3.2 樣本週期自校"),
    (
        "Content",
        "樣本週期為距離換算公式之關鍵常數，若採用錯誤數值將使全部距離估計產生系統性偏移。"
        "本研究不沿用任何外部或前期估計值，而是於每一批新實驗中，"
        "以已知距離之目標沿感測器視軸方向做等距離掃描（20 個距離點，涵蓋 0.15–1.20 m），"
        "取峰值樣本索引與已知距離做最小平方法（OLS）迴歸，"
        "以回歸斜率反推樣本週期（樣本週期 = 2 ÷（斜率 × 聲速））。"
        "掃描之具體程序為：感測器全程固定不動，目標物依 3.4 節所述之位置改寫方式"
        "依序移至各已知距離點；每移動一次，先等待 40 個模擬影格使聲學輸出穩定，"
        "再連續擷取 24 影格取平均波形、讀出峰值樣本索引，"
        "如此得到 20 組「已知距離、量測峰值位置」之配對資料供迴歸使用。"
        "迴歸所得之斜率（單位：樣本數／公尺）與截距即構成該批實驗之距離預測模型——"
        "此後量測到任一峰值位置，即以（峰值位置 − 截距）÷ 斜率預測感測器與目標之距離。",
    ),
    (
        "Content",
        "本研究以兩種獨立幾何交叉驗證此自校程序：一為感測器視軸（boresight，即感測器指向軸）高度之量測，"
        "二為目標實際置於桌面高度之量測（兩者之感測器—目標三維距離換算不同，"
        "後者須另計入垂直高度差）。兩種幾何獨立解得之樣本週期分別為 103.09 µs 與 100.77 µs，"
        "彼此相近且均與引擎預設值（schema）102.4 µs 接近，顯示自校結果具跨幾何一致性；"
        "凡本研究後續之距離換算，一律採用當輪實驗獨立自校所得之數值，不假設任一固定常數可跨場景沿用。",
    ),
    ("Header2", "3.3 本研究之實驗方法學：四支柱"),
    (
        "Content",
        "支柱一：包絡優先（envelope-first）。本研究之核心方法論主張是："
        "先以配對移除與訊噪比（SNR）地圖量測「感測器在什麼幾何下讀得到目標」，"
        "再把機器人任務設計進已驗證之包絡之內——先驗證感測、再建構控制，"
        "避免將控制系統建立於未經驗證之感測假設上。"
        "配對移除之量測程序為：於同一場景、同一感測器姿態下，"
        "先量測目標存在時之波形，再將目標自場景中物理移除後量測背景波形，"
        "兩者皆與同條件下緊接之重複量測（代表量測雜訊底）比較。"
        "偵測訊噪比定義為 SNR = max|W_有目標 − W_無目標| ÷ max|W_有目標 − W_雜訊參考|，"
        "其中 W 為多幀平均波形；SNR 大於 10 判定為可偵測，此門檻選定考量雜訊底本身即含有限之量測變異。",
    ),
    (
        "Content",
        "支柱二：三臂對照設計。每一組閉環實驗均配對『聲學臂』（closed，使用聲學估距驅動接近與停止決策）、"
        "『盲走臂』（blind，量測管線與聲學臂完全相同，僅將控制器可用之估距通道置換為無資訊值 +∞，"
        "使其無法觸發停止條件）、『開環臂』（open，完全不執行量測，僅依固定名義行程移動）三臂，"
        "三臂使用同一組隨機種子（seed）與同一批隨機目標位置，確保比較之公平性。"
        "任何閉環宣稱必須通過「盲走對照失能」檢驗——若盲走臂亦能達成相近之接近效果，"
        "即表示聲學臂之成功可能來自場景幾何或走廊設計本身，而非聲學資訊，此宣稱即不成立。",
    ),
    (
        "Content",
        "支柱三：預註冊判準。每個實驗之通過／失敗標準寫在執行腳本之註解區塊，先於執行即固定，"
        "避免以事後觀察到之結果回頭調整判準（即避免資料窺探）。"
        "本研究之主指標一律為「停止位置與目標位置之相關係數（r）與誤差（RMSE）」，"
        "刻意不採用單純到達率作為主指標，因為在有限寬度之目標帶下，"
        "即使完全不追蹤目標之固定行程策略也可能達到不低之到達率，"
        "此點於第六章 6.1 節以實測數據具體說明。",
    ),
    (
        "Content",
        "支柱四：量測稽核制度。本研究設計三類稽核，皆將不合格量測標記為無效（INVALID）並排除於分析之外，"
        "而非事後以插補或其他方式修正：（一）平穩性稽核，針對 WPM 場景建立後之啟動暫態與特定幾何組合下"
        "之持續性慢震盪，以量測前之穩定等待（settle）幀數門檻與事後漂移檢查排除；"
        "（二）姿態稽核，於機械手臂之每一控制步檢查手臂各連桿（前臂、腕部各關節）之世界座標，"
        "是否有連桿穿越桌面或地面之非物理姿態；（三）感測器位姿稽核，"
        "確認感測器之實際世界座標與姿態符合校正時之前提條件（如視軸水平、掛載高度固定），"
        "此稽核為所有距離校正結果之有效性前提。",
    ),
    ("Header2", "3.4 場景建構與物件操作"),
    (
        "Content",
        "本研究全部實驗共用同一基準場景，於每次模擬器啟動時以程式重新建構，確保條件一致："
        "工作桌為 1.2 m（寬）× 0.8 m（深）× 0.40 m（高）之長方體，"
        "置於機械手臂基座正前方（桌面中心距基座 1.05 m）；"
        "UR10e 機械手臂（含 Robotiq 2F-85 夾爪，僅第五章 D3 實驗實際啟用夾爪）固定於原點；"
        "超音波感測器依實驗階段之不同，或為可自由放置之獨立物件（第四章與 D1），"
        "或掛載於手臂腕部連桿並前伸 0.25 m（D1.5 與 D3，前伸量之選定使感測器脫離夾爪機構之聲學陰影），"
        "兩種情形下感測器皆維持離地 0.65 m、視軸水平朝前，"
        "且每一步皆由感測器位姿稽核（3.3 節支柱四）確認此前提未被破壞。"
        "目標物為置於桌面上之長方體（各實驗之尺寸於對應章節載明），"
        "隨機位置由固定之隨機種子產生：自預先劃定之範圍內均勻抽取，"
        "同一實驗之三臂使用同一批抽取結果，確保對照公平。",
    ),
    (
        "Content",
        "物件之放置與移動方式：模擬環境中之物件移動並非以物理力推動，"
        "而是直接改寫該物件之空間位置屬性，使其於下一影格即出現於指定位置——"
        "此操作之聲學有效性（改寫位置後，聲波追蹤引擎確實依新位置計算回波）"
        "已由前置探針實驗獨立驗證：移動目標物後，量測波形之變化量達背景雜訊之四百倍以上，"
        "且將目標移除出場景與移至遠處兩種操作之效果一致。"
        "「將目標自場景移除」（配對移除量測之關鍵步驟）即以自場景刪除該物件實作。"
        "每次物件位置變動後之量測程序固定為：先等待 40 影格（消化場景變動後之啟動暫態），"
        "再連續擷取 24 影格、分為前後兩段各 12 影格分別平均；"
        "兩段平均波形之早期能量若相差超過 5%，即判定該點量測不平穩、標記為無效，"
        "此設計源自前期觀察：場景建立後之數十影格內輸出有確定性爬升，"
        "且特定幾何組合下存在持續之慢震盪，若不設此稽核將污染量測。"
        "機械手臂之移動同樣採直接寫入關節角度之方式（運動學寫入），"
        "每步移動後亦執行相同之穩定等待與量測程序；"
        "感測器隨手臂移動之聲學有效性亦由前置探針驗證（詳見第五章各實驗之啟動閘門）。",
    ),
    ("Header2", "3.5 聲學特徵定義與閉環控制律"),
    (
        "Content",
        "本研究自原始波形擷取兩項聲學特徵，定義如下。"
        "特徵一：峰值樣本索引（peak index）——多影格平均波形中，振幅絕對值最大之取樣點位置（整數）。"
        "其物理意義為最強回波之到達時間：聲波自發射器出發、經目標反射回到接收器所需之時間，"
        "正比於感測器與目標之往返距離，故峰值位置隨距離線性後移；"
        "此特徵是本研究全部距離估計之依據，且經第四章量測確認其對能量慢震盪免疫"
        "（能量漂移之量測點其峰值位置仍精確落在距離迴歸線上）。"
        "特徵二：早期能量（early energy）——平均波形前 20 個取樣點之振幅平方和。"
        "其物理意義為近程回波之總強度；本研究僅將其用於兩處輔助功能："
        "配對移除量測之訊噪比計算（4.1 節）與量測平穩性稽核（3.4 節），"
        "刻意不以能量推算距離——因為能量同時受目標距離、尺寸、材質與場景幾何影響，"
        "以能量反推距離在含手臂與桌面之複雜場景中不可靠（此為前期探索之教訓，"
        "亦是本研究以峰值位置為主特徵之原因）。",
    ),
    (
        "Content",
        "閉環控制律——自聲學特徵到手臂動作之完整因果鏈如下，以 D1.5 為例："
        "（一）量測：手臂於當前位置依 3.4 節程序取得平均波形，讀出峰值樣本索引；"
        "（二）預測：以 3.2 節自校迴歸模型將峰值位置換算為感測器至目標之三維距離，"
        "再依感測器與目標之已知垂直高度差（0.19–0.20 m）換算為水平距離估計值；"
        "（三）決策：若水平距離估計值小於或等於預定停止距離 0.35 m，控制器即判定到達、停止前進；"
        "否則命令手臂沿接近軸前進一步（步長 0.05 m）；"
        "（四）執行：目標位置經逆向運動學解算為六個關節角度後寫入手臂，"
        "求解時以上一步之關節解作為初始猜測（暖啟動），並限制單步關節變化量上限，"
        "防止逆向運動學在多組合法解之間跳躍；"
        "（五）稽核：每步移動後檢查手臂姿態與感測器位姿（3.3 節支柱四），隨即回到步驟（一）。"
        "迴圈另設兩道護欄：步數上限 40 步、走廊端點護欄（手臂前進至預設邊界即強制終止），"
        "兩者皆為與聲學無關之安全終止條件，其觸發於記錄中明確標示、與聲學觸發之停止區分。",
    ),
    (
        "Content",
        "三臂之差異即在上述因果鏈之步驟（二）與（三）："
        "聲學臂完整執行五個步驟；盲走臂執行完全相同之量測（步驟一之成本與時序皆保留），"
        "但於步驟（二）將水平距離估計值強制置換為無窮大，"
        "使步驟（三）之停止條件永遠不成立——盲走臂因此只能被走廊護欄強制終止，"
        "其存在使「量測動作本身之副作用」（如每步之等待時間、手臂之走停節奏）與"
        "「量測資訊之實際使用」兩者得以分離檢驗；"
        "開環臂則完全跳過步驟（一）（二）（三），直接以固定名義行程走到預定點停止，"
        "作為「完全無感測」之基準線。改善機制方面，本研究之控制器刻意維持最簡形式"
        "（單一比例步進、無濾波、無多步預測），使每一次停止決策皆可追溯至單一次量測之單一特徵值——"
        "此為因果歸屬清晰性與控制效能之間之刻意取捨，"
        "控制效能之改善（如加入狀態估計或學習式策略）列於第六章未來工作。",
    ),
    ("Header2", "3.6 章節間資料鏈"),
    (
        "Content",
        "第四章與第五章之數據依序遞進：S1（感測包絡地圖）界定可偵測幾何範圍 →"
        " S2（感測器量化特性表，datasheet）在包絡內建立距離編碼之量化關係 →"
        " D1（感測＋控制之隔離驗證，採自由移動之飛行感測器）驗證控制迴路本身之因果有效性 →"
        " D1.5（加入手臂載具）驗證同一控制迴路在真實機械手臂運動學下之表現 →"
        " D3（端到端夾取整合）將已驗證之接近能力延伸至夾取對位與附著升舉，構成本研究之完整任務鏈。"
        "每一層皆有獨立之預先寫定判準與資訊消融對照組，且後一層之場景設計直接引用前一層之量測結論，"
        "而非各自獨立假設：D1 與 D1.5 之場景幾何直接沿用 S1 界定之可偵測範圍與 S2 之校正參數；"
        "D3 之夾取目標物與距離校正則於實驗前以三道前置閘門重新量測確認"
        "（目標物可偵測性、距離編碼有效性、夾取動作力學有效性），"
        "確保「換了目標物」這一變因不會使前層結論失效。",
    ),
    (
        "Content",
        "此外，本研究對校正參數之可信度另行執行歸因檢驗：不同實驗批次獨立量測之距離校正斜率"
        "曾出現表面上約正負一成之差異，經統計分析確認該差異完全落在小樣本迴歸之不確定度範圍內"
        "（量測點數少、且峰值樣本索引為整數所致之量化誤差），"
        "並以直接對照實驗（同一場景內分別移動目標與移動感測器，各量測十三個距離點）確認"
        "兩種量測方式解得之斜率無系統性差異。此檢驗確立了一項可遷移之結論："
        "距離校正斜率為傳播介質與取樣機制之性質，與目標物之形狀尺寸無關"
        "（不同目標物獨立解得之斜率相差不及百分之一），"
        "因此校正可在同幾何下跨目標物沿用，惟本研究仍一律於更換目標物時重新自校以資保守。",
    ),
]

# ---------------------------------------------------------------------------
# Chapter 4 (rewritten)
# ---------------------------------------------------------------------------

CH4 = [
    ("Header1", "第四章、感測特性化與包絡"),
    ("Header2", "4.1 S1 感測包絡地圖"),
    (
        "Content",
        "本章之感測包絡量測（實驗代號 S1）目的在回答第一章 RQ1：超音波感測器在何種感測器—目標幾何下"
        "能穩定偵測目標。實驗設計為四因子配對移除掃描：距離（0.15、0.3、0.5、0.8、1.2 m 五個水準）、"
        "目標尺寸（0.04、0.10、0.20 m 三個水準）、感測器俯仰角（0°、30°、60° 三個水準），"
        "以及場景干擾物（無干擾、僅桌面、桌面加機械手臂三個水準），"
        "共分為四個區塊（A–D），依因子組合裁切出 52 個量測格點，全數完成、0 格無效"
        "（少數格點因量測稽核偵測到平穩性未達標而重測，最終皆通過）。",
    ),
    (
        "Content",
        "每一格點之實驗程序如下。每格使用一次獨立之模擬器啟動（避免格點間之狀態殘留），"
        "場景依該格之因子設定建構：感測器置於固定位置（離地 0.65 m），"
        "俯仰角依格點設定繞水平軸旋轉（0°、30° 或 60°，俯視為正）；"
        "立方體目標置於感測器視軸延伸線上之指定距離處（俯仰非零時目標隨視軸放低），"
        "使目標中心始終位於感測器指向之正前方；"
        "干擾物依格點水準放置——「桌面」水準將 1.2×0.8 m 之實心桌置於目標正下方（目標改置桌面上），"
        "「桌面加手臂」水準另將機械手臂以固定姿態立於感測器正後方約 0.1 m 處，"
        "模擬腕載感測器背後即為手臂本體之實際幾何。"
        "量測順序為三段：先量「有目標」波形，再於完全相同條件下緊接量測一次作為雜訊參考"
        "（兩次量測之差即為該模擬工作階段之量測雜訊底），"
        "最後將目標自場景刪除、量「無目標」背景波形；"
        "三段各依 3.4 節之標準程序（等待 40 影格、擷取 24 影格平均）執行，"
        "訊噪比即以三段波形依 3.3 節公式計算。",
    ),
    (
        "Content",
        "每一格點採配對移除程序：先於固定幾何下量測目標存在之波形，"
        "再將目標自場景物理移除後量測背景波形，兩者皆與同條件下緊接之重複量測比較，計算訊噪比（SNR）。"
        "四個區塊之結果為：A 區（無干擾、水平指向，距離×尺寸）14/15 可偵測"
        "（唯一失格為 0.04 m 目標於 1.2 m 距離，SNR 僅 3.9）；"
        "B 區（俯仰效應，30° 與 60°）6/10 可偵測（30° 全部距離段皆可偵測，60° 僅最近之 0.15 m 距離可偵測）；"
        "C 區（含桌面干擾，距離×俯仰）9/15 可偵測（水平指向全數可偵測，SNR 介於 67–148；"
        "30° 俯仰僅至 0.5 m 距離；60° 俯仰僅最近距離可偵測）；"
        "D 區（含桌面與手臂雙重干擾，距離×尺寸×俯仰）7/12 可偵測（水平指向全數可偵測，SNR 介於 67–293；"
        "60° 俯仰僅 0.3 m 距離、0.20 m 尺寸之目標可偵測）。四區合計 36/52 格可偵測，"
        "此結果已足以否定「感測包絡完全不可行」之最壞情境，亦未觸及「含手臂干擾即全數失敗」之另一項預先寫定之停損判準。",
    ),
    (
        "Content",
        "關鍵發現一：感測包絡之主宰因子是「指向」而非「干擾物」。"
        "水平指向（俯仰角 0°）時，即使桌面與手臂兩項干擾物同時存在，"
        "0.10 m 目標於 0.3–0.8 m 距離範圍內全數可偵測（SNR ≥ 67）；"
        "反之，俯仰角提升至 60° 時，即使沒有任何干擾物，可偵測格點也幾乎全滅——"
        "推測原因是立方體目標之鏡面反射特性，使大角度俯視下之回波偏離感測器接收方向，"
        "而非因為訊號被場景中其他物體遮蔽或吸收。",
    ),
    (
        "Content",
        "關鍵發現二：感測器後方之物體對前向偵測路徑之貢獻在此確定性模擬下精確為零。"
        "比對 C 區（僅桌面）與 D 區（桌面加手臂）在相同距離、相同俯仰角下之量測結果，"
        "兩者之 SNR 數值逐位相同（例如 148.36、94.58、67.67 三組數值於兩區塊完全一致），"
        "顯示置於感測器後方之機械手臂對前向聲學路徑沒有任何可量測之干擾貢獻。"
        "此一發現具有明確之工程意涵：即使在含手臂與桌面之複雜抓取場景中，"
        "若目標偵測失敗，其根因不必然是手臂或桌面本身造成之遮蔽或反射干擾，"
        "而更可能是感測器相對於目標之擺位與指向角度不當——此發現直接指導了第五章之場景設計。",
    ),
    (
        "Content",
        "關鍵發現三：目標尺寸存在明確之下限。0.04 m 尺寸之目標在超過 1.2 m 距離即失效"
        "（SNR 降至個位數）；0.10 m 尺寸之目標在全部測試距離範圍（0.15–1.2 m）皆維持可偵測；"
        "0.20 m 尺寸之目標則有最高之訊噪比表現（SNR 介於 216–311）。"
        "此結果為後續實驗選擇目標尺寸提供依據：本研究後續之感測器 datasheet 與閉環接近實驗"
        "皆採用 0.10 m 尺寸，兼顧可偵測性與貼近實際工件尺度之考量。",
    ),
    ("Header2", "4.2 S2 感測器量化特性表（Datasheet）"),
    (
        "Content",
        "在 S1 界定之可偵測包絡內，本研究進一步以 15 組量測建立感測器之量化特性表（datasheet），"
        "採用 S1 之 D 區實戰幾何（桌面加手臂雙重干擾、水平指向、0.10 m 目標）作為量測條件，"
        "確保後續控制器設計所依據之校正數值來自與實際任務場景一致之幾何配置，而非理想化之無干擾場景。"
        "15 組量測包含：距離編碼（視軸高度與桌面高度各進行掃描，目標物依 3.4 節方式在同一工作階段內"
        "沿視軸依序移至各距離點）、側向編碼（目標物沿垂直於視軸之方向橫移 13 點）、"
        "以及重複性測試（將模擬器完全關閉並重新啟動十次，每次以相同設定量測同一格點，"
        "檢驗跨工作階段之結果一致性）。",
    ),
    (
        "Content",
        "距離編碼結果：於感測器視軸高度（z=0.65 m）進行三遍獨立掃描，"
        "峰值樣本索引與已知距離之皮爾森相關係數 r=0.9994，均方根誤差（RMSE）1.21 cm，"
        "三遍掃描之自校樣本週期為 103.09 µs；於目標實際置於桌面高度（z=0.45 m，"
        "即感測器與目標之間存在固定 0.20 m 垂直高度差）進行掃描，"
        "相關係數 r=0.9998，優於視軸高度掃描，可用距離範圍 0.32 m 以上之均方根誤差為 5.3 mm，"
        "自校樣本週期為 100.77 µs。0.15–0.26 m 之近距離量測點因感測器俯視角超過 50 度，"
        "被平穩性稽核正確排除，此結果符合幾何預期（近距離時垂直高度差相對距離之角度效應顯著增加）。"
        "三遍距離掃描之結果逐位相同（包含被稽核排除之量測點），"
        "與另外進行之 10 次重複性測試（峰值樣本索引結果完全相同、能量特徵之變異係數為 0.0000）互相印證，"
        "顯示本模擬環境在固定隨機種子下具有高度之數值確定性，此為本研究得以進行精確之逐點稽核之基礎。",
    ),
    (
        "Content",
        "校正斜率之跨批次一致性檢驗：由於距離換算完全依賴校正斜率，"
        "本研究對不同實驗批次獨立量測之斜率差異（表面上約正負一成）進行了兩層歸因。"
        "第一層為統計歸因：以最小平方法迴歸之標準誤計算各批次斜率之 95% 信賴區間，"
        "結果顯示量測點數較少之批次其信賴區間完全涵蓋主校正值，"
        "亦即表面差異落在小樣本估計之不確定度內，並非物理性之系統差；"
        "第二層為直接實驗：於同一場景中，分別以「移動目標、感測器固定」與"
        "「手臂載運感測器移動、目標固定」兩種方式量測相同之十三個距離點，"
        "兩者解得之斜率差異小於合併標準誤之兩倍，確認量測方式本身不引入系統偏差。"
        "此檢驗同時帶來一項附帶發現：不同尺寸形狀之目標物獨立解得之校正斜率相差不及百分之一，"
        "顯示斜率反映的是聲波傳播與取樣機制之性質，目標物幾何僅影響迴歸截距。",
    ),
    ("Header2", "4.3 負結果與失效機制（誠實記錄）"),
    (
        "Content",
        "側向感知之四重證偽：本研究以四項互相獨立之實驗，系統性檢驗感測器原生輸出是否含有目標之左右方向資訊，"
        "四項全數證偽。其一，能量線索：兩接收器之能量差異與目標橫移量（±0.15 m 掃描）之間無單調關係"
        "（斯皮爾曼等級相關係數 ρ=0.357，遠低於預先寫定之 0.9 判準）；"
        "其二，時間線索：兩接收訊號間之互相關時間差恆為固定值（與橫移量之相關係數僅 0.002），"
        "且對左右橫移呈完全鏡像對稱，顯示該時間差為輸出管線之固定偏移而非幾何資訊；"
        "其三，身分欄位：逐幀檢視原始輸出，各幀之信號路徑標籤（發射器、接收器、通道三元組）恆為 (0, 0, 0)，"
        "個別接收器之身分並未編碼於資料中；"
        "其四，接收器分組：將兩接收器改編為兩個獨立群組之感測器組態下，"
        "第一路輸出與原組態逐位元相同，第二路輸出則成為無意義之雜訊（峰值位置隨機跳動），"
        "顯示引擎並不支援依群組分離渲染。四項證據共同確立：側向資訊之缺失是引擎輸出層之根本限制，"
        "而非量測雜訊、演算法選擇或程式錯誤——任何依賴單次量測內「雙耳差異」之側向方法在此模擬器中皆不可行。"
        "此一結論促成第五章之後續發展：改以手臂運動合成多個量測位置之多點定位演算法恢復側向資訊。",
    ),
    (
        "Content",
        "中心頻率參數之無效性：本研究另以六個中心頻率設定（20、30、40、60、80、100 kHz）"
        "對同一場景執行相同之距離掃描。六組結果中，距離特徵（峰值樣本索引）之全部量測點逐位元相同；"
        "能量特徵僅存在千萬分之一量級之浮點尾數差異——此量級與跨工作階段之浮點雜訊相當，"
        "遠低於真實聲學中頻率每變化一倍所應造成之顯著吸收與繞射差異，"
        "故判定本模擬引擎並未對頻率相關之物理效應（如空氣吸收隨頻率上升、波長與目標尺寸之繞射關係）建模。"
        "此發現界定了模擬結論之適用邊界：本研究之 40 kHz 設定對應真實世界最普及之商用超音波頻段，"
        "其選擇依據為實務對應性（波長約 8.6 mm，遠小於目標尺寸，屬鏡面反射區；"
        "量測距離 0.4–1.2 m 位於該頻段之有效射程內），"
        "而頻段對感測效能之實際影響須待實體硬體驗證，於模擬內進行頻段比較實驗並無意義。",
    ),
    (
        "Content",
        "腕載聲影機制：本研究以配對移除實驗量測同一目標在含手臂與桌面之複雜場景（arm+table）中之聲學貢獻，"
        "發現其貢獻全程維持在 2.2×10⁻⁵ 以下（相較於約 135 之背景能量量級，此貢獻已落入浮點運算之雜訊水準），"
        "遠低於同尺寸目標在無手臂之簡單場景（arm-free）中約 124,000 能量單位之貢獻"
        "（訊號與背景比約為 6000 比 1）。此一巨大落差之根因並非該場景本身聲學不可行，"
        "而是感測器裝設於機械手臂腕部、且被夾爪機構之網格幾何遮蔽所形成之聲學陰影效應。"
        "此發現與 4.1 節之 S1 包絡地圖互相印證，共同指向：感測器擺位與指向角度，"
        "而非場景中之背景物體本身，才是決定超音波感測任務可行性之核心工程約束——"
        "此一結論直接形塑了第五章聲學閉環接近實驗之感測器掛載設計。",
    ),
]

# ---------------------------------------------------------------------------
# Chapter 5 (rewritten — new core result)
# ---------------------------------------------------------------------------

CH5 = [
    ("Header1", "第五章、聲學閉環接近"),
    ("Header2", "5.1 D1：飛行感測器三臂對照（感測＋控制隔離驗證）"),
    (
        "Content",
        "本章之閉環接近實驗直接回應第一章 RQ2：不讀取目標世界座標之純聲學控制迴路，"
        "能否驅動機械手臂接近隨機擺放目標，且其因果可經資訊消融對照證實。"
        "考量到手臂載具本身之運動學誤差、關節姿態限制等因素可能與感測器估距誤差交雜，"
        "本研究先以自由移動之感測器（不掛載於實體手臂，而是可獨立於空間中移動之感測器物件）"
        "進行第一階段驗證，稱為 D1，用以在排除手臂運動學變因之情況下，"
        "單獨檢驗「感測＋控制」這一環節之因果有效性；待此環節驗證通過後，"
        "5.2 節再將感測器實際掛載於機械手臂，加入運動學變因進行完整驗證（D1.5）。",
    ),
    (
        "Content",
        "D1 場景設計：0.10 m 方塊目標隨機置於桌面之 x ∈ [0.45, 1.10] m 範圍內"
        "（此範圍刻意避開第四章確認之 0.32 m 以內桌高失效區，並保留足夠之預定停止距離裕度）；"
        "感測器為自由飛行之獨立物件，水平前視（掛載高度 z=0.65 m）沿 X 軸方向逐步接近，"
        "每步步長 0.05 m，預定停止距離（standoff）設定為 0.35 m。"
        "每個試驗回合之程序為：依隨機種子自目標範圍內均勻抽取本回合之目標位置，"
        "以位置改寫方式將目標立方體置於該處；感測器回到固定起點（0.60 m 處）；"
        "隨後進入 3.5 節所述之「量測—預測—決策—執行—稽核」迴圈，"
        "控制律為：若當前估距大於預定停止距離，則繼續前進一步；若估距小於或等於預定停止距離，則停止。"
        "三臂（聲學臂、盲走臂、開環臂）各執行 30 個試驗回合，三臂共用同一組隨機種子與同一批隨機目標位置，"
        "確保比較之公平性；目標之真實世界座標僅寫入記錄欄位供事後評估之用，不曾進入任何控制分支之判斷邏輯。"
        "執行三臂正式量測前，另先執行 D0 探針量測：將目標固定於已知位置，"
        "感測器沿接近軸依序移至 13 個已知位置、於每一位置依標準程序量測估距，"
        "再以估距對真實距離做迴歸——此探針之目的為驗證「感測器本身移動」這一操作之聲學有效性"
        "（此前僅驗證過移動目標物），因為若聲波追蹤引擎未正確追蹤感測器之位置變化，"
        "後續閉環實驗之每一步量測皆屬無效，"
        "探針結果之相關係數 r=0.9958，通過預先寫定之啟動閘門判準（要求 r 不低於 0.99）。",
    ),
    (
        "Content",
        "D1 三臂結果：聲學臂之停止位置與目標位置相關係數 r(停止, 目標)=0.9970，"
        "停止誤差平均值與均方根誤差分別為 2.1 cm 與 2.5 cm，30 個試驗回合中全部 30 個誤差皆在 10 cm 以內，"
        "且全數由聲學估距觸發停止條件而終止；盲走臂（估距通道被置換為無資訊值後）完全失能，"
        "恆定停止於走廊護欄端點 1.15 m 處（與目標位置完全無關），誤差平均值與均方根誤差分別高達 77.6 cm 與 79.3 cm，"
        "30 個試驗回合中無一誤差在 10 cm 以內；開環臂（固定名義行程、不執行任何量測）"
        "恆定停止於 0.425 m 處，誤差平均值與均方根誤差分別為 13.4 cm 與 16.9 cm，30 個試驗回合中有 14 個誤差在 10 cm 以內。"
        "此結果構成感測＋控制環節之隔離驗證：僅將聲學資訊自控制迴路中移除（即盲走臂之設定），"
        "同一套量測與控制管線即刻完全失能，確認聲學臂之接近行為因果確實來自聲學估距，而非場景幾何或走廊設計本身。",
    ),
    ("Header2", "5.2 D1.5：手臂載具三臂對照（主結果）"),
    (
        "Content",
        "D1 驗證通過後，本研究進一步將感測器實際掛載於 UR10e 機械手臂，"
        "加入真實手臂運動學變因，構成本文之主結果實驗（代號 D1.5）。"
        "感測器改掛載於手臂之腕部第三連桿（wrist_3_link），並另加 0.25 m 之前伸修正變換，"
        "使感測器實際位置位於夾爪機構之聲學陰影範圍之外（見 4.3 節之腕載聲影機制討論）。"
        "手臂運動由逆向運動學（IK）解算：每一步依目標之感測器末端位置反解對應之六軸關節角，"
        "並以上一步之關節解作為此次求解之暖啟動（warm-start）初始值，"
        "以避免逆向運動學在多組合法解之間跳躍造成不連續之姿態變化。",
    ),
    (
        "Content",
        "為直接回應本研究對機械手臂姿態可能出現非物理現象（如連桿穿越桌面或地面）之高度重視，"
        "D1.5 於每一控制步新增兩類稽核：其一為姿態稽核，"
        "檢查手臂前臂與各腕部關節之世界座標是否低於地面或桌面之安全裕度，"
        "任何一項違規即將該試驗回合標記為無效並排除於分析之外；"
        "其二為感測器位姿稽核，確認感測器之實際世界座標與姿態（水平視軸、固定掛載高度）"
        "始終符合校正時之前提條件。三臂設計與 D1 完全相同，各執行 30 個試驗回合、"
        "使用同一組隨機種子與目標組；執行正式量測前之 D0.5 探針（手臂沿固定路徑接近已知目標）"
        "相關係數 r=0.9918，且姿態與感測器位姿違規次數皆為零，通過預先寫定之啟動閘門判準。",
    ),
    (
        "Content",
        "D1.5 主結果：聲學臂之停止位置與目標位置相關係數 r(停止, 目標)=0.9856，"
        "停止誤差平均值與均方根誤差分別為 2.5 cm 與 2.8 cm，30 個試驗回合中全部誤差皆在 10 cm 以內，"
        "平均步數為 5.0 步，且全數由聲學估距觸發停止而終止；盲走臂恆定停止於走廊護欄端點 0.95 m 處，"
        "誤差平均值與均方根誤差分別為 17.4 cm 與 18.9 cm，30 個試驗回合中僅 4 個誤差在 10 cm 以內；"
        "開環臂恆定停止於固定行程之 0.80 m 處，誤差平均值與均方根誤差分別為 6.2 cm 與 7.8 cm，"
        "30 個試驗回合中有 22 個誤差在 10 cm 以內。"
        "為檢驗聲學臂與盲走臂之停止誤差差異是否具統計顯著性，"
        "本研究採用 Welch t 檢定（一種不假設兩組樣本變異數相等之雙樣本 t 檢定，"
        "適用於兩組樣本數相同但變異程度可能不同之情形），"
        "檢定結果 t = −10.6、p < 0.001，達統計顯著水準（對應之 D1 飛行感測器實驗檢定結果為 t = −25.1、p < 0.001，"
        "顯著性更為明確）。三臂共 90 個試驗回合全數通過姿態與感測器位姿稽核、判定為有效，"
        "姿態與感測器位姿違規步數為零，逆向運動學求解失敗次數亦為零。"
        "與 D1 自由移動感測器版本對照：相關係數由 0.997 略降至 0.9856、均方根誤差由 2.5 cm 略增至 2.8 cm——"
        "此微小差異顯示掛載於真實機械手臂並加入運動學變因後，接近精度幾乎無明顯損失。",
    ),
    (
        "TableCaption",
        "表5.1  D1／D1.5 三臂對照（停止位置 vs 目標位置）",
    ),
    (
        "Table",
        ["實驗／臂", "r(停止, 目標)", "停止誤差 mean/RMSE", "P(誤差≤10 cm)", "終止方式"],
        [
            ["D1 聲學臂（飛行感測器）", "0.9970", "2.1 / 2.5 cm", "30/30", "聲學觸發"],
            ["D1 盲走臂", "0（恆停 1.15 m）", "77.6 / 79.3 cm", "0/30", "撞護欄"],
            ["D1 開環臂", "0（恆停 0.425 m）", "13.4 / 16.9 cm", "14/30", "固定行程"],
            ["D1.5 聲學臂（手臂載具）", "0.9856", "2.5 / 2.8 cm", "30/30", "聲學觸發"],
            ["D1.5 盲走臂", "0（恆停 0.95 m）", "17.4 / 18.9 cm", "4/30", "撞護欄"],
            ["D1.5 開環臂", "0（恆停 0.80 m）", "6.2 / 7.8 cm", "22/30", "固定行程"],
        ],
    ),
    ("Header2", "5.3 D3：端到端夾取整合"),
    (
        "Content",
        "在接近能力驗證成立之基礎上，本研究進一步將任務鏈延伸至夾取（實驗代號 D3）："
        "機械手臂以聲學估距接近目標並停止後，執行以下固定之夾取序列："
        "（一）以停止當下之聲學估距推算目標位置（停止位置加上估距即為目標之推算座標——"
        "此為一次性推算，因為校正之有效距離下限為 0.32 m，夾取階段之更近距離已在有效範圍之外，"
        "故不再以聲學量測回授）；（二）手臂抬升至安全通過高度（夾爪指尖高於目標頂面約 3 cm），"
        "沿水平方向以 2 cm 步長移動至推算座標之正上方；（三）垂直下降至夾取高度"
        "（指尖低於目標頂面、包夾目標之中上段）；（四）閉合夾爪並偵測接觸；"
        "（五）附著成立後垂直升舉 0.10 m（以 5 mm 小步執行，每步後等待物理穩定），"
        "維持 60 影格後量測目標之實際高度變化，升幅達 0.05 m 以上判定升舉成功。"
        "全程與接近階段相同，控制器不讀取目標之真實世界座標；"
        "目標真實位置僅用於事後評估夾取對位之準確度。"
        "目標物更換為可被夾爪開口容納之直立長方柱（截面 0.06 m 見方、高 0.12 m），"
        "由於「更換目標物」使前章之可偵測性與距離校正結論不再當然適用，"
        "正式實驗前先執行三道前置閘門並全數通過：目標物可偵測性"
        "（三個距離下之配對移除訊噪比 31.9–82.3，全數高於門檻 10）、"
        "距離編碼有效性（重新校正之相關係數 r=0.996）、"
        "以及夾取動作力學有效性（十次已知位置之完整夾取序列，姿態稽核零違規）。",
    ),
    (
        "Content",
        "夾持機制之如實說明：本研究於開發過程中發現，模擬器對夾爪指墊與物體間摩擦力之模擬"
        "不足以在升舉過程中持續抓持物體（經二十餘輪系統性排查，"
        "含目標物尺寸、摩擦係數、質量、閉合速度與夾取高度等變因，均無法使摩擦夾持成立），"
        "故夾持改以「接觸觸發之固定關節」模擬：夾爪閉合時，"
        "若手指因物體阻擋而停止於未完全閉合之角度（此為純物理之接觸訊號，不涉及任何目標座標資訊），"
        "即在夾爪與物體之間建立剛性附著，隨後升舉。"
        "此設計保留了對照實驗之區辨力——盲走臂停在錯誤位置時，夾爪閉合時抓空、手指完全閉合、"
        "不觸發附著，夾取即失敗——因此夾取成功與否仍忠實反映對位品質。"
        "本文據此明確界定宣稱範圍：可宣稱「聲學對位＋接觸觸發附著之端到端夾取」，"
        "不可宣稱「物理摩擦夾持」；後者屬模擬器保真度限制，列入未來工作。",
    ),
    (
        "Content",
        "D3 三臂結果（各 30 個試驗回合，目標隨機置於 1.00–1.20 m 範圍）："
        "聲學臂之夾取中心與目標位置相關係數 r=0.9885、對位誤差均方根 1.9 cm，"
        "對位成功率（誤差在預先鎖定之 2 cm 容差內）為 18/30（60%）；"
        "盲走臂與開環臂皆恆停於固定名義位置，對位成功率同為 7/30（23%）——"
        "此 23% 恰為固定停止點與隨機目標「碰巧」落在容差內之先驗機率，"
        "與目標實際位置無關（相關係數為 0）。"
        "聲學臂與盲走臂對位率之差異以費雪精確檢定（Fisher's exact test，"
        "一種適用於小樣本二乘二列聯表、直接計算精確機率之統計檢定）檢驗，"
        "單尾 p=0.004，達統計顯著水準。對位成功之試驗回合中，附著升舉成功率為 15/18（83%）；"
        "本文依預先寫定之報告格式，將對位成功率與升舉成功率分開陳報，"
        "不將兩者相乘為單一「總成功率」，以避免混淆對位（聲學能力）與夾持（力學能力）兩個不同層次之因果。",
    ),
    (
        "Content",
        "誠實記錄：D3 之四項預先寫定判準中，三項通過（對位追蹤、對位優於盲走、對位後升舉如實陳報），"
        "一項未通過——姿態全淨判準因 90 個試驗回合中有 3 個回合在升舉階段出現逆向運動學無解而判定不通過。"
        "該 3 個回合之目標皆位於工作走廊之最遠端（約 1.19 m），"
        "手臂於該處已接近其運動學可達範圍之極限，無法再向上抬升 0.10 m；"
        "接近階段之全部 130 個控制步之姿態與感測器位姿稽核則完全乾淨。"
        "此失效模式屬手臂構型之可達性邊界，與聲學感測無關；"
        "本文依預先寫定之判準字面如實判定不通過、不作事後放寬，"
        "並記錄修正方向（縮減走廊遠端邊界或降低升舉高度）供後續驗證。",
    ),
    (
        "TableCaption",
        "表5.2  D3 三臂對照（夾取對位與附著升舉）",
    ),
    (
        "Table",
        ["臂", "r(夾取中心, 目標)", "對位率（±2 cm）", "對位誤差 RMSE", "P(升舉|對位)"],
        [
            ["聲學臂", "0.9885", "18/30（60%）", "1.9 cm", "15/18（83%）"],
            ["盲走臂", "0（恆停名義點）", "7/30（23%）", "5.4 cm", "4/7"],
            ["開環臂", "0（恆停名義點）", "7/30（23%）", "5.3 cm", "5/7"],
        ],
    ),
    ("Header2", "5.4 盲走臂／開環臂對照組的角色"),
    (
        "Content",
        "盲走臂與開環臂在本研究中扮演不同但互補之角色，皆不可省略。"
        "盲走臂之核心作用在於證明「僅拿掉聲學資訊，同一套控制管線即完全失能」，"
        "藉此排除聲學臂之接近行為僅是幾何巧合、走廊設計本身、或量測管線副作用（如量測所需之等待時間）"
        "所造成的可能性——因為盲走臂之量測管線與聲學臂完全相同，唯一差異僅在於控制器"
        "是否實際使用估距結果做出停止決策。",
    ),
    (
        "Content",
        "開環臂則扮演另一種角色：作為完全不執行任何量測之固定行程基準線（baseline）。"
        "D1.5 之隨機目標帶寬度僅 0.30 m，在此相對狹窄之範圍內，"
        "即使是固定行程之開環臂，其表現亦不算差（均方根誤差 7.8 cm、73% 之試驗回合誤差在 10 cm 以內）。"
        "然而開環臂之區辨力僅止於單一固定停止點，本質上無法逐試驗回合追蹤隨機變化之目標位置"
        "（相關係數 r=0）。聲學臂之優勢因此並非單純反映在誤差量級之比較上"
        "（2.8 cm 對 7.8 cm 雖有明顯差距，但兩者量級接近同一數量級），"
        "而是反映在相關係數之本質差異（0.9856 對 0）與到達率之一致性（100% 對 73%）："
        "唯有聲學臂能夠對每一個隨機出現之目標位置做出對應之停止決策，此為因果關係之直接證據。"
        "此一觀察亦是第六章 6.1 節「實驗效度設計」討論之核心論據來源。",
    ),
]

# ---------------------------------------------------------------------------
# Chapter 6 (rewritten)
# ---------------------------------------------------------------------------

CH6 = [
    ("Header1", "第六章、討論與限制"),
    ("Header2", "6.1 實驗效度設計之討論"),
    (
        "Content",
        "三臂對照設計之必要性，可直接由 D1.5 之開環臂實測數據具體說明，而不需仰賴假設性論證。"
        "僅執行固定行程、完全不進行任何量測之開環臂，在本實驗僅 0.30 m 寬之目標帶設定下，"
        "即可達成 22/30（73%）之到達率；若研究僅以到達率作為評估閉環系統之主指標，"
        "將嚴重高估其真實之接近能力——因為此到達率絕大部分來自目標帶本身之幾何寬度，"
        "而非任何形式之感測回授。開環臂之停止位置與目標位置之相關係數為 0，"
        "顯示其逐試驗回合之表現與隨機出現之目標位置完全無關，僅反映走廊寬度與固定停止點之幾何巧合。",
    ),
    (
        "Content",
        "唯有同時檢視兩項指標，方能可靠區辨接近行為之因果是否確實來自聲學資訊："
        "其一為停止位置與目標位置之相關性（本研究之聲學臂達 0.9856，開環臂則為 0）；"
        "其二為資訊消融對照之結果（將估距通道置換為無資訊值 +∞ 之盲走臂，"
        "在同一套量測與控制管線下僅能達成 4/30 之到達率，與聲學臂之 30/30 形成鮮明對比）。"
        "此三臂對照設計與以停止位置相關性、而非到達率作為預先寫定之主指標，"
        "構成本研究確保閉環宣稱效度之核心實驗方法，其設計原則不限於超音波感測領域，"
        "亦可推廣應用於其他仰賴模擬環境驗證感測回授控制系統之機器人研究，"
        "作為區辨「真實感測驅動」與「場景幾何巧合」之通用驗證框架。",
    ),
    ("Header2", "6.2 Claim boundary（可宣稱與不可宣稱之範圍界定）"),
    (
        "Content",
        "本研究可宣稱之結論如下：其一，純聲學閉環控制迴路（全程不讀取目標之真實世界座標）"
        "可驅動 UR10e 機械手臂接近隨機擺放於桌面之目標，停止誤差達 2.8 cm 均方根誤差、"
        "30 個試驗回合全數成功，此結果經三臂資訊消融對照與逐步姿態稽核驗證"
        "（驗證範圍為模擬環境、單一隨機種子系列、確定性物理引擎）；"
        "其二，聲學閉環可進一步完成端到端夾取對位（夾取中心與目標相關係數 r=0.9885、"
        "對位誤差均方根 1.9 cm、對位率顯著優於盲走對照），"
        "且對位成功後之接觸觸發附著升舉成功率為 83%；"
        "其三，本研究建立之 WPM 感測包絡系統性量測方法（52 格配對移除掃描、36/52 可偵測）"
        "提供了一套可重複之感測器擺位設計規範，感測器距離編碼之量化特性表亦已建立"
        "（相關係數 r=0.9994，桌面高度目標之均方根誤差為 5.3 mm）；"
        "其四，側向資訊可經手臂運動合成之多點定位演算法自單軸測距恢復"
        "（十三個已知位置之驗證中，側向估計相關係數 r=0.960、誤差均方根 3.4 cm）；"
        "其五，本研究對失效機制提供了實證歸因（腕載聲影、側向四重證偽、頻率參數無效），"
        "並提出可推廣之三臂對照實驗效度設計。",
    ),
    (
        "Content",
        "本研究不可宣稱之結論包括：物理摩擦夾持能力（本研究之夾持以接觸觸發之固定關節模擬，"
        "夾爪指墊摩擦之保真度限制詳見 5.3 節，實體夾爪之夾持表現未經驗證）；"
        "單次量測內之側向感知能力（第四章 4.3 節已以四項實驗證偽；"
        "多點定位為多次量測之演算法恢復，且其完整三臂對照實驗尚未執行）；"
        "任何部署級或實機環境下之效能表現；預定停止距離 0.35 m 以內之聲學控制"
        "（桌面高度目標之距離編碼已知於 0.32 m 以內失效，夾取階段於此範圍內採停止當下估距之"
        "一次性推算，不宣稱該範圍內之閉環量測能力）；"
        "以及跨隨機種子之統計穩健性（本研究為單一隨機種子之確定性模擬，"
        "尚未驗證於不同隨機種子下之表現一致性）。",
    ),
    ("Header2", "6.3 未來工作"),
    (
        "Content",
        "夾持物理保真度與姿態全淨之補完：本研究之端到端夾取已驗證聲學對位能力（5.3 節），"
        "但夾爪指墊之摩擦夾持受模擬器保真度限制而以附著機制替代，"
        "且工作走廊最遠端存在升舉階段之運動學可達性邊界（3/90 個回合受影響）。"
        "未來工作一為在後續版本模擬器或實體夾爪上重新檢驗摩擦夾持，"
        "二為以縮減之走廊範圍重新執行對照實驗，使四項判準全數通過。",
    ),
    (
        "Content",
        "多點定位之完整對照實驗：側向感知之感測器原生路徑已於本研究四重證偽"
        "（含「將兩接收器分編為獨立群組」之組態實驗，詳見 4.3 節），"
        "而多點定位演算法之可行性探針已通過（側向相關係數 r=0.960）。"
        "未來工作為將此定位能力納入完整之三臂對照閉環實驗："
        "目標同時隨機分佈於前向與側向、聲學臂以五視點定位後執行二維接近、"
        "盲走臂與開環臂如常對照，以資訊消融確認二維接近之因果同樣來自聲學。"
        "此實驗之場景、判準與誤差預算均已設計完成，惟執行與分析尚待進行。",
    ),
    (
        "Content",
        "強化學習策略之延伸：本研究現行之控制器為規則式比例步進控制，"
        "邏輯簡單且透明，便於因果分析與稽核，但未必是最具效率或最能泛化之控制策略。"
        "如第二章所述，Isaac Sim 與其延伸之 Isaac Lab 訓練框架（NVIDIA, 2026d）"
        "已提供大規模 GPU 並行模擬之基礎設施，配合 Rudin 等（2022）展示之大規模並行策略訓練方法"
        "與 Schulman 等（2017）之近端策略最佳化演算法，未來工作可探索以強化學習訓練之控制策略"
        "取代現行規則式控制器，並以本研究已建立之三臂對照與稽核框架驗證其效度，確保學習型策略"
        "之閉環行為因果亦可被清楚歸屬於感測資訊，而非訓練過程中意外習得之場景捷徑。"
        "此外，本研究各實驗過程中留存之逐步原始波形與手臂位姿資料"
        "（接近、夾取與定位實驗合計數百個試驗回合），"
        "亦可直接作為監督式狀態估計（如以聲學特徵回歸感測器位姿、偵測目標存在與否）之訓練資料，"
        "此為不需額外模擬成本即可展開之延伸方向。",
    ),
    (
        "Content",
        "實機對應：後續可規劃對應於商用超音波測距晶片（如 TDK CH201）等級之實機任務級驗證協定，"
        "檢驗本研究於模擬環境中建立之感測包絡地圖與三臂對照結論，"
        "在真實聲學環境、真實感測器硬體與真實機械手臂動力學下之可移轉性，"
        "作為本研究模擬結論邁向實際應用前之最終驗證環節。",
    ),
]

# Apply numeric-citation replacement to the remaining chapters too (CH2_FIXED
# was already done above, at definition time). No author-year citations are
# currently known outside Chapter 2, but this keeps the mechanism general.
CH1 = _replace_citations_in_items(CH1)
CH3 = _replace_citations_in_items(CH3)
CH4 = _replace_citations_in_items(CH4)
CH5 = _replace_citations_in_items(CH5)
CH6 = _replace_citations_in_items(CH6)

# ---------------------------------------------------------------------------
# Mechanism (copied from rebuild_thesis_six_chapters.py)
# ---------------------------------------------------------------------------


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
            from docx.shared import Inches

            new_p.add_run().add_picture(str(path), width=Inches(5.2))
            cap = insert_paragraph_after(new_p)
            set_text(cap, caption, "Content", center=True)
            prev = cap
            continue
        elif kind == "TableCaption":
            set_text(new_p, item[1], "Content", center=True)
        prev = new_p
    return prev


def paragraph_text(element) -> str:
    texts = []
    for node in element.iter():
        if node.tag.endswith("}t") and node.text:
            texts.append(node.text)
    return "".join(texts).strip()


def remove_body_between(doc: Document, start_marker: str, end_marker: str) -> None:
    body = doc.element.body
    start_el = end_el = None
    for child in list(body):
        if child.tag.endswith("}p"):
            text = paragraph_text(child)
            if text == start_marker and start_el is None:
                start_el = child
            if text == end_marker and start_el is not None:
                end_el = child
                break
    if start_el is None or end_el is None:
        raise RuntimeError("Cannot find body block")

    removing = False
    for child in list(body):
        if child is start_el:
            removing = True
            body.remove(child)
            continue
        if child is end_el:
            break
        if removing:
            body.remove(child)


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
    remove_body_between(doc, "第一章、緒論", "參考文獻")

    body = CH1 + [("Header1", "第二章、文獻探討")] + CH2_FIXED + CH3 + CH4 + CH5 + CH6
    append_items(doc, anchor, body)

    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "參考文獻":
            nxt = doc.paragraphs[i + 1] if i + 1 < len(doc.paragraphs) else None
            if nxt is not None:
                set_text(nxt, REFERENCES_NUMBERED, "Content")
                # The v1 template stores each reference entry as its own
                # paragraph (one "w:p" per entry), not as one paragraph with
                # embedded line breaks; `nxt` is only the first of these.
                # Rewriting just `nxt` leaves the remaining old, unnumbered
                # entry paragraphs trailing after it (they are the last
                # thing in the document body), so remove them.
                for extra in list(doc.paragraphs[i + 2:]):
                    remove_paragraph(extra)
            break


def _norm(t: str) -> str:
    return t.replace(" ", "").replace("　", "").strip()


def replace_front_matter(doc: Document) -> None:
    """Replace 摘要/Abstract body paragraphs and keyword lines (V2 narrative).

    Locates Header1 "摘  要" / "Abstract" and replaces the immediately
    following Normal paragraph's text; keyword lines are matched by prefix.
    """
    paras = doc.paragraphs
    for i, p in enumerate(paras):
        t = _norm(p.text)
        if p.style.name == "Header1" and t == "摘要":
            if i + 1 < len(paras):
                set_text(paras[i + 1], ABSTRACT_ZH, "Normal")
        elif p.style.name == "Header1" and t == "Abstract":
            if i + 1 < len(paras):
                set_text(paras[i + 1], ABSTRACT_EN, "Normal")

    for p in doc.paragraphs:
        t = p.text.strip()
        if t.startswith("關鍵詞："):
            set_text(p, KEYWORDS_ZH, "Normal")
        elif t.startswith("Keywords:"):
            set_text(p, KEYWORDS_EN, "Normal")


def _toc_entries() -> list[tuple[str, str]]:
    """Derive the static TOC from the V2 body structure (the template's TOC
    paragraphs are plain text, not a Word field, so they must be rebuilt
    whenever the body changes — the v1 template's TOC still listed the OLD
    chapter structure and contained corrupted concatenated lines)."""
    entries: list[tuple[str, str]] = [
        ("toc 1", "誌  謝"),
        ("toc 1", "摘  要"),
        ("toc 1", "Abstract"),
    ]
    body = CH1 + [("Header1", "第二章、文獻探討")] + CH2_FIXED + CH3 + CH4 + CH5 + CH6
    for item in body:
        if item[0] == "Header1":
            entries.append(("toc 1", item[1]))
        elif item[0] == "Header2":
            entries.append(("toc 2", item[1]))
    entries.append(("toc 1", "參考文獻"))
    return entries


def _set_toc_text(p: Paragraph, text: str, style: str) -> None:
    """Hard-replace a TOC paragraph's content at the XML level.

    Template TOC paragraphs contain w:hyperlink elements; python-docx's run
    APIs do not clear runs nested inside hyperlinks, so naive set_text APPENDS
    after the surviving old text (this is also how the v1 template's TOC got
    its concatenated corrupted lines). Remove every child except w:pPr, then
    add a fresh run."""
    pel = p._p
    for child in list(pel):
        if not child.tag.endswith("}pPr"):
            pel.remove(child)
    p.style = style
    p.add_run(text)


def rebuild_toc(doc: Document) -> None:
    """Replace all existing toc-styled paragraphs with the V2 structure
    (page numbers are patched in a second pass from the rendered PDF)."""
    toc_paras = [p for p in doc.paragraphs if p.style.name in ("toc 1", "toc 2")]
    if not toc_paras:
        print("WARN: no toc paragraphs found; skipping TOC rebuild")
        return
    entries = _toc_entries()
    # Reuse existing toc paragraphs in place; add/remove to match count.
    n_reuse = min(len(toc_paras), len(entries))
    for p, (style, title) in zip(toc_paras[:n_reuse], entries[:n_reuse]):
        _set_toc_text(p, title, style)
    for p in toc_paras[n_reuse:]:
        remove_paragraph(p)
    anchor = toc_paras[n_reuse - 1]
    for style, title in entries[n_reuse:]:
        anchor = insert_paragraph_after(anchor, style)
        _set_toc_text(anchor, title, style)
    print(f"TOC rebuilt: {len(entries)} entries")


def _pdf_page_of(headings: list[str], pdf_path: Path) -> dict[str, int]:
    """Map each heading to the first PDF page containing it (monotonic scan).

    Two gotchas handled here (observed 2026-07-09, first pass patched only
    17/36): pdftotext page text contains newlines inside wrapped headings, so
    normalization must strip ALL whitespace; and the TOC page itself contains
    every heading, so pages holding many entry titles at once (>=8) are
    treated as TOC pages and excluded from the search."""
    import re
    import subprocess
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, check=True,
    )
    pages = result.stdout.split("\f")
    norm_pages = [re.sub(r"\s+", "", pg) for pg in pages]
    keys = [_norm(h) for h in headings]
    toc_like = set()
    for idx, pg in enumerate(norm_pages):
        hits = sum(1 for k in keys if k and k in pg)
        if hits >= 8:
            toc_like.add(idx)
    mapping: dict[str, int] = {}
    page_ptr = 0
    for h, key in zip(headings, keys):
        for idx in range(page_ptr, len(norm_pages)):
            if idx in toc_like:
                continue
            if key and key in norm_pages[idx]:
                mapping[h] = idx + 1
                page_ptr = idx
                break
    return mapping


def _convert_pdf() -> Path:
    import subprocess
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf",
         "--outdir", str(DOC_OUT.parent), str(DOC_OUT)],
        capture_output=True, text=True, check=True,
    )
    return DOC_OUT.with_suffix(".pdf")


def patch_toc_pages() -> None:
    """Second pass: render PDF, locate each TOC heading's page, write the
    page numbers back into the TOC lines (tab-separated, matching the
    template's toc style), then re-render the final PDF."""
    pdf_path = _convert_pdf()
    entries = _toc_entries()
    mapping = _pdf_page_of([t for _, t in entries], pdf_path)
    doc = Document(str(DOC_OUT))
    patched = 0
    for p in doc.paragraphs:
        if p.style.name in ("toc 1", "toc 2"):
            title = p.text.split("\t")[0].strip()
            if title in mapping:
                _set_toc_text(p, f"{title}\t{mapping[title]}", p.style.name)
                patched += 1
    doc.save(str(DOC_OUT))
    _convert_pdf()
    print(f"TOC page numbers patched: {patched}/{len(entries)} (final PDF regenerated)")


def main() -> None:
    if not DOC_IN.exists():
        raise FileNotFoundError(f"Input template not found: {DOC_IN}")
    doc = Document(str(DOC_IN))
    replace_front_matter(doc)
    # Body FIRST, then TOC: freshly rebuilt TOC lines carry no page suffix
    # yet, so their text exactly equals the chapter anchors replace_body
    # searches for — running rebuild_toc first makes replace_body anchor onto
    # the TOC block and splice the chapters there (observed 2026-07-09).
    replace_body(doc)
    rebuild_toc(doc)
    doc.save(str(DOC_OUT))
    print(f"Wrote V2 thesis draft: {DOC_OUT}")
    patch_toc_pages()


if __name__ == "__main__":
    main()
