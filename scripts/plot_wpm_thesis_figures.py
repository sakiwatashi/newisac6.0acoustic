"""Generate WPM thesis figures from experiment CSV files.

Produces publication-quality plots saved to runtime/figures/:
  Fig 1: oracle vs inferred scatter (arm-free, multiple geometries)
  Fig 2: Pearson r bar chart (arm-free vs arm-fixed, all conditions)
  Fig 3: distance error vs oracle distance (bias + scatter)
  Fig 4: cube size detection summary (r by cube size, linear zone)

Usage:
    python3 scripts/plot_wpm_thesis_figures.py
"""
from __future__ import annotations

import csv
import math
import pathlib

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = pathlib.Path("/home/lab109/song/isaacsim6.0")
OUT_DIR = ROOT / "runtime" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BG_DIR   = ROOT / "runtime/outputs/armfree_background_sweep"
WIN_DIR  = ROOT / "runtime/outputs/armfree_windowed_peak_sweep"
FREQ_DIR = ROOT / "runtime/outputs/armfree_freq_sweep"

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return list(csv.DictReader(path.open()))

def pearson_r(xs, ys):
    paired = [(x, y) for x, y in zip(xs, ys)
              if not (math.isnan(x) or math.isnan(y))]
    n = len(paired)
    if n < 2:
        return float("nan")
    xs2, ys2 = zip(*paired)
    mx, my = sum(xs2) / n, sum(ys2) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs2, ys2))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs2) *
                    sum((y - my) ** 2 for y in ys2))
    return num / den if den > 0 else float("nan")

def rmse_bias(rows):
    valid = [(float(r["oracle_distance_m"]), float(r["inferred_dist_m"]))
             for r in rows
             if not math.isnan(float(r.get("inferred_dist_m", "nan")))]
    if not valid:
        return float("nan"), float("nan")
    errs = [i - o for o, i in valid]
    rmse = math.sqrt(sum(e ** 2 for e in errs) / len(errs))
    bias = sum(errs) / len(errs)
    return rmse, bias

def linfit(xs, ys):
    """Return (slope, intercept) of OLS fit."""
    paired = [(x, y) for x, y in zip(xs, ys)
              if not (math.isnan(x) or math.isnan(y))]
    if len(paired) < 2:
        return float("nan"), float("nan")
    xs2, ys2 = zip(*paired)
    n = len(xs2)
    mx, my = sum(xs2) / n, sum(ys2) / n
    slope = sum((x - mx) * (y - my) for x, y in zip(xs2, ys2)) / \
            sum((x - mx) ** 2 for x in xs2)
    return slope, my - slope * mx

# ── Data catalogue ────────────────────────────────────────────────────────────
ARM_FREE_DIR   = ROOT / "runtime/outputs/armfree_geometry_sweep"
ARMFIX_DIR     = ROOT / "runtime/outputs/armfixed_proximity_sweep"
SIZE_DIR       = ROOT / "runtime/outputs/armfree_cube_size_sweep"
FARFIELD_DIR   = ROOT / "runtime/outputs/armfree_farfield_sweep"
BASELINE_DIR   = ROOT / "runtime/outputs/armfree_test_v1"

# (label, csv_path, color, marker)
GEOM_DATASETS = [
    ("Cube 0.10m",           ARM_FREE_DIR / "cube_0.10m"             / "armfree_proximity_sweep.csv",  "#1f77b4", "s"),
    ("Sphere r=0.05m",       ARM_FREE_DIR / "sphere_r0.05m"          / "armfree_proximity_sweep.csv",  "#ff7f0e", "o"),
    ("Sphere r=0.10m",       ARM_FREE_DIR / "sphere_r0.10m"          / "armfree_proximity_sweep.csv",  "#2ca02c", "^"),
    ("Cylinder r=0.05m h=0.20m", ARM_FREE_DIR / "cylinder_r0.05m_h0.20m" / "armfree_proximity_sweep.csv", "#d62728", "D"),
    ("Cylinder r=0.05m h=0.30m", ARM_FREE_DIR / "cylinder_r0.05m_h0.30m" / "armfree_proximity_sweep.csv", "#9467bd", "v"),
]

