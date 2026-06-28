#!/usr/bin/env python3
"""Update thesis cover metadata for 電聲碩士學位學程."""

from pathlib import Path

from docx import Document

DOC = Path(__file__).resolve().parent / "THESIS_DRAFT_FCU_v1.docx"

PROGRAM = "電聲碩士學位學程"
TITLE_ZH = (
    "UR10 末端 RTX 聲學感測之可審計模擬管線研究："
    "室內聲學特徵驗證與 Isaac Lab 延伸"
)
DATE = "中華民國 115 年 6 月"
ADVISOR_LINE = "指導教授：蔡鈺鼎 教授"


def replace_paragraph_text(paragraph, new_text: str) -> None:
    for run in paragraph.runs:
        run._element.getparent().remove(run._element)
    paragraph.add_run(new_text)


def main() -> None:
    doc = Document(str(DOC))
    for p in doc.paragraphs:
        t = p.text.strip()
        if t == "智能製造與工程管理碩士在職學位學程":
            replace_paragraph_text(p, PROGRAM)
        elif t.startswith("UR10 末端 RTX"):
            replace_paragraph_text(p, TITLE_ZH)
        elif t.startswith("中華民國") and "年" in t:
            replace_paragraph_text(p, DATE)

    # Insert advisor line after date if not present
    has_advisor = any("蔡鈺鼎" in p.text for p in doc.paragraphs)
    if not has_advisor:
        for i, p in enumerate(doc.paragraphs):
            if p.text.strip() == DATE:
                new_p = p._element
                from docx.oxml import OxmlElement
                from docx.text.paragraph import Paragraph

                advisor_xml = OxmlElement("w:p")
                new_p.addnext(advisor_xml)
                advisor_para = Paragraph(advisor_xml, p._parent)
                replace_paragraph_text(advisor_para, ADVISOR_LINE)
                break

    doc.save(str(DOC))
    print(f"Updated cover: {DOC}")


if __name__ == "__main__":
    main()