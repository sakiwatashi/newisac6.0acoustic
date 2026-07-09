"""Arm-free WPM acoustic proximity test.

Scene: fixed acoustic sensor + single Cube target, NO robot arm, NO room walls.
Sweeps the Cube from min_dist to max_dist along x-axis.
Tests whether WPM responds to the Cube's distance at all.

Usage:
    /home/lab109/song/isaacsim6.0/app/python.sh \\
        scripts/armfree_acoustic_proximity_test.py

    /home/lab109/song/isaacsim6.0/app/python.sh \\
        scripts/armfree_acoustic_proximity_test.py \\
        --min-dist 0.20 --max-dist 1.20 --n-steps 20 \\
        --output-dir runtime/outputs/armfree_test_v1
"""
from __future__ import annotations

import argparse
import csv
import math
import pathlib

# ── Argument parsing BEFORE SimulationApp ─────────────────────────────────────
parser = argparse.ArgumentParser(description="Arm-free WPM acoustic proximity test.")
parser.add_argument("--min-dist",    type=float, default=0.30,
                    help="Minimum target distance in metres")
parser.add_argument("--max-dist",    type=float, default=1.00,
                    help="Maximum target distance in metres")
parser.add_argument("--n-steps",     type=int,   default=15,
                    help="Number of distance steps in sweep")
parser.add_argument("--n-settle",    type=int,   default=12,
                    help="Simulation frames to wait after moving cube")
parser.add_argument("--n-measure",   type=int,   default=6,
                    help="Simulation frames to average per distance")
parser.add_argument("--cube-size",   type=float, default=0.20,
                    help="Target Cube edge length in metres")
parser.add_argument("--center-freq", type=float, default=40_000.0,
                    help="WPM center frequency in Hz (matches UR10e experiments)")
parser.add_argument("--mount-spacing", type=float, default=0.10,
                    help="TX-to-RX mount spacing in metres")
parser.add_argument("--az-span",     type=float, default=90.0,
                    help="Azimuth beam span in degrees")
parser.add_argument("--el-span",     type=float, default=90.0,
                    help="Elevation beam span in degrees")
# WPM close-range model parameters (schema defaults if not specified)
parser.add_argument("--close-range",          type=float, default=None,
                    help="WPM closeRange threshold (m). Default=1.42")
parser.add_argument("--close-direct-ampl",    type=float, default=None,
                    help="WPM closeDirectAmpl. Default=12.66")
parser.add_argument("--close-indirect-ampl",  type=float, default=None,
                    help="WPM closeIndirectAmpl. Default=17.64")
parser.add_argument("--close-direct-ampl-base",   type=float, default=None,
                    help="WPM closeDirectAmplBase. Default=1.39")
parser.add_argument("--close-indirect-ampl-base", type=float, default=None,
                    help="WPM closeIndirectAmplBase. Default=1.12")
parser.add_argument("--geometry",        type=str,   default="cube",
                    choices=["cube", "sphere", "cylinder"],
                    help="Target geometry type (cube/sphere/cylinder)")
parser.add_argument("--geom-radius",     type=float, default=None,
                    help="Sphere/cylinder radius (m). Default: cube-size/2")
parser.add_argument("--cylinder-height", type=float, default=0.30,
                    help="Cylinder height in metres (axis=Y, default 0.30m)")
parser.add_argument("--output-dir",  type=str,
                    default="runtime/outputs/armfree_test_v1")
args, _ = parser.parse_known_args()

# ── SimulationApp must come before all Isaac Sim imports ──────────────────────
from isaacsim import SimulationApp  # noqa: E402
simulation_app = SimulationApp({"headless": True})

import numpy as np                                   # noqa: E402
import omni.replicator.core as rep                  # noqa: E402
import omni.timeline                                # noqa: E402
import omni.usd                                     # noqa: E402
from isaacsim.core.experimental.objects import Cube  # noqa: E402
from isaacsim.sensors.experimental.rtx import (     # noqa: E402
    Acoustic, AcousticSensor, parse_generic_model_output_data,
)
from omni.replicator.core import Writer             # noqa: E402
from pxr import Gf, UsdGeom                        # noqa: E402