# ── Style ─────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "legend.fontsize": 9.5,
    "figure.dpi": 150,
    "lines.linewidth": 1.5,
    "axes.grid": True,
    "grid.alpha": 0.35,
})

NEAR_FIELD_LIMIT = 0.45   # WPM closeRange anomaly below this


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 1  Oracle vs Inferred distance — arm-free, multiple geometries
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7, 6))

ideal_x = np.linspace(0.15, 1.55, 100)
ax.plot(ideal_x, ideal_x, "k--", lw=1.2, alpha=0.5, label="Perfect (oracle = inferred)")
ax.axvspan(0.0, NEAR_FIELD_LIMIT, alpha=0.07, color="red")
ax.text(0.23, 1.42, "Near-field\nzone", fontsize=8.5, color="red", alpha=0.7, ha="center")

for label, csv_path, color, marker in GEOM_DATASETS:
    rows = load_csv(csv_path)
    if not rows:
        print(f"  [SKIP] {label}: no CSV")
        continue
    ox = [float(r["oracle_distance_m"]) for r in rows]
    iy = [float(r["inferred_dist_m"])   for r in rows
          if not math.isnan(float(r.get("inferred_dist_m", "nan")))]
    # only valid inferred
    ox_v = [float(r["oracle_distance_m"]) for r in rows
            if not math.isnan(float(r.get("inferred_dist_m", "nan")))]
    r_val = pearson_r(ox, [float(r.get("inferred_dist_m", "nan")) for r in rows])
    rmse, bias = rmse_bias(rows)
    ax.scatter(ox_v, iy, color=color, marker=marker, s=40, alpha=0.85,
               label=f"{label}  r={r_val:+.4f}")
    # fit line for valid data
    slope, intercept = linfit(ox_v, iy)
    if not math.isnan(slope):
        xr = np.array([min(ox_v), max(ox_v)])
        ax.plot(xr, slope * xr + intercept, color=color, lw=1.0, alpha=0.5)

ax.set_xlabel("Oracle distance (m)")
ax.set_ylabel("WPM inferred distance (m)")
ax.set_title("Fig 1  Arm-Free: Oracle vs WPM Inferred Distance\n(multiple target geometries, 0.20–1.50 m)")
ax.legend(loc="upper left", framealpha=0.9)
ax.set_xlim(0.10, 1.60)
ax.set_ylim(0.10, 1.60)
ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.1))
ax.yaxis.set_minor_locator(ticker.MultipleLocator(0.1))

