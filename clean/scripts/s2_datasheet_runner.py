"""S2 datasheet capture runner (distance / lateral / repeat encoding sweeps).

Full spec: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 6, "S2: datasheet".
Skeleton borrowed from scripts/paired_capture_runner.py (argparse-before-
SimulationApp order, module-level writer buffer dict, >=20-frame warmup,
numSamplesPerSgw stride waveform reconstruction, settle=40 convention, and
the post-hoc stationarity-drift audit) per docs/WPM_EXPERIMENT_RULES.md.
Target-move technique (xformOp:translate rewrite, no prim re-creation) is
scripts/visibility_wpm_probe.py's `_move_target`, which that script validated
against WPM ray tracing (condition C).

This script is single-session, single-mode: one invocation runs exactly one
of {distance, lateral, repeat} over a SHARED, FIXED scene (S1 Block D
geometry: sensor + table + static UR10e clutter). Only TARGET_PATH is ever
moved mid-session (via xformOp:translate); the sensor prim's position/pitch
is set once at scene-build time and never touched again, matching
paired_capture_runner's single-cell architecture note (moving the SENSOR
mid-session is unvalidated; moving the TARGET is validated, see above).

Five-iron-law header (docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 4):

  1. Paired control:
     not applicable to S2 -- S2 assumes the cell is already known-detectable
     from S1 (SNR_peak > 10) and characterises its response curve; there is
     no with/without-target pairing here. (Paired control lives entirely in
     paired_capture_runner.py / S1.)
  2. Information-ablation control:
     not applicable -- S2 has no control loop to blind (that is D1's job).
  3. Pre-registered criterion (written here, BEFORE this script is ever run):
       distance_r_ge_0.95      : Pearson r(peak_idx, true_distance_3d_m) over
                                 the combined p1-p3 distance passes >= 0.95.
       lateral_monotonic_ge_0.9: |Spearman rho(balance, y_offset_m)| >= 0.9
                                 over the 13-point lateral sweep.
       repeat_cv_lt_5pct       : CV(early_energy) over 10 repeat trials of the
                                 same point < 0.05.
     The adjudication itself (True/False against these numbers) is computed
     by the companion offline analyzer, scripts/analyze_s2_datasheet.py, from
     the raw points.csv / point.json files this script writes -- never by
     this script, and never fed back into control.
  4. Raw waveform landing:
     every measured point saves its averaged primary/rx0/rx1 waveforms as
     .npy under waveforms/, so every derived number (peak_idx, early_energy,
     balance, the S2 regression) can be recomputed offline from raw samples.
  5. acoustic_only exclusivity:
     target_distance_m / target height / y_offset are oracle-only in the
     sense that they exist purely to BUILD the scene and to annotate
     points.csv; nothing this script computes is fed back to move the
     sensor, the target, or any exit condition -- there is no control loop
     in this script at all.

CLI
---
    --mode {distance,lateral,repeat}   Required.
    --output-dir PATH                 Required. Sub-directory created inside.
    --pass-id STR                     Required for distance/repeat (labels
                                       the output sub-directory and the
                                       repeated-pass identity for offline
                                       aggregation). Ignored for lateral.
    --target-height {boresight,table} distance mode only (default boresight).
    --n-settle INT                    default 40 (validated convergence
                                       settle, see paired_capture_runner.py).
    --n-measure INT                   default 6.

Shared scene (fixed for all three modes; = S1 Block D geometry)
-----------------------------------------------------------------
    Sensor   : (0, 0, 0.65) m, pitch 0 (no xformOp:orient needed -- identity
               already matches "horizontal", consistent with S1), 40 kHz,
               mount_spacing 0.10 m.
    Clutter  : clutter=table_arm -- 1.2x0.8x0.4 m solid table (top face at
               z=0.40) anchored under a canonical x=sensor_x+0.5 m (the
               distance value shared by the lateral and repeat sweeps; the
               table is scene background, not a physically-simulated support,
               so it is built once and not re-anchored per distance-sweep
               point) + a static UR10e USD reference
               (Isaac/Robots/UniversalRobots/ur10e/ur10e.usd) sitting
               ARM_BACKSET_M=0.10 m behind the sensor, exactly like
               paired_capture_runner._build_clutter_arm.
    Target   : 0.10 m Cube, moved between points via xformOp:translate only
               (never re-created), per visibility_wpm_probe._move_target.

Writer / per-RX split
----------------------
Each frame the writer stores a FULL copy of the GMO scalar array, the
numSamplesPerSgw stride, and the rx id (gmo.y) at each signal-way's start
index -- enough to reconstruct any way, not just "the" primary. From this,
`_per_rx_primary(frame)` groups signal ways by rx id into (up to) two mount
groups (mount 0 / mount 1) and, within each group, picks the way with the
highest peak amplitude as that RX's primary -- returning one waveform per
RX id. The "overall" primary used for peak_idx/early_energy is simply
whichever of the two RX primaries has the higher peak (the global best way
must live inside one of the two per-RX groups).

Standard per-point procedure (shared by all 3 modes)
-----------------------------------------------------
    settle n_settle frames
    -> measure n_measure frames, average  => block A
    -> measure n_measure MORE frames (no extra settle), average => block B
    point value = (A + B) / 2
    point_drift = |earlyE(A) - earlyE(B)| / max(|earlyE(A)|, |earlyE(B)|, eps)
    point_drift > STATIONARITY_DRIFT_MAX => stationarity_ok = False
        (RECORDED, never used to abort/skip the point -- same "invalid
        measurement, not undetectable" philosophy as paired_capture_runner).
early_energy := sum of squares of the first N_EARLY=20 samples.

Usage
-----
    ./app/python.sh scripts/s2_datasheet_runner.py \\
        --mode distance --pass-id p1 \\
        --output-dir runtime/outputs/v2_s2_datasheet
    ./app/python.sh scripts/s2_datasheet_runner.py \\
        --mode lateral \\
        --output-dir runtime/outputs/v2_s2_datasheet
    ./app/python.sh scripts/s2_datasheet_runner.py \\
        --mode repeat --pass-id r01 \\
        --output-dir runtime/outputs/v2_s2_datasheet
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ── Argument parsing BEFORE SimulationApp (rule 4-1) ──────────────────────────
parser = argparse.ArgumentParser(
    description="S2 datasheet capture (distance / lateral / repeat encoding sweeps)."
)
parser.add_argument("--mode", type=str, required=True,
                     choices=("distance", "lateral", "repeat"),
                     help="Which S2 sweep to run in this session")
parser.add_argument("--output-dir", type=str, required=True,
                     help="Output root; a mode-specific sub-directory is created underneath")
parser.add_argument("--pass-id", type=str, default=None,
                     help="Pass identity label; required for distance/repeat, ignored for lateral")
parser.add_argument("--target-height", type=str, default="boresight",
                     choices=("boresight", "table"),
                     help="distance mode only: boresight (z=0.65, on-axis) or table (z=0.45, on table top)")
parser.add_argument("--n-settle", type=int, default=40,
                     help="Settle frames before each block's measurement (validated convergence value)")
parser.add_argument("--n-measure", type=int, default=12,
                     help="Frames averaged per measurement block (two blocks per point, A and B)")
args, _ = parser.parse_known_args()

if args.mode in ("distance", "repeat") and not args.pass_id:
    raise SystemExit(f"--pass-id is required for --mode {args.mode}")

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
from isaacsim.storage.native import get_assets_root_path  # noqa: E402
from omni.replicator.core import Writer              # noqa: E402
from pxr import Gf, UsdGeom                          # noqa: E402

from rtx_acoustic_factory import create_passport_acoustic  # noqa: E402
from ur10e_robotiq_common import ROBOT_USD_REL              # noqa: E402

try:
    from isaacsim.core.utils.stage import add_reference_to_stage as _add_reference_to_stage
except Exception:  # pragma: no cover - fallback path exercised only if the above import fails
    _add_reference_to_stage = None

# ── Physical constants (rule 1-4 / S1 table) ──────────────────────────────────
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

SENSOR_POS_M = (0.0, 0.0, 0.65)
TARGET_SIZE_M = 0.10

TABLE_WIDTH_M = 1.2
TABLE_DEPTH_M = 0.8
TABLE_HEIGHT_M = 0.4
ARM_BACKSET_M = 0.10       # arm base sits this far behind the sensor (S1 Block D table_arm)
TABLE_ANCHOR_DISTANCE_M = 0.5  # canonical distance the shared table is anchored under (see
                               # module docstring "Shared scene" note): the table is scene
                               # background built once, not a per-point physical support.

STATIONARITY_DRIFT_MAX = 0.05  # same threshold as paired_capture_runner.py

# distance-mode sweep: 20 equally spaced points, near to far
DISTANCE_NEAR_M = 0.15
DISTANCE_FAR_M = 1.20
DISTANCE_N_POINTS = 20

# lateral-mode sweep: 13 equally spaced points, fixed distance 0.5 m, boresight height
LATERAL_DISTANCE_M = 0.5
LATERAL_Y_MIN_M = -0.15
LATERAL_Y_MAX_M = 0.15
LATERAL_N_POINTS = 13

# repeat-mode: single point, same as lateral's fixed distance / boresight height
REPEAT_DISTANCE_M = 0.5

# ── Module-level data buffer (Writer -> main loop communication, rule 4-2) ────
_buf: dict = {"latest": None}


def _extract_frame(gmo) -> dict | None:
    """Copy everything needed to reconstruct ANY signal way, not just the
    primary one: the full scalar array, the numSamplesPerSgw stride, and the
    rx id (gmo.y) sampled at each way's start index. Per-RX splitting
    (_per_rx_primary) happens later, outside the writer, from this dict.
    """
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None

    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float).copy()
    rx_all = np.ctypeslib.as_array(gmo.y, shape=(n,)).copy()

    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    if num_spsgw <= 0 or n % num_spsgw != 0:
        return None  # no stride -> cannot split into signal ways (rule 1-2)

    n_ways = n // num_spsgw
    way_start_rx_ids = [int(rx_all[w * num_spsgw]) for w in range(n_ways)]

    if os.environ.get("S2_DEBUG_IDS") == "1" and not _buf.get("ids_printed"):
        tx_all = np.ctypeslib.as_array(gmo.x, shape=(n,))
        ch_all = np.ctypeslib.as_array(gmo.z, shape=(n,))
        keys = [(int(tx_all[w * num_spsgw]), int(rx_all[w * num_spsgw]), int(ch_all[w * num_spsgw]))
                for w in range(n_ways)]
        print(f"S2_DEBUG_IDS frame: n={n} num_spsgw={num_spsgw} n_ways={n_ways} "
              f"(tx,rx,ch) at way starts = {keys}", flush=True)
        _buf["ids_printed"] = True

    return {
        "amp_all": amp_all,
        "num_spsgw": num_spsgw,
        "way_start_rx_ids": way_start_rx_ids,
        "n_elements": n,
    }


class S2DatasheetWriter(Writer):
    """Parses GMO each frame and stores the full-fidelity frame dict in the
    module-level _buf (rule 4-2)."""

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
            feats = _extract_frame(gmo)
            if feats is not None:
                _buf["latest"] = feats
                return  # first render product is sufficient


def _per_rx_primary(frame: dict) -> dict[int, np.ndarray]:
    """Split one frame's signal ways into per-receiver groups BY WAY ORDINAL.

    Measured 2026-07-08 (S2_DEBUG_IDS): in this rxGroup config the GMO labels
    every way (tx,rx,ch)=(0,0,0) — receiver identity is NOT encoded in the id
    fields. Each frame carries n_ways=2 ways; we treat way ordinal 0/1 as the
    two receiver mounts. This is a testable assumption: the lateral sweep
    adjudicates it — if the way0-vs-way1 energy balance does not track the
    target's lateral offset, ordinal mapping (and hence dual-RX lateral
    encoding in this config) is falsified and the pre-registered lateral
    criterion reports False.

    Returns {ordinal: waveform}; empty dict if the frame has no stride info.
    """
    amp_all = frame["amp_all"]
    num_spsgw = frame["num_spsgw"]
    n_ways = len(frame["way_start_rx_ids"])

    per_rx: dict[int, np.ndarray] = {}
    for w in range(n_ways):
        s = w * num_spsgw
        per_rx[w] = amp_all[s : s + num_spsgw].copy()
    return per_rx


# ── Geometry helpers ───────────────────────────────────────────────────────────
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


def _move_target(stage, x: float, y: float, z: float) -> None:
    """Rewrite TARGET_PATH's xformOp:translate (world frame). Validated
    against WPM ray tracing by visibility_wpm_probe._move_target (condition
    C: translate-far-and-back). The target is NEVER re-created between
    points -- only this op is rewritten."""
    prim = stage.GetPrimAtPath(TARGET_PATH)
    xformable = UsdGeom.Xformable(prim)
    ops_by_name = {op.GetOpName(): op for op in xformable.GetOrderedXformOps()}
    key = "xformOp:translate"
    if key in ops_by_name:
        ops_by_name[key].Set(Gf.Vec3d(x, y, z))
    else:
        xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))


def _distance_target_center(d: float, target_height: str) -> tuple[float, float, float, float]:
    """Return (x, y, z, true_distance_3d_m) for a distance-mode point.

    boresight: target center on-axis at sensor height (z=0.65); true 3D
    distance equals the nominal (horizontal) distance.
    table: target center resting on the table top (z=0.45); true 3D distance
    accounts for the fixed 0.20 m height offset between sensor and table-top
    target center.
    """
    x = SENSOR_POS_M[0] + d
    y = SENSOR_POS_M[1]
    if target_height == "boresight":
        z = SENSOR_POS_M[2]
        true3d = d
    else:  # "table"
        z = 0.45
        dz = SENSOR_POS_M[2] - z  # = 0.20
        true3d = math.sqrt(d * d + dz * dz)
    return x, y, z, true3d


# ── Frame-level feature helpers ────────────────────────────────────────────────
def _early_energy(wf: np.ndarray) -> float:
    if wf is None or wf.size == 0:
        return float("nan")
    return float(np.sum(wf[:N_EARLY] ** 2))


def _peak_idx(wf: np.ndarray) -> float:
    if wf is None or wf.size == 0:
        return float("nan")
    return float(np.argmax(wf))


def _avg_common(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a is None or b is None or a.size == 0 or b.size == 0:
        return np.array([], dtype=float)
    n = min(a.size, b.size)
    return (a[:n] + b[:n]) / 2.0


def _measure_block(n_frames: int) -> dict:
    """Advance n_frames simulation steps, accumulating per-RX primary
    waveforms ACROSS frames (a single GMO frame is not guaranteed to carry
    both mounts — frames may alternate signal-way structure, which is why the
    original per-frame 2-RX requirement produced all-NaN results 2026-07-08).
    Each RX group is averaged over whatever frames contained it; the overall
    primary is the higher-peak of the two block-mean RX waveforms."""
    by_rx: dict[int, list[np.ndarray]] = {}
    n_frames_valid = 0

    for _ in range(n_frames):
        simulation_app.update()
        frame = _buf["latest"]
        if frame is None:
            continue
        per_rx = _per_rx_primary(frame)
        if not per_rx:
            continue
        n_frames_valid += 1
        for rid, wf in per_rx.items():
            by_rx.setdefault(int(rid), []).append(wf)

    def _mean_stack(wfs: list[np.ndarray]) -> np.ndarray:
        if not wfs:
            return np.array([], dtype=float)
        min_len = min(w.size for w in wfs)
        stacked = np.array([w[:min_len] for w in wfs], dtype=float)
        return np.mean(stacked, axis=0)

    rids = sorted(by_rx.keys())
    rx0_wf = _mean_stack(by_rx[rids[0]]) if len(rids) >= 1 else np.array([], dtype=float)
    rx1_wf = _mean_stack(by_rx[rids[1]]) if len(rids) >= 2 else np.array([], dtype=float)
    if rx0_wf.size and rx1_wf.size:
        primary_wf = rx0_wf if float(np.max(rx0_wf)) >= float(np.max(rx1_wf)) else rx1_wf
    elif rx0_wf.size:
        primary_wf = rx0_wf
    else:
        primary_wf = rx1_wf

    return {
        "n_frames_valid": n_frames_valid,
        "primary": primary_wf,
        "rx0": rx0_wf,
        "rx1": rx1_wf,
        "rx_ids": rids,
    }


def _measure_point(n_settle: int, n_measure: int) -> dict:
    """Standard per-point procedure: settle -> block A -> block B (no extra
    settle between A and B) -> point value = (A+B)/2, plus the A-vs-B drift
    audit."""
    for _ in range(n_settle):
        simulation_app.update()

    block_a = _measure_block(n_measure)
    block_b = _measure_block(n_measure)

    mean_primary = _avg_common(block_a["primary"], block_b["primary"])
    mean_rx0 = _avg_common(block_a["rx0"], block_b["rx0"])
    mean_rx1 = _avg_common(block_a["rx1"], block_b["rx1"])

    early_a = _early_energy(block_a["primary"])
    early_b = _early_energy(block_b["primary"])
    if math.isfinite(early_a) and math.isfinite(early_b):
        point_drift = abs(early_a - early_b) / max(abs(early_a), abs(early_b), 1e-12)
    else:
        point_drift = float("nan")
    stationarity_ok = bool(math.isfinite(point_drift) and point_drift <= STATIONARITY_DRIFT_MAX)

    return {
        "mean_primary": mean_primary,
        "mean_rx0": mean_rx0,
        "mean_rx1": mean_rx1,
        "peak_sample_idx": _peak_idx(mean_primary),
        "early_energy": _early_energy(mean_primary),
        "rx0_early": _early_energy(mean_rx0),
        "rx1_early": _early_energy(mean_rx1),
        "point_drift": point_drift,
        "stationarity_ok": stationarity_ok,
        "n_frames_valid_a": block_a["n_frames_valid"],
        "n_frames_valid_b": block_b["n_frames_valid"],
    }


# ── Scene construction ─────────────────────────────────────────────────────────
print("=== s2_datasheet_runner.py ===")
print(f"mode={args.mode}  pass_id={args.pass_id}  target_height={args.target_height}")
print(f"n_settle={args.n_settle}  n_measure={args.n_measure}")
print()

stage = omni.usd.get_context().get_stage()

acoustic, sensor = create_passport_acoustic(
    SENSOR_PATH,
    Acoustic=Acoustic,
    AcousticSensor=AcousticSensor,
    np=np,
    tick_rate_hz=TICK_RATE_HZ,
    center_frequency_hz=CENTER_FREQ_HZ,
    sensor_local_offset_m=SENSOR_POS_M,
    mount_spacing_m=MOUNT_SPACING_M,
    aux_output_level="BASIC",
    writer_brings_annotator=True,
    az_span_deg=AZ_SPAN_DEG,
    el_span_deg=EL_SPAN_DEG,
    trace_tree_depth=TRACE_TREE_DEPTH,
)
rep.WriterRegistry.register(S2DatasheetWriter)
sensor.attach_writer("S2DatasheetWriter")
# Sensor pitch is 0 (horizontal); identity xformOp:orient already matches
# this, so unlike paired_capture_runner._set_sensor_pitch we do not need to
# touch xformOp:orient at all (per module docstring's "Shared scene" note).
# The sensor prim's translate is fixed at SENSOR_POS_M and is NEVER touched
# again for the rest of the session.

# Clutter: table + static UR10e arm reference (S1 Block D geometry, shared
# by all three modes -- see module docstring).
_build_table(stage, (SENSOR_POS_M[0] + TABLE_ANCHOR_DISTANCE_M, SENSOR_POS_M[1]))
print(f"clutter table built, top-face center at x={SENSOR_POS_M[0] + TABLE_ANCHOR_DISTANCE_M:.3f}, "
      f"y={SENSOR_POS_M[1]:.3f}")

assets_root_used = get_assets_root_path()
if not assets_root_used:
    raise RuntimeError("get_assets_root_path() returned empty/None; cannot spawn clutter arm asset")
arm_base = (SENSOR_POS_M[0] - ARM_BACKSET_M, SENSOR_POS_M[1], 0.0)
usd_path_used = _build_clutter_arm(stage, assets_root_used, arm_base)
print(f"clutter arm referenced from {usd_path_used} at base {arm_base}")

# ── Initial target placement (depends on mode) ────────────────────────────────
if args.mode == "distance":
    nominal_distances = np.linspace(DISTANCE_NEAR_M, DISTANCE_FAR_M, DISTANCE_N_POINTS)
    init_x, init_y, init_z, _ = _distance_target_center(float(nominal_distances[0]), args.target_height)
elif args.mode == "lateral":
    lateral_y_offsets = np.linspace(LATERAL_Y_MIN_M, LATERAL_Y_MAX_M, LATERAL_N_POINTS)
    init_x = SENSOR_POS_M[0] + LATERAL_DISTANCE_M
    init_y = SENSOR_POS_M[1] + float(lateral_y_offsets[0])
    init_z = SENSOR_POS_M[2]
else:  # "repeat"
    init_x = SENSOR_POS_M[0] + REPEAT_DISTANCE_M
    init_y = SENSOR_POS_M[1]
    init_z = SENSOR_POS_M[2]

Cube(
    TARGET_PATH,
    sizes=[TARGET_SIZE_M],
    positions=np.array([[init_x, init_y, init_z]]),
)
print(f"target Cube created at ({init_x:.4f}, {init_y:.4f}, {init_z:.4f}) (edge={TARGET_SIZE_M}m)")
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

# ── Output paths ───────────────────────────────────────────────────────────────
out_root = pathlib.Path(args.output_dir)
if args.mode == "distance":
    out_dir = out_root / f"distance_{args.pass_id}"
elif args.mode == "lateral":
    out_dir = out_root / "lateral"
else:
    out_dir = out_root / f"repeat_{args.pass_id}"
wf_dir = out_dir / "waveforms"
wf_dir.mkdir(parents=True, exist_ok=True)

points: list[dict] = []
n_drift_flagged = 0

# ── Mode-specific sweep ────────────────────────────────────────────────────────
if args.mode == "distance":
    for i, d in enumerate(nominal_distances):
        d = float(d)
        cx, cy, cz, true3d = _distance_target_center(d, args.target_height)
        _move_target(stage, cx, cy, cz)
        res = _measure_point(args.n_settle, args.n_measure)
        if not res["stationarity_ok"]:
            n_drift_flagged += 1

        wf_tag = f"point_{i:02d}"
        np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])
        np.save(wf_dir / f"{wf_tag}_rx0.npy", res["mean_rx0"])
        np.save(wf_dir / f"{wf_tag}_rx1.npy", res["mean_rx1"])

        row = {
            "point_index": i,
            "nominal_distance_m": d,
            "true_distance_3d_m": true3d,
            "target_x_m": cx, "target_y_m": cy, "target_z_m": cz,
            "peak_sample_idx": res["peak_sample_idx"],
            "early_energy": res["early_energy"],
            "rx0_early": res["rx0_early"],
            "rx1_early": res["rx1_early"],
            "point_drift": res["point_drift"],
            "stationarity_ok": res["stationarity_ok"],
            "waveform_tag": wf_tag,
        }
        points.append(row)
        print(f"[{i+1:02d}/{DISTANCE_N_POINTS}] d={d:.4f}m true3d={true3d:.4f}m "
              f"peak_idx={res['peak_sample_idx']:.1f} early_e={res['early_energy']:.6f} "
              f"drift={res['point_drift']:.4f} ok={res['stationarity_ok']}")

    csv_path = out_dir / "points.csv"
    fieldnames = ["point_index", "nominal_distance_m", "true_distance_3d_m",
                  "target_x_m", "target_y_m", "target_z_m",
                  "peak_sample_idx", "early_energy", "rx0_early", "rx1_early",
                  "point_drift", "stationarity_ok", "waveform_tag"]
    with csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(points)

elif args.mode == "lateral":
    for i, y_off in enumerate(lateral_y_offsets):
        y_off = float(y_off)
        cx = SENSOR_POS_M[0] + LATERAL_DISTANCE_M
        cy = SENSOR_POS_M[1] + y_off
        cz = SENSOR_POS_M[2]
        _move_target(stage, cx, cy, cz)
        res = _measure_point(args.n_settle, args.n_measure)
        if not res["stationarity_ok"]:
            n_drift_flagged += 1

        rx0e, rx1e = res["rx0_early"], res["rx1_early"]
        balance = (rx0e - rx1e) / (rx0e + rx1e + 1e-12) if math.isfinite(rx0e) and math.isfinite(rx1e) else float("nan")

        wf_tag = f"point_{i:02d}"
        np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])
        np.save(wf_dir / f"{wf_tag}_rx0.npy", res["mean_rx0"])
        np.save(wf_dir / f"{wf_tag}_rx1.npy", res["mean_rx1"])

        row = {
            "point_index": i,
            "y_offset_m": y_off,
            "target_x_m": cx, "target_y_m": cy, "target_z_m": cz,
            "rx0_early": rx0e,
            "rx1_early": rx1e,
            "balance": balance,
            "peak_sample_idx": res["peak_sample_idx"],
            "point_drift": res["point_drift"],
            "stationarity_ok": res["stationarity_ok"],
            "waveform_tag": wf_tag,
        }
        points.append(row)
        print(f"[{i+1:02d}/{LATERAL_N_POINTS}] y_offset={y_off:+.4f}m "
              f"rx0_early={rx0e:.6f} rx1_early={rx1e:.6f} balance={balance:+.4f} "
              f"drift={res['point_drift']:.4f} ok={res['stationarity_ok']}")

    csv_path = out_dir / "points.csv"
    fieldnames = ["point_index", "y_offset_m", "target_x_m", "target_y_m", "target_z_m",
                  "rx0_early", "rx1_early", "balance", "peak_sample_idx",
                  "point_drift", "stationarity_ok", "waveform_tag"]
    with csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(points)

else:  # "repeat"
    cx = SENSOR_POS_M[0] + REPEAT_DISTANCE_M
    cy = SENSOR_POS_M[1]
    cz = SENSOR_POS_M[2]
    _move_target(stage, cx, cy, cz)  # no-op move (already there); keeps procedure uniform
    res = _measure_point(args.n_settle, args.n_measure)
    if not res["stationarity_ok"]:
        n_drift_flagged += 1

    wf_tag = "point_00"
    np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])
    np.save(wf_dir / f"{wf_tag}_rx0.npy", res["mean_rx0"])
    np.save(wf_dir / f"{wf_tag}_rx1.npy", res["mean_rx1"])

    row = {
        "point_index": 0,
        "nominal_distance_m": REPEAT_DISTANCE_M,
        "target_x_m": cx, "target_y_m": cy, "target_z_m": cz,
        "peak_sample_idx": res["peak_sample_idx"],
        "early_energy": res["early_energy"],
        "rx0_early": res["rx0_early"],
        "rx1_early": res["rx1_early"],
        "point_drift": res["point_drift"],
        "stationarity_ok": res["stationarity_ok"],
        "waveform_tag": wf_tag,
        "pass_id": args.pass_id,
    }
    points.append(row)
    print(f"repeat point: peak_idx={res['peak_sample_idx']:.1f} early_e={res['early_energy']:.6f} "
          f"drift={res['point_drift']:.4f} ok={res['stationarity_ok']}")

    with (out_dir / "point.json").open("w") as f:
        json.dump(row, f, indent=2)

timeline.stop()

# ── meta.json (all modes) ─────────────────────────────────────────────────────
meta = {
    "mode": args.mode,
    "pass_id": args.pass_id,
    "target_height": args.target_height,
    "n_settle": args.n_settle,
    "n_measure": args.n_measure,
    "sensor_pos_m": list(SENSOR_POS_M),
    "target_size_m": TARGET_SIZE_M,
    "table_anchor_distance_m": TABLE_ANCHOR_DISTANCE_M,
    "arm_backset_m": ARM_BACKSET_M,
    "assets_root_used": assets_root_used,
    "usd_path_used": usd_path_used,
    "n_points": len(points),
    "n_drift_flagged": n_drift_flagged,
    "warmup_frames": _warmup_frames,
    "timestamp": datetime.datetime.now().isoformat(),
    "script": "s2_datasheet_runner.py",
}
with (out_dir / "meta.json").open("w") as f:
    json.dump(meta, f, indent=2)

print()
print(f"-> outputs saved under {out_dir}")
print(f"RESULT mode={args.mode} pass={args.pass_id} n_points={len(points)} n_drift_flagged={n_drift_flagged}")

simulation_app.close()
