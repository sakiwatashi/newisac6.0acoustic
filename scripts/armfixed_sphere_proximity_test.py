"""Arm-Fixed WPM sphere proximity test.

Scene:
  - UR10 arm at a fixed joint configuration (static throughout)
  - Acoustic sensor fixed at world origin (same as arm-free baseline)
  - Sphere / Cube obstacle sweeps along +X axis

Goal: does the arm mesh confound the sphere echo?
  r > 0.90 → arm background does not dominate; raw features work
  r < 0.50 → arm mesh occludes/confounds sphere echo → need differential approach

Compare results to arm-free baseline (sphere r=0.05m: r=+0.9992).

Usage:
    /home/lab109/song/isaacsim6.0/app/python.sh \\
        scripts/armfixed_sphere_proximity_test.py \\
        --arm-pose home --geometry sphere --geom-radius 0.05
"""
from __future__ import annotations

import argparse
import csv
import math
import pathlib

# ── Argparse BEFORE SimulationApp ────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Fixed-arm WPM sphere proximity test.")
parser.add_argument("--min-dist",      type=float, default=0.20)
parser.add_argument("--max-dist",      type=float, default=1.50)
parser.add_argument("--n-steps",       type=int,   default=20)
parser.add_argument("--n-settle",      type=int,   default=15,
                    help="Settle frames per distance step (arm-free uses 12)")
parser.add_argument("--n-measure",     type=int,   default=6)
parser.add_argument("--geometry",      type=str,   default="sphere",
                    choices=["sphere", "cube"])
parser.add_argument("--geom-radius",   type=float, default=0.05,
                    help="Sphere radius (m)")
parser.add_argument("--cube-size",     type=float, default=0.10,
                    help="Cube edge length (m), used only when --geometry cube")
parser.add_argument("--arm-pose",      type=str,   default="home",
                    choices=["home", "reach_forward", "reach_left", "reach_right", "up"],
                    help="Fixed joint configuration for the UR10 arm")
parser.add_argument("--center-freq",   type=float, default=40_000.0)
parser.add_argument("--mount-spacing", type=float, default=0.10)
parser.add_argument("--az-span",       type=float, default=90.0)
parser.add_argument("--el-span",       type=float, default=90.0)
parser.add_argument("--output-dir",    type=str,
                    default="runtime/outputs/armfixed_sphere_test_v1")
args, _ = parser.parse_known_args()

# ── SimulationApp (must come before all Isaac Sim imports) ────────────────────
from isaacsim import SimulationApp  # noqa: E402
simulation_app = SimulationApp({"headless": True})

import numpy as np                                           # noqa: E402
import omni.replicator.core as rep                          # noqa: E402
import omni.timeline                                        # noqa: E402
import omni.usd                                             # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
from isaacsim.core.api import World                         # noqa: E402
from isaacsim.core.api.robots import Robot                  # noqa: E402
from isaacsim.sensors.experimental.rtx import (            # noqa: E402
    Acoustic, AcousticSensor, parse_generic_model_output_data,
)
from isaacsim.storage.native import get_assets_root_path   # noqa: E402
from omni.replicator.core import Writer                     # noqa: E402
from pxr import Gf, UsdGeom                               # noqa: E402

# ── Physical constants ────────────────────────────────────────────────────────
T_US    = 132.5e-6   # s / sample
V_SOUND = 343.0      # m/s
N_EARLY = 20
N_ULTRA = 8

# ── Joint configurations (radians) ──────────────────────────────────────────
# home: arm pointing upward, end-effector ~above the base → +X axis is clear
# reach_forward: arm extended toward +X (might partially overlap measurement axis)
ARM_POSES: dict[str, tuple[float, ...]] = {
    "home":          (0.0, -1.5708,  1.5708, -1.5708, -1.5708, 0.0),
    "reach_forward": (0.0, -1.20,    1.20,   -1.57,   -1.57,   0.0),
    "reach_left":    (0.45, -1.25,   1.35,   -1.67,   -1.57,   0.0),
    "reach_right":   (-0.45, -1.25,  1.35,   -1.67,   -1.57,   0.0),
    "up":            (0.0, -1.5708,  0.0,    -1.5708,  0.0,    0.0),
}

# ── Module-level data buffer ──────────────────────────────────────────────────
_buf: dict = {"latest": None}


