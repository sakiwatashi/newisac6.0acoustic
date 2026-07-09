"""Arm-free WPM proximity test — windowed peak detection with background.

Key insight: background walls create strong late echoes (sample > target echo).
Using argmax within a LIMITED window (0 to N_CUT samples) avoids wall echoes
and recovers target tracking.

This script saves BOTH:
  - peak_sample_idx: full-window argmax (conventional)
  - win_peak_idx:    windowed argmax (samples 0..n_cut-1)

Demonstrates that windowed peak restores r>0.90 even with background walls.

Usage:
    app/python.sh scripts/armfree_windowed_peak_proximity_test.py \\
        --floor-y -0.50 --wall-x 2.00 --window-size 90 \\
        --output-dir runtime/outputs/armfree_windowed_peak_test/wall200_win090
"""
from __future__ import annotations

import argparse
import csv
import math
import pathlib

parser = argparse.ArgumentParser()
parser.add_argument("--min-dist",      type=float, default=0.20)
parser.add_argument("--max-dist",      type=float, default=1.50)
parser.add_argument("--n-steps",       type=int,   default=20)
parser.add_argument("--n-settle",      type=int,   default=15)
parser.add_argument("--n-measure",     type=int,   default=6)
parser.add_argument("--geom-radius",   type=float, default=0.05)
parser.add_argument("--center-freq",   type=float, default=40_000.0)
parser.add_argument("--mount-spacing", type=float, default=0.10)
parser.add_argument("--az-span",       type=float, default=90.0)
parser.add_argument("--el-span",       type=float, default=90.0)
# Background
parser.add_argument("--no-floor",      action="store_true")
parser.add_argument("--floor-y",       type=float, default=-0.50)
parser.add_argument("--no-wall",       action="store_true")
parser.add_argument("--wall-x",        type=float, default=2.00)
# Windowed peak
parser.add_argument("--window-size",   type=int,   default=90,
                    help="Max sample index for windowed peak (0..N-1). "
                         "Default=90 (~2.05m equiv, before wall at 2m arrives at sample~116)")
parser.add_argument("--output-dir",    type=str,
                    default="runtime/outputs/armfree_windowed_peak_test/default")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

import numpy as np
import omni.replicator.core as rep
import omni.timeline
import omni.usd
from isaacsim.sensors.experimental.rtx import (
    Acoustic, AcousticSensor, parse_generic_model_output_data,
)
from omni.replicator.core import Writer
from pxr import Gf, UsdGeom

T_US = 132.5e-6
V_SOUND = 343.0
N_EARLY = 20

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

    # Full-window peak (conventional)
    peak_idx = int(np.argmax(amps))
    # Windowed peak (early window, avoids far wall echoes)
    n_cut = min(args.window_size, len(amps))
    win_peak_idx = int(np.argmax(amps[:n_cut]))

    peak_amp = float(amps[peak_idx])
    total_e  = float(np.sum(amps ** 2))
    early_e  = float(np.sum(amps[:N_EARLY] ** 2))
    early_frac = early_e / total_e if total_e > 0.0 else 0.0

    return {
        "peak_sample_idx":    float(peak_idx),
        "win_peak_idx":       float(win_peak_idx),
        "inferred_dist_m":    peak_idx * T_US * V_SOUND / 2.0,
        "win_inferred_dist_m": win_peak_idx * T_US * V_SOUND / 2.0,
        "peak_amplitude":     peak_amp,
        "total_energy":       total_e,
        "early_energy":       early_e,
        "early_fraction":     early_frac,
        "n_signal_ways":      float(n_ways),
        "n_samples_per_sgw":  float(num_spsgw),
        "n_elements":         float(n),
    }


class WinPeakWriter(Writer):
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


# ── Scene ─────────────────────────────────────────────────────────────────────
add_floor = not args.no_floor
add_wall  = not args.no_wall

# Predict wall echo sample (for annotation)
wall_echo_sample = float("nan")
if add_wall:
    path_wall = args.wall_x + (args.wall_x - args.mount_spacing)
    wall_echo_sample = path_wall / (T_US * V_SOUND)

print("=== WPM Windowed Peak Background Test ===")
print(f"Floor  : {'YES y=' + str(args.floor_y) + 'm' if add_floor else 'NO'}")
print(f"Wall   : {'YES x=' + str(args.wall_x) + 'm  (echo≈sample ' + f'{wall_echo_sample:.0f})' if add_wall else 'NO'}")
print(f"Window : samples 0..{args.window_size-1}  "
      f"(equiv ≤{args.window_size * T_US * V_SOUND / 2:.2f}m)")
print(f"Sweep  : {args.min_dist:.2f}–{args.max_dist:.2f}m  ({args.n_steps} steps)")
print()

omni.usd.get_context().new_stage()
_stage = omni.usd.get_context().get_stage()

# Target sphere
_tp = UsdGeom.Sphere.Define(_stage, "/World/target")
_tp.GetRadiusAttr().Set(args.geom_radius)
UsdGeom.Xformable(_tp).AddTranslateOp().Set(Gf.Vec3d(args.min_dist, 0.0, 0.0))

# Floor
if add_floor:
    _ft = 0.04
    _fc = (args.min_dist + args.max_dist) / 2.0
    _fp = UsdGeom.Cube.Define(_stage, "/World/floor")
    _fp.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(_fp)
    xf.AddTranslateOp().Set(Gf.Vec3d(_fc, args.floor_y - _ft/2.0, 0.0))
    xf.AddScaleOp().Set(Gf.Vec3d(4.0, _ft, 3.0))

