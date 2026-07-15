#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""論文結果圖（S1/S2/D1.5/D3/D2）— 真實數據 + 非 Colab 預設風格 + Noto CJK。

字體：Noto Sans CJK（避免中文框框）。
樣式：白底、細軸、低彩、無 seaborn 預設彩虹。
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
OUT4 = Path(__file__).resolve().parent / "ch04"
OUT5 = Path(__file__).resolve().parent / "ch05"
OUT4.mkdir(parents=True, exist_ok=True)
OUT5.mkdir(parents=True, exist_ok=True)

FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# 論文線稿色票（低彩、印刷友善）
INK = "#1e1e1e"
MUTED = "#5a5a5a"
GRID = "#e6e6e6"
SPINE = "#4a4a4a"
C_CLOSED = "#2c5f7c"  # 聲學
C_BLIND = "#8b5a4a"  # 盲走
C_OPEN = "#5f7a5a"  # 開環
C_FIT = "#3d3d3d"
C_OK = "#2d6a4f"
C_BAD = "#a65d4a"
C_HEAT_LOW = "#f4f1ea"
C_HEAT_MID = "#7d9bb0"
C_HEAT_HI = "#1f3d52"


def _setup_fonts() -> fm.FontProperties:
    if not Path(FONT_REG).is_file():
        raise FileNotFoundError(f"Noto CJK not found: {FONT_REG}")
    fm.fontManager.addfont(FONT_REG)
    prop = fm.FontProperties(fname=FONT_REG)
    name = prop.get_name()
    plt.rcParams.update(
        {
            "font.family": name,
            "font.sans-serif": [name, "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": SPINE,
            "axes.labelcolor": INK,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "xtick.color": INK,
            "ytick.color": INK,
            "text.color": INK,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 1.0,
            "axes.grid": True,
            "axes.axisbelow": True,
            "legend.frameon": True,
            "legend.fancybox": False,
            "legend.edgecolor": "#cccccc",
            "legend.fontsize": 8.5,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.12,
            "pdf.fonttype": 42,  # editable text in PDF
            "ps.fonttype": 42,
        }
    )
    return prop


FP = _setup_fonts()
try:
    FP_BOLD = fm.FontProperties(fname=FONT_BOLD)
except Exception:
    FP_BOLD = FP


def _style_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SPINE)
    ax.spines["bottom"].set_color(SPINE)
    ax.tick_params(length=3.5, width=0.8)
    ax.grid(True, linestyle="-", linewidth=0.7, color=GRID)