# ── Physical constants (same as existing UR10e experiments) ───────────────────
T_US = 132.5e-6   # seconds per WPM sample index
V_SOUND = 343.0   # m/s speed of sound
N_EARLY = 20      # sample boundary for "early" window (~0–0.45 m round-trip)
N_ULTRA = 8       # sample boundary for "ultra-early" window (~0–0.18 m)

# ── Module-level data buffer (Writer → main loop communication) ───────────────
_buf: dict = {"latest": None}


def _extract_features(gmo) -> dict | None:
    """Extract scalar acoustic features from a parsed GMO struct.

    KEY: Isaac Sim 6.0 returns timeOffsetNs=0 for all elements (known API
    limitation).  The correct temporal ordering is encoded in the GMO buffer
    layout: samples within a signal way are stored sequentially in time order,
    and numSamplesPerSgw gives the stride.  This mirrors the logic used in
    rtx_acoustic_factory.py (see matched_filter_tof / parse_signal_ways).
    """
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None

    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float)
    tof_all = np.ctypeslib.as_array(gmo.timeOffsetNs, shape=(n,)).astype(float)

    # ── Primary signal way amplitude slice ────────────────────────────────────
    # numSamplesPerSgw splits the flat GMO buffer into temporally-ordered slices.
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    n_ways = 0
    if num_spsgw > 0 and n % num_spsgw == 0:
        n_ways = n // num_spsgw
        # Use the signal way with the highest peak amplitude as "primary"
        best_start, best_peak = 0, -math.inf
        for w in range(n_ways):
            s = w * num_spsgw
            pk = float(np.max(amp_all[s : s + num_spsgw]))
            if pk > best_peak:
                best_peak, best_start = pk, s
        amps = amp_all[best_start : best_start + num_spsgw]
        tof_first = float(tof_all[best_start])
    else:
        # Fallback: group by (tx, rx, ch) – old behaviour
        tx_arr = np.ctypeslib.as_array(gmo.x, shape=(n,))
        rx_arr = np.ctypeslib.as_array(gmo.y, shape=(n,))
        ch_arr = np.ctypeslib.as_array(gmo.z, shape=(n,)).astype(int)
        pairs = sorted(set(zip(tx_arr.tolist(), rx_arr.tolist(), ch_arr.tolist())))
        n_ways = len(pairs)
        tx0, rx0, ch0 = pairs[0]
        mask = (tx_arr == tx0) & (rx_arr == rx0) & (ch_arr == ch0)
        amps = amp_all[mask]
        tof_first = float(tof_all[np.where(mask)[0][0]])

    if len(amps) == 0:
        return None

    # ── Features (temporal order = array index order) ─────────────────────────
    peak_idx = int(np.argmax(amps))
    peak_amp = float(amps[peak_idx])
    total_e  = float(np.sum(amps ** 2))
    early_e  = float(np.sum(amps[:N_EARLY] ** 2))
    ultra_e  = float(np.sum(amps[:N_ULTRA] ** 2))
    early_frac = early_e / total_e if total_e > 0.0 else 0.0

    return {
        "peak_sample_idx":    float(peak_idx),
        "peak_amplitude":     peak_amp,
        "total_energy":       total_e,
        "early_energy":       early_e,
        "ultra_early_energy": ultra_e,
        "early_fraction":     early_frac,
        "inferred_dist_m":    peak_idx * T_US * V_SOUND / 2.0,
        "tof_first_ns":       tof_first,            # diagnostic: is timeOffsetNs 0?
        "n_signal_ways":      float(n_ways),
        "n_samples_per_sgw":  float(num_spsgw),
        "n_elements":         float(n),
    }


# ── Writer class ──────────────────────────────────────────────────────────────
class ArmfreeProximityWriter(Writer):
    """Parses GMO each frame and stores features in module-level _buf."""

    def __init__(self):
        self.data_structure = "renderProduct"
        self.annotators = [rep.annotators.get("GenericModelOutput")]

    def write(self, data):
        _buf["latest"] = None
        if "renderProducts" not in data:
            return
        for _rp, rp_data in data["renderProducts"].items():
            raw = rp_data.get("GenericModelOutput")
            if isinstance(raw, dict):
                raw = raw.get("data")
            gmo = parse_generic_model_output_data(raw)
            feats = _extract_features(gmo)
            if feats is not None:
                _buf["latest"] = feats
                return  # first render product is sufficient