# Back wall
if add_wall:
    _wt = 0.04
    _wp = UsdGeom.Cube.Define(_stage, "/World/wall_back")
    _wp.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(_wp)
    xf.AddTranslateOp().Set(Gf.Vec3d(args.wall_x + _wt/2.0, 0.0, 0.0))
    xf.AddScaleOp().Set(Gf.Vec3d(_wt, 2.0, 2.0))

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
rep.WriterRegistry.register(WinPeakWriter)
sensor.attach_writer("WinPeakWriter")

_target_usd = _stage.GetPrimAtPath("/World/target")
_xform = UsdGeom.Xformable(_target_usd)


def _move_target(x):
    ops = {op.GetOpName(): op for op in _xform.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(x, 0.0, 0.0))
    else:
        _xform.AddTranslateOp().Set(Gf.Vec3d(x, 0.0, 0.0))


timeline = omni.timeline.get_timeline_interface()
timeline.play()

print("Warming up (25 frames)…")
for _ in range(25):
    simulation_app.update()

distances = np.linspace(args.min_dist, args.max_dist, args.n_steps)
rows: list[dict] = []

HDR = (f"{'dist_m':>8}  {'full_peak':>9}  {'win_peak':>9}  "
       f"{'full_inf':>9}  {'win_inf':>9}")
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
                     "peak_sample_idx": float("nan"), "win_peak_idx": float("nan"),
                     "inferred_dist_m": float("nan"), "win_inferred_dist_m": float("nan"),
                     "peak_amplitude": float("nan"), "total_energy": float("nan"),
                     "early_energy": float("nan"), "early_fraction": float("nan"),
                     "n_signal_ways": float("nan"), "n_samples_per_sgw": float("nan"),
                     "n_elements": 0.0})
        continue

    avg = {k: float(sum(s[k] for s in samples)) / len(samples) for k in samples[0]}
    avg["oracle_distance_m"] = dist_f
    rows.append(avg)
    print(
        f"{dist_f:>8.3f}  "
        f"{avg['peak_sample_idx']:>9.1f}  "
        f"{avg['win_peak_idx']:>9.1f}  "
        f"{avg['inferred_dist_m']:>9.3f}  "
        f"{avg['win_inferred_dist_m']:>9.3f}"
    )

timeline.stop()

out_dir = pathlib.Path(args.output_dir)
out_dir.mkdir(parents=True, exist_ok=True)
csv_path = out_dir / "armfree_winpeak_sweep.csv"

fieldnames = ["oracle_distance_m", "peak_sample_idx", "win_peak_idx",
              "inferred_dist_m", "win_inferred_dist_m",
              "peak_amplitude", "total_energy", "early_energy", "early_fraction",
              "n_signal_ways", "n_samples_per_sgw", "n_elements"]
with csv_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
print(f"\n→ {len(rows)} rows saved to {csv_path}")


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


valid = [r for r in rows if not math.isnan(r.get("peak_sample_idx", float("nan")))]
dists = [r["oracle_distance_m"] for r in rows]

r_full = pearson_r(dists, [r.get("peak_sample_idx", float("nan"))     for r in rows])
r_win  = pearson_r(dists, [r.get("win_peak_idx",   float("nan"))     for r in rows])

def _rmse_bias(rows_valid, key_inf):
    vals = [r for r in rows_valid if not math.isnan(r.get(key_inf, float("nan")))]
    if not vals: return float("nan"), float("nan")
    rmse = math.sqrt(sum((r[key_inf] - r["oracle_distance_m"])**2 for r in vals) / len(vals))
    bias = sum(r[key_inf] - r["oracle_distance_m"] for r in vals) / len(vals)
    return rmse, bias

rmse_f, bias_f = _rmse_bias(valid, "inferred_dist_m")
rmse_w, bias_w = _rmse_bias(valid, "win_inferred_dist_m")

print(f"\n=== 結果 ===")
print(f"場景：floor={'on' if add_floor else 'off'}  wall={'on (x=' + str(args.wall_x) + 'm)' if add_wall else 'off'}")
if not math.isnan(wall_echo_sample):
    print(f"牆壁回聲預測位置：sample {wall_echo_sample:.0f}")
print(f"早期窗口截止：sample {args.window_size}  (≤{args.window_size*T_US*V_SOUND/2:.2f}m)")
print()
print(f"{'方法':>20}  {'r(peak,dist)':>13}  {'RMSE':>8}  {'bias':>8}  {'判定'}")
print("-" * 65)
flag_f = "✅" if abs(r_full) > 0.90 else ("⚠️" if abs(r_full) > 0.60 else "❌")
flag_w = "✅" if abs(r_win)  > 0.90 else ("⚠️" if abs(r_win)  > 0.60 else "❌")
print(f"{'全窗口 argmax':>20}  {r_full:>+13.4f}  {rmse_f:>8.4f}  {bias_f:>+8.4f}  {flag_f}")
print(f"{'早期窗口 argmax':>20}  {r_win:>+13.4f}  {rmse_w:>8.4f}  {bias_w:>+8.4f}  {flag_w}")
print()
print("arm-free 基準（無背景，全窗口）: r=+0.9992")
if abs(r_win) > 0.90 and abs(r_full) < 0.90:
    print("★ 早期窗口成功恢復目標追蹤！背景牆壁干擾可透過時間窗口消除。")
elif abs(r_win) > 0.90:
    print("★ 兩種方法都成功（背景干擾有限）。")
else:
    print("△ 早期窗口仍不足，需要差分方法。")

simulation_app.close()