def _save(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    for ext in ("png", "pdf"):
        path = out_dir / f"{stem}.{ext}"
        fig.savefig(path, facecolor="white", edgecolor="none")
        print("wrote", path)
    plt.close(fig)


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── S1 感測包絡 ──────────────────────────────────────────────
def fig_s1_envelope() -> None:
    cells = []
    base = ROOT / "runtime/outputs/v2_s1_envelope"
    for d in sorted(base.iterdir()):
        f = d / "cell_result.json"
        if not f.is_file():
            continue
        c = json.loads(f.read_text(encoding="utf-8"))
        snr = float(c.get("snr_peak") or 0.0)
        thr = 10.0
        cells.append(
            {
                "d": float(c["target_distance_m"]),
                "size": float(c["target_size_m"]),
                "pitch": float(c["sensor_pitch_deg"]),
                "snr": snr,
                "det": snr >= thr,
                "clutter": str(c.get("clutter") or "none"),
            }
        )

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.9), gridspec_kw={"width_ratios": [1.25, 1.0]})

    # Left: pitch=0 heatmap of mean log10(SNR+1) over sizes at each distance×size
    ax = axes[0]
    pitch0 = [c for c in cells if c["pitch"] == 0.0]
    dists = sorted({c["d"] for c in pitch0})
    sizes = sorted({c["size"] for c in pitch0})
    mat = np.full((len(sizes), len(dists)), np.nan)
    det_mat = np.zeros_like(mat)
    for c in pitch0:
        i = sizes.index(c["size"])
        j = dists.index(c["d"])
        # if multiple clutter, take max SNR (best case at that geom)
        val = math.log10(max(c["snr"], 1e-6) + 1.0)
        if np.isnan(mat[i, j]) or val > mat[i, j]:
            mat[i, j] = val
            det_mat[i, j] = 1.0 if c["det"] else 0.0

    cmap = LinearSegmentedColormap.from_list(
        "thesis_snr", [C_HEAT_LOW, C_HEAT_MID, C_HEAT_HI]
    )
    im = ax.imshow(
        mat,
        origin="lower",
        aspect="auto",
        cmap=cmap,
        extent=[
            min(dists) - 0.05,
            max(dists) + 0.05,
            min(sizes) - 0.02,
            max(sizes) + 0.02,
        ],
    )
    # mark non-detectable with ×
    for c in pitch0:
        if not c["det"]:
            ax.plot(c["d"], c["size"], "x", color=C_BAD, markersize=7, markeredgewidth=1.4)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("偵測訊噪比（對數刻度）", fontproperties=FP, fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    ax.set_xlabel("感測器到目標的距離（公尺）", fontproperties=FP)
    ax.set_ylabel("目標邊長（公尺）", fontproperties=FP)
    ax.set_title("感測器水平朝前：各格點的偵測訊噪比\n（紅色×＝未達可偵測門檻）", fontproperties=FP_BOLD, fontsize=10)
    _style_ax(ax)
    ax.grid(False)

    # Right: detect rate by pitch
    ax = axes[1]
    pitches = sorted({c["pitch"] for c in cells})
    rates = []
    ns = []
    for p in pitches:
        sub = [c for c in cells if c["pitch"] == p]
        n = len(sub)
        k = sum(1 for c in sub if c["det"])
        rates.append(100.0 * k / n if n else 0.0)
        ns.append(n)
    bars = ax.bar(
        [str(int(p)) for p in pitches],
        rates,
        color=[C_CLOSED if r >= 50 else C_BAD for r in rates],
        edgecolor=INK,
        linewidth=0.7,
        width=0.55,
    )
    for b, r, n in zip(bars, rates, ns):
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + 1.5,
            f"{r:.0f}%\n（{n} 格）",
            ha="center",
            va="bottom",
            fontsize=8,
            fontproperties=FP,
            color=MUTED,
        )
    ax.set_ylim(0, 115)
    ax.set_xlabel("感測器俯仰角（度，0＝水平朝前）", fontproperties=FP)
    ax.set_ylabel("可偵測的格點比例（%）", fontproperties=FP)
    n_det = sum(1 for c in cells if c["det"])
    ax.set_title(
        f"全部 52 個格點的可偵測比例\n（門檻：偵測訊噪比 ≥ 10；共 {n_det}/52 格可偵測）",
        fontproperties=FP_BOLD,
        fontsize=10,
    )
    _style_ax(ax)

    fig.suptitle(
        "圖 4.1  感測包絡量測：選定格點下「讀不讀得到目標」",
        fontproperties=FP_BOLD,
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()
    _save(fig, OUT4, "fig_4_1_s1_envelope")


# ── S2 距離校正 ──────────────────────────────────────────────
def fig_s2_distance() -> None:
    summary = json.loads((ROOT / "runtime/outputs/v2_s2_datasheet/datasheet_summary.json").read_text())
    comb = summary["distance"]["combined"]
    slope = float(comb["slope_sample_per_m"])
    intercept = float(comb["intercept_samples"])
    r = float(comb["pearson_r"])
    rmse = float(comb["distance_rmse_m"])

    xs, ys, kept_flags = [], [], []
    for pass_name in ("distance_p1", "distance_p2", "distance_p3"):
        p = ROOT / "runtime/outputs/v2_s2_datasheet" / pass_name / "points.csv"
        if not p.is_file():
            continue
        for row in _read_csv(p):
            d = float(row["true_distance_3d_m"])
            peak = float(row["peak_sample_idx"])
            ok = str(row.get("stationarity_ok", "True")).lower() == "true"
            xs.append(d)
            ys.append(peak)
            kept_flags.append(ok)

    xs = np.asarray(xs)
    ys = np.asarray(ys)
    kept = np.asarray(kept_flags)

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.7))

    ax = axes[0]
    ax.scatter(
        xs[kept],
        ys[kept],
        s=28,
        c=C_CLOSED,
        edgecolors="white",
        linewidths=0.5,
        zorder=3,
        label="用於擬合的量測點",
    )
    if np.any(~kept):
        ax.scatter(
            xs[~kept],
            ys[~kept],
            s=28,
            facecolors="none",
            edgecolors=C_BAD,
            linewidths=1.1,
            zorder=3,
            label="因量測不穩而排除",
        )
    xline = np.linspace(xs.min(), xs.max(), 100)
    yline = slope * xline + intercept
    ax.plot(xline, yline, color=C_FIT, linewidth=1.4, label="直線擬合（當輪自校）", zorder=2)
    ax.set_xlabel("真實距離（公尺，已知擺放位置）", fontproperties=FP)
    ax.set_ylabel("回波最強處的取樣點編號（無單位）", fontproperties=FP)
    ax.set_title(
        f"峰值位置隨距離上升（相關係數 r＝{r:.4f}）",
        fontproperties=FP_BOLD,
        fontsize=10,
    )
    ax.legend(prop=FP, loc="upper left", framealpha=0.95)
    _style_ax(ax)

    ax = axes[1]
    # residual in meters for kept: dist_hat = (peak - intercept)/slope
    d_hat = (ys[kept] - intercept) / slope
    resid_cm = (d_hat - xs[kept]) * 100.0
    ax.axhline(0, color=MUTED, linewidth=1.0, linestyle="--")
    ax.scatter(
        xs[kept],
        resid_cm,
        s=28,
        c=C_CLOSED,
        edgecolors="white",
        linewidths=0.5,
        zorder=3,
    )
    ax.set_xlabel("真實距離（公尺）", fontproperties=FP)
    ax.set_ylabel("估距減真值（公分）\n正＝估得比實際遠", fontproperties=FP)
    ax.set_title(
        f"擬合後的距離誤差（均方根誤差＝{rmse*100:.2f} 公分）",
        fontproperties=FP_BOLD,
        fontsize=10,
    )
    _style_ax(ax)

    fig.suptitle(
        "圖 4.2  距離校正：用已知距離把「峰值位置」換成公尺",
        fontproperties=FP_BOLD,
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()
    _save(fig, OUT4, "fig_4_2_s2_distance_cal")


# ── D1.5 三臂散點 ────────────────────────────────────────────
def fig_d15_scatter() -> None:
    base = ROOT / "runtime/outputs/v2_d15_arm_approach"
    arms = {
        "closed": ("聲學臂", C_CLOSED, "o"),
        "blind": ("盲走臂", C_BLIND, "s"),
        "open": ("開環臂", C_OPEN, "^"),
    }
    fig, ax = plt.subplots(figsize=(5.8, 4.6))
    series = {}
    for key, (label, color, marker) in arms.items():
        rows = _read_csv(base / key / "episodes.csv")
        tx = np.array([float(r["target_x"]) for r in rows])
        sx = np.array(
            [
                float(r.get("stop_sensor_x_actual") or r.get("stop_sensor_x") or 0)
                for r in rows
            ]
        )
        series[key] = (tx, sx, label, color, marker)
        ax.scatter(
            tx,
            sx,
            s=36,
            c=color,
            marker=marker,
            edgecolors="white",
            linewidths=0.5,
            alpha=0.92,
            label=label,
            zorder=3,
        )
    # 聲學臂：最小平方趨勢線（standoff 使停止點低於目標，非 y=x）
    tx, sx, _, _, _ = series["closed"]
    coef = np.polyfit(tx, sx, 1)
    xline = np.linspace(tx.min(), tx.max(), 50)
    ax.plot(
        xline,
        np.polyval(coef, xline),
        color=C_CLOSED,
        linewidth=1.5,
        linestyle="-",
        label="聲學趨勢",
        zorder=2,
    )
    # 盲走／開環：水平中位線（固定停點）
    for key in ("blind", "open"):
        _, sx, lab, col, _ = series[key]
        med = float(np.median(sx))
        ax.axhline(med, color=col, linewidth=1.0, linestyle="--", alpha=0.85, zorder=1)
    ax.set_xlabel("目標在前進方向上的位置（公尺）", fontproperties=FP)
    ax.set_ylabel("手臂／感測器實際停止的位置（公尺）", fontproperties=FP)
    ax.set_title(
        "主結果：三組對照臂各 30 回合\n（若能追目標，點會隨目標位置上下移動）",
        fontproperties=FP_BOLD,
        fontsize=10,
    )
    ax.legend(prop=FP, loc="best", framealpha=0.95, ncol=2)
    _style_ax(ax)
    fig.suptitle(
        "圖 5.1  閉環接近主結果：停止位置是否跟著目標走",
        fontproperties=FP_BOLD,
        fontsize=11,
        y=1.01,
    )
    fig.tight_layout()
    _save(fig, OUT5, "fig_5_1_d15_stop_vs_target")


# ── D3 對位 ─────────────────────────────────────────────────
def fig_d3_align() -> None:
    base = ROOT / "runtime/outputs/v2_d3_grasp_r3"
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.8))

    # left: closed grasp center vs target
    ax = axes[0]
    rows = _read_csv(base / "closed" / "episodes.csv")
    tx = np.array([float(r["target_x"]) for r in rows])
    gx = np.array([float(r["grasp_center_x_actual"]) for r in rows])
    aligned = np.array([str(r["aligned"]).lower() == "true" for r in rows])
    ax.scatter(
        tx[aligned],
        gx[aligned],
        s=36,
        c=C_OK,
        edgecolors="white",
        linewidths=0.5,
        label="對位成功（誤差 ≤ 2 公分）",
        zorder=3,
    )
    ax.scatter(
        tx[~aligned],
        gx[~aligned],
        s=36,
        c=C_BAD,
        edgecolors="white",
        linewidths=0.5,
        label="對位失敗",
        zorder=3,
    )
    lo = min(tx.min(), gx.min()) - 0.02
    hi = max(tx.max(), gx.max()) + 0.02
    ax.plot([lo, hi], [lo, hi], color="#888888", linestyle="--", linewidth=1.1, zorder=1, label="完全對齊線")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("目標在前進方向上的位置（公尺）", fontproperties=FP)
    ax.set_ylabel("夾爪中心實際到達的位置（公尺）", fontproperties=FP)
    ax.set_title(
        "聲學臂：夾爪是否對準目標\n（點越靠近虛線越準）",
        fontproperties=FP_BOLD,
        fontsize=10,
    )
    ax.legend(prop=FP, loc="upper left", framealpha=0.95)
    _style_ax(ax)

    # right: alignment rates
    ax = axes[1]
    labels = []
    rates = []
    colors = [C_CLOSED, C_BLIND, C_OPEN]
    names = [("closed", "聲學臂"), ("blind", "盲走臂"), ("open", "開環臂")]
    for key, lab in names:
        rows = _read_csv(base / key / "episodes.csv")
        n = len(rows)
        k = sum(1 for r in rows if str(r["aligned"]).lower() == "true")
        labels.append(lab)
        rates.append(100.0 * k / n if n else 0.0)
    bars = ax.bar(labels, rates, color=colors, edgecolor=INK, linewidth=0.7, width=0.55)
    for b, r in zip(bars, rates):
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + 1.2,
            f"{r:.0f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            fontproperties=FP,
            color=MUTED,
        )
    ax.set_ylim(0, 100)
    ax.set_ylabel("對位成功的回合比例（%）", fontproperties=FP)
    ax.set_title(
        "三組對照臂的對位成功率\n（成功定義：水平誤差 ≤ 2 公分）",
        fontproperties=FP_BOLD,
        fontsize=10,
    )
    _style_ax(ax)

    fig.suptitle(
        "圖 5.2  夾取對位結果（走廊遠端修正後的正式複驗）",
        fontproperties=FP_BOLD,
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()
    _save(fig, OUT5, "fig_5_2_d3_alignment_r3")


# ── D2 二維 ──────────────────────────────────────────────────
def fig_d2_2d() -> None:
    base = ROOT / "runtime/outputs/v2_d2v2_formal"
    rows = _read_csv(base / "closed" / "episodes.csv")
    tx = np.array([float(r["target_x"]) for r in rows])
    ty = np.array([float(r["target_y"]) for r in rows])
    xh = np.array([float(r["x_hat"]) for r in rows])
    yh = np.array([float(r["y_hat"]) for r in rows])

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.9))

    ax = axes[0]
    # true positions + estimates linked
    ax.scatter(
        tx,
        ty,
        s=40,
        c=C_CLOSED,
        marker="o",
        edgecolors="white",
        linewidths=0.5,
        label="目標真實位置",
        zorder=3,
    )
    ax.scatter(
        xh,
        yh,
        s=40,
        c="#c4a35a",
        marker="x",
        linewidths=1.3,
        label="多點測距估出的位置",
        zorder=4,
    )
    for i in range(len(tx)):
        ax.plot([tx[i], xh[i]], [ty[i], yh[i]], color="#bbbbbb", linewidth=0.7, zorder=1)
    ax.set_xlabel("前進方向位置（公尺）", fontproperties=FP)
    ax.set_ylabel("左右方向位置（公尺）\n正值＝一側，負值＝另一側", fontproperties=FP)
    ax.set_title(
        "聲學臂：估出的平面位置 vs 真實位置\n（灰線連接同一回合的真值與估計）",
        fontproperties=FP_BOLD,
        fontsize=10,
    )
    ax.legend(prop=FP, loc="best", framealpha=0.95)
    ax.set_aspect("equal", adjustable="datalim")
    _style_ax(ax)

    ax = axes[1]
    # stop 2d error by arm
    data = []
    labels = []
    colors = []
    for key, lab, col in (
        ("closed", "聲學臂", C_CLOSED),
        ("blind", "盲走臂", C_BLIND),
        ("open", "開環臂", C_OPEN),
    ):
        rs = _read_csv(base / key / "episodes.csv")
        err = np.array([float(r["stop_err_2d"]) for r in rs]) * 100.0  # cm
        data.append(err)
        labels.append(lab)
        colors.append(col)
    bp = ax.boxplot(
        data,
        tick_labels=labels,
        patch_artist=True,
        widths=0.5,
        medianprops=dict(color=INK, linewidth=1.3),
        whiskerprops=dict(color=MUTED),
        capprops=dict(color=MUTED),
        boxprops=dict(linewidth=0.9),
        flierprops=dict(marker="o", markersize=4, markerfacecolor=MUTED, markeredgecolor="none"),
    )
    for patch, col in zip(bp["boxes"], colors):
        patch.set_facecolor(col)
        patch.set_alpha(0.55)
        patch.set_edgecolor(INK)
    ax.set_ylabel("平面停止誤差（公分）\n愈小＝停得愈接近預定距離", fontproperties=FP)
    ax.set_title("三組對照臂的停止誤差分布", fontproperties=FP_BOLD, fontsize=10)
    _style_ax(ax)

    fig.suptitle(
        "圖 5.3  二維定位：左右方向能否估回來，以及停止好不好",
        fontproperties=FP_BOLD,
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()
    _save(fig, OUT5, "fig_5_3_d2_multilateration")


def main() -> None:
    # smoke: Chinese glyph
    fig, ax = plt.subplots(figsize=(2, 1))
    ax.text(0.5, 0.5, "測試中文", ha="center", va="center", fontproperties=FP)
    ax.axis("off")
    smoke = OUT4 / "_font_smoke.png"
    fig.savefig(smoke)
    plt.close(fig)
    print("font smoke", smoke)

    fig_s1_envelope()
    fig_s2_distance()
    fig_d15_scatter()
    fig_d3_align()
    fig_d2_2d()
    print("done")


if __name__ == "__main__":
    main()