# ── Scene setup ───────────────────────────────────────────────────────────────
_eff_radius = args.geom_radius if args.geom_radius is not None else args.cube_size / 2.0

print(f"=== Arm-Free WPM Acoustic Proximity Test ===")
if args.geometry == "cube":
    print(f"Target  : Cube {args.cube_size}m × {args.cube_size}m × {args.cube_size}m along +X axis")
elif args.geometry == "sphere":
    print(f"Target  : Sphere radius={_eff_radius:.3f}m along +X axis")
else:
    print(f"Target  : Cylinder r={_eff_radius:.3f}m h={args.cylinder_height:.3f}m (axis=Y) along +X axis")
print(f"Sensor  : center_freq={args.center_freq:.0f} Hz  "
      f"mount_spacing={args.mount_spacing}m  "
      f"az={args.az_span}°  el={args.el_span}°")
print(f"Sweep   : {args.min_dist:.2f} m → {args.max_dist:.2f} m  ({args.n_steps} steps)")
print(f"Settle  : {args.n_settle} frames / position")
_cr_info = []
for k, v in [("closeRange", args.close_range),
             ("closeDirectAmpl", args.close_direct_ampl),
             ("closeIndirectAmpl", args.close_indirect_ampl)]:
    if v is not None:
        _cr_info.append(f"{k}={v}")
if _cr_info:
    print(f"WPM CR  : {', '.join(_cr_info)}")
print()

# Target geometry — starts at min_dist, will be moved by USD API
if args.geometry == "cube":
    target = Cube(
        "/World/target",
        positions=np.array([[args.min_dist, 0.0, 0.0]]),
        scales=np.array([[args.cube_size, args.cube_size, args.cube_size]]),
    )
    _stage = omni.usd.get_context().get_stage()
else:
    # Sphere / Cylinder — create via USD API on a fresh stage
    omni.usd.get_context().new_stage()
    _stage = omni.usd.get_context().get_stage()
    if args.geometry == "sphere":
        _pd = UsdGeom.Sphere.Define(_stage, "/World/target")
        _pd.GetRadiusAttr().Set(_eff_radius)
    else:  # cylinder
        _pd = UsdGeom.Cylinder.Define(_stage, "/World/target")
        _pd.GetRadiusAttr().Set(_eff_radius)
        _pd.GetHeightAttr().Set(args.cylinder_height)
        _pd.GetAxisAttr().Set("Y")   # vertical cylinder, perpendicular to +X approach
    UsdGeom.Xformable(_pd).AddTranslateOp().Set(Gf.Vec3d(args.min_dist, 0.0, 0.0))

