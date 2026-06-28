#!/usr/bin/env python3
"""Generate thesis figures 4.2 and 4.4 from canonical CSV data."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "figures"
COMPARISON_CSV = (
    ROOT
    / "runtime/outputs/phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1"
    / "fixed_tcp_rtx_pra_comparison.csv"
)
MATERIAL_CSV = (
    ROOT / "runtime/outputs/phase3_material_sensitivity_sgw/material_cross_condition_features.csv"
)


def fig_42_early_energy() -> Path:
    df = pd.read_csv(COMPARISON_CSV)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(
        df["target_distance_m"],
        df["primary_sgw_early_energy_mean"],
        "o-",
        color="#2E75B6",
        linewidth=2,
        markersize=8,
        label="RTX primary_sgw_early_energy",
    )
    ax.set_xlabel("Target distance (m)")
    ax.set_ylabel("Early energy (a.u.)")
    ax.set_title("RTX early energy vs distance (material B, n=5 repeats)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = OUT / "fig4_2_rtx_early_energy_vs_distance.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def fig_44_material() -> Path:
    df = pd.read_csv(MATERIAL_CSV)
    near = df[df["target_distance_m"] == 0.5]
    fig, ax = plt.subplots(figsize=(6, 4))
    colors = {"A": "#5B9BD5", "B": "#70AD47", "C": "#ED7D31"}
    bars = ax.bar(
        near["material_condition"],
        near["primary_sgw_early_energy_mean"],
        color=[colors[c] for c in near["material_condition"]],
        edgecolor="black",
        linewidth=0.8,
    )
    ax.set_xlabel("Material condition")
    ax.set_ylabel("Early energy @ 0.5 m (a.u.)")
    ax.set_title("Material sensitivity: early energy at 0.5 m")
    ax.grid(axis="y", alpha=0.3)
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 1, f"{h:.1f}", ha="center", va="bottom", fontsize=10)
    fig.tight_layout()
    path = OUT / "fig4_4_material_early_energy_0p5m.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p1 = fig_42_early_energy()
    p2 = fig_44_material()
    print(f"Wrote {p1}")
    print(f"Wrote {p2}")


if __name__ == "__main__":
    main()