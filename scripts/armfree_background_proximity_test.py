"""Arm-free WPM acoustic proximity test — with background geometry.

Scene: fixed acoustic sensor + sphere target + optional floor/wall background.
Sweeps the sphere from min_dist to max_dist along +X axis.
Tests whether WPM can still detect target distance in a realistic scene
(i.e. with ground plane and back wall echoes competing with target echo).

Conditions (controlled by flags):
  --no-floor / --floor-y  : floor at y=-0.50m (default adds floor)
  --no-wall  / --wall-x   : back wall at x=2.00m (default adds wall)

Usage:
    # Baseline: no background
    app/python.sh scripts/armfree_background_proximity_test.py \\
        --no-floor --no-wall --output-dir runtime/outputs/armfree_bg_test/no_bg

    # Floor only
    app/python.sh scripts/armfree_background_proximity_test.py \\
        --no-wall --output-dir runtime/outputs/armfree_bg_test/floor_only

    # Floor + back wall (realistic)
    app/python.sh scripts/armfree_background_proximity_test.py \\
        --output-dir runtime/outputs/armfree_bg_test/floor_wall
"""
from __future__ import annotations

import argparse
import csv
import math
import pathlib

# ── Argument parsing BEFORE SimulationApp ─────────────────────────────────────
parser = argparse.ArgumentParser(description="Arm-free WPM proximity test with background.")
parser.add_argument("--min-dist",      type=float, default=0.20)
parser.add_argument("--max-dist",      type=float, default=1.50)
parser.add_argument("--n-steps",       type=int,   default=20)
parser.add_argument("--n-settle",      type=int,   default=15)
parser.add_argument("--n-measure",     type=int,   default=6)
parser.add_argument("--geom-radius",   type=float, default=0.05,
                    help="Sphere radius (m), default 0.05m (human-hand size)")
parser.add_argument("--center-freq",   type=float, default=40_000.0)
parser.add_argument("--mount-spacing", type=float, default=0.10)
parser.add_argument("--az-span",       type=float, default=90.0)
parser.add_argument("--el-span",       type=float, default=90.0)
# Background geometry
parser.add_argument("--no-floor",      action="store_true",
                    help="Do NOT add a floor plane (default: floor is present)")
parser.add_argument("--floor-y",       type=float, default=-0.50,
                    help="Y position of floor top surface (m), default=-0.50")
parser.add_argument("--floor-size-x",  type=float, default=4.0,
                    help="Floor extent along X (m), default=4.0")
parser.add_argument("--floor-size-z",  type=float, default=3.0,
                    help="Floor extent along Z (m), default=3.0")
parser.add_argument("--no-wall",       action="store_true",
                    help="Do NOT add a back wall (default: wall is present)")
parser.add_argument("--wall-x",        type=float, default=2.00,
                    help="X position of back wall front face (m), default=2.00")
parser.add_argument("--wall-size-y",   type=float, default=2.0,
                    help="Wall extent along Y (m), default=2.0")
parser.add_argument("--wall-size-z",   type=float, default=2.0,
                    help="Wall extent along Z (m), default=2.0")
parser.add_argument("--output-dir",    type=str,
                    default="runtime/outputs/armfree_bg_test/default")
args, _ = parser.parse_known_args()

# ── SimulationApp must come before all Isaac Sim imports ──────────────────────
from isaacsim import SimulationApp  # noqa: E402
simulation_app = SimulationApp({"headless": True})

import numpy as np                                   # noqa: E402
import omni.replicator.core as rep                  # noqa: E402
import omni.timeline                                # noqa: E402
import omni.usd                                     # noqa: E402
from isaacsim.sensors.experimental.rtx import (     # noqa: E402
    Acoustic, AcousticSensor, parse_generic_model_output_data,
)
from omni.replicator.core import Writer             # noqa: E402
from pxr import Gf, UsdGeom                        # noqa: E402

# ── Physical constants ────────────────────────────────────────────────────────
T_US = 132.5e-6
V_SOUND = 343.0
N_EARLY = 20
N_ULTRA = 8

# ── Module-level data buffer ──────────────────────────────────────────────────
_buf: dict = {"latest": None}