fig.tight_layout()
p = OUT_DIR / "fig1_oracle_vs_inferred_armfree.png"
fig.savefig(p, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {p}")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 2  Pearson r comparison bar chart
# ═══════════════════════════════════════════════════════════════════════════════
BAR_DATA = [
    # (group_label, csv_path, condition_label, color)
    # arm-free
    ("Cube\n0.05m",       SIZE_DIR / "cube_0.05m" / "armfree_proximity_sweep.csv",             "arm-free",  "#1f77b4"),
    ("Cube\n0.10m",       ARM_FREE_DIR / "cube_0.10m" / "armfree_proximity_sweep.csv",          "arm-free",  "#1f77b4"),
    ("Cube\n0.20m",       SIZE_DIR / "cube_0.20m" / "armfree_proximity_sweep.csv",              "arm-free",  "#1f77b4"),
    ("Sphere\nr=0.05m",   ARM_FREE_DIR / "sphere_r0.05m" / "armfree_proximity_sweep.csv",       "arm-free",  "#ff7f0e"),
    ("Sphere\nr=0.10m",   ARM_FREE_DIR / "sphere_r0.10m" / "armfree_proximity_sweep.csv",       "arm-free",  "#ff7f0e"),
    ("Cylinder\nr=0.05m", ARM_FREE_DIR / "cylinder_r0.05m_h0.20m" / "armfree_proximity_sweep.csv", "arm-free", "#2ca02c"),
    # arm-fixed (hatched)
    ("Sphere\nr=0.05m\n(arm home)",   ARMFIX_DIR / "home_sphere_r0.05m"   / "armfixed_proximity_sweep.csv", "arm-fixed", "#ff7f0e"),
    ("Sphere\nr=0.10m\n(arm home)",   ARMFIX_DIR / "home_sphere_r0.10m"   / "armfixed_proximity_sweep.csv", "arm-fixed", "#ff7f0e"),
    ("Sphere r=0.05m\n(arm fwd)",     ARMFIX_DIR / "reach_forward_sphere_r0.05m" / "armfixed_proximity_sweep.csv", "arm-fixed", "#ff7f0e"),
]

fig, ax = plt.subplots(figsize=(11, 5))
xs, ys, colors, hatches, xlabels = [], [], [], [], []

for i, (glabel, csv_path, cond, color) in enumerate(BAR_DATA):
    rows = load_csv(csv_path)
    if not rows:
        continue
    dists = [float(r["oracle_distance_m"]) for r in rows]
    peaks = [float(r.get("peak_sample_idx", "nan")) for r in rows]
    r_val = abs(pearson_r(dists, peaks))
    xs.append(i)
    ys.append(r_val)
    colors.append(color)
    hatches.append("///" if cond == "arm-fixed" else "")
    xlabels.append((glabel, cond))

bars = ax.bar(range(len(xs)), ys, color=colors, alpha=0.85,
              edgecolor="black", linewidth=0.7)
for bar, hatch in zip(bars, hatches):
    bar.set_hatch(hatch)

# Annotate each bar
for i, (bar, r_val) in enumerate(zip(bars, ys)):
    ax.text(bar.get_x() + bar.get_width() / 2, r_val + 0.002,
            f"{r_val:.4f}", ha="center", va="bottom", fontsize=7.5)

ax.axhline(0.90, color="green", ls="--", lw=1.2, alpha=0.7, label="r = 0.90 threshold")
ax.axhline(0.60, color="orange", ls="--", lw=1.2, alpha=0.7, label="r = 0.60 threshold")

ax.set_xticks(range(len(xlabels)))
ax.set_xticklabels([f"{lb}\n({cond})" for lb, cond in xlabels], fontsize=7.5)
ax.set_ylabel("|Pearson r|  (peak_sample_idx vs oracle_distance)")
ax.set_ylim(0, 1.08)
ax.set_title("Fig 2  |Pearson r| Comparison: Arm-Free vs Arm-Fixed, Multiple Geometries")
ax.legend(loc="lower right", framealpha=0.9)

# Add condition legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor="gray", alpha=0.7, label="arm-free (no hatch)"),
    Patch(facecolor="gray", alpha=0.7, hatch="///", label="arm-fixed (UR10 static)"),
]
ax.legend(handles=legend_elements + ax.get_legend_handles_labels()[0],
          loc="lower right", framealpha=0.9, fontsize=9)

fig.tight_layout()
p = OUT_DIR / "fig2_pearson_r_comparison.png"
fig.savefig(p, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {p}")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 3  Distance error vs oracle distance (arm-free, sphere + cube)
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7, 5))

ERROR_SETS = [
    ("Cube 0.10m (arm-free)",   ARM_FREE_DIR / "cube_0.10m"       / "armfree_proximity_sweep.csv",  "#1f77b4", "s"),
    ("Sphere r=0.05m (arm-free)", ARM_FREE_DIR / "sphere_r0.05m"  / "armfree_proximity_sweep.csv",  "#ff7f0e", "o"),
    ("Sphere r=0.05m (arm home)", ARMFIX_DIR / "home_sphere_r0.05m" / "armfixed_proximity_sweep.csv", "#d62728", "o"),
    ("Sphere r=0.05m (arm fwd)",  ARMFIX_DIR / "reach_forward_sphere_r0.05m" / "armfixed_proximity_sweep.csv", "#9467bd", "^"),
]

ax.axhline(0.0, color="black", lw=1.0, ls="-", alpha=0.6)
ax.axvspan(0.0, NEAR_FIELD_LIMIT, alpha=0.07, color="red")
ax.text(0.23, -0.43, "Near-field\nzone", fontsize=8.5, color="red", alpha=0.7, ha="center")