def _extract_features(gmo) -> dict | None:
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None

    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float)
    tof_all = np.ctypeslib.as_array(gmo.timeOffsetNs, shape=(n,)).astype(float)
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    n_ways = 0
    if num_spsgw > 0 and n % num_spsgw == 0:
        n_ways = n // num_spsgw
        best_start, best_peak = 0, -math.inf
        for w in range(n_ways):
            s = w * num_spsgw
            pk = float(np.max(amp_all[s : s + num_spsgw]))
            if pk > best_peak:
                best_peak, best_start = pk, s
        amps = amp_all[best_start : best_start + num_spsgw]
        tof_first = float(tof_all[best_start])
    else:
        amps = amp_all
        tof_first = float(tof_all[0]) if n > 0 else 0.0

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
        "tof_first_ns":       tof_first,
        "n_samples_per_sgw":  float(num_spsgw),
        "n_elements":         float(n),
    }


class ArmfixedWriter(Writer):
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
target_desc = (f"Sphere r={args.geom_radius:.3f}m" if args.geometry == "sphere"
               else f"Cube {args.cube_size}m")
print("=== Arm-Fixed WPM Proximity Test ===")
print(f"Arm pose: {args.arm_pose}")
print(f"Target  : {target_desc} along +X axis")
print(f"Sensor  : world origin  center_freq={args.center_freq:.0f} Hz  "
      f"mount_spacing={args.mount_spacing}m")
print(f"Sweep   : {args.min_dist:.2f} m → {args.max_dist:.2f} m  ({args.n_steps} steps)")
print(f"Settle  : {args.n_settle} frames / position")
print()

context = omni.usd.get_context()
context.new_stage()
stage = context.get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# Load UR10 from official assets
assets_root = get_assets_root_path()
ur10_usd = f"{assets_root}/Isaac/Robots/UniversalRobots/ur10/ur10.usd"
print(f"Loading UR10 from: {ur10_usd}")
stage_utils.add_reference_to_stage(usd_path=ur10_usd, path="/World/ur10")
for _ in range(15):
    simulation_app.update()
print("UR10 loaded.")

# Target geometry — placed along +X axis, will be swept during experiment
if args.geometry == "sphere":
    _pd = UsdGeom.Sphere.Define(stage, "/World/target")
    _pd.GetRadiusAttr().Set(args.geom_radius)
else:
    _pd = UsdGeom.Cube.Define(stage, "/World/target")
    _pd.GetSizeAttr().Set(args.cube_size)
UsdGeom.Xformable(_pd).AddTranslateOp().Set(Gf.Vec3d(args.min_dist, 0.0, 0.0))

# Acoustic sensor — FIXED at world origin (same layout as arm-free experiments)
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

rep.WriterRegistry.register(ArmfixedWriter)
sensor.attach_writer("ArmfixedWriter")

# World + Robot (physics for joint position control)
world = World()
robot = world.scene.add(Robot(prim_path="/World/ur10", name="ur10"))
world.reset()

_locked_q = np.array(ARM_POSES[args.arm_pose], dtype=float)
robot.set_joint_positions(_locked_q)
print(f"Locking arm to '{args.arm_pose}'...")
for _ in range(40):
    world.step(render=False)
    simulation_app.update()
print("Arm locked.")

# USD helper: move target
_target_prim = stage.GetPrimAtPath("/World/target")
_xformable   = UsdGeom.Xformable(_target_prim)


def _move_target(x: float, y: float = 0.0, z: float = 0.0) -> None:
    ops = {op.GetOpName(): op for op in _xformable.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(x, y, z))
    else:
        _xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))


# ── Simulation ────────────────────────────────────────────────────────────────
timeline = omni.timeline.get_timeline_interface()
timeline.play()

print("\nWarming up (30 frames)...")
for _ in range(30):
    robot.set_joint_positions(_locked_q)
    world.step(render=False)
    simulation_app.update()

# ── Distance sweep ────────────────────────────────────────────────────────────
distances = np.linspace(args.min_dist, args.max_dist, args.n_steps)
rows: list[dict] = []

HDR = (f"{'dist_m':>8}  {'peak_idx':>9}  {'inferred_m':>10}  "
       f"{'early_e':>10}  {'ultra_e':>10}  {'frac':>7}  {'amp':>8}  {'spsgw':>6}")
print(HDR)
print("-" * len(HDR))