def _extract_features(gmo) -> dict | None:
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None

    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float)

    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    n_ways = 0
    if num_spsgw > 0 and n % num_spsgw == 0:
        n_ways = n // num_spsgw
        best_start, best_peak = 0, -math.inf
        for w in range(n_ways):
            s = w * num_spsgw
            pk = float(np.max(amp_all[s: s + num_spsgw]))
            if pk > best_peak:
                best_peak, best_start = pk, s
        amps = amp_all[best_start: best_start + num_spsgw]
    else:
        amps = amp_all

    if len(amps) == 0:
        return None

    peak_idx  = int(np.argmax(amps))
    peak_amp  = float(amps[peak_idx])
    total_e   = float(np.sum(amps ** 2))
    early_e   = float(np.sum(amps[:N_EARLY] ** 2))
    ultra_e   = float(np.sum(amps[:N_ULTRA] ** 2))
    early_frac = early_e / total_e if total_e > 0.0 else 0.0

    return {
        "peak_sample_idx":    float(peak_idx),
        "peak_amplitude":     peak_amp,
        "total_energy":       total_e,
        "early_energy":       early_e,
        "ultra_early_energy": ultra_e,
        "early_fraction":     early_frac,
        "inferred_dist_m":    peak_idx * T_US * V_SOUND / 2.0,
        "n_signal_ways":      float(n_ways),
        "n_samples_per_sgw":  float(num_spsgw),
        "n_elements":         float(n),
    }


class BgProximityWriter(Writer):
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
                return


# ── Scene setup ───────────────────────────────────────────────────────────────
add_floor = not args.no_floor
add_wall  = not args.no_wall

print("=== Arm-Free WPM Background Robustness Test ===")
print(f"Target  : Sphere r={args.geom_radius:.3f}m along +X axis")
print(f"Floor   : {'YES (y=' + str(args.floor_y) + 'm)' if add_floor else 'NO'}")
print(f"Wall    : {'YES (x=' + str(args.wall_x) + 'm)' if add_wall else 'NO'}")
print(f"Sensor  : center_freq={args.center_freq:.0f} Hz  "
      f"mount_spacing={args.mount_spacing}m  "
      f"az={args.az_span}°  el={args.el_span}°")
print(f"Sweep   : {args.min_dist:.2f} m → {args.max_dist:.2f} m  ({args.n_steps} steps)")
print()

# Fresh USD stage
omni.usd.get_context().new_stage()
_stage = omni.usd.get_context().get_stage()

# Target: sphere
_target_prim_def = UsdGeom.Sphere.Define(_stage, "/World/target")
_target_prim_def.GetRadiusAttr().Set(args.geom_radius)
UsdGeom.Xformable(_target_prim_def).AddTranslateOp().Set(
    Gf.Vec3d(args.min_dist, 0.0, 0.0))

# Background: floor (a wide, thin Cube)
if add_floor:
    _floor_thickness = 0.04
    _floor_cx = (args.min_dist + args.max_dist) / 2.0
    _floor_cy = args.floor_y - _floor_thickness / 2.0  # top face at floor_y
    _floor_prim = UsdGeom.Cube.Define(_stage, "/World/floor")
    _floor_prim.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(_floor_prim)
    xf.AddTranslateOp().Set(Gf.Vec3d(_floor_cx, _floor_cy, 0.0))
    xf.AddScaleOp().Set(Gf.Vec3d(args.floor_size_x, _floor_thickness, args.floor_size_z))
    print(f"Floor   : center=({_floor_cx:.2f}, {_floor_cy:.3f}, 0)  "
          f"scale=({args.floor_size_x}×{_floor_thickness}×{args.floor_size_z})m")

# Background: back wall (thin Cube perpendicular to +X)
if add_wall:
    _wall_thickness = 0.04
    _wall_cx = args.wall_x + _wall_thickness / 2.0  # front face at wall_x
    _wall_prim = UsdGeom.Cube.Define(_stage, "/World/wall_back")
    _wall_prim.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(_wall_prim)
    xf.AddTranslateOp().Set(Gf.Vec3d(_wall_cx, 0.0, 0.0))
    xf.AddScaleOp().Set(Gf.Vec3d(_wall_thickness, args.wall_size_y, args.wall_size_z))
    print(f"Wall    : center=({_wall_cx:.3f}, 0.0, 0.0)  "
          f"scale=({_wall_thickness}×{args.wall_size_y}×{args.wall_size_z})m")

print()

