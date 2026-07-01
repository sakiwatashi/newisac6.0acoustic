"""Tier-B acoustic calibration tables from dynamic approach sweep (labeling uses oracle distance)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from grasp_passport_v1 import DEFAULT_CALIBRATION, DEFAULT_TOF_CALIBRATION

DEFAULT_CALIBRATION_JSON = Path(
    "/home/lab109/song/isaacsim6.0/runtime/outputs/ur10e_dynamic_approach_calibration_v1/tier_b_calibration.json"
)

MIN_VALID_TOF_NS = 1.0e5


def _valid_sweep_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("gmo_valid"):
            continue
        energy = float(row.get("primary_sgw_early_energy", math.nan))
        distance = float(row.get("oracle_distance_m", math.nan))
        if not math.isfinite(energy) or not math.isfinite(distance):
            continue
        valid.append(row)
    return valid


def build_energy_calibration_points(
    rows: list[dict[str, Any]],
    *,
    num_points: int = 8,
) -> list[tuple[float, float]]:
    """Monotonic early_energy → oracle distance (m)."""
    valid = _valid_sweep_rows(rows)
    if not valid:
        return []
    valid.sort(key=lambda r: float(r["oracle_distance_m"]), reverse=True)
    if len(valid) <= num_points:
        picked = valid
    else:
        idxs = [int(round(i * (len(valid) - 1) / (num_points - 1))) for i in range(num_points)]
        picked = [valid[i] for i in idxs]
    points = [(float(r["primary_sgw_early_energy"]), float(r["oracle_distance_m"])) for r in picked]
    points.sort(key=lambda p: p[0], reverse=True)
    cleaned: list[tuple[float, float]] = []
    min_d = math.inf
    for energy, distance in points:
        d = min(float(distance), min_d)
        min_d = d
        cleaned.append((float(energy), float(d)))
    return cleaned


def build_tof_calibration_points(
    rows: list[dict[str, Any]],
    *,
    num_points: int = 8,
    min_valid_tof_ns: float = MIN_VALID_TOF_NS,
) -> list[tuple[float, float]]:
    """Monotonic first_time_offset_ns → oracle distance (m)."""
    valid: list[dict[str, Any]] = []
    for row in _valid_sweep_rows(rows):
        tof_ns = float(row.get("primary_sgw_first_time_offset_ns", math.nan))
        if not math.isfinite(tof_ns) or tof_ns < float(min_valid_tof_ns):
            continue
        valid.append(row)
    if not valid:
        return []
    valid.sort(key=lambda r: float(r["oracle_distance_m"]), reverse=True)
    if len(valid) <= num_points:
        picked = valid
    else:
        idxs = [int(round(i * (len(valid) - 1) / (num_points - 1))) for i in range(num_points)]
        picked = [valid[i] for i in idxs]
    points = [
        (float(r["primary_sgw_first_time_offset_ns"]), float(r["oracle_distance_m"])) for r in picked
    ]
    points.sort(key=lambda p: p[0])
    cleaned: list[tuple[float, float]] = []
    min_d = math.inf
    for tof_ns, distance in reversed(points):
        d = min(float(distance), min_d)
        min_d = d
        cleaned.append((float(tof_ns), float(d)))
    cleaned.sort(key=lambda p: p[0])
    return cleaned


def tier_b_calibration_payload(
    rows: list[dict[str, Any]],
    *,
    trial_id: int,
    spawn_seed: int,
    wrench_position_m: tuple[float, float, float],
) -> dict[str, Any]:
    energy_points = build_energy_calibration_points(rows)
    tof_points = build_tof_calibration_points(rows)
    return {
        "tier": "B",
        "trial_id": int(trial_id),
        "spawn_seed": int(spawn_seed),
        "wrench_position_m": list(wrench_position_m),
        "num_samples": len(rows),
        "energy_calibration": [list(p) for p in energy_points],
        "tof_calibration": [list(p) for p in tof_points],
        "fallback_energy_calibration": [list(p) for p in DEFAULT_CALIBRATION],
        "fallback_tof_calibration": [list(p) for p in DEFAULT_TOF_CALIBRATION],
        "claim_boundary": "Tables built from oracle_distance_m for offline labeling only.",
    }


def _tuple_table(raw: Any, fallback: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw, list) or not raw:
        return fallback
    out: list[tuple[float, float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        a, b = float(item[0]), float(item[1])
        if math.isfinite(a) and math.isfinite(b):
            out.append((a, b))
    return tuple(out) if out else fallback


def load_tier_b_calibration(
    path: Path | str | None = None,
) -> tuple[tuple[tuple[float, float], ...], tuple[tuple[float, float], ...], dict[str, Any]]:
    """Return (energy_table, tof_table, metadata). Uses baked-in defaults if JSON missing."""
    cal_path = Path(path) if path is not None else DEFAULT_CALIBRATION_JSON
    if not cal_path.is_file():
        return DEFAULT_CALIBRATION, DEFAULT_TOF_CALIBRATION, {"source": "builtin_defaults", "path": str(cal_path)}
    with cal_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    energy = _tuple_table(payload.get("energy_calibration"), DEFAULT_CALIBRATION)
    tof_raw = payload.get("tof_calibration")
    tof = _tuple_table(tof_raw, DEFAULT_TOF_CALIBRATION)
    if not tof_raw:
        tof = DEFAULT_TOF_CALIBRATION
    meta = {
        "source": "tier_b_calibration_json",
        "path": str(cal_path),
        "trial_id": payload.get("trial_id"),
        "num_samples": payload.get("num_samples"),
    }
    return energy, tof, meta