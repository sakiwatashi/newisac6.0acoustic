"""D1 1-DOF closed-loop approach runner (probe / closed / blind / open).

Full spec: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 7, "D1: 1-DOF closed
-loop approach", and the "對 D1 的輸入" section at the end of
docs/plan_v2/reports/S2_datasheet_report.md (D1 spec draft: scene, target
range, estimator, standoff, three-arm design, pre-registered criterion).

Skeleton borrowed wholesale from scripts/s2_datasheet_runner.py: argparse-
before-SimulationApp order, module-level writer buffer dict (`_buf`),
`_extract_frame` (numSamplesPerSgw stride reconstruction), `_per_rx_primary`
(way-ordinal grouping into per-RX waveforms), `_measure_block` (cross-frame
accumulation -- a single GMO frame does not reliably carry both mounts),
`_measure_point` (settle -> block A -> block B, point value = mean, plus the
A-vs-B drift audit), the table/table_arm clutter scene, and the
xformOp:translate rewrite technique (`_move_target` in s2_datasheet_runner.py,
itself borrowed from scripts/visibility_wpm_probe.py's validated
`_move_target`).

THE ONE NEW THING THIS SCRIPT DOES (D0): it rewrites the SENSOR prim's
xformOp:translate mid-session, which V2's Stage-0 architecture decision
(V2_HANDOFF_FOR_NEXT_AI.md Section 5.1) explicitly flagged as unvalidated
("感測器建立後是否追蹤 transform 未經驗證"). `--mode probe` is the D0
validation run for exactly this: it sweeps the SENSOR (not the target) over
13 known positions and regresses peak_sample_idx against the resulting known
3D distance, using the identical xformOp:translate technique already
validated for the TARGET prim. If that regression's r < 0.99, moving the
sensor mid-session is not behaving like moving the target did, and D1 must
fall back to the "rig moves as a whole" design instead (see
runtime/run_v2_d1_approach.sh's ABORT branch) -- this script does not
silently assume sensor-motion validity.

Five-iron-law header (docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md Section 4)
------------------------------------------------------------------------
  1. Paired control:
     not applicable to D1 in the S1 sense (with/without-target pairing) --
     D1 assumes the cell is already known-detectable from S1/S2 and measures
     closed-loop CONTROL behavior, not detectability. The analogous "pairing"
     here is the closed-vs-blind comparison (law 2 below).
  2. Information-ablation control:
     the `blind` arm runs the IDENTICAL measurement pipeline every step
     (same settle/measure cost, same GMO draw) but the estimator's usable
     output is forced to d_horiz_est=+inf before the stop decision, so blind
     NEVER stops on the estimate -- only the corridor/max-steps guards can
     end a blind episode. `open` is the even-blinder control: it performs NO
     measurement at all and walks straight to a fixed nominal position.
  3. Pre-registered criterion (written here BEFORE this script is ever run):
       d0_sensor_motion_valid : probe-mode live regression of peak_sample_idx
                                vs true_distance_3d_m (sensor swept, target
                                fixed) has r >= 0.99.
       d1_tracking_r_ge_0.9   : r(stop_sensor_x, target_x) over the CLOSED
                                arm's 30 episodes >= 0.9.
       d1_beats_blind         : closed arm's stop_error RMSE
                                (|stop_oracle_horiz_dist - standoff|) is
                                lower than blind's, AND a Welch two-sample
                                t-test on the two arms' stop_error samples
                                has p < 0.05.
     All three are computed ONLY by the companion offline analyzer,
     scripts/analyze_d1_approach.py, from the raw steps.csv / episodes.csv /
     points.csv this script writes -- never by this script itself, and never
     fed back into any control decision.
  4. Raw waveform landing:
     every measured point (probe sweep points, and every closed/blind step)
     saves its averaged primary-way waveform as .npy under waveforms/, so
     peak_sample_idx (and hence every downstream distance estimate) can be
     recomputed offline from raw samples. `open` performs no measurement, so
     it has no waveform to save (documented here, not a silent omission).
  5. acoustic_only exclusivity (THE rule this script is built around):
     target_x / oracle_horiz_dist are oracle-only quantities that exist
     PURELY to build the scene (target placement) and to annotate
     steps.csv/episodes.csv for offline evaluation. The control decision in
     the closed/blind step loop reads exactly one number, d_horiz_est
     (derived from peak_sample_idx via the pre-loaded S2 calibration), and
     compares it against --standoff. It never reads target_x, never reads
     oracle_horiz_dist, and the guardrails (corridor end at x>1.20 m,
     max-steps) are pure CLI-configured constants -- no oracle quantity ever
     enters a branch that changes sensor motion or exit conditions.

Startup self-calibration (every mode, before the scene is even built)
-----------------------------------------------------------------------
Reads runtime/outputs/v2_s2_datasheet/distance_tableh/points.csv (the S2
"target on table top" distance pass), keeps only stationarity_ok == True
rows, and fits an OLS line peak_sample_idx = slope * true_distance_3d_m +
intercept (pure stdlib, no numpy needed yet -- this happens BEFORE
SimulationApp is created, so a bad/missing calibration file aborts before any
GPU time is spent). Requires r >= 0.99, else SystemExit. The resulting
slope/intercept are used for the rest of the session as:

    d3d_est      = (peak_sample_idx - intercept) / slope
    d_horiz_est  = sqrt(max(d3d_est**2 - 0.20**2, 1e-6))

(0.20 m is the fixed sensor-height-minus-table-target-height offset, SENSOR_
POS_M[2] - TARGET_Z_M, matching the distance_tableh geometry the calibration
was fit against.)

CLI
---
    --mode {probe,closed,blind,open}   Required.
    --output-dir PATH                  Required.
    --n-episodes INT                   default 30 (closed/blind/open only).
    --seed INT                         default 20260708. random.Random(seed)
                                        draws n-episodes uniform target x
                                        positions in [0.45, 1.10] -- THE SAME
                                        draw regardless of --mode, so all
                                        three arms see the same 30 target
                                        positions (paired design across arms).
    --standoff FLOAT                   default 0.35 m.
    --step FLOAT                       default 0.05 m per control step.
    --max-steps INT                    default 40.

Scene (built once per session; probe/closed/blind/open all share it)
------------------------------------------------------------------------
    Sensor  : /World/acoustic_sensor, starts at (0, 0, 0.65) m, horizontal
              (identity orient, no xformOp:orient needed, matches S2).
              probe/closed/blind rewrite its xformOp:translate mid-session
              (see D0 note above); open also moves it once, directly to the
              fixed nominal position.
    Clutter : table (1.2 x 0.8 x 0.4 m, top face z=0.40) centered at
              x=0.775 so it spans roughly [0.175, 1.375] and comfortably
              covers the target range [0.45, 1.10] with standoff margin;
              UR10e static USD reference 0.10 m behind the sensor's START
              position (scene background, never re-anchored -- same
              "not a per-point physical support" note as S2's table).
    Target  : 0.10 m Cube, center resting on the table top (z=0.45).
              probe: fixed at x=1.0 for the whole probe sweep.
              closed/blind/open: moved once per episode to that episode's
              drawn target_x (xformOp:translate rewrite, never re-created,
              per visibility_wpm_probe._move_target).

Usage
-----
    ./app/python.sh scripts/d1_approach_runner.py \\
        --mode probe --output-dir runtime/outputs/v2_d1_approach
    ./app/python.sh scripts/d1_approach_runner.py \\
        --mode closed --output-dir runtime/outputs/v2_d1_approach \\
        --n-episodes 30 --seed 20260708 --standoff 0.35 --step 0.05 --max-steps 40
    ./app/python.sh scripts/d1_approach_runner.py \\
        --mode blind --output-dir runtime/outputs/v2_d1_approach
    ./app/python.sh scripts/d1_approach_runner.py \\
        --mode open --output-dir runtime/outputs/v2_d1_approach
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import pathlib
import random
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ── Argument parsing BEFORE SimulationApp (rule 4-1) ──────────────────────────
parser = argparse.ArgumentParser(
    description="D1 1-DOF closed-loop approach (probe / closed / blind / open)."
)
parser.add_argument("--mode", type=str, required=True,
                     choices=("probe", "closed", "blind", "open"),
                     help="probe = D0 sensor-motion validation sweep; "
                          "closed/blind/open = D1 three-arm episodes")
parser.add_argument("--output-dir", type=str, required=True,
                     help="Output root; a mode-specific sub-directory is created underneath")
parser.add_argument("--n-episodes", type=int, default=30,
                     help="Episodes per session (closed/blind/open only)")
parser.add_argument("--seed", type=int, default=20260708,
                     help="random.Random(seed) draws the SAME n-episodes target x "
                          "positions for all three arms (paired design)")
parser.add_argument("--standoff", type=float, default=0.35,
                     help="Stop when d_horiz_est <= standoff (m)")
parser.add_argument("--step", type=float, default=0.05,
                     help="Sensor forward step size (m) per control iteration")
parser.add_argument("--max-steps", type=int, default=40,
                     help="Guard: stop an episode after this many measurements")
args, _ = parser.parse_known_args()

# ── Physical / scene constants ────────────────────────────────────────────────
N_SETTLE = 40
N_MEASURE = 12
STATIONARITY_DRIFT_MAX = 0.05  # same threshold as s2_datasheet_runner.py
N_EARLY = 20

SENSOR_PATH = "/World/acoustic_sensor"
TARGET_PATH = "/World/target"
TABLE_PATH = "/World/clutter_table"
ARM_PATH = "/World/clutter_arm"

SENSOR_POS_M = (0.0, 0.0, 0.65)   # home / start position
TARGET_SIZE_M = 0.10
TARGET_Z_M = 0.45                 # target rests on the table top
HEIGHT_DIFF_M = SENSOR_POS_M[2] - TARGET_Z_M  # 0.20, matches S2 distance_tableh geometry

TABLE_WIDTH_M = 1.2
TABLE_DEPTH_M = 0.8
TABLE_HEIGHT_M = 0.4               # top face at z = 0.40
TABLE_CENTER_X_M = 0.775           # spans ~[0.175, 1.375], covers target range with margin
ARM_BACKSET_M = 0.10                # arm base this far behind sensor's START x

TARGET_X_MIN_M = 0.45
TARGET_X_MAX_M = 1.10
CORRIDOR_END_X_M = 1.20             # guard: sensor_x beyond this aborts an episode

PROBE_TARGET_X_M = 1.0
PROBE_SENSOR_X_START_M = 0.0
PROBE_SENSOR_X_END_M = 0.60
PROBE_STEP_M = 0.05                 # 13 points inclusive of both ends

CENTER_FREQ_HZ = 40_000.0
MOUNT_SPACING_M = 0.10
TICK_RATE_HZ = 30.0
AZ_SPAN_DEG = 90.0
EL_SPAN_DEG = 90.0
TRACE_TREE_DEPTH = 2

CALIB_CSV_PATH = REPO_ROOT / "runtime" / "outputs" / "v2_s2_datasheet" / "distance_tableh" / "points.csv"
CALIB_R_MIN = 0.99


# ── Pure-stdlib OLS (used both for the startup calibration load, BEFORE
#    SimulationApp/numpy exist, and again for the probe-mode live regression
#    after numpy is available -- kept numpy-free throughout for one code path) ──
def _ols_pure(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """y = slope*x + intercept OLS fit. Returns (slope, intercept, pearson_r);
    NaNs if fewer than 2 points or zero variance in x or y."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return float("nan"), float("nan"), float("nan")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx <= 0.0:
        return float("nan"), float("nan"), float("nan")
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    syy = sum((y - mean_y) ** 2 for y in ys)
    r = sxy / math.sqrt(sxx * syy) if syy > 0.0 else float("nan")
    return slope, intercept, r


