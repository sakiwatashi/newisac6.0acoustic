#!/usr/bin/env python3
"""Generate Figure 3.1 research architecture diagram."""

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
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", fontsize=9, wrap=True)


def arrow(ax, p1, p2, style="-|>", color="#444444", ls="-"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, color=color, lw=1.3, linestyle=ls, mutation_scale=12))


def main() -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.5)
    ax.axis("off")

    # Main Sim pipeline (solid)
    box(ax, (0.4, 3.6), 1.5, 0.9, "Geometry\nPassport", "#D5E8F0")
    box(ax, (2.2, 3.6), 1.5, 0.9, "Material\nPassport", "#D5E8F0")
    box(ax, (4.0, 3.6), 1.6, 0.9, "RTX GMO\nCapture", "#BDD7EE")
    box(ax, (6.0, 3.6), 1.6, 0.9, "Feature Factory\n(early energy)", "#BDD7EE")
    box(ax, (8.0, 3.6), 1.5, 0.9, "PRA Trend\nReference", "#E2EFDA")

    for x in [(1.9, 3.75), (3.7, 3.75), (5.6, 3.75), (7.6, 3.75)]:
        arrow(ax, x, (x[0] + 0.35, x[1]))

    box(ax, (3.2, 2.0), 3.6, 1.0, "Ch.4 Sim Evaluation\n30/30 · distance trend · material", "#FFF2CC")
    arrow(ax, (6.8, 3.6), (5.0, 3.05))
    arrow(ax, (5.0, 3.05), (5.0, 3.0))

    # Lab extension (dashed)
    box(ax, (0.8, 0.5), 2.0, 0.9, "Isaac Lab\nDynamic Env", "#FCE4D6")
    box(ax, (3.2, 0.5), 2.0, 0.9, "Sim→Lab SL\n(r≈0.47)", "#FCE4D6")
    box(ax, (5.6, 0.5), 2.2, 0.9, "In-sim RL\n(loop viability)", "#FCE4D6")
    box(ax, (8.2, 0.5), 1.4, 0.9, "Ch.5\nExtension", "#F8CBAD")

    arrow(ax, (6.8, 3.6), (1.8, 1.4), ls="--")
    arrow(ax, (1.8, 0.5), (3.2, 0.95))
    arrow(ax, (5.2, 0.95), (5.6, 0.95))
    arrow(ax, (7.8, 0.95), (8.2, 0.95), ls="--")

    ax.text(5.0, 5.2, "Figure 3.1  Research architecture (solid = Ch.3–4 core; dashed = Ch.5 extension)",
            ha="center", fontsize=11, fontweight="bold")
    ax.text(0.5, 1.8, "Same Passport +\nFactory reuse", fontsize=8, color="#666666")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()