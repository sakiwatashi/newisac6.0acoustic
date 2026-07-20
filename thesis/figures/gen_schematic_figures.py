#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""論文示意圖（非 Isaac Sim 畫面）：方法鏈、三臂、D3 序列、D4 雙軌與同場景串聯。

風格對齊 gen_ch01_figures.py：白底、細線、Noto CJK、低彩。
用法：
  python3 thesis/figures/gen_schematic_figures.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "schematic"
OUT.mkdir(parents=True, exist_ok=True)

FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

INK = (28, 28, 28)
MUTED = (95, 95, 95)
LINE = (55, 55, 55)
WHITE = (255, 255, 255)
FILL_A = (245, 247, 250)
FILL_B = (242, 248, 244)
FILL_C = (250, 246, 240)
FILL_D = (252, 244, 244)
FILL_E = (244, 246, 252)
ACCENT = (45, 85, 120)
OK = (40, 110, 70)
BAD = (140, 55, 55)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REG
    return ImageFont.truetype(path, size=size, index=0)


def text_size(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=f)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_center(draw, cx, cy, text, f, fill=INK):
    lines = text.split("\n")
    heights, widths = [], []
    for line in lines:
        w, h = text_size(draw, line, f)
        widths.append(w)
        heights.append(h)
    gap = 5
    total_h = sum(heights) + gap * (len(lines) - 1)
    y = cy - total_h / 2
    for line, w, h in zip(lines, widths, heights):
        draw.text((cx - w / 2, y), line, font=f, fill=fill)
        y += h + gap


def draw_text_left(draw, x, y, text, f, fill=INK):
    for i, line in enumerate(text.split("\n")):
        draw.text((x, y + i * (f.size + 6)), line, font=f, fill=fill)