def _load_calibration(csv_path: pathlib.Path) -> tuple[float, float, float, int]:
    """Load the S2 distance_tableh points.csv, keep stationarity_ok==True
    rows, OLS-fit peak_sample_idx vs true_distance_3d_m. Returns
    (slope, intercept, r, n_kept)."""
    if not csv_path.exists():
        raise SystemExit(
            f"ABORT: calibration source not found: {csv_path}\n"
            "Run the S2 distance_tableh pass first "
            "(bash runtime/run_v2_s2_datasheet.sh) before D1."
        )
    xs: list[float] = []
    ys: list[float] = []
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("stationarity_ok", "")).strip().lower() not in ("true", "1"):
                continue
            try:
                x = float(row["true_distance_3d_m"])
                y = float(row["peak_sample_idx"])
            except (KeyError, TypeError, ValueError):
                continue
            xs.append(x)
            ys.append(y)
    slope, intercept, r = _ols_pure(xs, ys)
    return slope, intercept, r, len(xs)


print("=== d1_approach_runner.py: startup self-calibration ===")
print(f"calib source: {CALIB_CSV_PATH}")
CALIB_SLOPE, CALIB_INTERCEPT, CALIB_R, CALIB_N = _load_calibration(CALIB_CSV_PATH)
print(f"calib n_kept={CALIB_N}  slope={CALIB_SLOPE:.4f} samples/m  "
      f"intercept={CALIB_INTERCEPT:.4f} samples  r={CALIB_R}")
