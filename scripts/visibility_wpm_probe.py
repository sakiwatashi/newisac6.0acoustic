"""Visibility vs WPM (RTX Acoustic) ray-tracing probe.

Purpose
-------
Verify whether `set_prim_visibility(stage, path, visible=False)` actually
removes a prim from the RTX Acoustic (WPM) ray tracer's view. Several
existing baseline experiments (e.g. official_asset_ur10_dynamic_approach_
calibration_sweep.py) hide a wall / wrench prim via `set_prim_visibility`
and assume the acoustic sensor then "does not see" it. This script checks
that assumption directly, in isolation, against two other known-effective
removal methods (USD xform translate far away, and `stage.RemovePrim`).

Scene (arm-free, rule 3-1 of docs/WPM_EXPERIMENT_RULES.md):
  Acoustic sensor fixed at origin (TX at (0,0,0), RX at (mount_spacing,0,0)).
  Single UsdGeom Cube target centered at (cube_x, 0, 0).
  No robot arm, no room walls, no other mesh.

Conditions (in order):
  A  — cube visible (baseline).
  B  — set_prim_visibility(stage, cube_path, visible=False).
  A2 — visibility restored to True; re-measured as an in-session noise
       reference (quantifies how much the waveform naturally jitters
       between two "visible" measurements, absent any real change).
  C  — cube translated far away (50 m) via direct USD xformOp:translate
       (rule 3-4), then moved back to its original position afterwards.
  D  — cube physically removed via stage.RemovePrim(cube_path).

For each condition we capture the primary signal-way waveform (rule 1-2:
reconstructed via numSamplesPerSgw stride) averaged over N_MEASURE frames,
after N_SETTLE settle frames. We report each condition's peak_sample_idx,
early_energy (first 20 samples squared sum), and the max|Δ| / RMS(Δ)
against condition A's waveform.

Verdict: a removal method is judged "effective" only if its max|Δ vs A| is
more than 10× larger than A2's max|Δ vs A| (A2 is a same-scene, same-
visibility replicate — i.e. the session's own noise floor). This guards
against mistaking ordinary frame-to-frame jitter for a real ray-tracing
effect.

Usage:
    /home/lab109/song/isaacsim6.0/app/python.sh \\
        scripts/visibility_wpm_probe.py \\
        --output-dir runtime/outputs/visibility_wpm_probe_v1 --cube-x 0.5
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ── Argument parsing BEFORE SimulationApp (rule 4-1) ──────────────────────────
parser = argparse.ArgumentParser(description="Visibility vs WPM ray-tracing probe.")
parser.add_argument("--output-dir", type=str,
                     default="runtime/outputs/visibility_wpm_probe_v1",
                     help="Directory to write probe_summary.json into")
parser.add_argument("--cube-x", type=float, default=0.5,
                     help="Cube target center x-distance in metres")
parser.add_argument("--cube-size", type=float, default=0.20,
                     help="Cube edge length in metres")
parser.add_argument("--far-x", type=float, default=50.0,
                     help="Translate-away distance in metres for condition C")
parser.add_argument("--n-settle", type=int, default=10,
                     help="Settle frames between conditions")
parser.add_argument("--n-measure", type=int, default=6,
                     help="Frames averaged per condition")
parser.add_argument("--center-freq", type=float, default=40_000.0,
                     help="WPM center frequency in Hz")
parser.add_argument("--mount-spacing", type=float, default=0.10,
                     help="TX-to-RX mount spacing in metres")
parser.add_argument("--az-span", type=float, default=90.0,
                     help="Azimuth beam span in degrees")
parser.add_argument("--el-span", type=float, default=90.0,
                     help="Elevation beam span in degrees")
args, _ = parser.parse_known_args()

# ── SimulationApp must come before all other Isaac Sim imports ───────────────
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

from geometry_passport_v1 import set_prim_visibility  # noqa: E402

# ── Physical constants (same as armfree_acoustic_proximity_test.py) ──────────
T_US = 132.5e-6   # seconds per WPM sample index (rule 1-4)
V_SOUND = 343.0   # m/s speed of sound
N_EARLY = 20      # sample boundary for "early" window

# ── Module-level data buffer (Writer → main loop communication, rule 4-2) ────
_buf: dict = {"latest": None}


def _extract_features(gmo) -> dict | None:
    """Extract primary-way waveform + scalar features from a parsed GMO struct.

    Follows rule 1-2 / rule 4-3 exactly: numSamplesPerSgw gives the stride
    used to slice the flat GMO buffer into temporally-ordered signal ways;
    timeOffsetNs is NOT used (rule 1-3, always 0 in Isaac Sim 6.0).
    """
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None

    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float)
    tof_all = np.ctypeslib.as_array(gmo.timeOffsetNs, shape=(n,)).astype(float)

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

    peak_idx = int(np.argmax(amps))
    peak_amp = float(amps[peak_idx])
    early_e = float(np.sum(amps[:N_EARLY] ** 2))

    return {
        "waveform":          amps.tolist(),
        "peak_sample_idx":   float(peak_idx),
        "peak_amplitude":    peak_amp,
        "early_energy":      early_e,
        "tof_first_ns":      tof_first,
        "n_signal_ways":     float(n_ways),
        "n_samples_per_sgw": float(num_spsgw),
        "n_elements":        float(n),
    }


# ── Writer class (module-level dict pattern, rule 4-2) ───────────────────────
class VisibilityProbeWriter(Writer):
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


# ── Scene setup (arm-free, rule 3-1) ──────────────────────────────────────────
CUBE_PATH = "/World/target"

print("=== Visibility vs WPM Ray-Tracing Probe ===")
print(f"Target  : Cube {args.cube_size}m at ({args.cube_x}, 0, 0), no arm, no room")
print(f"Sensor  : center_freq={args.center_freq:.0f} Hz  "
      f"mount_spacing={args.mount_spacing}m  "
      f"az={args.az_span}°  el={args.el_span}°")
print(f"Settle  : {args.n_settle} frames / condition   "
      f"Measure : {args.n_measure} frames / condition")
print()

target = Cube(
    CUBE_PATH,
    positions=np.array([[args.cube_x, 0.0, 0.0]]),
    scales=np.array([[args.cube_size, args.cube_size, args.cube_size]]),
)
stage = omni.usd.get_context().get_stage()

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
rep.WriterRegistry.register(VisibilityProbeWriter)
sensor.attach_writer("VisibilityProbeWriter")

# ── USD helper: move target by rewriting xform translate op (rule 3-4) ───────
_target_prim = stage.GetPrimAtPath(CUBE_PATH)
_xformable = UsdGeom.Xformable(_target_prim)


def _move_target(x: float, y: float = 0.0, z: float = 0.0) -> None:
    """Set the translation of CUBE_PATH via direct USD xformOp (world frame)."""
    ops_by_name = {op.GetOpName(): op for op in _xformable.GetOrderedXformOps()}
    translate_key = "xformOp:translate"
    if translate_key in ops_by_name:
        ops_by_name[translate_key].Set(Gf.Vec3d(x, y, z))
    else:
        _xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))


# ── Simulation start ──────────────────────────────────────────────────────────
timeline = omni.timeline.get_timeline_interface()
timeline.play()

print("Warming up until sensor produces data (>=20 frames, max 60)…")
_warmup_frames = 0
for _ in range(60):
    simulation_app.update()
    _warmup_frames += 1
    if _warmup_frames >= 20 and _buf["latest"] is not None:
        break
_n_elems = int(_buf["latest"]["n_elements"]) if _buf["latest"] is not None else 0
print(f"Warmup complete after {_warmup_frames} frames (numElements={_n_elems})")
print()


def _collect_condition(label: str, n_settle: int, n_measure: int) -> dict:
    """Settle n_settle frames, then average n_measure frames of the primary
    signal-way waveform. Returns a dict with the mean waveform and features
    recomputed from that mean waveform (peak_idx, early_energy)."""
    for _ in range(n_settle):
        simulation_app.update()

    samples: list[dict] = []
    for _ in range(n_measure):
        simulation_app.update()
        if _buf["latest"] is not None:
            samples.append(_buf["latest"])

    if not samples:
        return {
            "label": label,
            "n_samples": 0,
            "waveform": [],
            "peak_sample_idx": float("nan"),
            "early_energy": float("nan"),
            "n_samples_per_sgw": float("nan"),
        }

    wf_len = len(samples[0]["waveform"])
    wfs = [s["waveform"] for s in samples if len(s["waveform"]) == wf_len]
    if not wfs:
        return {
            "label": label,
            "n_samples": len(samples),
            "waveform": [],
            "peak_sample_idx": float("nan"),
            "early_energy": float("nan"),
            "n_samples_per_sgw": float("nan"),
        }

    mean_wf = np.mean(np.array(wfs), axis=0)
    peak_idx = int(np.argmax(mean_wf)) if len(mean_wf) else -1
    early_e = float(np.sum(mean_wf[:N_EARLY] ** 2)) if len(mean_wf) else float("nan")

    return {
        "label": label,
        "n_samples": len(samples),
        "waveform": mean_wf.tolist(),
        "peak_sample_idx": float(peak_idx),
        "early_energy": early_e,
        "n_samples_per_sgw": float(samples[0]["n_samples_per_sgw"]),
    }


def _diff_vs_a(cond: dict, cond_a: dict) -> tuple[float, float]:
    """Return (max|Δ|, RMS(Δ)) of cond's waveform against condition A's."""
    wf = np.asarray(cond["waveform"], dtype=float)
    wf_a = np.asarray(cond_a["waveform"], dtype=float)
    if len(wf) == 0 or len(wf_a) == 0 or len(wf) != len(wf_a):
        return float("nan"), float("nan")
    delta = wf - wf_a
    return float(np.max(np.abs(delta))), float(math.sqrt(float(np.mean(delta ** 2))))


# ── Condition A: visible (baseline) ───────────────────────────────────────────
cond_a = _collect_condition("A_visible", args.n_settle, args.n_measure)

# ── Condition B: visibility off ────────────────────────────────────────────────
vis_off_ok = set_prim_visibility(stage, CUBE_PATH, visible=False)
cond_b = _collect_condition("B_visibility_off", args.n_settle, args.n_measure)

# ── Restore visibility, re-measure as in-session noise reference (A2) ────────
vis_on_ok = set_prim_visibility(stage, CUBE_PATH, visible=True)
cond_a2 = _collect_condition("A2_visible_again", args.n_settle, args.n_measure)

# ── Condition C: translate far away, then move back ──────────────────────────
_move_target(args.far_x)
cond_c = _collect_condition("C_translated_far", args.n_settle, args.n_measure)
_move_target(args.cube_x)

# ── Condition D: physical deletion ────────────────────────────────────────────
stage.RemovePrim(CUBE_PATH)
cond_d = _collect_condition("D_deleted", args.n_settle, args.n_measure)

timeline.stop()

# ── Diff analysis ─────────────────────────────────────────────────────────────
diff_a_max, diff_a_rms = _diff_vs_a(cond_a, cond_a)          # trivially (0, 0)
diff_b_max, diff_b_rms = _diff_vs_a(cond_b, cond_a)
diff_a2_max, diff_a2_rms = _diff_vs_a(cond_a2, cond_a)       # session noise floor
diff_c_max, diff_c_rms = _diff_vs_a(cond_c, cond_a)
diff_d_max, diff_d_rms = _diff_vs_a(cond_d, cond_a)

noise_floor = diff_a2_max


def _verdict(diff_max: float) -> bool:
    if math.isnan(diff_max) or math.isnan(noise_floor):
        return False
    threshold = 10.0 * noise_floor
    if threshold <= 0.0:
        return diff_max > 0.0
    return diff_max > threshold


verdict_visibility = _verdict(diff_b_max)
verdict_translate = _verdict(diff_c_max)
verdict_delete = _verdict(diff_d_max)

# ── Report table ───────────────────────────────────────────────────────────────
HDR = (f"{'condition':<20}  {'peak_idx':>9}  {'early_e':>12}  "
       f"{'max|Δ vs A|':>13}  {'RMS(Δ vs A)':>13}  {'n_samples':>9}")
print(HDR)
print("-" * len(HDR))
_rows = [
    (cond_a, diff_a_max, diff_a_rms),
    (cond_b, diff_b_max, diff_b_rms),
    (cond_a2, diff_a2_max, diff_a2_rms),
    (cond_c, diff_c_max, diff_c_rms),
    (cond_d, diff_d_max, diff_d_rms),
]
for cond, dmax, drms in _rows:
    print(
        f"{cond['label']:<20}  "
        f"{cond['peak_sample_idx']:>9.1f}  "
        f"{cond['early_energy']:>12.4f}  "
        f"{dmax:>13.6f}  "
        f"{drms:>13.6f}  "
        f"{cond['n_samples']:>9d}"
    )

print()
print(f"session noise floor (A2 max|Δ vs A|) = {noise_floor:.6f}")
print(f"VERDICT visibility_effective: {verdict_visibility}")
print(f"VERDICT translate_effective: {verdict_translate}")
print(f"VERDICT delete_effective: {verdict_delete}")

# ── Save JSON ─────────────────────────────────────────────────────────────────
out_dir = pathlib.Path(args.output_dir)
out_dir.mkdir(parents=True, exist_ok=True)
json_path = out_dir / "probe_summary.json"

summary = {
    "args": vars(args),
    "prim_visibility_calls": {
        "set_visible_false_ok": bool(vis_off_ok),
        "set_visible_true_ok": bool(vis_on_ok),
    },
    "conditions": {
        "A_visible": cond_a,
        "B_visibility_off": cond_b,
        "A2_visible_again": cond_a2,
        "C_translated_far": cond_c,
        "D_deleted": cond_d,
    },
    "diffs_vs_A": {
        "A_visible":         {"max_abs_diff": diff_a_max,  "rms_diff": diff_a_rms},
        "B_visibility_off":  {"max_abs_diff": diff_b_max,  "rms_diff": diff_b_rms},
        "A2_visible_again":  {"max_abs_diff": diff_a2_max, "rms_diff": diff_a2_rms},
        "C_translated_far":  {"max_abs_diff": diff_c_max,  "rms_diff": diff_c_rms},
        "D_deleted":         {"max_abs_diff": diff_d_max,  "rms_diff": diff_d_rms},
    },
    "session_noise_floor_max_abs_diff": noise_floor,
    "verdicts": {
        "visibility_effective": verdict_visibility,
        "translate_effective": verdict_translate,
        "delete_effective": verdict_delete,
    },
}
with json_path.open("w") as f:
    json.dump(summary, f, indent=2)
print(f"\n→ summary saved to {json_path}")

simulation_app.close()