def rounded_rect(draw, xy, radius=10, fill=FILL_A, outline=LINE, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def arrow_right(draw, x0, y, x1, color=LINE, w=2):
    draw.line([(x0, y), (x1 - 8, y)], fill=color, width=w)
    draw.polygon([(x1, y), (x1 - 11, y - 5), (x1 - 11, y + 5)], fill=color)


def arrow_down(draw, x, y0, y1, color=LINE, w=2):
    draw.line([(x, y0), (x, y1 - 8)], fill=color, width=w)
    draw.polygon([(x, y1), (x - 5, y1 - 11), (x + 5, y1 - 11)], fill=color)


def save(im: Image.Image, stem: str) -> Path:
    png = OUT / f"{stem}.png"
    im.save(png, "PNG", optimize=True)
    try:
        pdf = OUT / f"{stem}.pdf"
        im_rgb = im.convert("RGB")
        im_rgb.save(pdf, "PDF", resolution=150.0)
    except Exception:
        pass
    print(f"  wrote {png}")
    return png


# ── figures ──────────────────────────────────────────────────────────────────

def fig_pipeline_s1_to_d4():
    """實驗鏈：S1 → S2 → D1 → D1.5 → D3 → D4"""
    W, H = 1400, 420
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    title = font(28, True)
    body = font(18)
    small = font(15)
    draw_text_center(d, W / 2, 32, "圖：實驗鏈（感測包絡 → 閉環接近 → 夾取整合 → 策略串聯）", title)

    stages = [
        ("S1", "感測包絡", "配對移除\nSNR 地圖", FILL_A),
        ("S2", "距離編碼", "OLS 校正\nr≈0.999", FILL_A),
        ("D1", "未掛臂閉環", "隔離感測\n+控制", FILL_B),
        ("D1.5", "腕載三臂", "主結果\nRMSE 2.8 cm", FILL_B),
        ("D3", "端到端夾取", "對位正典 r3\n接觸觸發附著", FILL_C),
        ("D4", "雙軌＋串聯", "規則 SM / PPO\n同場景 n=90", FILL_E),
    ]
    n = len(stages)
    box_w, box_h = 170, 150
    gap = 28
    total = n * box_w + (n - 1) * gap
    x0 = (W - total) // 2
    y0 = 100
    for i, (code, name, note, fill) in enumerate(stages):
        x = x0 + i * (box_w + gap)
        rounded_rect(d, (x, y0, x + box_w, y0 + box_h), fill=fill)
        draw_text_center(d, x + box_w / 2, y0 + 28, code, font(22, True), ACCENT)
        draw_text_center(d, x + box_w / 2, y0 + 62, name, font(18, True))
        draw_text_center(d, x + box_w / 2, y0 + 108, note, small, MUTED)
        if i < n - 1:
            arrow_right(d, x + box_w + 2, y0 + box_h // 2, x + box_w + gap - 2, ACCENT, 3)
    draw_text_center(
        d, W / 2, H - 36,
        "對位主結果以 D3 r3 為準；D4 為執行器再驗證與同場景策略接口（升舉＝接觸觸發附著，非摩擦）",
        small, MUTED,
    )
    save(im, "fig_pipeline_s1_to_d4")


def fig_three_arm():
    """三臂對照：closed / blind / open"""
    W, H = 1200, 520
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 30, "圖：三臂資訊消融對照（closed / blind / open）", font(26, True))

    arms = [
        ("closed\n聲學臂", "量測管線完整\n估距進入控制\n聲學觸發停止／對位", FILL_B, OK),
        ("blind\n盲走臂", "量測管線相同\n估距改為 +∞\n停止條件永不成立", FILL_D, BAD),
        ("open\n開環臂", "完全不量測\n固定行程\nr 與目標無關", FILL_C, MUTED),
    ]
    box_w, box_h = 300, 220
    xs = [120, 450, 780]
    y0 = 90
    for (title, body, fill, edge), x in zip(arms, xs):
        rounded_rect(d, (x, y0, x + box_w, y0 + box_h), fill=fill, outline=edge, width=3)
        draw_text_center(d, x + box_w / 2, y0 + 48, title, font(22, True), edge)
        draw_text_center(d, x + box_w / 2, y0 + 140, body, font(17), INK)

    # shared bottom
    rounded_rect(d, (120, 360, 1080, 460), fill=FILL_A)
    draw_text_center(
        d, W / 2, 410,
        "共用：同一 seed、同一批目標位置、姿態／感測器位姿稽核\n"
        "主指標：停止／對位位置 vs 目標（r、RMSE、對位率）；不用「到達率」當唯一成功定義",
        font(16),
    )
    save(im, "fig_three_arm_ablation")


def fig_d3_grasp_sequence():
    """D3 夾取序列（不含 Isaac 畫面）"""
    W, H = 1400, 380
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 28, "圖：D3 端到端夾取序列（聲學停靠後一次推算 → 附著升舉）", font(24, True))

    steps = [
        ("1", "聲學接近", "走廊前進\nstandoff 0.35 m"),
        ("2", "一次推算", "停點 + 估距\n近距不再閉環"),
        ("3", "進場／下降", "安全高度移入\n降至夾取高度"),
        ("4", "合爪＋接觸", "物理接觸訊號\n非目標座標"),
        ("5", "附著升舉", "weld-on-stall\n升 0.10 m"),
        ("6", "評測", "對位 ±2 cm\n升舉 z≥0.05 m\n分層陳報"),
    ]
    box_w, box_h = 180, 160
    gap = 22
    total = len(steps) * box_w + (len(steps) - 1) * gap
    x0 = (W - total) // 2
    y0 = 90
    for i, (num, name, note) in enumerate(steps):
        x = x0 + i * (box_w + gap)
        fill = FILL_E if i < 2 else (FILL_C if i < 4 else FILL_B)
        rounded_rect(d, (x, y0, x + box_w, y0 + box_h), fill=fill)
        draw_text_center(d, x + box_w / 2, y0 + 28, num, font(20, True), ACCENT)
        draw_text_center(d, x + box_w / 2, y0 + 62, name, font(18, True))
        draw_text_center(d, x + box_w / 2, y0 + 115, note, font(14), MUTED)
        if i < len(steps) - 1:
            arrow_right(d, x + box_w + 2, y0 + box_h // 2, x + box_w + gap - 2, ACCENT, 3)
    draw_text_center(
        d, W / 2, H - 40,
        "宣稱：聲學對位 + 接觸觸發附著｜不宣稱：物理摩擦夾持｜對位率與升舉率不相乘",
        font(15), MUTED,
    )
    save(im, "fig_d3_grasp_sequence")


def fig_d4_dual_track():
    """D4 雙軌架構"""
    W, H = 1300, 620
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 30, "圖：D4 雙軌——規則狀態機（A）與策略接近／合爪（B）", font(24, True))

    # shared top
    rounded_rect(d, (350, 70, 950, 140), fill=FILL_A)
    draw_text_center(d, W / 2, 105, "共享：GMO／peak → 距離估測（OLS 校正）｜obs 禁目標 xyz", font(17, True))

    # Track A
    rounded_rect(d, (80, 180, 580, 480), fill=FILL_B, outline=OK, width=3)
    draw_text_center(d, 330, 210, "Track A｜規則狀態機", font(20, True), OK)
    a_items = [
        "ACOUSTIC_APPROACH / ALIGN",
        "DESCEND → CLOSE",
        "接觸 → weld-on-stall",
        "LIFT → HOLD",
        "三臂 n=30：對位 73% vs 盲 40%",
        "P(升舉|對位) ≈ 86%（weld）",
    ]
    y = 250
    for t in a_items:
        draw_text_left(d, 110, y, "•  " + t, font(16))
        y += 34

    # Track B
    rounded_rect(d, (720, 180, 1220, 480), fill=FILL_E, outline=ACCENT, width=3)
    draw_text_center(d, 970, 210, "Track B｜PPO 策略", font(20, True), ACCENT)
    b_items = [
        "obs：聲學 + 本體（8-D）",
        "act：Δ距離 + 合爪",
        "訓練可含距離 scaffold",
        "Lab 評測：近距+合爪",
        "消融：pure d̂ → 真實 0%",
        "BLIND+true → 亦可 100%（邊界）",
    ]
    y = 250
    for t in b_items:
        draw_text_left(d, 750, y, "•  " + t, font(16))
        y += 34

    # bottom merge
    rounded_rect(d, (200, 510, 1100, 580), fill=FILL_C)
    draw_text_center(
        d, W / 2, 545,
        "同場景串聯：B 策略驅動接近 → A 狀態機附著升舉（見下一圖）｜正典對位數字仍以 D3 r3 為準",
        font(16),
    )
    save(im, "fig_d4_dual_track")