if not (math.isfinite(CALIB_R) and CALIB_R >= CALIB_R_MIN):
    raise SystemExit(
        f"ABORT: calibration r={CALIB_R} < required {CALIB_R_MIN} "
        f"(source: {CALIB_CSV_PATH}). Re-run/inspect S2 distance_tableh before D1."
    )
print()

if args.mode in ("closed", "blind", "open"):
    if args.n_episodes < 1:
        raise SystemExit("--n-episodes must be >= 1")
    _rng = random.Random(args.seed)
    TARGET_POSITIONS_M = [_rng.uniform(TARGET_X_MIN_M, TARGET_X_MAX_M) for _ in range(args.n_episodes)]
else:
    TARGET_POSITIONS_M = None


def _estimate_distance(peak_idx: float) -> tuple[float, float]:
    """d3d_est=(peak_idx-intercept)/slope; d_horiz_est=sqrt(max(d3d_est**2-0.2**2,1e-6)).
    Returns (d3d_est, d_horiz_est); d_horiz_est is +inf if peak_idx/d3d_est is
    non-finite (never lets a bad measurement look like "arrived")."""
    if not math.isfinite(peak_idx):
        return float("nan"), float("inf")
    d3d_est = (peak_idx - CALIB_INTERCEPT) / CALIB_SLOPE
    if not math.isfinite(d3d_est):
        return float("nan"), float("inf")
    d_horiz_est = math.sqrt(max(d3d_est ** 2 - HEIGHT_DIFF_M ** 2, 1e-6))
    return d3d_est, d_horiz_est


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