# Acoustic sensor — fixed at origin
# Same parameter convention as our UR10e experiments (geometry_passport_v1.py)
acoustic = Acoustic(
    "/World/acoustic",
    tick_rate=30.0,
    aux_output_level="BASIC",
    translations=np.array([[0.0, 0.0, 0.0]]),
    attributes={
        "omni:sensor:WpmAcoustic:centerFrequency": args.center_freq,
        "omni:sensor:WpmAcoustic:azSpanDeg":       args.az_span,
        "omni:sensor:WpmAcoustic:elSpanDeg":       args.el_span,
        # TX mount at sensor origin
        "omni:sensor:WpmAcoustic:sensorMount:m001:position": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m001:rotation": (0.0, 0.0, 0.0),
        # RX mount — same lateral spacing as UR10e sensor (0.10 m)
        "omni:sensor:WpmAcoustic:sensorMount:m002:position": (float(args.mount_spacing), 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:rotation": (0.0, 0.0, 0.0),
        # Receiver group
        "omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices": [0, 1],
        # Close-range model overrides (only set if explicitly provided)
        **({} if args.close_range          is None else {"omni:sensor:WpmAcoustic:closeRange":         args.close_range}),
        **({} if args.close_direct_ampl    is None else {"omni:sensor:WpmAcoustic:closeDirectAmpl":    args.close_direct_ampl}),
        **({} if args.close_indirect_ampl  is None else {"omni:sensor:WpmAcoustic:closeIndirectAmpl":  args.close_indirect_ampl}),
        **({} if args.close_direct_ampl_base   is None else {"omni:sensor:WpmAcoustic:closeDirectAmplBase":   args.close_direct_ampl_base}),
        **({} if args.close_indirect_ampl_base is None else {"omni:sensor:WpmAcoustic:closeIndirectAmplBase": args.close_indirect_ampl_base}),
    },
)

sensor = AcousticSensor(acoustic, annotators=[])

rep.WriterRegistry.register(ArmfreeProximityWriter)
sensor.attach_writer("ArmfreeProximityWriter")

# ── USD helper: move target by rewriting xform translate op ──────────────────
_target_prim = _stage.GetPrimAtPath("/World/target")
_xformable = UsdGeom.Xformable(_target_prim)


def _move_target(x: float, y: float = 0.0, z: float = 0.0) -> None:
    """Set the translation of /World/target via USD API (world frame)."""
    ops_by_name = {op.GetOpName(): op for op in _xformable.GetOrderedXformOps()}
    translate_key = "xformOp:translate"
    if translate_key in ops_by_name:
        ops_by_name[translate_key].Set(Gf.Vec3d(x, y, z))
    else:
        # Fall back: add a translate op
        _xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))


# ── Simulation ────────────────────────────────────────────────────────────────
timeline = omni.timeline.get_timeline_interface()
timeline.play()

print("Warming up (25 frames)…")
for _ in range(25):
    simulation_app.update()

# ── Distance sweep ────────────────────────────────────────────────────────────
distances = np.linspace(args.min_dist, args.max_dist, args.n_steps)
rows: list[dict] = []

HDR = (f"{'dist_m':>8}  {'peak_idx':>9}  {'inferred_m':>10}  "
       f"{'early_e':>10}  {'ultra_e':>10}  {'frac':>7}  "
       f"{'amp':>8}  {'spsgw':>6}  {'tof_ns':>10}")
print(HDR)
print("-" * len(HDR))

for dist in distances:
    dist_f = float(dist)
    _move_target(dist_f)

    # Let WPM settle
    for _ in range(args.n_settle):
        simulation_app.update()

    # Collect measurements
    samples: list[dict] = []
    for _ in range(args.n_measure):
        simulation_app.update()
        if _buf["latest"] is not None:
            samples.append(_buf["latest"].copy())

    if not samples:
        print(f"{dist_f:>8.3f}   NO DATA (numElements=0 every frame)")
        rows.append({"oracle_distance_m": dist_f,
                     "peak_sample_idx": float("nan"),
                     "peak_amplitude": float("nan"),
                     "total_energy": float("nan"),
                     "early_energy": float("nan"),
                     "ultra_early_energy": float("nan"),
                     "early_fraction": float("nan"),
                     "inferred_dist_m": float("nan"),
                     "tof_first_ns": float("nan"),
                     "n_signal_ways": float("nan"),
                     "n_samples_per_sgw": float("nan"),
                     "n_elements": 0.0})
        continue

    avg = {k: float(sum(s[k] for s in samples)) / len(samples) for k in samples[0]}
    avg["oracle_distance_m"] = dist_f
    rows.append(avg)

    print(
        f"{dist_f:>8.3f}  "
        f"{avg['peak_sample_idx']:>9.1f}  "
        f"{avg['inferred_dist_m']:>10.3f}  "
        f"{avg['early_energy']:>10.2f}  "
        f"{avg['ultra_early_energy']:>10.2f}  "
        f"{avg['early_fraction']:>7.4f}  "
        f"{avg['peak_amplitude']:>8.4f}  "
        f"{avg['n_samples_per_sgw']:>6.0f}  "
        f"{avg['tof_first_ns']:>10.0f}"
    )

timeline.stop()