def fig_same_scene_hookup():
    """同場景串聯 n=90"""
    W, H = 1300, 480
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 28, "圖：同場景串聯——策略接近 + 狀態機升舉（n=90）", font(24, True))

    boxes = [
        (80, 90, 380, 280, FILL_E, "策略（model_49）\n\na0 → 臂向前 Δx\na1 → 合爪意圖\nobs 無目標 xyz"),
        (480, 90, 820, 280, FILL_A, "停靠估測\n\nd3 經典 peak→d_horiz\nstandoff 觸發\n（非 gated 假近）"),
        (920, 90, 1220, 280, FILL_B, "狀態機末端\n\ndescend / close\nweld-on-stall\nlift + hold"),
    ]
    for x0, y0, x1, y1, fill, text in boxes:
        rounded_rect(d, (x0, y0, x1, y1), fill=fill)
        draw_text_center(d, (x0 + x1) / 2, (y0 + y1) / 2, text, font(17))
    arrow_right(d, 390, 185, 470, ACCENT, 3)
    arrow_right(d, 830, 185, 910, ACCENT, 3)

    # results bar
    rounded_rect(d, (120, 320, 1180, 430), fill=FILL_C)
    draw_text_center(
        d, W / 2, 375,
        "正式結果（closed，seed=20260718）\n"
        "對位 69/90 = 76.7%　　升舉 67/90 = 74.4%　　P(升舉|對位) = 76.8%　　mean |err| ≈ 1.5 cm\n"
        "停靠：90/90 standoff_est　　姿態／感測器違規：0　　≠ pure-reward 成功　　≠ 摩擦夾持",
        font(16),
    )
    save(im, "fig_same_scene_policy_n90")