for dist in distances:
    dist_f = float(dist)
    _move_target(dist_f)
    robot.set_joint_positions(_locked_q)   # keep arm pinned every step

    for _ in range(args.n_settle):
        world.step(render=False)
        simulation_app.update()

    samples: list[dict] = []
    for _ in range(args.n_measure):
        world.step(render=False)
        simulation_app.update()
        if _buf["latest"] is not None:
            samples.append(_buf["latest"].copy())

    if not samples:
        print(f"{dist_f:>8.3f}   NO DATA (numElements=0 every frame)")
        rows.append({"oracle_distance_m": dist_f,
                     "peak_sample_idx": float("nan"),
                     "peak_amplitude":  float("nan"),
                     "total_energy":    float("nan"),
                     "early_energy":    float("nan"),
                     "ultra_early_energy": float("nan"),
                     "early_fraction":  float("nan"),
                     "inferred_dist_m": float("nan"),
                     "tof_first_ns":    float("nan"),
                     "n_samples_per_sgw": float("nan"),
                     "n_elements": 0.0})
        continue

    avg = {k: float(sum(s[k] for s in samples)) / len(samples) for k in samples[0]}
    avg["oracle_distance_m"] = dist_f
    rows.append(avg)

    print(f"{dist_f:>8.3f}  "
          f"{avg['peak_sample_idx']:>9.1f}  "
          f"{avg['inferred_dist_m']:>10.3f}  "
          f"{avg['early_energy']:>10.2f}  "
          f"{avg['ultra_early_energy']:>10.2f}  "
          f"{avg['early_fraction']:>7.4f}  "
          f"{avg['peak_amplitude']:>8.4f}  "
          f"{avg['n_samples_per_sgw']:>6.0f}")

timeline.stop()

# ── Save CSV ──────────────────────────────────────────────────────────────────
out_dir  = pathlib.Path(args.output_dir)
out_dir.mkdir(parents=True, exist_ok=True)
csv_path = out_dir / "armfixed_proximity_sweep.csv"
fieldnames = ["oracle_distance_m", "peak_sample_idx", "inferred_dist_m",
              "early_energy", "ultra_early_energy", "early_fraction",
              "peak_amplitude", "total_energy", "tof_first_ns",
              "n_samples_per_sgw", "n_elements"]
with csv_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
print(f"\n→ {len(rows)} rows saved to {csv_path}")


# ── Pearson analysis (same as arm-free) ──────────────────────────────────────
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
for feat in ["peak_sample_idx", "inferred_dist_m",
             "early_energy", "ultra_early_energy",
             "early_fraction", "peak_amplitude", "total_energy"]:
    vals  = [r.get(feat, float("nan")) for r in rows]
    r_val = pearson_r(dists, vals)
    flag  = ("★★★" if abs(r_val) > 0.80 else
             "★★"  if abs(r_val) > 0.60 else
             "★"   if abs(r_val) > 0.40 else "✗")
    print(f"  {feat:<26}  r = {r_val:+.4f}  {flag}")

if valid_rows:
    rmse = math.sqrt(
        sum((r["inferred_dist_m"] - r["oracle_distance_m"]) ** 2
            for r in valid_rows) / len(valid_rows))
    bias = (sum(r["inferred_dist_m"] - r["oracle_distance_m"]
                for r in valid_rows) / len(valid_rows))
    print(f"\n  inferred_dist_m RMSE={rmse:.4f}m  bias={bias:+.4f}m  (n={len(valid_rows)})")

r_peak      = pearson_r(dists, [r.get("peak_sample_idx", float("nan")) for r in rows])
no_data_cnt = sum(1 for r in rows if math.isnan(r.get("peak_sample_idx", float("nan"))))

print(f"\n=== 診斷結論 (arm pose={args.arm_pose}) ===")
print(f"  有效步數: {len(valid_rows)}/{len(rows)}")

if abs(r_peak) > 0.90:
    print(f"  ★★★ peak r={r_peak:+.3f} — arm-fixed 場景下 {target_desc} 仍可偵測！")
    print(f"       → arm mesh 不干擾 sphere echo，raw features 可直接用於論文")
elif abs(r_peak) > 0.60:
    print(f"  ★★  peak r={r_peak:+.3f} — 部分可偵測，arm mesh 有干擾但未完全掩蓋")
    print(f"       → 可考慮差分特徵（diff vs baseline）進一步提升")
else:
    print(f"  ✗   peak r={r_peak:+.3f} — arm mesh 主導信號，{target_desc} echo 被掩蓋")
    print(f"       → 需要差分方法：目標 echo = (arm+target) - (arm only baseline)")

simulation_app.close()