# ── Module-level data buffer (Writer -> main loop communication, rule 4-2) ────
_buf: dict = {"latest": None}


def _extract_frame(gmo) -> dict | None:
    """See s2_datasheet_runner.py._extract_frame -- identical logic, copied
    verbatim (full scalar array + stride + rx id at each way's start index)."""
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

    if os.environ.get("D1_DEBUG_IDS") == "1" and not _buf.get("ids_printed"):
        tx_all = np.ctypeslib.as_array(gmo.x, shape=(n,))
        ch_all = np.ctypeslib.as_array(gmo.z, shape=(n,))
        keys = [(int(tx_all[w * num_spsgw]), int(rx_all[w * num_spsgw]), int(ch_all[w * num_spsgw]))
                for w in range(n_ways)]
        print(f"D1_DEBUG_IDS frame: n={n} num_spsgw={num_spsgw} n_ways={n_ways} "
              f"(tx,rx,ch) at way starts = {keys}", flush=True)
        _buf["ids_printed"] = True

    return {
        "amp_all": amp_all,
        "num_spsgw": num_spsgw,
        "way_start_rx_ids": way_start_rx_ids,
        "n_elements": n,
    }


class D1ApproachWriter(Writer):
    """Parses GMO each frame and stores the full-fidelity frame dict in the
    module-level _buf (rule 4-2). Identical to s2_datasheet_runner.py's
    S2DatasheetWriter."""

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
    """See s2_datasheet_runner.py._per_rx_primary: way-ordinal grouping (the
    GMO id fields are all-zero in this rxGroup config; way ordinal 0/1 stands
    in for the two receiver mounts). Returns {ordinal: waveform}."""
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
    against WPM ray tracing by visibility_wpm_probe._move_target. The target
    is NEVER re-created between points/episodes -- only this op is rewritten."""
    prim = stage.GetPrimAtPath(TARGET_PATH)
    xformable = UsdGeom.Xformable(prim)
    ops_by_name = {op.GetOpName(): op for op in xformable.GetOrderedXformOps()}
    key = "xformOp:translate"
    if key in ops_by_name:
        ops_by_name[key].Set(Gf.Vec3d(x, y, z))
    else:
        xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))


def _move_sensor(stage, x: float, y: float = 0.0, z: float = SENSOR_POS_M[2]) -> None:
    """Rewrite SENSOR_PATH's xformOp:translate (world frame), SAME technique
    as _move_target above. THIS IS THE UNVALIDATED-UNTIL-PROBE-PASSES
    operation this whole script exists to exercise (see module docstring's D0
    note) -- the sensor prim is never re-created, only this op is rewritten,
    and every call is followed by a settle (via _measure_point, or an
    explicit settle loop for --mode open which never measures)."""
    prim = stage.GetPrimAtPath(SENSOR_PATH)
    xformable = UsdGeom.Xformable(prim)
    ops_by_name = {op.GetOpName(): op for op in xformable.GetOrderedXformOps()}
    key = "xformOp:translate"
    if key in ops_by_name:
        ops_by_name[key].Set(Gf.Vec3d(x, y, z))
    else:
        xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))


# ── Frame-level feature helpers (identical to s2_datasheet_runner.py) ─────────
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
    """See s2_datasheet_runner.py._measure_block: advances n_frames, ACCUMULATES
    per-RX primary waveforms across frames (a single GMO frame does not
    reliably carry both mounts)."""
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
    """See s2_datasheet_runner.py._measure_point: settle -> block A -> block B
    (no extra settle between) -> point value = (A+B)/2, plus the A-vs-B drift
    audit. Any prim move (target OR, new in D1, sensor) must be followed by
    exactly this call so the settle is never skipped."""
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
        "point_drift": point_drift,
        "stationarity_ok": stationarity_ok,
        "n_frames_valid_a": block_a["n_frames_valid"],
        "n_frames_valid_b": block_b["n_frames_valid"],
    }


# ── Scene construction ─────────────────────────────────────────────────────────
print("=== d1_approach_runner.py ===")
print(f"mode={args.mode}  n_episodes={args.n_episodes if args.mode != 'probe' else '-'}  seed={args.seed}")
print(f"standoff={args.standoff}  step={args.step}  max_steps={args.max_steps}")
print(f"n_settle={N_SETTLE}  n_measure={N_MEASURE}")
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
rep.WriterRegistry.register(D1ApproachWriter)
sensor.attach_writer("D1ApproachWriter")
# Sensor pitch is 0 (horizontal); identity xformOp:orient already matches
# this (per S2's note), so we never touch xformOp:orient. Unlike S2, the
# sensor's xformOp:translate IS touched mid-session here (via _move_sensor) --
# that is exactly the D0 behavior this script validates.

_build_table(stage, (TABLE_CENTER_X_M, SENSOR_POS_M[1]))
print(f"clutter table built, top-face center at x={TABLE_CENTER_X_M:.3f}, y={SENSOR_POS_M[1]:.3f} "
      f"(spans x in [{TABLE_CENTER_X_M - TABLE_WIDTH_M/2:.3f}, {TABLE_CENTER_X_M + TABLE_WIDTH_M/2:.3f}])")

assets_root_used = get_assets_root_path()
if not assets_root_used:
    raise RuntimeError("get_assets_root_path() returned empty/None; cannot spawn clutter arm asset")
arm_base = (SENSOR_POS_M[0] - ARM_BACKSET_M, SENSOR_POS_M[1], 0.0)
usd_path_used = _build_clutter_arm(stage, assets_root_used, arm_base)
print(f"clutter arm referenced from {usd_path_used} at base {arm_base} (fixed; not re-anchored to sensor moves)")

# ── Initial target placement (depends on mode) ────────────────────────────────
if args.mode == "probe":
    init_target_x = PROBE_TARGET_X_M
else:
    init_target_x = TARGET_POSITIONS_M[0]

Cube(
    TARGET_PATH,
    sizes=[TARGET_SIZE_M],
    positions=np.array([[init_target_x, 0.0, TARGET_Z_M]]),
)
print(f"target Cube created at ({init_target_x:.4f}, 0.0000, {TARGET_Z_M:.4f}) (edge={TARGET_SIZE_M}m)")
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
out_dir = out_root / args.mode
wf_dir = out_dir / "waveforms"
wf_dir.mkdir(parents=True, exist_ok=True)

n_drift_flagged = 0

# ═══════════════════════════════════════════════════════════════════════════
# probe mode (D0): sweep the SENSOR, target fixed, regress peak_idx vs known
# 3D distance. This is the validation gate for moving the sensor mid-session.
# ═══════════════════════════════════════════════════════════════════════════
if args.mode == "probe":
    n_points = int(round((PROBE_SENSOR_X_END_M - PROBE_SENSOR_X_START_M) / PROBE_STEP_M)) + 1
    probe_rows: list[dict] = []
    for i in range(n_points):
        sx = PROBE_SENSOR_X_START_M + i * PROBE_STEP_M
        _move_sensor(stage, sx, 0.0, SENSOR_POS_M[2])
        res = _measure_point(N_SETTLE, N_MEASURE)
        if not res["stationarity_ok"]:
            n_drift_flagged += 1
        true3d = math.sqrt((PROBE_TARGET_X_M - sx) ** 2 + HEIGHT_DIFF_M ** 2)

        wf_tag = f"point_{i:02d}"
        np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])

        row = {
            "point_index": i,
            "sensor_x": sx,
            "true_distance_3d_m": true3d,
            "peak_sample_idx": res["peak_sample_idx"],
            "point_drift": res["point_drift"],
            "stationarity_ok": res["stationarity_ok"],
            "waveform_tag": wf_tag,
        }
        probe_rows.append(row)
        print(f"[{i+1:02d}/{n_points}] sensor_x={sx:.4f}m true3d={true3d:.4f}m "
              f"peak_idx={res['peak_sample_idx']:.1f} drift={res['point_drift']:.4f} "
              f"ok={res['stationarity_ok']}")

    csv_path = out_dir / "points.csv"
    fieldnames = ["point_index", "sensor_x", "true_distance_3d_m", "peak_sample_idx",
                  "point_drift", "stationarity_ok", "waveform_tag"]
    with csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(probe_rows)

    kept_x = [r["true_distance_3d_m"] for r in probe_rows if r["stationarity_ok"]]
    kept_y = [r["peak_sample_idx"] for r in probe_rows if r["stationarity_ok"]]
    probe_slope, probe_intercept, probe_r = _ols_pure(kept_x, kept_y)

    print()
    print(f"probe regression: n_kept={len(kept_x)}/{n_points}  "
          f"slope={probe_slope}  intercept={probe_intercept}  r={probe_r}")
    print(f"PROBE_RESULT r={probe_r} slope={probe_slope}")

    n_episodes_meta = None

# ═══════════════════════════════════════════════════════════════════════════
# closed / blind / open modes: n_episodes episodes, same target_x sequence
# ═══════════════════════════════════════════════════════════════════════════
else:
    episode_rows: list[dict] = []
    step_rows: list[dict] = []

    for ep_idx, target_x in enumerate(TARGET_POSITIONS_M):
        _move_target(stage, target_x, 0.0, TARGET_Z_M)
        _move_sensor(stage, 0.0, 0.0, SENSOR_POS_M[2])  # home; settle happens below

        if args.mode == "open":
            # No measurement at all: walk straight to the fixed nominal
            # position, oracle-blind by construction (never even queries the
            # estimator). Needs its own explicit settle since no
            # _measure_point call provides one.
            nominal_x = (TARGET_X_MIN_M + TARGET_X_MAX_M) / 2.0 - args.standoff
            for _ in range(N_SETTLE):
                simulation_app.update()
            _move_sensor(stage, nominal_x, 0.0, SENSOR_POS_M[2])
            for _ in range(N_SETTLE):
                simulation_app.update()

            oracle_horiz_dist = target_x - nominal_x
            step_rows.append({
                "episode": ep_idx, "step": 0, "sensor_x": nominal_x,
                "peak_idx": float("nan"), "d3d_est": float("nan"), "d_horiz_est": float("nan"),
                "oracle_horiz_dist": oracle_horiz_dist, "drift": float("nan"),
                "stationarity_ok": "", "waveform_tag": "",
            })
            episode_rows.append({
                "episode": ep_idx, "target_x": target_x,
                "stop_sensor_x": nominal_x, "stop_oracle_horiz_dist": oracle_horiz_dist,
                "n_steps": 1, "reason": "open_fixed",
            })
            print(f"[ep {ep_idx+1:02d}/{len(TARGET_POSITIONS_M)}] mode=open target_x={target_x:.4f} "
                  f"-> fixed sensor_x={nominal_x:.4f} oracle_horiz_dist={oracle_horiz_dist:+.4f}")
            continue

        # closed / blind: for-loop over at most --max-steps measurements; the
        # `else` clause on the for-loop fires only if it runs to completion
        # without `break`, i.e. exactly the max_steps guard condition.
        sensor_x = 0.0
        stop_reason = None
        stop_sensor_x = sensor_x
        ep_step_rows: list[dict] = []

        for step_idx in range(args.max_steps):
            res = _measure_point(N_SETTLE, N_MEASURE)
            if not res["stationarity_ok"]:
                n_drift_flagged += 1
            peak_idx = res["peak_sample_idx"]
            d3d_est, d_horiz_est_real = _estimate_distance(peak_idx)
            # Information-ablation control (law 2): blind forces the USABLE
            # estimate to +inf; d3d_est (informational only) is left as the
            # real computed value so the raw pipeline output is still on
            # record, but the control decision below reads d_horiz_est, which
            # can never trigger a standoff stop for blind.
            d_horiz_est = float("inf") if args.mode == "blind" else d_horiz_est_real

            oracle_horiz_dist = target_x - sensor_x  # RECORD ONLY -- never read by control

            wf_tag = f"ep{ep_idx:03d}_step{step_idx:03d}"
            np.save(wf_dir / f"{wf_tag}_primary.npy", res["mean_primary"])

            ep_step_rows.append({
                "episode": ep_idx, "step": step_idx, "sensor_x": sensor_x,
                "peak_idx": peak_idx, "d3d_est": d3d_est, "d_horiz_est": d_horiz_est,
                "oracle_horiz_dist": oracle_horiz_dist, "drift": res["point_drift"],
                "stationarity_ok": res["stationarity_ok"], "waveform_tag": wf_tag,
            })
            stop_sensor_x = sensor_x

            if d_horiz_est <= args.standoff:
                stop_reason = "standoff_est"
                break

            next_x = sensor_x + args.step
            if next_x > CORRIDOR_END_X_M:
                stop_reason = "corridor_end"
                break

            sensor_x = next_x
            _move_sensor(stage, sensor_x, 0.0, SENSOR_POS_M[2])
        else:
            stop_reason = "max_steps"
            # stop_sensor_x already holds the last measured position

        step_rows.extend(ep_step_rows)
        stop_oracle_horiz_dist = target_x - stop_sensor_x
        episode_rows.append({
            "episode": ep_idx, "target_x": target_x,
            "stop_sensor_x": stop_sensor_x, "stop_oracle_horiz_dist": stop_oracle_horiz_dist,
            "n_steps": len(ep_step_rows), "reason": stop_reason,
        })
        print(f"[ep {ep_idx+1:02d}/{len(TARGET_POSITIONS_M)}] mode={args.mode} target_x={target_x:.4f} "
              f"-> stop_sensor_x={stop_sensor_x:.4f} n_steps={len(ep_step_rows)} reason={stop_reason} "
              f"stop_oracle_horiz_dist={stop_oracle_horiz_dist:+.4f}")

    steps_csv_path = out_dir / "steps.csv"
    step_fieldnames = ["episode", "step", "sensor_x", "peak_idx", "d3d_est", "d_horiz_est",
                        "oracle_horiz_dist", "drift", "stationarity_ok", "waveform_tag"]
    with steps_csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=step_fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(step_rows)

    episodes_csv_path = out_dir / "episodes.csv"
    episode_fieldnames = ["episode", "target_x", "stop_sensor_x", "stop_oracle_horiz_dist",
                          "n_steps", "reason"]
    with episodes_csv_path.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=episode_fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(episode_rows)

    n_episodes_meta = len(episode_rows)
    print()
    print(f"RESULT mode={args.mode} episodes={n_episodes_meta}")

timeline.stop()

# ── meta.json (all modes) ─────────────────────────────────────────────────────
meta = {
    "mode": args.mode,
    "seed": args.seed,
    "n_episodes": args.n_episodes if args.mode != "probe" else None,
    "standoff_m": args.standoff,
    "step_m": args.step,
    "max_steps": args.max_steps,
    "n_settle": N_SETTLE,
    "n_measure": N_MEASURE,
    "calib_source": str(CALIB_CSV_PATH),
    "calib_slope_sample_per_m": CALIB_SLOPE,
    "calib_intercept_samples": CALIB_INTERCEPT,
    "calib_r": CALIB_R,
    "calib_n_kept": CALIB_N,
    "sensor_pos_m": list(SENSOR_POS_M),
    "target_size_m": TARGET_SIZE_M,
    "target_z_m": TARGET_Z_M,
    "height_diff_m": HEIGHT_DIFF_M,
    "table_center_x_m": TABLE_CENTER_X_M,
    "arm_backset_m": ARM_BACKSET_M,
    "corridor_end_x_m": CORRIDOR_END_X_M,
    "assets_root_used": assets_root_used,
    "usd_path_used": usd_path_used,
    "warmup_frames": _warmup_frames,
    "n_drift_flagged": n_drift_flagged,
    "timestamp": datetime.datetime.now().isoformat(),
    "script": "d1_approach_runner.py",
}
with (out_dir / "meta.json").open("w") as f:
    json.dump(meta, f, indent=2)

print()
print(f"-> outputs saved under {out_dir}")

simulation_app.close()