def fig_claim_boundary():
    """可宣稱／不可宣稱"""
    W, H = 1200, 560
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 30, "圖：推論範圍（可支持／不支持）", font(26, True))

    rounded_rect(d, (60, 80, 570, 500), fill=FILL_B, outline=OK, width=3)
    draw_text_center(d, 315, 115, "可支持", font(22, True), OK)
    yes = [
        "純聲學閉環接近（D1.5）",
        "三臂消融：盲走失能",
        "夾取對位（D3 r3 正典）",
        "接觸觸發附著後升舉",
        "包絡／距離編碼方法鏈",
        "D4 規則臂方向一致",
        "同場景策略串聯可接升舉",
    ]
    y = 160
    for t in yes:
        draw_text_left(d, 90, y, "○  " + t, font(17))
        y += 42

    rounded_rect(d, (630, 80, 1140, 500), fill=FILL_D, outline=BAD, width=3)
    draw_text_center(d, 885, 115, "不支持／不宣稱", font(22, True), BAD)
    no = [
        "物理摩擦夾持部署級",
        "純 d̂ 獎勵端到端成功",
        "「必須聽音」全稱命題",
        "對位×升舉合成假 e2e",
        "0.32 m 內桌高閉環",
        "實機／跨 seed 穩健",
        "側向誤差下的 2D 再夾取",
    ]
    y = 160
    for t in no:
        draw_text_left(d, 660, y, "×  " + t, font(17))
        y += 42
    save(im, "fig_claim_boundary")


def fig_acoustic_range_pipeline():
    """聲學距離管線（概念，非截圖）"""
    W, H = 1280, 360
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 28, "圖：聲學距離估測管線（概念）", font(24, True))
    steps = [
        ("WPM / GMO", "回波波形\n多幀平均"),
        ("peak 索引", "sample index\n（非振幅）"),
        ("OLS 校正", "d = (idx−b)/a\nbar 校正檔"),
        ("d̂_horiz", "水平距\nstandoff 比較"),
        ("控制", "前進／停止\n或策略 a0,a1"),
    ]
    box_w, box_h = 190, 150
    gap = 30
    total = len(steps) * box_w + (len(steps) - 1) * gap
    x0 = (W - total) // 2
    y0 = 90
    for i, (name, note) in enumerate(steps):
        x = x0 + i * (box_w + gap)
        rounded_rect(d, (x, y0, x + box_w, y0 + box_h), fill=FILL_A if i < 3 else FILL_B)
        draw_text_center(d, x + box_w / 2, y0 + 40, name, font(18, True), ACCENT)
        draw_text_center(d, x + box_w / 2, y0 + 100, note, font(15), MUTED)
        if i < len(steps) - 1:
            arrow_right(d, x + box_w + 2, y0 + box_h // 2, x + box_w + gap - 2, ACCENT, 3)
    draw_text_center(
        d, W / 2, H - 40,
        "pure-reward 失敗常見於 d̂ 假近；同場景停靠用 d3 經典 peak 管線以降低近場誤觸發",
        font(15), MUTED,
    )
    save(im, "fig_acoustic_range_pipeline")


def fig_d4_ablation_table_visual():
    """Lab 消融視覺化（非 Isaac）"""
    W, H = 1100, 420
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 28, "圖：Lab 策略消融（真實近距+合爪，n=20）", font(24, True))

    # table header
    cols = [80, 320, 560, 800, 1020]
    headers = ["配方", "觀測", "訓練獎勵", "真實成功"]
    y = 80
    for i, h in enumerate(headers):
        draw_text_left(d, cols[i], y, h, font(17, True), ACCENT)
    d.line([(70, 115), (1030, 115)], fill=LINE, width=2)

    rows = [
        ("聲學 close_ft（正典）", "8-D 聲學", "距離 scaffold", "100%", OK),
        ("BLIND + scaffold", "聲學通道=0", "距離 scaffold", "100%", MUTED),
        ("pure acoustic", "8-D 聲學", "僅 d̂", "0%", BAD),
        ("pure BLIND", "聲學通道=0", "僅 d̂", "0%", BAD),
    ]
    y = 140
    for name, obs, rew, rate, color in rows:
        draw_text_left(d, cols[0], y, name, font(16))
        draw_text_left(d, cols[1], y, obs, font(16), MUTED)
        draw_text_left(d, cols[2], y, rew, font(16), MUTED)
        draw_text_left(d, cols[3], y, rate, font(18, True), color)
        y += 48
    d.line([(70, y - 10), (1030, y - 10)], fill=(200, 200, 200), width=1)
    draw_text_center(
        d, W / 2, H - 50,
        "解讀：1-DOF + 特權距離獎勵時開環可過；純估距獎勵會假近合爪。\n"
        "故 Lab 100% 不作「必須聽音」或「pure 聲學 end-to-end」主宣稱。",
        font(15), MUTED,
    )
    save(im, "fig_lab_ablation_summary")