# ── Save CSV ──────────────────────────────────────────────────────────────────
out_dir = pathlib.Path(args.output_dir)
out_dir.mkdir(parents=True, exist_ok=True)
csv_path = out_dir / "armfree_proximity_sweep.csv"

fieldnames = ["oracle_distance_m", "peak_sample_idx", "inferred_dist_m",
              "early_energy", "ultra_early_energy", "early_fraction",
              "peak_amplitude", "total_energy", "tof_first_ns",
              "n_signal_ways", "n_samples_per_sgw", "n_elements"]
with csv_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
print(f"\n→ {len(rows)} rows saved to {csv_path}")

# ── Pearson correlation analysis ──────────────────────────────────────────────
def pearson_r(xs: list, ys: list) -> float:
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
    return num / den if den > 0.0 else float("nan")


valid_rows = [r for r in rows if not math.isnan(r.get("peak_sample_idx", float("nan")))]
dists = [r["oracle_distance_m"] for r in rows]

print(f"\n=== Pearson r (feature vs oracle_distance_m) ===")
feats_to_check = [
    "peak_sample_idx", "inferred_dist_m",
    "early_energy", "ultra_early_energy",
    "early_fraction", "peak_amplitude", "total_energy",
]
best_r, best_feat = 0.0, ""
for feat in feats_to_check:
    vals = [r.get(feat, float("nan")) for r in rows]
    r_val = pearson_r(dists, vals)
    flag = ("★★★" if abs(r_val) > 0.80 else
            "★★"  if abs(r_val) > 0.60 else
            "★"   if abs(r_val) > 0.40 else "✗")
    print(f"  {feat:<26}  r = {r_val:+.4f}  {flag}")
    if not math.isnan(r_val) and abs(r_val) > abs(best_r):
        best_r, best_feat = r_val, feat

# RMSE of inferred distance (only for valid rows)
if valid_rows:
    rmse = math.sqrt(
        sum((r["inferred_dist_m"] - r["oracle_distance_m"]) ** 2
            for r in valid_rows) / len(valid_rows)
    )
    bias = (sum(r["inferred_dist_m"] - r["oracle_distance_m"]
                for r in valid_rows) / len(valid_rows))
    print(f"\n  inferred_dist_m RMSE={rmse:.4f}m  bias={bias:+.4f}m  (n={len(valid_rows)})")

# Diagnosis: did peak_sample_idx track distance?
r_peak = pearson_r(dists, [r.get("peak_sample_idx", float("nan")) for r in rows])
no_data_count = sum(1 for r in rows
                    if math.isnan(r.get("peak_sample_idx", float("nan"))))

print(f"\n=== 診斷結論 ===")
print(f"  有效距離步數: {len(valid_rows)}/{len(rows)}  "
      f"(無資料: {no_data_count} 步)")

if no_data_count == len(rows):
    print("  ✗✗ 所有步驟都無資料 (numElements=0)")
    print("     → WPM 完全無法偵測 Cube prim！")
    print("     → 根本原因確認：WPM 對 UsdGeom.Cube 聲學透明")
elif abs(r_peak) > 0.80:
    print(f"  ★★★ peak_sample_idx 強相關 (r={r_peak:+.3f})")
    print(f"       → WPM 確實可偵測 Cube 目標距離！")
    print(f"       → 無手臂干擾的場景下，聲學測距可行！")
    print(f"       → 手臂實驗失敗的原因是：arm mesh 主導信號，confound 了距離信息")
elif abs(r_peak) > 0.50:
    print(f"  ★★  peak_sample_idx 中等相關 (r={r_peak:+.3f})")
    print(f"       → WPM 對 Cube 有部分響應，但噪音大")
    print(f"       → 調整 Cube 尺寸或感測器方向可能改善")
else:
    print(f"  ✗   peak_sample_idx 弱相關 (r={r_peak:+.3f})")
    print(f"       → WPM 對 Cube 幾乎無響應")
    if no_data_count < len(rows):
        print(f"       → 有信號但與距離無關：WPM 參數化模型主導")
    print(f"       → 無手臂方案與有手臂方案同樣無效")

simulation_app.close()
