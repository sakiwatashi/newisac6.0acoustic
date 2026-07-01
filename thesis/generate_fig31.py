#!/usr/bin/env python3
"""Generate Figure 3.1 research architecture diagram (Phase A→B→C + Physical AI)."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent / "figures" / "fig3_1_research_architecture.png"


def box(ax, xy, w, h, text, fc, ec="#333333"):
    patch = FancyBboxPatch(
        xy, w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2, edgecolor=ec, facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", fontsize=8.5, wrap=True)


def arrow(ax, p1, p2, style="-|>", color="#444444", ls="-"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, color=color, lw=1.3, linestyle=ls, mutation_scale=12))


def main() -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    # Phase A — feature pipeline (top)
    ax.text(5.0, 5.7, "Phase A  Feature audit (Ch.4)", ha="center", fontsize=9, fontweight="bold", color="#2F5496")
    box(ax, (0.3, 4.5), 1.4, 0.85, "Geometry\nPassport", "#D5E8F0")
    box(ax, (1.9, 4.5), 1.4, 0.85, "Material\nPassport", "#D5E8F0")
    box(ax, (3.5, 4.5), 1.5, 0.85, "RTX GMO\nCapture", "#BDD7EE")
    box(ax, (5.2, 4.5), 1.6, 0.85, "Feature Factory\n(early energy)", "#BDD7EE")
    box(ax, (7.0, 4.5), 2.2, 0.85, "30/30 repeatability\n+ distance trend", "#FFF2CC")
    for x in [(1.7, 4.9), (3.3, 4.9), (5.0, 4.9), (6.8, 4.9)]:
        arrow(ax, x, (x[0] + 0.25, x[1]))

    # Phase B/C — closed loop (middle)
    ax.text(5.0, 3.85, "Phase B/C  Closed-loop approach + Physical AI (Ch.5)", ha="center", fontsize=9, fontweight="bold", color="#C55A11")
    box(ax, (0.3, 2.5), 1.6, 0.9, "Grasp Passport\n+ UR10e/Robotiq", "#E2EFDA")
    box(ax, (2.1, 2.5), 1.8, 0.9, "Ultrasonic\nClosed-loop Ctrl", "#C6E0B4")
    box(ax, (4.1, 2.5), 1.5, 0.9, "Supervisor v1\n(safety envelope)", "#C6E0B4")
    box(ax, (5.8, 2.5), 1.6, 0.9, "Randomized\ntrials (v9)", "#FFE699")
    box(ax, (7.6, 2.5), 2.0, 0.9, "Physical AI\nablation / audit", "#FFE699")
    arrow(ax, (1.9, 2.95), (2.1, 2.95))
    arrow(ax, (3.9, 2.95), (4.1, 2.95))
    arrow(ax, (5.6, 2.95), (5.8, 2.95))
    arrow(ax, (7.4, 2.95), (7.6, 2.95))
    arrow(ax, (6.8, 4.5), (3.0, 3.4), ls="--")

    # Tier B grasp evaluation (bottom)
    ax.text(5.0, 1.85, "Phase C  Tier-B contact evaluation (limitation)", ha="center", fontsize=9, fontweight="bold", color="#7F7F7F")
    box(ax, (2.5, 0.6), 2.2, 0.9, "Contact-only\n(--skip-lift)", "#F2F2F2")
    box(ax, (5.0, 0.6), 2.4, 0.9, "Stage metrics\napproach / near / final", "#F2F2F2")
    arrow(ax, (4.7, 2.5), (3.6, 1.5), ls="--")
    arrow(ax, (6.2, 2.5), (6.2, 1.5), ls="--")

    ax.text(
        5.0, 0.15,
        "Figure 3.1  Research architecture (solid = core pipeline; dashed = downstream evaluation)",
        ha="center", fontsize=10, fontweight="bold",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()