def fig_gmo_structure():
    """GMO field semantics and signal-way layout."""
    W, H = 1280, 620
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 28, "GMO（Generic Model Output）在超音波下的語意", font(24, True))

    rows = [
        ("x[i]", "LiDAR：空間 X", "Acoustic：TX 掛載 ID"),
        ("y[i]", "LiDAR：空間 Y", "Acoustic：RX 掛載 ID"),
        ("z[i]", "LiDAR：空間 Z", "Acoustic：通道 ID（非時間）"),
        ("scalar[i]", "強度等", "振幅樣本"),
        ("timeOffsetNs", "到達時間", "Isaac Sim 6.0 恆 0，不可用"),
        ("numSamplesPerSgw", "—", "每條 signal way 樣本數"),
    ]
    rounded_rect(d, (50, 55, 620, 430), fill=FILL_A)
    draw_text_center(d, 335, 80, "欄位對照（勿當空間座標）", font(18, True), ACCENT)
    y = 110
    for a, b, c in rows:
        draw_text_left(d, 70, y, a, font(16, True), ACCENT)
        draw_text_left(d, 220, y, b, font(14), MUTED)
        draw_text_left(d, 220, y + 22, c, font(15), INK)
        y += 50

    rounded_rect(d, (660, 55, 1230, 430), fill=FILL_E)
    draw_text_center(d, 945, 80, "Buffer 排列（signal way）", font(18, True), ACCENT)
    bx, by, bw, bh = 700, 130, 480, 70
    for i, lab in enumerate(["way 0：樣本 0 … N-1", "way 1：樣本 0 … N-1", "way 2 …"]):
        y0 = by + i * (bh + 18)
        fill = FILL_B if i == 0 else FILL_A
        rounded_rect(d, (bx, y0, bx + bw, y0 + bh), fill=fill)
        extra = "  N=numSamplesPerSgw" if i == 0 else ""
        draw_text_center(d, bx + bw / 2, y0 + bh / 2, lab + extra, font(16))
    draw_text_center(
        d, 945, 390,
        "正確：amps=scalar[0:N]；peak=argmax(|amps|)\n錯誤：把 z（channel）當時間索引",
        font(15), MUTED,
    )

    rounded_rect(d, (50, 460, 1230, 580), fill=FILL_C)
    draw_text_center(
        d, W / 2, 520,
        "距離：當輪 OLS  peak ≈ a·d+b  →  d̂=(peak−b)/a\n"
        "不用固定 T；timeOffsetNs 不可用｜NVIDIA GMO 文件；ToF 譜系 Zhmud 等",
        font(16),
    )
    save(im, "fig_gmo_structure")


def fig_four_pillars():
    """Four methodology pillars."""
    W, H = 1300, 480
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 28, "實驗方法學四支柱（效度框架）", font(24, True))
    pillars = [
        ("一、包絡優先", "先畫聽得到的幾何\n再放任務\n配對移除 + SNR", "Valin / Liu 等"),
        ("二、三臂消融", "聲學 / 盲走 / 開環\n同 seed 同目標\n盲走＝資訊作廢", "Meyes 等"),
        ("三、預註冊", "判準先鎖死\n失敗不放寬門檻\n主指標 r / RMSE", "Nosek 等"),
        ("四、量測稽核", "平穩 / 姿態 / 位姿\n不合格剔除\n不插補", "效度工程"),
    ]
    box_w, box_h = 280, 280
    gap = 30
    total = 4 * box_w + 3 * gap
    x0 = (W - total) // 2
    y0 = 90
    fills = [FILL_A, FILL_B, FILL_C, FILL_E]
    for i, ((t, body, lit), fill) in enumerate(zip(pillars, fills)):
        x = x0 + i * (box_w + gap)
        rounded_rect(d, (x, y0, x + box_w, y0 + box_h), fill=fill)
        draw_text_center(d, x + box_w / 2, y0 + 40, t, font(18, True), ACCENT)
        draw_text_center(d, x + box_w / 2, y0 + 140, body, font(16))
        draw_text_center(d, x + box_w / 2, y0 + 240, lit, font(14), MUTED)
    draw_text_center(
        d, W / 2, H - 40,
        "分項方法族有文獻；RTX Acoustic + UR10e 組合落地為本研究貢獻",
        font(15), MUTED,
    )
    save(im, "fig_four_pillars")


