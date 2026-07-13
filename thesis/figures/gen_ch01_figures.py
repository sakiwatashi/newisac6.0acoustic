#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一章論文示意圖 — Pillow + Noto CJK（避開 matplotlib 缺字／Colab 預設風格）。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "ch01"
OUT.mkdir(parents=True, exist_ok=True)

FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# 論文線稿：白底、細線、低彩
INK = (30, 30, 30)
MUTED = (90, 90, 90)
LINE = (50, 50, 50)
FILL_A = (245, 247, 250)  # cool gray
FILL_B = (242, 248, 244)  # cool green-gray
FILL_C = (250, 246, 240)  # warm gray
FILL_D = (252, 244, 244)  # soft rose
WHITE = (255, 255, 255)
ACCENT = (45, 85, 120)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REG
    return ImageFont.truetype(path, size=size, index=0)


def text_size(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=f)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_center(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    text: str,
    f: ImageFont.ImageFont,
    fill=INK,
) -> None:
    lines = text.split("\n")
    heights = []
    widths = []
    for line in lines:
        w, h = text_size(draw, line, f)
        widths.append(w)
        heights.append(h)
    gap = 6
    total_h = sum(heights) + gap * (len(lines) - 1)
    y = cy - total_h / 2
    for line, w, h in zip(lines, widths, heights):
        draw.text((cx - w / 2, y), line, font=f, fill=fill)
        y += h + gap


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill,
    outline=LINE,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def arrow_right(draw: ImageDraw.ImageDraw, x0: int, y: int, x1: int, color=LINE, w: int = 2) -> None:
    draw.line([(x0, y), (x1 - 8, y)], fill=color, width=w)
    draw.polygon([(x1, y), (x1 - 12, y - 6), (x1 - 12, y + 6)], fill=color)


def save(im: Image.Image, stem: str) -> None:
    png = OUT / f"{stem}.png"
    im.save(png, "PNG")
    # PDF via pillow if available; also keep high-res png
    try:
        rgb = im.convert("RGB")
        rgb.save(OUT / f"{stem}.pdf", "PDF", resolution=200.0)
    except Exception:
        pass
    print("wrote", stem, im.size)


# ---------------------------------------------------------------------------
# Fig 1-1 hierarchy
# ---------------------------------------------------------------------------
def fig_1_1() -> None:
    W, H = 1400, 720
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    title_f = font(32, bold=True)
    body_f = font(22)
    small_f = font(18)

    title = "圖 1-1  階層式接近示意（互補而非取代）"
    tw, _ = text_size(d, title, title_f)
    d.text(((W - tw) / 2, 36), title, font=title_f, fill=INK)

    # two boxes
    left = (80, 140, 620, 400)
    right = (780, 140, 1320, 400)
    rounded_rect(d, left, 18, FILL_A, ACCENT, 3)
    rounded_rect(d, right, 18, FILL_B, (60, 110, 80), 3)
    draw_text_center(
        d,
        (left[0] + left[2]) / 2,
        (left[1] + left[3]) / 2,
        "上層：視覺語言模型（VLM）\n場景理解・語義・粗定位\n大範圍導航",
        body_f,
    )
    draw_text_center(
        d,
        (right[0] + right[2]) / 2,
        (right[1] + right[3]) / 2,
        "下層：超音波感測回授\n已知搜尋走廊內距離趨勢\n最後一公尺精細接近",
        body_f,
    )
    arrow_right(d, 640, 270, 760, ACCENT, 3)

    mid = "交接：粗定位完成後進入已知工作帶"
    mw, _ = text_size(d, mid, small_f)
    d.text(((W - mw) / 2, 430), mid, font=small_f, fill=MUTED)

    bot = (80, 500, 1320, 660)
    rounded_rect(d, bot, 14, WHITE, LINE, 2)
    draw_text_center(
        d,
        (bot[0] + bot[2]) / 2,
        (bot[1] + bot[3]) / 2,
        "本研究範圍：下層非視覺元件的可驗證閉環接近\n"
        "不宣稱取代相機或 VLM；提供可量化效度的最後一公尺感測回授",
        body_f,
    )
    save(im, "fig_1_1_last_meter_hierarchy")


