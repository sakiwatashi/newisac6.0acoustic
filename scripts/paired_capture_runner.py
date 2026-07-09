"""Paired capture engine for the V2 sensing-envelope survey (S1/S2 workhorse).

Full spec: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md §5.1-5.2.
Skeleton borrowed from scripts/visibility_wpm_probe.py (argparse-before-
SimulationApp order, module-level writer buffer, >=20-frame warmup, and the
numSamplesPerSgw stride waveform reconstruction) per docs/WPM_EXPERIMENT_RULES.md.

Five-iron-law header (docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md §4) — what this
script is and is not responsible for:

  1. Paired control (this script's core):
     every cell runs with_target / without_target in the SAME session, at the
     SAME sensor geometry — the only thing that changes is target presence
     (stage.RemovePrim). A same-condition noise_ref replicate is captured
     between them and used as the session noise floor for SNR normalisation.
  2. Information-ablation control:
     not applicable here. That law governs Stage 2 D1's three-arm design
     (closed/blind/open); this script has no control loop to blind.
  3. Pre-registered criterion:
     SNR_peak > 10 => detectable (per §6 S1). This script only computes and
     records snr_peak / snr_energy; the detectability call itself is made by
     the caller (e.g. analyze_envelope.py or a human reading cells.csv).
  4. Raw waveform landing:
     the three mean waveforms (with/noise_ref/without) are saved as .npy
     under waveforms/, so every derived number can be recomputed offline.
  5. acoustic_only exclusivity:
     this script has no control loop and makes no motion decisions. Cell
     fields such as target_distance_m / target_size_m are oracle-only in the
     sense that they exist purely to BUILD the scene and to annotate the
     output JSON; they are never read back to steer anything during capture.

Deliberate deviation from §5.1 (single-cell architecture decision)
--------------------------------------------------------------------------
§5.1 specifies both --cell-json (one cell) and --cells-json (a list, iterated
within one session). This script implements ONLY --cell-json: one session,
one cell. Rationale: whether the WPM acoustic sensor prim tracks a mid-session
transform change (translate/rotate) has never been validated in this repo —
only target removal/visibility/translate-far has been validated (rule 6 in
§3). Moving the SENSOR between cells within one session is a materially
different, unvalidated operation, so batch sweeps over multiple cells are
delegated to an outer shell loop that invokes this script once per cell
(each cell gets a fresh session, at the cost of ~10s GPU startup per cell).

CLI
---
    --cell-json PATH      Required. Path to a single cell JSON (see schema below).
    --output-dir PATH     Required. cell_id subdirectory is created underneath.
    --n-measure INT       Frames averaged per condition (default 6).
    --n-settle INT        Settle frames before each condition capture (default 10).

Cell JSON schema (§5.2)
------------------------
    {
      "cell_id": "A_d0.5_z0.20_p0_cnone",
      "target_distance_m": 0.5,
      "target_size_m": 0.20,
      "sensor_pitch_deg": 0,
      "clutter": "none",             # "none" | "table" | "table_arm"
      "sensor_pos_m": [0, 0, 0.65],
      "notes": ""
    }

target_size_m <= 0 means "no target" (empty-scene acceptance case): no Cube
is created, and the without_target capture becomes a same-condition repeat
instead of a post-removal capture.

Usage
-----
    ./app/python.sh scripts/paired_capture_runner.py \\
        --cell-json docs/plan_v2/acceptance/cell_visible.json \\
        --output-dir runtime/outputs/v2_paired_capture_acceptance
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ── Argument parsing BEFORE SimulationApp (rule 4-1) ──────────────────────────
parser = argparse.ArgumentParser(description="Paired with/without-target acoustic capture for one V2 cell.")
parser.add_argument("--cell-json", type=str, required=True,
                     help="Path to a single cell JSON (schema in module docstring)")
parser.add_argument("--output-dir", type=str, required=True,
                     help="Output root; a <cell_id>/ subdirectory is created underneath")
parser.add_argument("--n-measure", type=int, default=6,
                     help="Frames averaged per condition")
parser.add_argument("--n-settle", type=int, default=40,
                     help="Settle frames before each condition capture")
args, _ = parser.parse_known_args()

# ── Load + validate the cell JSON now (stdlib-only, no need to wait for the
#    ~10s SimulationApp startup if the input is malformed) ────────────────────
_cell_path = pathlib.Path(args.cell_json)
with _cell_path.open() as _f:
    CELL: dict = json.load(_f)

_REQUIRED_FIELDS = (
    "cell_id", "target_distance_m", "target_size_m",
    "sensor_pitch_deg", "clutter", "sensor_pos_m",
)
_missing = [k for k in _REQUIRED_FIELDS if k not in CELL]
if _missing:
    raise SystemExit(f"cell json {_cell_path} missing required fields: {_missing}")
if CELL["clutter"] not in ("none", "table", "table_arm"):
    raise SystemExit(f"cell json {_cell_path}: invalid clutter {CELL['clutter']!r} "
                      f"(must be 'none' | 'table' | 'table_arm')")
if len(CELL["sensor_pos_m"]) != 3:
    raise SystemExit(f"cell json {_cell_path}: sensor_pos_m must have 3 components")
CELL.setdefault("notes", "")

# ── SimulationApp must come before all other Isaac Sim imports (rule 4-1) ────
from isaacsim import SimulationApp  # noqa: E402
simulation_app = SimulationApp({"headless": True})

import numpy as np                                   # noqa: E402
import omni.replicator.core as rep                   # noqa: E402
import omni.timeline                                 # noqa: E402
import omni.usd                                      # noqa: E402
from isaacsim.core.experimental.objects import Cube  # noqa: E402
from isaacsim.sensors.experimental.rtx import (      # noqa: E402
    Acoustic, AcousticSensor, parse_generic_model_output_data,
)
from omni.replicator.core import Writer              # noqa: E402
from pxr import Gf, UsdGeom                          # noqa: E402

from rtx_acoustic_factory import create_passport_acoustic  # noqa: E402
from ur10e_robotiq_common import ROBOT_USD_REL              # noqa: E402

try:
    from isaacsim.core.utils.stage import add_reference_to_stage as _add_reference_to_stage
except Exception:  # pragma: no cover - fallback path exercised only if the above import fails
    _add_reference_to_stage = None

# ── Physical constants (rule 1-4 / §3 table) ──────────────────────────────────
T_US = 132.5e-6   # seconds per WPM sample index (historical calibration; S2 will re-derive)
V_SOUND = 343.0   # m/s speed of sound
N_EARLY = 20      # sample boundary for "early" window

CENTER_FREQ_HZ = 40_000.0
MOUNT_SPACING_M = 0.10
TICK_RATE_HZ = 30.0
AZ_SPAN_DEG = 90.0
EL_SPAN_DEG = 90.0
TRACE_TREE_DEPTH = 2

SENSOR_PATH = "/World/acoustic_sensor"
TARGET_PATH = "/World/target"
TABLE_PATH = "/World/clutter_table"
ARM_PATH = "/World/clutter_arm"

TABLE_WIDTH_M = 1.2
TABLE_DEPTH_M = 0.8
TABLE_HEIGHT_M = 0.4
ARM_BACKSET_M = 0.10  # arm base sits this far behind the sensor (rule §5.2 table_arm)

# ── Module-level data buffer (Writer -> main loop communication, rule 4-2) ────
_buf: dict = {"latest": None}


def _extract_features(gmo) -> dict | None:
    """Extract the primary signal-way waveform from a parsed GMO struct.

    Follows rule 1-2 / rule 4-3: numSamplesPerSgw gives the stride used to
    slice the flat GMO buffer into signal ways; timeOffsetNs is never used
    (rule 1-3, always 0 in Isaac Sim 6.0).
    """
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
            pk = float(np.max(amp_all[s : s + num_spsgw]))
            if pk > best_peak:
                best_peak, best_start = pk, s
        amps = amp_all[best_start : best_start + num_spsgw]
    else:
        # Fallback: group by (tx, rx, ch) - old behaviour
        tx_arr = np.ctypeslib.as_array(gmo.x, shape=(n,))
        rx_arr = np.ctypeslib.as_array(gmo.y, shape=(n,))
        ch_arr = np.ctypeslib.as_array(gmo.z, shape=(n,)).astype(int)
        pairs = sorted(set(zip(tx_arr.tolist(), rx_arr.tolist(), ch_arr.tolist())))
        n_ways = len(pairs)
        tx0, rx0, ch0 = pairs[0]
        mask = (tx_arr == tx0) & (rx_arr == rx0) & (ch_arr == ch0)
        amps = amp_all[mask]

    if len(amps) == 0:
        return None

    return {
        "waveform": amps.tolist(),
        "n_signal_ways": float(n_ways),
        "n_samples_per_sgw": float(num_spsgw),
        "n_elements": float(n),
    }


class PairedCaptureWriter(Writer):
    """Parses GMO each frame and stores features in the module-level _buf (rule 4-2)."""

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


# ── Geometry helpers ───────────────────────────────────────────────────────────
def _boresight_dir(pitch_deg: float) -> tuple[float, float, float]:
    """Unit boresight direction for a sensor pitched pitch_deg about world Y.

    Positive pitch tilts the +X boresight toward -Z (i.e. downward / a look-
    down attitude), matching the xformOp:orient quaternion applied to the
    sensor prim below (same right-hand-rule convention about +Y).
    """
    rad = math.radians(float(pitch_deg))
    return (math.cos(rad), 0.0, -math.sin(rad))


def _set_sensor_pitch(stage, sensor_path: str, pitch_deg: float) -> None:
    """Set the sensor prim's xformOp:orient to a pure rotation about world Y.

    Uses the existing xformOp:orient slot created by Acoustic's default
    reset_xform_op_properties() standard set (translate, orient, scale), so
    the local matrix stays T * R * S: the sensor's local geometry (TX/RX
    mounts) rotates about its own origin first, then the whole assembly is
    translated to sensor_pos_m. This call happens once, at scene-build time,
    strictly before warmup -- the sensor prim is never touched again during
    capture (its transform is not moved mid-session; only TARGET_PATH is
    removed later, per rule 3-4 and the module docstring's single-cell note).
    """
    prim = stage.GetPrimAtPath(sensor_path)
    xformable = UsdGeom.Xformable(prim)
    ops_by_name = {op.GetOpName(): op for op in xformable.GetOrderedXformOps()}
    half = math.radians(float(pitch_deg)) / 2.0
    quat = Gf.Quatd(math.cos(half), Gf.Vec3d(0.0, math.sin(half), 0.0))
    if "xformOp:orient" in ops_by_name:
        ops_by_name["xformOp:orient"].Set(quat)
    else:
        xformable.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(quat)


def _build_table(stage, top_center_xy: tuple[float, float]) -> None:
    Cube(
        TABLE_PATH,
        sizes=[1.0],
        scales=np.array([[TABLE_WIDTH_M, TABLE_DEPTH_M, TABLE_HEIGHT_M]]),
        positions=np.array([[top_center_xy[0], top_center_xy[1], TABLE_HEIGHT_M / 2.0]]),
    )


def _build_clutter_arm(stage, assets_root: str, base_xy_z: tuple[float, float, float]) -> str:
    usd_path = f"{assets_root}/{ROBOT_USD_REL}"
    if _add_reference_to_stage is not None:
        _add_reference_to_stage(usd_path=usd_path, prim_path=ARM_PATH)
    else:
        prim = stage.DefinePrim(ARM_PATH, "Xform")
        prim.GetReferences().AddReference(usd_path)
    for _ in range(5):
        simulation_app.update()
    arm_prim = stage.GetPrimAtPath(ARM_PATH)
    xformable = UsdGeom.Xformable(arm_prim)
    ops_by_name = {op.GetOpName(): op for op in xformable.GetOrderedXformOps()}
    if "xformOp:translate" in ops_by_name:
        ops_by_name["xformOp:translate"].Set(Gf.Vec3d(*base_xy_z))
    else:
        xformable.AddTranslateOp().Set(Gf.Vec3d(*base_xy_z))
    return usd_path


# Stationarity handling (measured 2026-07-08):
# - WPM output ramps for tens of frames after scene creation (frame-count-
#   deterministic: same scene reads early_energy 24458 at ~30 frames vs a
#   converged 35226 at ~60+, byte-reproducible across sessions).
# - Per-frame energy jitters >0.1% indefinitely (frames alternate signal-way
#   structure), so a per-frame convergence gate cannot work; only the
#   n_measure-frame MEAN is stable (0.02% at settle=40 in the acceptance
#   scene).
# Strategy: fixed settle (default 40, validated) + POST-HOC audit — the
# with_target vs noise_ref energy drift is computed after capture; cells
# whose drift exceeds STATIONARITY_DRIFT_MAX are flagged stationarity_ok=
# False and must be treated as INVALID MEASUREMENTS (re-run with a larger
# --n-settle), never as "not detectable".
STATIONARITY_DRIFT_MAX = 0.05


def _collect_condition(label: str, n_settle: int, n_measure: int) -> dict:
    """Settle n_settle frames, then average n_measure frames of the primary
    signal-way waveform."""
    for _ in range(n_settle):
        simulation_app.update()
    settle_frames, converged = n_settle, True  # post-hoc audit decides validity

    samples: list[dict] = []
    for _ in range(n_measure):
        simulation_app.update()
        if _buf["latest"] is not None:
            samples.append(_buf["latest"])

    if not samples:
        return {"label": label, "n_samples": 0, "waveform": np.array([], dtype=float),
                "n_samples_per_sgw": float("nan"),
                "settle_frames": settle_frames, "converged": converged}

    wf_len = len(samples[0]["waveform"])
    wfs = [s["waveform"] for s in samples if len(s["waveform"]) == wf_len]
    if not wfs:
        return {"label": label, "n_samples": len(samples), "waveform": np.array([], dtype=float),
                "n_samples_per_sgw": float("nan"),
                "settle_frames": settle_frames, "converged": converged}

    mean_wf = np.mean(np.array(wfs, dtype=float), axis=0)
    return {
        "label": label,
        "n_samples": len(samples),
        "waveform": mean_wf,
        "n_samples_per_sgw": float(samples[0]["n_samples_per_sgw"]),
        "settle_frames": settle_frames,
        "converged": converged,
    }


def _peak_and_early(wf: np.ndarray) -> tuple[float, float, int]:
    if wf.size == 0:
        return float("nan"), float("nan"), 0
    peak_idx = int(np.argmax(wf))
    early_e = float(np.sum(wf[:N_EARLY] ** 2))
    return float(peak_idx), early_e, int(wf.size)


def _truncate_common(*arrays: np.ndarray) -> tuple[list[np.ndarray], int, bool]:
    lengths = [a.size for a in arrays if a is not None]
    if not lengths or min(lengths) == 0:
        return [np.array([], dtype=float) for _ in arrays], 0, False
    min_len = min(lengths)
    truncated_flag = len(set(lengths)) > 1
    out = [np.asarray(a[:min_len], dtype=float) for a in arrays]
    return out, min_len, truncated_flag


# ── Scene construction ─────────────────────────────────────────────────────────
print("=== paired_capture_runner.py ===")
print(f"cell_id={CELL['cell_id']}  d={CELL['target_distance_m']}m  "
      f"z={CELL['target_size_m']}m  pitch={CELL['sensor_pitch_deg']}deg  "
      f"clutter={CELL['clutter']}  sensor_pos={CELL['sensor_pos_m']}")
print(f"n_settle={args.n_settle}  n_measure={args.n_measure}")
print()

stage = omni.usd.get_context().get_stage()

sensor_pos = tuple(float(v) for v in CELL["sensor_pos_m"])
pitch_deg = float(CELL["sensor_pitch_deg"])
target_size_m = float(CELL["target_size_m"])
target_distance_m = float(CELL["target_distance_m"])
clutter = str(CELL["clutter"])

acoustic, sensor = create_passport_acoustic(
    SENSOR_PATH,
    Acoustic=Acoustic,
    AcousticSensor=AcousticSensor,
    np=np,
    tick_rate_hz=TICK_RATE_HZ,
    center_frequency_hz=CENTER_FREQ_HZ,
    sensor_local_offset_m=sensor_pos,
    mount_spacing_m=MOUNT_SPACING_M,
    aux_output_level="BASIC",
    writer_brings_annotator=True,
    az_span_deg=AZ_SPAN_DEG,
    el_span_deg=EL_SPAN_DEG,
    trace_tree_depth=TRACE_TREE_DEPTH,
)
rep.WriterRegistry.register(PairedCaptureWriter)
sensor.attach_writer("PairedCaptureWriter")

# Sensor orientation is set once, here, before warmup/capture ever starts.
# It is NEVER touched again for the rest of the session (see module docstring's
# single-cell deviation note and _set_sensor_pitch's docstring).
_set_sensor_pitch(stage, SENSOR_PATH, pitch_deg)

boresight = _boresight_dir(pitch_deg)
target_center = tuple(sensor_pos[i] + target_distance_m * boresight[i] for i in range(3))

target_created = target_size_m > 0.0
if target_created:
    Cube(
        TARGET_PATH,
        sizes=[target_size_m],
        positions=np.array([[target_center[0], target_center[1], target_center[2]]]),
    )
    print(f"target Cube created at {target_center} (edge={target_size_m}m)")
else:
    print("target_size_m <= 0: no target Cube created (empty-scene acceptance case)")

table_built = False
arm_built = False
assets_root_used = None
if clutter in ("table", "table_arm"):
    _build_table(stage, (target_center[0], target_center[1]))
    table_built = True
    print(f"clutter table built, top-face center under target xy=({target_center[0]:.3f}, {target_center[1]:.3f})")
if clutter == "table_arm":
    from isaacsim.storage.native import get_assets_root_path  # noqa: E402 (deferred, only needed here)
    assets_root_used = get_assets_root_path()
    if not assets_root_used:
        raise RuntimeError("get_assets_root_path() returned empty/None; cannot spawn clutter arm asset")
    arm_base = (sensor_pos[0] - ARM_BACKSET_M, sensor_pos[1], 0.0)
    usd_path = _build_clutter_arm(stage, assets_root_used, arm_base)
    arm_built = True
    print(f"clutter arm referenced from {usd_path} at base {arm_base}")

print()

# ── Simulation start + warmup (rule: >=20 frames until numElements>0) ────────
timeline = omni.timeline.get_timeline_interface()
timeline.play()

print("Warming up until sensor produces data (>=20 frames, max 60)...")
_warmup_frames = 0
for _ in range(60):
    simulation_app.update()
    _warmup_frames += 1
    if _warmup_frames >= 20 and _buf["latest"] is not None:
        break
_n_elems = int(_buf["latest"]["n_elements"]) if _buf["latest"] is not None else 0
print(f"Warmup complete after {_warmup_frames} frames (numElements={_n_elems})")
print()

# ── Capture sequence (rule §5.1 steps 1-4) ────────────────────────────────────
cond_with = _collect_condition("with_target", args.n_settle, args.n_measure)

cond_noise = _collect_condition("noise_ref", args.n_settle, args.n_measure)

if target_created:
    stage.RemovePrim(TARGET_PATH)
    cond_without = _collect_condition("without_target", args.n_settle, args.n_measure)
else:
    cond_without = _collect_condition("without_target_repeat", args.n_settle, args.n_measure)

timeline.stop()

# ── Metrics ────────────────────────────────────────────────────────────────────
(wf_with, wf_noise, wf_without), n_common, wf_truncated = _truncate_common(
    cond_with["waveform"], cond_noise["waveform"], cond_without["waveform"]
)

if n_common > 0:
    noise_floor_peak = float(np.max(np.abs(wf_with - wf_noise)))
    noise_floor_energy = float(np.sum(np.abs(wf_with - wf_noise)))
    diff_wo = np.abs(wf_with - wf_without)
    snr_peak = float(np.max(diff_wo)) / max(noise_floor_peak, 1e-12)
    snr_energy = float(np.sum(diff_wo)) / max(noise_floor_energy, 1e-12)
else:
    noise_floor_peak = float("nan")
    noise_floor_energy = float("nan")
    snr_peak = float("nan")
    snr_energy = float("nan")

peak_with, early_with, n_with = _peak_and_early(cond_with["waveform"])
peak_noise, early_noise, n_noise = _peak_and_early(cond_noise["waveform"])
peak_without, early_without, n_without = _peak_and_early(cond_without["waveform"])

# Post-hoc stationarity audit: with_target and noise_ref are the same scene,
# so their mean-waveform energies must agree; a large drift means the WPM
# startup ramp was still in progress and the whole cell is an INVALID
# measurement (re-run with larger --n-settle), not an undetectable cell.
if math.isfinite(early_with) and math.isfinite(early_noise):
    energy_drift_rel = abs(early_with - early_noise) / max(abs(early_with), abs(early_noise), 1e-12)
else:
    energy_drift_rel = float("nan")
stationarity_ok = bool(math.isfinite(energy_drift_rel) and energy_drift_rel <= STATIONARITY_DRIFT_MAX)

# ── stdout summary ─────────────────────────────────────────────────────────────
HDR = f"{'condition':<22}  {'peak_idx':>9}  {'early_energy':>14}  {'n_samples':>10}"
print(HDR)
print("-" * len(HDR))
print(f"{'with_target':<22}  {peak_with:>9.1f}  {early_with:>14.6f}  {n_with:>10d}")
print(f"{'noise_ref':<22}  {peak_noise:>9.1f}  {early_noise:>14.6f}  {n_noise:>10d}")
print(f"{cond_without['label']:<22}  {peak_without:>9.1f}  {early_without:>14.6f}  {n_without:>10d}")
print()
print(f"noise_floor_peak={noise_floor_peak:.6f}  noise_floor_energy={noise_floor_energy:.6f}")
print(f"snr_peak={snr_peak:.6f}  snr_energy={snr_energy:.6f}")
if wf_truncated:
    print(f"WARNING: waveform lengths differed across conditions; truncated to n_common={n_common}")

# ── Save outputs ───────────────────────────────────────────────────────────────
out_dir = pathlib.Path(args.output_dir) / str(CELL["cell_id"])
wf_dir = out_dir / "waveforms"
wf_dir.mkdir(parents=True, exist_ok=True)

np.save(wf_dir / "with.npy", np.asarray(cond_with["waveform"], dtype=float))
np.save(wf_dir / "noise_ref.npy", np.asarray(cond_noise["waveform"], dtype=float))
np.save(wf_dir / "without.npy", np.asarray(cond_without["waveform"], dtype=float))

result = {
    # cell inputs, verbatim
    "cell_id": CELL["cell_id"],
    "target_distance_m": target_distance_m,
    "target_size_m": target_size_m,
    "sensor_pitch_deg": pitch_deg,
    "clutter": clutter,
    "sensor_pos_m": list(sensor_pos),
    "notes": CELL.get("notes", ""),
    # derived scene facts
    "target_created": target_created,
    "target_center_m": list(target_center),
    "table_built": table_built,
    "arm_built": arm_built,
    "assets_root_used": assets_root_used,
    # per-condition features
    "with_target": {
        "peak_sample_idx": peak_with, "early_energy": early_with,
        "n_samples": n_with, "n_frames_averaged": cond_with["n_samples"],
        "n_samples_per_sgw": cond_with["n_samples_per_sgw"],
        "settle_frames": cond_with["settle_frames"], "converged": cond_with["converged"],
    },
    "noise_ref": {
        "peak_sample_idx": peak_noise, "early_energy": early_noise,
        "n_samples": n_noise, "n_frames_averaged": cond_noise["n_samples"],
        "n_samples_per_sgw": cond_noise["n_samples_per_sgw"],
        "settle_frames": cond_noise["settle_frames"], "converged": cond_noise["converged"],
    },
    "without_target": {
        "label": cond_without["label"],
        "peak_sample_idx": peak_without, "early_energy": early_without,
        "n_samples": n_without, "n_frames_averaged": cond_without["n_samples"],
        "n_samples_per_sgw": cond_without["n_samples_per_sgw"],
        "settle_frames": cond_without["settle_frames"], "converged": cond_without["converged"],
    },
    # metrics
    "noise_floor_peak": noise_floor_peak,
    "noise_floor_energy": noise_floor_energy,
    "snr_peak": snr_peak,
    "snr_energy": snr_energy,
    "energy_drift_rel": energy_drift_rel,
    "stationarity_ok": stationarity_ok,
    "waveform_lengths_truncated": wf_truncated,
    "n_samples_common": n_common,
    # run metadata
    "n_measure": args.n_measure,
    "n_settle": args.n_settle,
    "timestamp": datetime.datetime.now().isoformat(),
    "script": "paired_capture_runner.py",
    "warmup_frames": _warmup_frames,
}
with (out_dir / "cell_result.json").open("w") as f:
    json.dump(result, f, indent=2)

print(f"\n-> cell_result.json + waveforms/ saved under {out_dir}")
print(f"RESULT cell_id={CELL['cell_id']} snr_peak={snr_peak:.2f} snr_energy={snr_energy:.2f} "
      f"stationarity_ok={stationarity_ok} drift={energy_drift_rel:.4f}")

simulation_app.close()
