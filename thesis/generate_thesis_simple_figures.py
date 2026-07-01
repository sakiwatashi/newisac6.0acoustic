#!/usr/bin/env python3
"""Generate simple Chinese-labeled thesis figures for advisor-facing draft."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "figures"
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def fig_timeline() -> Path:
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 3)
    ax.axis("off")
    steps = [
        ("① 環境建置", "UR10 資產\n感測器掛載"),
        ("② 資料穩定", "固定手臂\n30 次擷取"),
        ("③ 感測回授", "UR10e 接近\n與對照組"),
        ("④ 問題修正", "接觸級評估\n隨機化目標"),
        ("⑤ 主結果", "84% vs 29%\n狀態判斷"),
    ]
    xs = [0.3 + i * 1.75 for i in range(5)]
    for x, (title, body) in zip(xs, steps):
        box = FancyBboxPatch(
            (x, 0.8), 1.55, 1.5,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.2, edgecolor="#333", facecolor="#E8F1FA",
        )
        ax.add_patch(box)
        ax.text(x + 0.78, 1.95, title, ha="center", va="center", fontsize=10, fontweight="bold")
        ax.text(x + 0.78, 1.25, body, ha="center", va="center", fontsize=8.5)
    for x in xs[:-1]:
        ax.add_patch(FancyArrowPatch((x + 1.55, 1.55), (x + 1.75, 1.55), arrowstyle="-|>", mutation_scale=12, lw=1.2))
    ax.text(4.5, 0.25, "圖1  本研究歷程與系統演進（2026 年 3–7 月）", ha="center", fontsize=11, fontweight="bold")
    path = OUT / "fig1_research_timeline.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_scene_schematic() -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.2, 0.2), 6.6, 3.6, fill=False, lw=1.5, ec="#666"))
    ax.text(3.5, 3.55, "六面牆室內場景（Isaac Sim）", ha="center", fontsize=11, fontweight="bold")
    ax.add_patch(plt.Rectangle((0.5, 0.5), 1.0, 1.2, color="#BDD7EE"))
    ax.text(1.0, 1.1, "UR10e\n底座", ha="center", va="center", fontsize=9)
    ax.plot([1.0, 2.3, 3.2], [1.1, 1.8, 1.5], "o-", color="#2E75B6", lw=3, ms=8)
    ax.text(3.35, 1.55, "腕部\n超音波感測", fontsize=8, bbox=dict(boxstyle="round", fc="#FFF2CC"))
    ax.add_patch(plt.Rectangle((2.0, 0.5), 3.5, 0.35, color="#D9D9D9"))
    ax.text(3.75, 0.67, "工作台面", ha="center", va="center", fontsize=9)
    ax.add_patch(plt.Rectangle((4.8, 0.85), 0.8, 0.15, color="#C0C0C0"))
    ax.text(5.2, 0.92, "目標工件", ha="center", va="center", fontsize=8)
    ax.annotate("", xy=(4.0, 1.5), xytext=(5.0, 0.95), arrowprops=dict(arrowstyle="<->", color="#C55A11"))
    ax.text(4.5, 1.35, "接近方向", ha="center", fontsize=8, color="#C55A11")
    ax.text(3.5, 0.08, "圖2  模擬場景示意（手臂、超音波感測與目標工件）", ha="center", fontsize=11, fontweight="bold")
    path = OUT / "fig2_scene_schematic.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_approach_bar() -> Path:
    labels = ["進入 0.45 m 內", "進入 0.35 m 內", "最終成功"]
    feedback = [84.0, 84.0, 20.0]
    control = [29.2, 4.2, 20.8]
    x = range(len(labels))
    w = 0.35
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar([i - w / 2 for i in x], feedback, width=w, label="感測回授組", color="#2E75B6")
    ax.bar([i + w / 2 for i in x], control, width=w, label="未使用回授組", color="#A6A6A6")
    ax.set_ylabel("成功率 (%)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 100)
    ax.legend()
    ax.set_title("感測回授與對照組之階段成功率比較")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = OUT / "fig5_approach_success_bar.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_state_f1_bar() -> Path:
    labels = ["合併特徵", "僅感測特徵", "僅姿態特徵"]
    f1 = [0.684, 0.598, 0.533]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, f1, color=["#2E75B6", "#5B9BD5", "#A6A6A6"])
    ax.set_ylabel("F1 分數")
    ax.set_ylim(0, 1.0)
    ax.set_title("停止前進區域判斷：不同特徵組合之比較")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = OUT / "fig6_state_f1_bar.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (fig_timeline, fig_scene_schematic, fig_approach_bar, fig_state_f1_bar):
        p = fn()
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()