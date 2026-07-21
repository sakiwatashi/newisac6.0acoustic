#!/usr/bin/env python3
"""P0 optional GPU capture: fixed sensor, no arm, range × with/without, full GMO dump.

Does NOT replace offline audit (scripts/p0_gmo_chain_offline_audit.py).
Purpose: archive one complete GMO frame's raw fields + per-way arrays for
examiner inspection.

Scene (minimal):
  - Sensor fixed at (0, 0, 0.65), level pitch
  - Single 0.10 m Cube on boresight (no table, no arm)
  - Distances default: 0.2, 0.4, 0.6, 0.8, 1.0 m
  - Each distance: measure with target, then remove, measure without

Outputs under --output-dir (default runtime/outputs/p0_fixed_sensor_gmo_dump/):
  meta.json
  points.csv
  frames/<tag>_raw.npz   # scalar,x,y,z,timeOffsetNs,numSamplesPerSgw,numElements,ways
  frames/<tag>_way{i}.npy

Usage:
  source scripts/env_host_isolated.sh   # if used on this host
  ./app/python.sh scripts/p0_fixed_sensor_gmo_dump.py
  ./app/python.sh scripts/p0_fixed_sensor_gmo_dump.py --distances 0.3,0.6,0.9 --n-settle 40
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

# ── argparse BEFORE SimulationApp (Isaac pattern) ────────────────────────────
parser = argparse.ArgumentParser(description="P0 fixed-sensor GMO dump (optional).")
parser.add_argument("--output-dir", type=str, default="runtime/outputs/p0_fixed_sensor_gmo_dump")
parser.add_argument("--distances", type=str, default="0.2,0.4,0.6,0.8,1.0")
parser.add_argument("--n-settle", type=int, default=40)
parser.add_argument("--n-measure", type=int, default=12)
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--smoke", action="store_true", help="Single distance 0.5 m only")
args, _unknown = parser.parse_known_args()

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": bool(args.headless)})

import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.timeline  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.objects import Cube  # noqa: E402
from isaacsim.sensors.experimental.rtx import (  # noqa: E402
    Acoustic,
    AcousticSensor,
    parse_generic_model_output_data,
)
from omni.replicator.core import Writer  # noqa: E402
from pxr import UsdGeom  # noqa: E402

from rtx_acoustic_factory import create_passport_acoustic  # noqa: E402

CENTER_FREQ_HZ = 40_000.0
MOUNT_SPACING_M = 0.10
TICK_RATE_HZ = 30.0
SENSOR_PATH = "/World/acoustic_sensor"
TARGET_PATH = "/World/target"
SENSOR_POS = (0.0, 0.0, 0.65)
TARGET_SIZE = 0.10

_buf: dict = {"latest": None}


class P0GmoDumpWriter(Writer):
    def __init__(self):
        self.data_structure = "renderProduct"
        self.annotators = [rep.annotators.get("GenericModelOutput")]

    def write(self, data):
        if "renderProducts" not in data:
            return
        for _name, rp in data["renderProducts"].items():
            raw = rp.get("GenericModelOutput")
            if isinstance(raw, dict):
                raw = raw.get("data")
            gmo = parse_generic_model_output_data(raw)
            if int(getattr(gmo, "numElements", 0) or 0) == 0:
                continue
            _buf["latest"] = gmo


def _copy_gmo(gmo) -> dict | None:
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n <= 0:
        return None
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    scalar = np.ctypeslib.as_array(gmo.scalar, shape=(n,)).astype(np.float64).copy()
    x = np.ctypeslib.as_array(gmo.x, shape=(n,)).astype(np.float64).copy()
    y = np.ctypeslib.as_array(gmo.y, shape=(n,)).astype(np.float64).copy()
    z = np.ctypeslib.as_array(gmo.z, shape=(n,)).astype(np.float64).copy()
    tof = np.ctypeslib.as_array(gmo.timeOffsetNs, shape=(n,)).astype(np.float64).copy()
    ways = []
    if num_spsgw > 0 and n % num_spsgw == 0:
        n_ways = n // num_spsgw
        for w in range(n_ways):
            s = w * num_spsgw
            ways.append(
                {
                    "way_index": w,
                    "tx0": int(x[s]),
                    "rx0": int(y[s]),
                    "ch0": int(z[s]),
                    "amp": scalar[s : s + num_spsgw].copy(),
                }
            )
    return {
        "numElements": n,
        "numSamplesPerSgw": num_spsgw,
        "scalar": scalar,
        "x": x,
        "y": y,
        "z": z,
        "timeOffsetNs": tof,
        "ways": ways,
        "timestampNs": int(getattr(gmo, "timestampNs", 0) or 0),
    }


def _step(n: int):
    for _ in range(n):
        simulation_app.update()


def _wait_gmo(max_frames: int = 90):
    _buf["latest"] = None
    for _ in range(max_frames):
        simulation_app.update()
        if _buf["latest"] is not None:
            return _buf["latest"]
    return None


def _measure_stack(n_settle: int, n_measure: int) -> dict | None:
    _step(n_settle)
    frames = []
    for _ in range(n_measure):
        gmo = _wait_gmo()
        if gmo is None:
            continue
        fr = _copy_gmo(gmo)
        if fr is not None:
            frames.append(fr)
    if not frames:
        return None
    # mean primary = way with highest mean |peak| across frames, per way ordinal
    n_ways = len(frames[0]["ways"])
    if n_ways == 0:
        return {"frames": frames, "mean_ways": [], "peak_idx": float("nan"), "primary_way": -1}
    mean_ways = []
    for w in range(n_ways):
        stack = np.stack([f["ways"][w]["amp"] for f in frames if len(f["ways"]) > w], axis=0)
        mean_ways.append(stack.mean(axis=0))
    peaks = [float(np.max(np.abs(mw))) for mw in mean_ways]
    primary = int(np.argmax(peaks))
    pk = int(np.argmax(np.abs(mean_ways[primary])))
    return {
        "frames": frames,
        "mean_ways": mean_ways,
        "peak_idx": float(pk),
        "primary_way": primary,
        "n_frames": len(frames),
    }


def _set_target(stage, distance_m: float | None):
    """Create/move target or remove. distance_m None => remove."""
    if stage.GetPrimAtPath(TARGET_PATH):
        stage.RemovePrim(TARGET_PATH)
    if distance_m is None:
        return
    Cube(
        TARGET_PATH,
        positions=np.array([float(distance_m), 0.0, float(SENSOR_POS[2])], dtype=float),
        scales=np.array([TARGET_SIZE, TARGET_SIZE, TARGET_SIZE], dtype=float),
    )


def main() -> int:
    out = pathlib.Path(args.output_dir)
    if not out.is_absolute():
        out = REPO / out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    if args.smoke:
        distances = [0.5]
    else:
        distances = [float(x) for x in args.distances.split(",") if x.strip()]

    # empty stage + sensor
    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    # place sensor via Acoustic translations
    acoustic, sensor = create_passport_acoustic(
        SENSOR_PATH,
        Acoustic=Acoustic,
        AcousticSensor=AcousticSensor,
        np=np,
        tick_rate_hz=TICK_RATE_HZ,
        center_frequency_hz=CENTER_FREQ_HZ,
        sensor_local_offset_m=SENSOR_POS,
        mount_spacing_m=MOUNT_SPACING_M,
    )
    rep.WriterRegistry.register(P0GmoDumpWriter)
    sensor.attach_writer("P0GmoDumpWriter")

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    _step(30)  # warmup

    # version meta
    try:
        import carb

        app_ver = str(carb.settings.get_settings().get("/app/version") or "")
    except Exception:
        app_ver = ""

    meta = {
        "script": "p0_fixed_sensor_gmo_dump.py",
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "sensor_pos_m": list(SENSOR_POS),
        "mount_spacing_m": MOUNT_SPACING_M,
        "center_frequency_hz": CENTER_FREQ_HZ,
        "target_size_m": TARGET_SIZE,
        "n_settle": args.n_settle,
        "n_measure": args.n_measure,
        "distances_m": distances,
        "app_version_setting": app_ver,
        "note": "Optional P0 raw dump; offline audit is authoritative for pass/fail.",
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    rows = []
    for d in distances:
        for cond, dist_arg in (("with", d), ("without", None)):
            tag = f"d{d:.2f}_{cond}".replace(".", "p")
            print(f"=== {tag} ===", flush=True)
            _set_target(stage, dist_arg)
            _step(5)
            res = _measure_stack(args.n_settle, args.n_measure)
            if res is None or not res["frames"]:
                print(f"WARN: no GMO for {tag}", flush=True)
                rows.append(
                    {
                        "tag": tag,
                        "distance_m": d,
                        "condition": cond,
                        "peak_idx": "",
                        "primary_way": "",
                        "n_frames": 0,
                        "num_spsgw": "",
                        "n_ways": "",
                    }
                )
                continue
            # save last raw frame fully + mean ways
            last = res["frames"][-1]
            np.savez_compressed(
                frames_dir / f"{tag}_raw.npz",
                scalar=last["scalar"],
                x=last["x"],
                y=last["y"],
                z=last["z"],
                timeOffsetNs=last["timeOffsetNs"],
                numSamplesPerSgw=np.array([last["numSamplesPerSgw"]]),
                numElements=np.array([last["numElements"]]),
                timestampNs=np.array([last["timestampNs"]]),
            )
            for i, mw in enumerate(res["mean_ways"]):
                np.save(frames_dir / f"{tag}_way{i}_mean.npy", mw)
            # also per-way from last frame
            for w in last["ways"]:
                np.save(frames_dir / f"{tag}_way{w['way_index']}_last.npy", w["amp"])
            # ids summary
            id_summary = [
                {"way": w["way_index"], "tx0": w["tx0"], "rx0": w["rx0"], "ch0": w["ch0"]}
                for w in last["ways"]
            ]
            (frames_dir / f"{tag}_ids.json").write_text(json.dumps(id_summary, indent=2))
            rows.append(
                {
                    "tag": tag,
                    "distance_m": d,
                    "condition": cond,
                    "peak_idx": res["peak_idx"],
                    "primary_way": res["primary_way"],
                    "n_frames": res["n_frames"],
                    "num_spsgw": last["numSamplesPerSgw"],
                    "n_ways": len(last["ways"]),
                    "timeOffsetNs_all_zero": bool(np.all(last["timeOffsetNs"] == 0)),
                }
            )
            print(
                f"  peak_idx={res['peak_idx']} primary_way={res['primary_way']} "
                f"n_ways={len(last['ways'])} spsgw={last['numSamplesPerSgw']}",
                flush=True,
            )

    fieldnames = list(rows[0].keys()) if rows else []
    with (out / "points.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # quick with-only OLS if enough points
    with_rows = [r for r in rows if r["condition"] == "with" and r["peak_idx"] != ""]
    if len(with_rows) >= 2:
        xd = np.array([float(r["distance_m"]) for r in with_rows])
        yk = np.array([float(r["peak_idx"]) for r in with_rows])
        xm, ym = xd.mean(), yk.mean()
        sxx = float(np.sum((xd - xm) ** 2))
        slope = float(np.sum((xd - xm) * (yk - ym)) / sxx) if sxx > 0 else float("nan")
        intercept = float(ym - slope * xm)
        r = float(np.corrcoef(xd, yk)[0, 1]) if np.std(xd) > 0 and np.std(yk) > 0 else float("nan")
        adj = {
            "n_with": len(with_rows),
            "slope": slope,
            "intercept": intercept,
            "pearson_r": r,
            "note": "Informational only; P0 pass/fail remains offline audit on S1/S2 canon.",
        }
        (out / "adjudication_informational.json").write_text(json.dumps(adj, indent=2))
        print("informational OLS:", adj, flush=True)

    print(f"done -> {out}", flush=True)
    timeline.stop()
    simulation_app.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        try:
            simulation_app.close()
        except Exception:
            pass
        raise