# ---------------------------------------------------------------------------
# Fig 1-2 RQ map
# ---------------------------------------------------------------------------
def fig_1_2() -> None:
    W, H = 1500, 900
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    title_f = font(32, bold=True)
    head_f = font(20, bold=True)
    body_f = font(20)

    title = "圖 1-2  研究問題（RQ）與實驗代號對照"
    tw, _ = text_size(d, title, title_f)
    d.text(((W - tw) / 2, 28), title, font=title_f, fill=INK)

    cols = [(90, "研究問題"), (520, "要回答的事"), (1080, "對應實驗")]
    for x, lab in cols:
        lw, _ = text_size(d, lab, head_f)
        d.text((x + 160 - lw / 2, 100), lab, font=head_f, fill=ACCENT)

    rows = [
        ("RQ1 感測包絡", "何種幾何下讀得到目標？", "S1 包絡地圖\nS2 量化特性", FILL_A),
        ("RQ2 聲學閉環", "純聲學能否驅動接近？因果？", "D1 未掛臂\nD1.5 手臂主結果", FILL_B),
        ("RQ3 實驗效度", "如何排除幾何巧合？", "三臂對照・預註冊\n姿態與量測稽核", FILL_C),
        ("RQ4 範圍邊界", "夾取與側向邊界在哪？", "D3 夾取整合\nD2 二維多點定位", FILL_D),
    ]
    y0 = 150
    row_h = 160
    gap = 20
    for i, (a, b, c, fill) in enumerate(rows):
        y = y0 + i * (row_h + gap)
        boxes = [
            (70, y, 400, y + row_h, a),
            (430, y, 980, y + row_h, b),
            (1010, y, 1430, y + row_h, c),
        ]
        for x0, y0b, x1, y1, text in boxes:
            rounded_rect(d, (x0, y0b, x1, y1), 12, fill if text == a or text == c else WHITE, LINE, 2)
            draw_text_center(d, (x0 + x1) / 2, (y0b + y1) / 2, text, body_f if text != a else font(21, True))
        # arrows between
        arrow_right(d, 405, y + row_h // 2, 425, LINE, 2)
        arrow_right(d, 985, y + row_h // 2, 1005, LINE, 2)

    save(im, "fig_1_2_rq_experiment_map")


# ---------------------------------------------------------------------------
# Fig 1-3 platform
# ---------------------------------------------------------------------------
def fig_1_3() -> None:
    W, H = 1600, 620
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    title_f = font(32, bold=True)
    body_f = font(22)
    small_f = font(18)

    title = "圖 1-3  實驗平台鏈（軟硬體環境）"
    tw, _ = text_size(d, title, title_f)
    d.text(((W - tw) / 2, 30), title, font=title_f, fill=INK)

    items = [
        (60, "Isaac Sim 6.0\n場景・物理\nUSD 表示", FILL_A),
        (430, "RTX Acoustic\nWPM 波傳\nGMO 輸出", FILL_B),
        (800, "UR10e\n六軸協作臂\n運動載具", FILL_C),
        (1170, "Robotiq 2F-85\n二指夾爪\n僅 D3 啟用", FILL_D),
    ]
    box_w, box_h = 300, 220
    y = 140
    for i, (x, text, fill) in enumerate(items):
        rounded_rect(d, (x, y, x + box_w, y + box_h), 16, fill, LINE, 2)
        draw_text_center(d, x + box_w / 2, y + box_h / 2, text, body_f)
        if i < len(items) - 1:
            arrow_right(d, x + box_w + 8, y + box_h // 2, items[i + 1][0] - 8, ACCENT, 3)

    foot1 = "感測回授閉環：觀測（Acoustic）→ 估距 → 手臂運動（UR10e）→（可選）夾取"
    foot2 = "官方文件見論文 1.5 節引用"
    for i, (txt, f) in enumerate([(foot1, small_f), (foot2, font(16))]):
        tw, _ = text_size(d, txt, f)
        d.text(((W - tw) / 2, 430 + i * 40), txt, font=f, fill=MUTED if i else INK)

    save(im, "fig_1_3_platform_chain")


# ---------------------------------------------------------------------------
# Fig 1-4 mount
# ---------------------------------------------------------------------------
def fig_1_4() -> None:
    W, H = 1300, 900
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    title_f = font(30, bold=True)
    body_f = font(20)
    small_f = font(17)

    title = "圖 1-4  腕載感測器前伸示意（避開聲學陰影）"
    tw, _ = text_size(d, title, title_f)
    d.text(((W - tw) / 2, 24), title, font=title_f, fill=INK)

    # notes top
    n1 = "D1.5／D3：感測器掛腕部並前伸，離開夾爪網格遮蔽區（見 4.3 腕載聲影）"
    n2 = "D1：感測器可為未掛臂之獨立物件（隔離感測＋控制）"
    for i, t in enumerate([n1, n2]):
        tw, _ = text_size(d, t, small_f)
        d.text(((W - tw) / 2, 90 + i * 32), t, font=small_f, fill=MUTED)

    # table
    d.rectangle([200, 720, 1100, 780], fill=(210, 210, 210), outline=LINE, width=2)
    t = "工作桌（示意）"
    tw, _ = text_size(d, t, small_f)
    d.text((650 - tw / 2, 795), t, font=small_f, fill=MUTED)

    # base
    d.rectangle([240, 620, 320, 720], fill=(120, 120, 120), outline=LINE, width=2)
    d.text((245, 590), "基座", font=small_f, fill=MUTED)

    # arm polyline
    pts = [(280, 620), (420, 420), (620, 460), (800, 500)]
    d.line(pts, fill=ACCENT, width=8)
    for p in pts:
        d.ellipse([p[0] - 8, p[1] - 8, p[0] + 8, p[1] + 8], fill=ACCENT, outline=LINE)
    d.text((400, 370), "UR10e 連桿（示意）", font=small_f, fill=ACCENT)

    # wrist
    d.rectangle([780, 480, 830, 530], fill=(139, 90, 43), outline=LINE, width=2)
    d.text((770, 540), "腕部", font=small_f, fill=MUTED)

    # shadow ellipse
    d.ellipse([820, 520, 980, 680], outline=(166, 93, 87), width=2)
    # fill light
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse([820, 520, 980, 680], fill=(245, 208, 208, 90), outline=(166, 93, 87, 255), width=2)
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(im)
    d.text((835, 690), "夾爪聲學陰影", font=small_f, fill=(140, 60, 55))

    # extension arrow + sensor
    d.line([(830, 505), (1020, 505)], fill=(60, 120, 80), width=5)
    d.polygon([(1035, 505), (1015, 495), (1015, 515)], fill=(60, 120, 80))
    d.text((880, 455), "前伸 0.25 m", font=font(19, True), fill=(40, 100, 60))
    d.ellipse([1025, 480, 1095, 550], fill=(90, 150, 110), outline=LINE, width=2)
    d.text((1010, 560), "超音波感測器", font=body_f, fill=(40, 90, 60))

    # boresight
    d.line([(1095, 515), (1220, 515)], fill=MUTED, width=2)
    d.polygon([(1235, 515), (1215, 505), (1215, 525)], fill=MUTED)
    d.text((1120, 475), "視軸水平", font=small_f, fill=MUTED)

    # height
    d.line([(170, 515), (170, 720)], fill=MUTED, width=2)
    d.line([(160, 515), (180, 515)], fill=MUTED, width=2)
    d.line([(160, 720), (180, 720)], fill=MUTED, width=2)
    d.text((95, 600), "約\n0.65 m", font=small_f, fill=MUTED)

    save(im, "fig_1_4_sensor_mount_extension")


# ---------------------------------------------------------------------------
# Fig 1-5 multipath
# ---------------------------------------------------------------------------
def fig_1_5() -> None:
    W, H = 1300, 780
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    title_f = font(30, bold=True)
    body_f = font(20)
    small_f = font(17)

    title = "圖 1-5  多徑與殘響概念示意（室內主動聲學）"
    tw, _ = text_size(d, title, title_f)
    d.text(((W - tw) / 2, 28), title, font=title_f, fill=INK)

    # wall
    d.line([(80, 160), (1220, 160)], fill=(100, 100, 100), width=10)
    t = "牆面／其他反射面"
    tw, _ = text_size(d, t, small_f)
    d.text(((W - tw) / 2, 120), t, font=small_f, fill=MUTED)

    # TX/RX
    d.rectangle([140, 400, 220, 480], fill=ACCENT, outline=LINE, width=2)
    d.text((135, 500), "TX／RX", font=body_f, fill=INK)

    # target
    d.rectangle([980, 390, 1100, 510], fill=FILL_C, outline=(139, 90, 43), width=2)
    d.text((1005, 530), "目標", font=body_f, fill=INK)

    # direct path
    d.line([(220, 440), (980, 440)], fill=(60, 120, 80), width=4)
    d.polygon([(980, 440), (955, 428), (955, 452)], fill=(60, 120, 80))
    d.text((480, 390), "直達／最短路徑（往返）", font=font(19, True), fill=(40, 100, 60))

    # multipath via wall
    d.line([(220, 400), (650, 170), (980, 400)], fill=(160, 70, 60), width=3)
    # small arrow near target
    d.polygon([(980, 400), (955, 385), (960, 415)], fill=(160, 70, 60))
    d.text((560, 220), "多徑（多次反射）", font=body_f, fill=(140, 50, 45))

    foot1 = "殘響：較晚到達的回波在時間上拖尾疊加；單看一個峰不足以斷定物理路徑"
    foot2 = "本文以配對移除隔離目標貢獻（程序見第三章）"
    for i, (txt, f) in enumerate([(foot1, small_f), (foot2, small_f)]):
        tw, _ = text_size(d, txt, f)
        d.text(((W - tw) / 2, 640 + i * 40), txt, font=f, fill=MUTED if i else INK)

    save(im, "fig_1_5_multipath_concept")


def write_readme() -> None:
    (OUT / "README.md").write_text(
        """# 第一章 圖檔（重製版・供審閱）

路徑：`thesis/figures/ch01/`

## 技術
- **Pillow** 直接繪製（不用 matplotlib）
- 字型：**Noto Sans CJK Regular/Bold**（`.ttc` index=0），中英數字同一字型
- 風格：論文線稿、白底、細線、低彩（避免 Colab／seaborn 預設感）

## 檔案
| 檔名 | 圖號 | 小節 |
|------|------|------|
| fig_1_1_last_meter_hierarchy | 圖 1-1 | 1.1 |
| fig_1_2_rq_experiment_map | 圖 1-2 | 1.2 |
| fig_1_3_platform_chain | 圖 1-3 | 1.5 |
| fig_1_4_sensor_mount_extension | 圖 1-4 | 1.5 |
| fig_1_5_multipath_concept | 圖 1-5 | 1.1 |

PNG 供預覽；PDF 供插入論文。

## 重跑
```bash
python3 thesis/figures/gen_ch01_figures.py
```
""",
        encoding="utf-8",
    )


def main() -> None:
    # clear old matplotlib versions
    for p in OUT.glob("fig_1_*"):
        p.unlink()
    fig_1_1()
    fig_1_2()
    fig_1_3()
    fig_1_4()
    fig_1_5()
    write_readme()
    print("done ->", OUT)


if __name__ == "__main__":
    main()