# Acoustic sensor — fixed at origin
acoustic = Acoustic(
    "/World/acoustic",
    tick_rate=30.0,
    aux_output_level="BASIC",
    translations=np.array([[0.0, 0.0, 0.0]]),
    attributes={
        "omni:sensor:WpmAcoustic:centerFrequency": args.center_freq,
        "omni:sensor:WpmAcoustic:azSpanDeg":       args.az_span,
        "omni:sensor:WpmAcoustic:elSpanDeg":       args.el_span,
        "omni:sensor:WpmAcoustic:sensorMount:m001:position": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m001:rotation": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:position": (float(args.mount_spacing), 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:rotation": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices": [0, 1],
    },
)

sensor = AcousticSensor(acoustic, annotators=[])
rep.WriterRegistry.register(BgProximityWriter)
sensor.attach_writer("BgProximityWriter")

# USD helper: move target along +X
_target_usd = _stage.GetPrimAtPath("/World/target")
_xformable  = UsdGeom.Xformable(_target_usd)


def _move_target(x: float) -> None:
    ops = {op.GetOpName(): op for op in _xformable.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(x, 0.0, 0.0))
    else:
        _xformable.AddTranslateOp().Set(Gf.Vec3d(x, 0.0, 0.0))


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
       f"{'early_e':>10}  {'frac':>7}  {'amp':>8}")
print(HDR)
print("-" * len(HDR))

for dist in distances:
    dist_f = float(dist)
    _move_target(dist_f)

    for _ in range(args.n_settle):
        simulation_app.update()

    samples: list[dict] = []
    for _ in range(args.n_measure):
        simulation_app.update()
        if _buf["latest"] is not None:
            samples.append(_buf["latest"].copy())

    if not samples:
        print(f"{dist_f:>8.3f}   NO DATA")
        rows.append({"oracle_distance_m": dist_f,
                     "peak_sample_idx":    float("nan"),
                     "inferred_dist_m":    float("nan"),
                     "peak_amplitude":     float("nan"),
                     "total_energy":       float("nan"),
                     "early_energy":       float("nan"),
                     "ultra_early_energy": float("nan"),
                     "early_fraction":     float("nan"),
                     "n_signal_ways":      float("nan"),
                     "n_samples_per_sgw":  float("nan"),
                     "n_elements":         0.0})
        continue

    avg = {k: float(sum(s[k] for s in samples)) / len(samples) for k in samples[0]}
    avg["oracle_distance_m"] = dist_f
    rows.append(avg)

    print(
        f"{dist_f:>8.3f}  "
        f"{avg['peak_sample_idx']:>9.1f}  "
        f"{avg['inferred_dist_m']:>10.3f}  "
        f"{avg['early_energy']:>10.2f}  "
        f"{avg['early_fraction']:>7.4f}  "
        f"{avg['peak_amplitude']:>8.4f}"
    )

timeline.stop()

# ── Save CSV ──────────────────────────────────────────────────────────────────
out_dir = pathlib.Path(args.output_dir)
out_dir.mkdir(parents=True, exist_ok=True)
csv_path = out_dir / "armfree_bg_proximity_sweep.csv"

fieldnames = ["oracle_distance_m", "peak_sample_idx", "inferred_dist_m",
              "peak_amplitude", "total_energy", "early_energy",
              "ultra_early_energy", "early_fraction",
              "n_signal_ways", "n_samples_per_sgw", "n_elements"]
with csv_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
print(f"\n→ {len(rows)} rows saved to {csv_path}")

# ── Pearson r analysis ────────────────────────────────────────────────────────
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
    return num / den if den > 0.0 else float("nan")


valid_rows = [r for r in rows if not math.isnan(r.get("peak_sample_idx", float("nan")))]
dists = [r["oracle_distance_m"] for r in rows]

r_peak = pearson_r(dists, [r.get("peak_sample_idx", float("nan")) for r in rows])
rmse = (math.sqrt(sum((r["inferred_dist_m"] - r["oracle_distance_m"]) ** 2
                      for r in valid_rows) / len(valid_rows))
        if valid_rows else float("nan"))
bias = (sum(r["inferred_dist_m"] - r["oracle_distance_m"] for r in valid_rows)
        / len(valid_rows) if valid_rows else float("nan"))

print(f"\n=== 結果 ===")
print(f"  場景：sphere r={args.geom_radius:.3f}m  "
      f"floor={'on' if add_floor else 'off'}  wall={'on' if add_wall else 'off'}")
print(f"  r(peak,dist) = {r_peak:+.4f}")
print(f"  RMSE         = {rmse:.4f}m   bias={bias:+.4f}m   n={len(valid_rows)}")
flag = ("✅ 可偵測" if abs(r_peak) > 0.90 else
        ("⚠️ 部分" if abs(r_peak) > 0.60 else "❌ 被掩蓋"))
print(f"  判定         : {flag}")
print(f"  arm-free 基準: r=+0.9992  (sphere r=0.05m, 無背景)")

simulation_app.close()