for label, csv_path, color, marker in ERROR_SETS:
    rows = load_csv(csv_path)
    if not rows:
        continue
    fname = "inferred_dist_m" if "armfree" in str(csv_path) or "armfixed" in str(csv_path) else "inferred_dist_m"
    valid = [(float(r["oracle_distance_m"]), float(r[fname]))
             for r in rows if not math.isnan(float(r.get(fname, "nan")))]
    if not valid:
        continue
    ox, err = zip(*[(o, i - o) for o, i in valid])
    rmse_v, bias_v = rmse_bias(rows)
    ax.scatter(ox, err, color=color, marker=marker, s=40, alpha=0.85,
               label=f"{label}  bias={bias_v:+.3f}m RMSE={rmse_v:.3f}m")

ax.set_xlabel("Oracle distance (m)")
ax.set_ylabel("Error = inferred − oracle (m)")
ax.set_title("Fig 3  WPM Distance Error Analysis\n(inferred − oracle)")
ax.legend(loc="upper right", framealpha=0.9)
ax.set_xlim(0.10, 1.60)
ax.set_ylim(-0.55, 0.55)

fig.tight_layout()
p = OUT_DIR / "fig3_distance_error.png"
fig.savefig(p, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {p}")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 4  Cube size detectability (full-range and far-field)
# ═══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

# Left: full-range r by cube size (including near-field contamination)
CUBE_SIZES_FULL = [
    ("0.05m", SIZE_DIR / "cube_0.05m" / "armfree_proximity_sweep.csv"),
    ("0.10m", SIZE_DIR / "cube_0.10m" / "armfree_proximity_sweep.csv"),
    ("0.20m", SIZE_DIR / "cube_0.20m" / "armfree_proximity_sweep.csv"),
    ("0.30m", SIZE_DIR / "cube_0.30m" / "armfree_proximity_sweep.csv"),
    ("0.50m", SIZE_DIR / "cube_0.50m" / "armfree_proximity_sweep.csv"),
]
CUBE_SIZES_FAR = [
    ("0.30m\n(far-field)", FARFIELD_DIR / "cube_0.30m_farfield" / "armfree_proximity_sweep.csv"),
    ("0.50m\n(far-field)", FARFIELD_DIR / "cube_0.50m_farfield" / "armfree_proximity_sweep.csv"),
]

def bar_cube(ax_obj, datasets, title, color_fn):
    labels, r_vals = [], []
    for label, csv_path in datasets:
        rows = load_csv(csv_path)
        if not rows:
            labels.append(label); r_vals.append(0)
            continue
        dists = [float(r["oracle_distance_m"]) for r in rows]
        peaks = [float(r.get("peak_sample_idx", "nan")) for r in rows]
        labels.append(label)
        r_vals.append(abs(pearson_r(dists, peaks)))
    colors_b = [color_fn(r) for r in r_vals]
    bars = ax_obj.bar(range(len(labels)), r_vals, color=colors_b, alpha=0.85,
                      edgecolor="black", linewidth=0.7)
    for bar, rv in zip(bars, r_vals):
        ax_obj.text(bar.get_x() + bar.get_width() / 2, rv + 0.01,
                    f"{rv:.3f}", ha="center", va="bottom", fontsize=9)
    ax_obj.axhline(0.90, color="green", ls="--", lw=1.2, alpha=0.7)
    ax_obj.axhline(0.60, color="orange", ls="--", lw=1.2, alpha=0.7)
    ax_obj.set_xticks(range(len(labels)))
    ax_obj.set_xticklabels(labels)
    ax_obj.set_xlabel("Cube edge length")
    ax_obj.set_ylim(0, 1.10)
    ax_obj.set_title(title)

def rcolor(r):
    if r > 0.90: return "#2ca02c"
    if r > 0.60: return "#ff7f0e"
    return "#d62728"

bar_cube(axes[0], CUBE_SIZES_FULL,
         "Full range (0.20–1.50m)\n(includes near-field zone)", rcolor)
axes[0].set_ylabel("|Pearson r|  (peak_sample_idx vs oracle)")

bar_cube(axes[1], CUBE_SIZES_FAR,
         "Far-field only (≥0.65m)\n(near-field contamination removed)", rcolor)

fig.suptitle("Fig 4  Cube Size Detectability: Effect of Near-Field Zone", fontsize=13)
fig.tight_layout()
p = OUT_DIR / "fig4_cube_size_detectability.png"
fig.savefig(p, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {p}")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 5  Background Robustness — windowed vs full-window peak
# ═══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Left panel: background conditions × full-window r
BG_CONDS = [
    ("no_bg",            "No bg\n(baseline)"),
    ("floor_only",       "Floor only\n(y=-0.50m)"),
    ("floor_wall",       "Floor+Wall\n(x=2.00m)"),
    ("floor_wall_close", "Floor+Wall\n(x=1.60m)"),
]

ax_l = axes[0]
bg_labels, bg_r_vals = [], []
for label, desc in BG_CONDS:
    csv_path = BG_DIR / label / "armfree_bg_proximity_sweep.csv"
    rows = load_csv(csv_path)
    bg_labels.append(desc)
    if not rows:
        bg_r_vals.append(float("nan"))
        continue
    dists = [float(r["oracle_distance_m"]) for r in rows]
    peaks = [float(r.get("peak_sample_idx", "nan")) for r in rows]
    bg_r_vals.append(abs(pearson_r(dists, peaks)))

bar_colors = [rcolor(r) if not math.isnan(r) else "#cccccc" for r in bg_r_vals]
bars = ax_l.bar(range(len(bg_labels)), bg_r_vals, color=bar_colors, alpha=0.85,
                edgecolor="black", linewidth=0.7)
for bar, rv in zip(bars, bg_r_vals):
    if not math.isnan(rv):
        ax_l.text(bar.get_x() + bar.get_width() / 2, rv + 0.01,
                  f"{rv:.4f}", ha="center", va="bottom", fontsize=9)
ax_l.axhline(0.90, color="green", ls="--", lw=1.2, alpha=0.7, label="r=0.90")
ax_l.axhline(0.60, color="orange", ls="--", lw=1.2, alpha=0.7, label="r=0.60")
ax_l.set_xticks(range(len(bg_labels)))
ax_l.set_xticklabels(bg_labels, fontsize=9.5)
ax_l.set_ylabel("|Pearson r|  (full-window peak vs oracle)")
ax_l.set_ylim(0, 1.12)
ax_l.set_title("Background scene impact\n(full-window argmax)")
ax_l.legend(fontsize=9)

# Right panel: full-window vs early-window for wall+floor conditions
WIN_CONDS = [
    ("no_bg_full",          "No bg\n(full win)"),
    ("floor_wall200_full",  "Floor+Wall x=2m\n(full win)"),
    ("floor_wall200_win090","Floor+Wall x=2m\n(early win=90)"),
    ("floor_wall160_win085","Floor+Wall x=1.6m\n(early win=85)"),
]

ax_r = axes[1]
wlabels, wfull, wwin = [], [], []
for label, desc in WIN_CONDS:
    csv_path = WIN_DIR / label / "armfree_winpeak_sweep.csv"
    rows = load_csv(csv_path)
    wlabels.append(desc)
    if not rows:
        wfull.append(float("nan"))
        wwin.append(float("nan"))
        continue
    dists = [float(r["oracle_distance_m"]) for r in rows]
    fpks  = [float(r.get("peak_sample_idx", "nan")) for r in rows]
    wpks  = [float(r.get("win_peak_idx",   "nan")) for r in rows]
    wfull.append(abs(pearson_r(dists, fpks)))
    wwin.append(abs(pearson_r(dists, wpks)))

x = np.arange(len(wlabels))
w = 0.35
bars_f = ax_r.bar(x - w/2, wfull, w, color="#ff7f0e", alpha=0.8,
                  edgecolor="black", linewidth=0.7, label="Full-window argmax")
bars_w = ax_r.bar(x + w/2, wwin,  w, color="#2ca02c", alpha=0.8,
                  edgecolor="black", linewidth=0.7, label="Early-window argmax")
for bar, rv in list(zip(bars_f, wfull)) + list(zip(bars_w, wwin)):
    if not math.isnan(rv):
        ax_r.text(bar.get_x() + bar.get_width() / 2, rv + 0.01,
                  f"{rv:.4f}", ha="center", va="bottom", fontsize=7.5)
ax_r.axhline(0.90, color="green", ls="--", lw=1.2, alpha=0.7)
ax_r.set_xticks(x)
ax_r.set_xticklabels(wlabels, fontsize=8.5)
ax_r.set_ylabel("|Pearson r|")
ax_r.set_ylim(0, 1.15)
ax_r.set_title("Early-window fix restores r>0.999\n(windowed peak beats full-window)")
ax_r.legend(fontsize=9)

fig.suptitle("Fig 5  Background Robustness: Floor/Wall Interference & Early-Window Fix",
             fontsize=13)
fig.tight_layout()
p = OUT_DIR / "fig5_background_robustness.png"
fig.savefig(p, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {p}")


# ═══════════════════════════════════════════════════════════════════════════════
# Summary table (text)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("SUMMARY TABLE — All experiments")
print("=" * 70)
print(f"{'條件':<40} {'r':>8} {'RMSE':>8} {'bias':>8}")
print("-" * 70)

ALL = [
    ("arm-free cube 0.05m (0.20-1.50m)",   SIZE_DIR / "cube_0.05m" / "armfree_proximity_sweep.csv"),
    ("arm-free cube 0.10m (0.20-1.50m)",   ARM_FREE_DIR / "cube_0.10m" / "armfree_proximity_sweep.csv"),
    ("arm-free cube 0.20m (0.20-1.50m)",   SIZE_DIR / "cube_0.20m" / "armfree_proximity_sweep.csv"),
    ("arm-free sphere r=0.05m",            ARM_FREE_DIR / "sphere_r0.05m" / "armfree_proximity_sweep.csv"),
    ("arm-free sphere r=0.10m",            ARM_FREE_DIR / "sphere_r0.10m" / "armfree_proximity_sweep.csv"),
    ("arm-free cylinder r=0.05m h=0.20m",  ARM_FREE_DIR / "cylinder_r0.05m_h0.20m" / "armfree_proximity_sweep.csv"),
    ("arm-free cylinder r=0.05m h=0.30m",  ARM_FREE_DIR / "cylinder_r0.05m_h0.30m" / "armfree_proximity_sweep.csv"),
    ("arm-free cube 0.30m FARFIELD",       FARFIELD_DIR / "cube_0.30m_farfield" / "armfree_proximity_sweep.csv"),
    ("arm-free cube 0.50m FARFIELD",       FARFIELD_DIR / "cube_0.50m_farfield" / "armfree_proximity_sweep.csv"),
    ("arm-fixed (home) sphere r=0.05m",    ARMFIX_DIR / "home_sphere_r0.05m" / "armfixed_proximity_sweep.csv"),
    ("arm-fixed (home) sphere r=0.10m",    ARMFIX_DIR / "home_sphere_r0.10m" / "armfixed_proximity_sweep.csv"),
    ("arm-fixed (reach_fwd) sphere r=0.05m", ARMFIX_DIR / "reach_forward_sphere_r0.05m" / "armfixed_proximity_sweep.csv"),
    # background robustness (full-window)
    ("bg: no floor/wall  (full win)",      BG_DIR  / "no_bg"            / "armfree_bg_proximity_sweep.csv"),
    ("bg: floor only     (full win)",      BG_DIR  / "floor_only"       / "armfree_bg_proximity_sweep.csv"),
    ("bg: floor+wall x=2m (full win)",     BG_DIR  / "floor_wall"       / "armfree_bg_proximity_sweep.csv"),
    ("bg: floor+wall x=1.6m (full win)",   BG_DIR  / "floor_wall_close" / "armfree_bg_proximity_sweep.csv"),
]

for label, csv_path in ALL:
    rows = load_csv(csv_path)
    if not rows:
        print(f"  {label:<40} (no data)")
        continue
    fname = "inferred_dist_m"
    dists = [float(r["oracle_distance_m"]) for r in rows]
    peaks = [float(r.get("peak_sample_idx", "nan")) for r in rows]
    r_val = pearson_r(dists, peaks)
    rmse, bias = rmse_bias(rows)
    flag = "✅" if abs(r_val) > 0.90 else ("⚠️" if abs(r_val) > 0.60 else "❌")
    print(f"  {label:<40} {r_val:>+8.4f} {rmse:>8.4f} {bias:>+8.4f}  {flag}")

print("=" * 70)


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 6  Frequency sweep — r vs center frequency
# ═══════════════════════════════════════════════════════════════════════════════
FREQS = [20000, 30000, 40000, 60000, 80000, 100000]
freq_labels = ["20k", "30k", "40k\n(baseline)", "60k", "80k", "100k"]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

# Left: |r| vs frequency
ax_l = axes[0]
r_vals_freq, rmse_vals_freq = [], []
for freq in FREQS:
    csv_path = FREQ_DIR / f"freq_{freq}hz" / "armfree_proximity_sweep.csv"
    rows = load_csv(csv_path)
    if not rows:
        r_vals_freq.append(float("nan"))
        rmse_vals_freq.append(float("nan"))
        continue
    dists = [float(r["oracle_distance_m"]) for r in rows]
    peaks = [float(r.get("peak_sample_idx", "nan")) for r in rows]
    infs  = [float(r.get("inferred_dist_m", "nan")) for r in rows]
    r_vals_freq.append(abs(pearson_r(dists, peaks)))
    valid = [(float(r["oracle_distance_m"]), float(r["inferred_dist_m"]))
             for r in rows if not math.isnan(float(r.get("inferred_dist_m","nan")))]
    if valid:
        errs = [i - o for o, i in valid]
        rmse_vals_freq.append(math.sqrt(sum(e**2 for e in errs) / len(errs)))
    else:
        rmse_vals_freq.append(float("nan"))

xs = range(len(FREQS))
bar_c = [rcolor(r) if not math.isnan(r) else "#cccccc" for r in r_vals_freq]
bars = ax_l.bar(xs, r_vals_freq, color=bar_c, alpha=0.85, edgecolor="black", linewidth=0.7)
for bar, rv in zip(bars, r_vals_freq):
    if not math.isnan(rv):
        ax_l.text(bar.get_x() + bar.get_width()/2, rv + 0.003,
                  f"{rv:.4f}", ha="center", va="bottom", fontsize=8.5)
ax_l.axhline(0.90, color="green", ls="--", lw=1.2, alpha=0.7, label="r=0.90")
ax_l.set_xticks(list(xs))
ax_l.set_xticklabels(freq_labels)
ax_l.set_xlabel("Center frequency (Hz)")
ax_l.set_ylabel("|Pearson r|  (peak_sample_idx vs oracle_distance)")
ax_l.set_ylim(0, 1.10)
ax_l.set_title("|Pearson r| across frequencies\n(sphere r=0.05m, arm-free)")
ax_l.legend(fontsize=9)

# Right: peak_sample_idx sequences overlay (to visualise they are identical)
ax_r = axes[1]
colors6 = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd","#8c564b"]
for i, freq in enumerate(FREQS):
    csv_path = FREQ_DIR / f"freq_{freq}hz" / "armfree_proximity_sweep.csv"
    rows = load_csv(csv_path)
    if not rows: continue
    dists = [float(r["oracle_distance_m"]) for r in rows]
    peaks = [float(r.get("peak_sample_idx","nan")) for r in rows]
    valid_dp = [(d, p) for d, p in zip(dists, peaks) if not math.isnan(p)]
    if not valid_dp: continue
    dvs, pvs = zip(*valid_dp)
    # Only show non-overlapping points for clarity; lines overlap perfectly
    ax_r.plot(dvs, pvs, color=colors6[i], lw=2.0, alpha=0.7,
              label=f"{freq//1000}kHz", linestyle=["-","--","-.",":","--","-."][i])

ax_r.set_xlabel("Oracle distance (m)")
ax_r.set_ylabel("peak_sample_idx")
ax_r.set_title("peak_sample_idx vs distance (all frequencies)\n(lines perfectly overlap — frequency-agnostic)")
ax_r.legend(fontsize=9, ncol=2)

fig.suptitle("Fig 6  Frequency Sweep: WPM Distance Sensing is Frequency-Agnostic (20k–100kHz)",
             fontsize=12)
fig.tight_layout()
p = OUT_DIR / "fig6_frequency_sweep.png"
fig.savefig(p, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {p}")

print(f"\nFigures saved to: {OUT_DIR}")
