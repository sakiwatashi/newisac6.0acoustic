#!/usr/bin/env python3
"""P0 offline audit: GMO → way → peak → distance (no GPU / no Isaac).

Uses existing V2 canon products:
  runtime/outputs/v2_s1_envelope/
  runtime/outputs/v2_s2_datasheet/

Writes:
  runtime/outputs/p0_gmo_chain_audit/
    figures/*.png
    metrics.json
  and prints a short adjudication block for the markdown report.

Usage:
  python3 scripts/p0_gmo_chain_offline_audit.py
  python3 scripts/p0_gmo_chain_offline_audit.py --repo-root /path/to/isaacsim6.0
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import sys

import numpy as np

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MPL = True
except Exception:
    HAS_MPL = False

V_SOUND = 343.0
SAMPLE_DURATION_SCHEMA_S = 102.4e-6  # NVIDIA acoustic_extension.rst default
N_SPS_EXPECTED = 320


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size < 2:
        return float("nan"), float("nan"), float("nan")
    xm, ym = float(x.mean()), float(y.mean())
    sxx = float(np.sum((x - xm) ** 2))
    if sxx <= 0:
        return float("nan"), float("nan"), float("nan")
    slope = float(np.sum((x - xm) * (y - ym)) / sxx)
    intercept = ym - slope * xm
    r = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else float("nan")
    return slope, intercept, r


def _load_points(csv_path: pathlib.Path) -> list[dict]:
    with csv_path.open(newline="") as f:
        return list(csv.DictReader(f))


def _peak_abs(wf: np.ndarray) -> tuple[int, float]:
    a = np.asarray(wf, dtype=float)
    if a.size == 0:
        return -1, float("nan")
    i = int(np.argmax(np.abs(a)))
    return i, float(np.abs(a[i]))


def audit_s1_block_a(s1_root: pathlib.Path) -> dict:
    """Horizontal pitch=0 cells: peak moves with distance; without-target does not."""
    rows = []
    for cr in sorted(s1_root.glob("A_*/cell_result.json")):
        d = json.loads(cr.read_text())
        if float(d.get("sensor_pitch_deg", 0)) != 0:
            continue
        rows.append(
            {
                "cell_id": d["cell_id"],
                "distance_m": float(d["target_distance_m"]),
                "size_m": float(d["target_size_m"]),
                "with_peak_idx": float(d["with_target"]["peak_sample_idx"]),
                "without_peak_idx": float(d["without_target"]["peak_sample_idx"]),
                "snr_peak": float(d["snr_peak"]),
                "detectable": float(d["snr_peak"]) >= 10.0,
            }
        )
    # 0.10 m target only for clean distance monotonicity
    r10 = [r for r in rows if abs(r["size_m"] - 0.10) < 1e-9]
    r10 = sorted(r10, key=lambda r: r["distance_m"])
    dists = np.array([r["distance_m"] for r in r10], dtype=float)
    with_pk = np.array([r["with_peak_idx"] for r in r10], dtype=float)
    wo_pk = np.array([r["without_peak_idx"] for r in r10], dtype=float)
    slope, intercept, r = _ols(dists, with_pk)
    # without-target peaks should not track distance the same way
    _, _, r_wo = _ols(dists, wo_pk)
    return {
        "n_cells_pitch0": len(rows),
        "n_size_0p10": len(r10),
        "rows_size_0p10": r10,
        "with_peak_vs_distance": {
            "slope": slope,
            "intercept": intercept,
            "pearson_r": r,
        },
        "without_peak_vs_distance_pearson_r": r_wo,
        "without_peak_mostly_fixed": bool(np.all(np.abs(wo_pk - wo_pk[0]) < 1e-6) or np.std(wo_pk) < 1.0),
        "gate_with_tracks_distance": bool(math.isfinite(r) and r >= 0.95),
        "gate_without_not_same_track": bool(
            (not math.isfinite(r_wo)) or abs(r_wo) < 0.5 or np.std(wo_pk) < 5.0
        ),
    }


def audit_s2_distance(s2_root: pathlib.Path) -> dict:
    summary_path = s2_root / "datasheet_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    p1 = _load_points(s2_root / "distance_p1" / "points.csv")
    kept = [r for r in p1 if str(r.get("stationarity_ok", "True")).lower() in ("true", "1")]
    # If stationarity_ok missing treat all as kept for plotting; OLS uses kept only
    if not any("stationarity_ok" in r for r in p1):
        kept = p1
    d = np.array([float(r["true_distance_3d_m"]) for r in kept], dtype=float)
    k = np.array([float(r["peak_sample_idx"]) for r in kept], dtype=float)
    slope, intercept, r = _ols(d, k)
    t_cal = 2.0 / (slope * V_SOUND) if slope and math.isfinite(slope) and slope != 0 else float("nan")
    mono_slope = 2.0 / (V_SOUND * SAMPLE_DURATION_SCHEMA_S)
    # dual-way comparison on a few points
    wf_dir = s2_root / "distance_p1" / "waveforms"
    dual = []
    for tag in ["point_05", "point_10", "point_15"]:
        p0 = wf_dir / f"{tag}_rx0.npy"
        p1p = wf_dir / f"{tag}_rx1.npy"
        if not (p0.exists() and p1p.exists()):
            continue
        a0, a1 = np.load(p0), np.load(p1p)
        i0, m0 = _peak_abs(a0)
        i1, m1 = _peak_abs(a1)
        corr = float(np.corrcoef(a0, a1)[0, 1]) if a0.size == a1.size and a0.size > 2 else float("nan")
        dual.append(
            {
                "tag": tag,
                "rx0_peak_idx": i0,
                "rx1_peak_idx": i1,
                "rx0_peak_abs": m0,
                "rx1_peak_abs": m1,
                "corr": corr,
                "identical": bool(np.allclose(a0, a1)),
                "n_samples": int(a0.size),
            }
        )
    # concatenate-as-time negative control: glue rx0|rx1 and take global max index
    concat_demo = None
    if dual:
        tag = dual[0]["tag"]
        a0 = np.load(wf_dir / f"{tag}_rx0.npy")
        a1 = np.load(wf_dir / f"{tag}_rx1.npy")
        cat = np.concatenate([a0, a1])
        i_cat, _ = _peak_abs(cat)
        concat_demo = {
            "tag": tag,
            "concat_peak_idx": i_cat,
            "rx0_len": int(a0.size),
            "note": "If ways were time-contiguous segments, concat peak index would be meaningful; "
            "NVIDIA defines each way as a full TX-RX waveform of length numSamplesPerSgw.",
        }
    return {
        "summary_combined": summary.get("distance", {}).get("combined", {}),
        "p1_ols": {
            "n_kept": int(d.size),
            "slope": slope,
            "intercept": intercept,
            "pearson_r": r,
            "t_cal_us": t_cal * 1e6 if math.isfinite(t_cal) else float("nan"),
            "schema_sample_duration_us": SAMPLE_DURATION_SCHEMA_S * 1e6,
            "monostatic_theory_slope": mono_slope,
            "slope_ratio_measured_over_theory": (slope / mono_slope) if mono_slope else float("nan"),
        },
        "dual_way": dual,
        "concat_negative_control": concat_demo,
        "gate_r_ge_0_95": bool(math.isfinite(r) and r >= 0.95),
        "gate_slope_near_schema": bool(
            math.isfinite(slope) and abs(slope / mono_slope - 1.0) < 0.05
        ),
        "gate_ways_not_identical": bool(dual and all(not x["identical"] for x in dual)),
    }


def make_figures(
    out_fig: pathlib.Path,
    s1: dict,
    s2: dict,
    s1_root: pathlib.Path,
    s2_root: pathlib.Path,
) -> list[str]:
    if not HAS_MPL:
        return []
    out_fig.mkdir(parents=True, exist_ok=True)
    made = []

    # Fig1: S1 with vs without peak idx
    r10 = s1["rows_size_0p10"]
    if r10:
        d = [r["distance_m"] for r in r10]
        wp = [r["with_peak_idx"] for r in r10]
        wo = [r["without_peak_idx"] for r in r10]
        fig, ax = plt.subplots(figsize=(6.2, 4.0))
        ax.plot(d, wp, "o-", label="with target (global |max| idx)")
        ax.plot(d, wo, "s--", label="without target")
        ax.set_xlabel("Target distance (m)")
        ax.set_ylabel("Peak sample index")
        ax.set_title("S1 Block A, 0.10 m cube, pitch=0: peak tracks target only when present")
        ax.grid(True, alpha=0.3)
        ax.legend()
        p = out_fig / "fig1_s1_peak_with_without.png"
        fig.tight_layout()
        fig.savefig(p, dpi=140)
        plt.close(fig)
        made.append(str(p))

    # Fig2: waveforms at 0.5 m with/without
    cell = s1_root / "A_d0.5_z0.10_p0_cnone" / "waveforms"
    if (cell / "with.npy").exists() and (cell / "without.npy").exists():
        w = np.load(cell / "with.npy")
        wo = np.load(cell / "without.npy")
        fig, axes = plt.subplots(2, 1, figsize=(7.0, 5.0), sharex=True)
        axes[0].plot(w, lw=0.9)
        i, _ = _peak_abs(w)
        axes[0].axvline(i, color="C3", ls="--", label=f"|max| @ {i}")
        axes[0].set_ylabel("amplitude")
        axes[0].set_title("S1 A_d0.5_z0.10: WITH target (primary way mean)")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        axes[1].plot(wo, lw=0.9, color="C1")
        i2, _ = _peak_abs(wo)
        axes[1].axvline(i2, color="C3", ls="--", label=f"|max| @ {i2}")
        axes[1].set_xlabel("sample index within signal way")
        axes[1].set_ylabel("amplitude")
        axes[1].set_title("WITHOUT target")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        p = out_fig / "fig2_s1_waveform_with_without_0p5m.png"
        fig.tight_layout()
        fig.savefig(p, dpi=140)
        plt.close(fig)
        made.append(str(p))

    # Fig3: S2 peak vs distance + theory line
    p1 = _load_points(s2_root / "distance_p1" / "points.csv")
    if p1:
        d_all = np.array([float(r["true_distance_3d_m"]) for r in p1])
        k_all = np.array([float(r["peak_sample_idx"]) for r in p1])
        ok = np.array(
            [
                str(r.get("stationarity_ok", "True")).lower() in ("true", "1")
                for r in p1
            ]
        )
        slope = s2["p1_ols"]["slope"]
        intercept = s2["p1_ols"]["intercept"]
        mono = s2["p1_ols"]["monostatic_theory_slope"]
        fig, ax = plt.subplots(figsize=(6.2, 4.2))
        ax.plot(d_all[ok], k_all[ok], "o", label="kept (stationarity_ok)")
        if np.any(~ok):
            ax.plot(d_all[~ok], k_all[~ok], "x", color="0.5", label="excluded drift")
        xs = np.linspace(float(np.nanmin(d_all)), float(np.nanmax(d_all)), 50)
        if math.isfinite(slope):
            ax.plot(xs, slope * xs + intercept, "-", label=f"OLS (r={s2['p1_ols']['pearson_r']:.4f})")
        ax.plot(xs, mono * xs, "--", label=f"monostatic 2d/(cT), T=102.4µs")
        ax.set_xlabel("true_distance_3d_m")
        ax.set_ylabel("peak_sample_idx")
        ax.set_title("S2 distance_p1: peak index vs range")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        p = out_fig / "fig3_s2_peak_vs_distance.png"
        fig.tight_layout()
        fig.savefig(p, dpi=140)
        plt.close(fig)
        made.append(str(p))

    # Fig4: dual ways at one distance (not concatenated)
    wf = s2_root / "distance_p1" / "waveforms"
    tag = "point_10"
    if (wf / f"{tag}_rx0.npy").exists():
        a0 = np.load(wf / f"{tag}_rx0.npy")
        a1 = np.load(wf / f"{tag}_rx1.npy")
        fig, axes = plt.subplots(2, 1, figsize=(7.0, 5.0), sharex=True)
        for ax, a, name in [(axes[0], a0, "way ordinal 0 (rx0)"), (axes[1], a1, "way ordinal 1 (rx1)")]:
            ax.plot(a, lw=0.9)
            i, _ = _peak_abs(a)
            ax.axvline(i, color="C3", ls="--", label=f"|max| @ {i}")
            ax.set_ylabel("amplitude")
            ax.set_title(f"S2 {tag}: {name} — separate ways (NOT time-concatenated)")
            ax.legend()
            ax.grid(True, alpha=0.3)
        axes[1].set_xlabel("sample index within way (len=numSamplesPerSgw)")
        p = out_fig / "fig4_s2_dual_ways_separate.png"
        fig.tight_layout()
        fig.savefig(p, dpi=140)
        plt.close(fig)
        made.append(str(p))

    # Fig5: overlay several distances on primary way (moving peak)
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for idx in [0, 5, 10, 15, 19]:
        fp = wf / f"point_{idx:02d}_primary.npy"
        if not fp.exists():
            continue
        a = np.load(fp)
        row = p1[idx]
        ax.plot(a, lw=0.8, label=f"d={float(row['true_distance_3d_m']):.2f}m k={float(row['peak_sample_idx']):.0f}")
    ax.set_xlabel("sample index")
    ax.set_ylabel("amplitude")
    ax.set_title("S2 primary way: peak location moves with target distance")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)
    p = out_fig / "fig5_s2_primary_overlay_distances.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    made.append(str(p))

    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[1],
    )
    args = ap.parse_args()
    root = args.repo_root
    s1 = root / "runtime" / "outputs" / "v2_s1_envelope"
    s2 = root / "runtime" / "outputs" / "v2_s2_datasheet"
    out = root / "runtime" / "outputs" / "p0_gmo_chain_audit"
    out.mkdir(parents=True, exist_ok=True)

    if not s1.is_dir() or not s2.is_dir():
        print(f"ABORT: need {s1} and {s2}", file=sys.stderr)
        return 2

    s1_m = audit_s1_block_a(s1)
    s2_m = audit_s2_distance(s2)
    figs = make_figures(out / "figures", s1_m, s2_m, s1, s2)

    # Drop bulky row dumps for metrics file readability (keep in nested)
    metrics = {
        "official_semantics": {
            "signal_way": "TX→RX→channel waveform; NOT a time shard to concatenate",
            "scalar": "amplitude sample (not 40 kHz carrier ADC stream)",
            "sampleDuration_schema_us": SAMPLE_DURATION_SCHEMA_S * 1e6,
            "numSamplesPerSgw_expected": N_SPS_EXPECTED,
            "sources": [
                "app/standalone_examples/.../inspect_acoustic_gmo.py",
                "app/extscache/omni.sensors.nv.acoustic-*/docs/acoustic_extension.rst",
            ],
        },
        "s1": {
            "with_peak_vs_distance": s1_m["with_peak_vs_distance"],
            "without_peak_vs_distance_pearson_r": s1_m["without_peak_vs_distance_pearson_r"],
            "without_peak_mostly_fixed": s1_m["without_peak_mostly_fixed"],
            "gate_with_tracks_distance": s1_m["gate_with_tracks_distance"],
            "gate_without_not_same_track": s1_m["gate_without_not_same_track"],
            "rows_size_0p10": s1_m["rows_size_0p10"],
        },
        "s2": s2_m,
        "figures": figs,
        "adjudication": {
            "p0_1_way_semantics_not_concat": True,
            "p0_2_scalar_not_40khz_carrier": True,
            "p0_3_control_uses_ols_not_bare_tof": True,
            "p0_3_slope_consistent_with_sampleDuration": s2_m["gate_slope_near_schema"],
            "p0_4_peak_is_target_related": s1_m["gate_with_tracks_distance"]
            and s1_m["gate_without_not_same_track"],
            "p0_4_distance_encoding_stable": s2_m["gate_r_ge_0_95"],
            "all_offline_gates_pass": bool(
                s1_m["gate_with_tracks_distance"]
                and s1_m["gate_without_not_same_track"]
                and s2_m["gate_r_ge_0_95"]
                and s2_m["gate_slope_near_schema"]
                and s2_m["gate_ways_not_identical"]
            ),
        },
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print("=== P0 offline adjudication ===")
    for k, v in metrics["adjudication"].items():
        print(f"  {k}: {v}")
    print(f"figures: {len(figs)} -> {out / 'figures'}")
    print(f"metrics: {out / 'metrics.json'}")
    return 0 if metrics["adjudication"]["all_offline_gates_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
