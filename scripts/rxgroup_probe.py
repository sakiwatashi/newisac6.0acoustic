"""rxGroup probe: does splitting the two receivers into SEPARATE receiver
groups (g001:[0] / g002:[1]) make the WPM engine render them as spatially
distinct outputs?

Motivation chain (all falsified so far under the SINGLE-group config):
  - S2 lateral (2026-07-08): way-ordinal ENERGY balance carries no lateral
    info (Spearman rho=0.36) -> ILD dead.
  - 2026-07-10 offline: rx0/rx1 cross-correlation TIME lag is constant
    (~2.8 samples pipeline offset), r=0.002 vs lateral offset, mirror-
    symmetric -> TDOA dead.
  - GMO way id fields (tx,rx,ch) all zero -> receiver identity not encoded.
S2's report left exactly one untested lever: one rxGroup per receiver
("g001:[0], g002:[1] 配置或許可分離接收器,未驗證"). This probe tests it.

Design: minimal armfree scene (no robot/no table -- lateral encodability is a
sensor-engine question, not a scene question; the clean scene maximizes the
target echo, S1 Block A geometry). Static sensor at (0,0,0.65) facing +X;
0.10 m cube target at boresight height, base distance 0.8 m, swept laterally
y in [-0.15, +0.15], 13 points (same sweep shape as S2 lateral). Two modes
run as separate sessions:
    --mode single : original config (rxGroup g001:[0,1]) -- A/B control
    --mode dual   : rxGroup g001:[0] + g002:[1]          -- the hypothesis

Per point, per GMO way: waveform saved (.npy), peak_sample_idx, early_energy,
way id fields; plus pairwise sub-sample cross-correlation lag between the
first two ways. Pre-registered criterion (adjudicated OFFLINE from points.csv,
never by this script):
    rxgroup_lateral_encodable: in dual mode, EITHER
      |Spearman rho(energy_balance, y)| >= 0.9   (ILD revived), OR
      |Pearson r(pairwise_lag, y)|     >= 0.9    (TDOA revived).
    Additionally the single-mode run must remain non-encodable (sanity: the
    probe scene itself does not invent lateral info).

Five iron laws: measurement-only probe (laws 2/5 n/a: no control loop, no
oracle-fed decisions; target y is scene-build input recorded for evaluation).
Law 4: all way waveforms land as .npy. Law 3: criterion above, written before
any run. Law 1 (paired control): the single-vs-dual A/B is the pairing.

Usage:
    ./app/python.sh scripts/rxgroup_probe.py --mode single --output-dir runtime/outputs/rxgroup_probe_v1
    ./app/python.sh scripts/rxgroup_probe.py --mode dual   --output-dir runtime/outputs/rxgroup_probe_v1
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

parser = argparse.ArgumentParser(description="rxGroup separation probe (single vs dual receiver groups)")
parser.add_argument("--mode", type=str, required=True, choices=("single", "dual"))
parser.add_argument("--output-dir", type=str, required=True)
parser.add_argument("--base-distance", type=float, default=0.8)
parser.add_argument("--n-settle", type=int, default=40)
parser.add_argument("--n-measure", type=int, default=12)
parser.add_argument("--smoke", action="store_true", help="3 lateral points instead of 13")
args, _ = parser.parse_known_args()

SENSOR_POS = (0.0, 0.0, 0.65)
TARGET_X = None  # set below from base distance
TARGET_SIZE_M = 0.10
CENTER_FREQ_HZ = 40_000.0
MOUNT_SPACING_M = 0.10
TICK_RATE_HZ = 30.0
AZ_SPAN_DEG = 90.0
EL_SPAN_DEG = 90.0
TRACE_TREE_DEPTH = 2
Y_OFFSETS = [-0.15 + i * 0.025 for i in range(13)] if not args.smoke else [-0.15, 0.0, 0.15]

from isaacsim import SimulationApp  # noqa: E402
simulation_app = SimulationApp({"headless": True})

import numpy as np                                    # noqa: E402
import omni.replicator.core as rep                    # noqa: E402
import omni.timeline                                  # noqa: E402
import omni.usd                                       # noqa: E402
from isaacsim.core.experimental.objects import Cube    # noqa: E402
from isaacsim.sensors.experimental.rtx import (        # noqa: E402
    Acoustic, AcousticSensor, parse_generic_model_output_data,
)
from omni.replicator.core import Writer                # noqa: E402
from pxr import Gf, UsdGeom                             # noqa: E402


def _wpm_attrs(mode: str) -> dict:
    """Copy of rtx_acoustic_factory.default_wpm_attributes' output shape (the
    whitelisted factory stays untouched); ONLY the rxGroup lines differ
    between modes -- that is the entire experimental manipulation."""
    attrs = {
        "omni:sensor:WpmAcoustic:centerFrequency": float(CENTER_FREQ_HZ),
        "omni:sensor:WpmAcoustic:azSpanDeg": float(AZ_SPAN_DEG),
        "omni:sensor:WpmAcoustic:elSpanDeg": float(EL_SPAN_DEG),
        "omni:sensor:WpmAcoustic:traceTreeDepth": int(TRACE_TREE_DEPTH),
        "omni:sensor:WpmAcoustic:sensorMount:m001:position": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m001:rotation": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:position": (float(MOUNT_SPACING_M), 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:rotation": (0.0, 0.0, 0.0),
    }
    if mode == "single":
        attrs["omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices"] = [0, 1]
    else:
        attrs["omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices"] = [0]
        attrs["omni:sensor:WpmAcoustic:rxGroup:g002:receiverIndices"] = [1]
    return attrs


_buf: dict = {"latest": None}


def _extract_frame(gmo) -> dict | None:
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n == 0:
        return None
    amp_all = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(float).copy()
    # id-ish channels: x/y/z per element (z is channel id per rule 1-1; y observed as rx id)
    ids = {}
    for field in ("x", "y", "z"):
        try:
            ids[field] = np.ctypeslib.as_array(getattr(gmo, field), shape=(n,)).copy()
        except Exception:
            ids[field] = None
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    if num_spsgw <= 0 or n % num_spsgw != 0:
        return None
    n_ways = n // num_spsgw
    way_ids = []
    for w in range(n_ways):
        s = w * num_spsgw
        way_ids.append(tuple(
            (float(ids[f][s]) if ids[f] is not None else float("nan")) for f in ("x", "y", "z")
        ))
    return {"amp_all": amp_all, "num_spsgw": num_spsgw, "n_ways": n_ways,
            "way_ids": way_ids, "n_elements": n}


class RxGroupProbeWriter(Writer):
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
                return


def _ways(frame: dict) -> list[np.ndarray]:
    k = frame["num_spsgw"]
    return [frame["amp_all"][w * k:(w + 1) * k].copy() for w in range(frame["n_ways"])]


def _measure(n_settle: int, n_measure: int) -> dict:
    for _ in range(n_settle):
        simulation_app.update()
    acc: dict[int, list[np.ndarray]] = {}
    ids_seen: list = []
    n_valid = 0
    max_ways = 0
    for _ in range(n_measure * 2):  # two blocks worth, accumulated
        simulation_app.update()
        fr = _buf["latest"]
        if fr is None:
            continue
        n_valid += 1
        max_ways = max(max_ways, fr["n_ways"])
        ids_seen.append(fr["way_ids"])
        for w, wf in enumerate(_ways(fr)):
            acc.setdefault(w, []).append(wf)
    means = {}
    for w, wfs in acc.items():
        m = min(x.size for x in wfs)
        means[w] = np.mean(np.array([x[:m] for x in wfs]), axis=0)
    return {"means": means, "n_valid": n_valid, "max_ways": max_ways,
            "ids_example": ids_seen[-1] if ids_seen else []}


def _xcorr_lag(a: np.ndarray, b: np.ndarray) -> float:
    n = min(a.size, b.size)
    if n < 8:
        return float("nan")
    a = a[:n] - a[:n].mean()
    b = b[:n] - b[:n].mean()
    xc = np.correlate(a, b, "full")
    k = int(np.argmax(xc))
    if 0 < k < xc.size - 1:
        y0, y1, y2 = xc[k - 1], xc[k], xc[k + 1]
        d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-30)
    else:
        d = 0.0
    return float((k + d) - (n - 1))


# ── Scene ─────────────────────────────────────────────────────────────────────
print(f"=== rxgroup_probe.py === mode={args.mode} smoke={args.smoke}")
context = omni.usd.get_context()
context.new_stage()
stage = context.get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

TARGET_X = SENSOR_POS[0] + float(args.base_distance)
TARGET_PATH = "/World/target"
Cube(TARGET_PATH, sizes=[1.0],
     scales=np.array([[TARGET_SIZE_M, TARGET_SIZE_M, TARGET_SIZE_M]]),
     positions=np.array([[TARGET_X, 0.0, SENSOR_POS[2]]]))
print(f"target cube at ({TARGET_X:.3f}, 0, {SENSOR_POS[2]}) edge={TARGET_SIZE_M}")

acoustic = Acoustic(
    "/World/acoustic_sensor",
    tick_rate=float(TICK_RATE_HZ),
    aux_output_level="BASIC",
    translations=np.array(SENSOR_POS, dtype=float),
    attributes=_wpm_attrs(args.mode),
)
sensor = AcousticSensor(acoustic, annotators=[])
rep.WriterRegistry.register(RxGroupProbeWriter)
sensor.attach_writer("RxGroupProbeWriter")
print(f"sensor created with {args.mode} rxGroup config")

timeline = omni.timeline.get_timeline_interface()
timeline.play()

print("warmup (>=20 frames, max 80)...")
wf_count = 0
for _ in range(80):
    simulation_app.update()
    wf_count += 1
    if wf_count >= 20 and _buf["latest"] is not None:
        break
fr0 = _buf["latest"]
if fr0 is None:
    print("ABORT: sensor produced no data after warmup", flush=True)
    simulation_app.close()
    sys.exit(2)
print(f"warmup done ({wf_count} frames): n_elements={fr0['n_elements']} "
      f"n_ways={fr0['n_ways']} numSamplesPerSgw={fr0['num_spsgw']} way_ids={fr0['way_ids']}")

out_dir = pathlib.Path(args.output_dir) / args.mode
wf_dir = out_dir / "waveforms"
wf_dir.mkdir(parents=True, exist_ok=True)


def _move_target(y: float) -> None:
    prim = stage.GetPrimAtPath(TARGET_PATH)
    xf = UsdGeom.Xformable(prim)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(TARGET_X, y, SENSOR_POS[2]))
    else:
        xf.AddTranslateOp().Set(Gf.Vec3d(TARGET_X, y, SENSOR_POS[2]))


rows = []
for i, y in enumerate(Y_OFFSETS):
    _move_target(y)
    res = _measure(args.n_settle, args.n_measure)
    means = res["means"]
    tags = {}
    for w, wf in means.items():
        tag = f"p{i:02d}_way{w}"
        np.save(wf_dir / f"{tag}.npy", wf)
        tags[w] = tag
    row = {"point_index": i, "y_offset_m": y,
           "true_distance_3d_m": math.sqrt(args.base_distance ** 2 + y ** 2),
           "n_ways": res["max_ways"], "n_frames_valid": res["n_valid"],
           "way_ids": json.dumps(res["ids_example"])}
    for w in sorted(means):
        wf = means[w]
        row[f"way{w}_peak_idx"] = float(np.argmax(wf))
        row[f"way{w}_early_energy"] = float(np.sum(wf[:20] ** 2))
    if len(means) >= 2:
        ws = sorted(means)
        row["lag_way01"] = _xcorr_lag(means[ws[0]], means[ws[1]])
        e0, e1 = row[f"way{ws[0]}_early_energy"], row[f"way{ws[1]}_early_energy"]
        row["balance_way01"] = (e0 - e1) / max(e0 + e1, 1e-12)
    if len(means) >= 4:
        ws = sorted(means)
        row["lag_way23"] = _xcorr_lag(means[ws[2]], means[ws[3]])
        row["lag_way02"] = _xcorr_lag(means[ws[0]], means[ws[2]])
    rows.append(row)
    print(f"[{i+1}/{len(Y_OFFSETS)}] y={y:+.3f} n_ways={res['max_ways']} "
          f"ids={res['ids_example']} "
          f"lag01={row.get('lag_way01', float('nan')):+.3f} "
          f"bal01={row.get('balance_way01', float('nan')):+.4f}")

fields = sorted({k for r in rows for k in r}, key=lambda k: (k != "point_index", k))
with (out_dir / "points.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

meta = {"mode": args.mode, "smoke": args.smoke, "base_distance_m": args.base_distance,
        "y_offsets_m": Y_OFFSETS, "sensor_pos_m": list(SENSOR_POS),
        "target_size_m": TARGET_SIZE_M, "mount_spacing_m": MOUNT_SPACING_M,
        "n_settle": args.n_settle, "n_measure": args.n_measure,
        "criterion_text": "rxgroup_lateral_encodable: dual mode |Spearman rho(balance,y)|>=0.9 "
                           "OR |Pearson r(lag,y)|>=0.9; single mode must remain non-encodable. "
                           "Adjudicated OFFLINE by the main agent.",
        "timestamp": datetime.datetime.now().isoformat(),
        "script": "rxgroup_probe.py"}
with (out_dir / "meta.json").open("w") as f:
    json.dump(meta, f, indent=1)

timeline.stop()
print(f"-> {out_dir}/points.csv")
simulation_app.close()