def fig_multilateration():
    """D2 multilateration schematic."""
    W, H = 1100, 520
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 28, "二維多點定位示意（運動合成基線）", font(24, True))

    tx, ty = 780, 220
    d.ellipse((tx - 14, ty - 14, tx + 14, ty + 14), fill=BAD, outline=LINE)
    draw_text_left(d, tx + 20, ty - 10, "目標 (x,y)", font(16, True))

    ys = [160, 220, 280, 340, 400]
    for i, y in enumerate(ys):
        x = 200
        d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=ACCENT, outline=LINE)
        draw_text_left(d, 60, y - 10, f"視點 {i+1}", font(14), MUTED)
        d.line([(x, y), (tx, ty)], fill=(180, 180, 180), width=1)
    draw_text_center(
        d, 280, 460,
        "五視點各得 d̂_i\n最小平方圓交會 → (x̂,ŷ)\n再沿方位接近",
        font(16),
    )
    rounded_rect(d, (520, 120, 1040, 400), fill=FILL_A)
    draw_text_left(
        d, 560, 160,
        "為何需要？\n"
        "單次 GMO 輸出無可靠左右\n"
        "（第四章四重證偽）\n\n"
        "文獻譜系：\n"
        "• Kapoor 等：多點／信標定位\n"
        "• Hayes 等：合成孔徑／移動基線\n\n"
        "本文：離散五點 + Gauss–Newton\n"
        "側向 RMSE≈3.3 cm → 未宣稱再夾取",
        font(16),
    )
    save(im, "fig_multilateration")


def fig_paired_removal():
    """Paired removal three conditions."""
    W, H = 1200, 360
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    draw_text_center(d, W / 2, 28, "配對移除量測（有目標／雜訊參考／無目標）", font(24, True))
    steps = [
        ("1 有目標", "同姿態\n量波形 W有", FILL_B),
        ("2 雜訊參考", "同場景再量\nW雜（底噪）", FILL_A),
        ("3 無目標", "移除目標\n量 W無", FILL_C),
        ("SNR", "max|W有−W無|\n÷ max|W有−W雜|", FILL_E),
    ]
    box_w, box_h = 220, 160
    gap = 40
    total = 4 * box_w + 3 * gap
    x0 = (W - total) // 2
    y0 = 100
    for i, (name, note, fill) in enumerate(steps):
        x = x0 + i * (box_w + gap)
        rounded_rect(d, (x, y0, x + box_w, y0 + box_h), fill=fill)
        draw_text_center(d, x + box_w / 2, y0 + 40, name, font(18, True), ACCENT)
        draw_text_center(d, x + box_w / 2, y0 + 105, note, font(15), MUTED)
        if i < 3:
            arrow_right(d, x + box_w + 2, y0 + box_h // 2, x + box_w + gap - 2, ACCENT, 3)
    draw_text_center(
        d, W / 2, H - 40,
        "動機：分離目標回波與背景多路徑（Valin；Tsuchiya；Liu）｜SNR>10 可偵測",
        font(15), MUTED,
    )
    save(im, "fig_paired_removal")



def main():
    print(f"Output → {OUT}")
    fig_pipeline_s1_to_d4()
    fig_three_arm()
    fig_d3_grasp_sequence()
    fig_d4_dual_track()
    fig_same_scene_hookup()
    fig_claim_boundary()
    fig_acoustic_range_pipeline()
    fig_d4_ablation_table_visual()
    fig_gmo_structure()
    fig_four_pillars()
    fig_multilateration()
    fig_paired_removal()
    print("DONE")
    for p in sorted(OUT.glob("*.png")):
        print(p.name, p.stat().st_size)


if __name__ == "__main__":
    main()
