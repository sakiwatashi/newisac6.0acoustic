"""Shared RTX Acoustic factory — Isaac Sim 6.0 experimental API patterns.

Aligns with official examples:
  standalone_examples/api/isaacsim.sensors.experimental.rtx/create_acoustic_basic.py
  standalone_examples/api/isaacsim.sensors.experimental.rtx/inspect_acoustic_gmo.py
  exts/isaacsim.sensors.experimental.rtx/tests/test_acoustic_sensor.py

Canonical path:
  /home/lab109/song/isaacsim6.0/scripts/rtx_acoustic_factory.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

PASSPORT_FACTORY_VERSION = "v1.0"

# Default reference signal way for the passport dual-mount layout (tx=0, rx=0, ch=0).
REFERENCE_SIGNAL_WAY = (0, 0, 0)


@dataclass(frozen=True)
class SignalWayStats:
    tx_id: int
    rx_id: int
    ch_id: int
    sample_count: int
    peak_amplitude: float
    mean_amplitude: float
    std_amplitude: float
    early_energy: float
    first_time_offset_ns: float

    @property
    def key(self) -> tuple[int, int, int]:
        return (self.tx_id, self.rx_id, self.ch_id)

    def as_key_str(self) -> str:
        return f"tx={self.tx_id},rx={self.rx_id},ch={self.ch_id}"


def default_wpm_attributes(
    *,
    center_frequency_hz: float,
    mount_spacing_m: float,
) -> dict[str, Any]:
    """WPM acoustic attributes for the passport dual-mount receiver group."""
    return {
        "omni:sensor:WpmAcoustic:centerFrequency": float(center_frequency_hz),
        "omni:sensor:WpmAcoustic:sensorMount:m001:position": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m001:rotation": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:position": (float(mount_spacing_m), 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:rotation": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices": [0, 1],
    }


def create_passport_acoustic(
    sensor_path: str,
    *,
    Acoustic: Any,
    AcousticSensor: Any,
    np: Any,
    tick_rate_hz: float,
    center_frequency_hz: float,
    sensor_local_offset_m: tuple[float, float, float],
    mount_spacing_m: float,
    aux_output_level: str = "BASIC",
    writer_brings_annotator: bool = True,
) -> tuple[Any, Any]:
    """Create passport-aligned Acoustic prim and AcousticSensor runtime wrapper."""
    acoustic = Acoustic(
        sensor_path,
        tick_rate=float(tick_rate_hz),
        aux_output_level=str(aux_output_level),
        translations=np.array(sensor_local_offset_m, dtype=float),
        attributes=default_wpm_attributes(
            center_frequency_hz=center_frequency_hz,
            mount_spacing_m=mount_spacing_m,
        ),
    )
    if writer_brings_annotator:
        sensor = AcousticSensor(acoustic, annotators=[])
    else:
        sensor = AcousticSensor(
            acoustic,
            annotators=["generic-model-output"],
            render_vars=["GenericModelOutput"],
        )
    return acoustic, sensor


def _finite_stats(values: Any, np: Any) -> tuple[float, float, float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return math.nan, math.nan, math.nan, math.nan
    return float(np.min(arr)), float(np.max(arr)), float(np.mean(arr)), float(np.std(arr))


def _early_energy(amplitudes: Any, np: Any, fraction: float = 0.25, min_samples: int = 4) -> float:
    arr = np.abs(np.asarray(amplitudes, dtype=float))
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return math.nan
    count = max(min_samples, int(math.ceil(arr.size * fraction)))
    count = min(count, arr.size)
    return float(np.sum(arr[:count]))


def validate_acoustic_gmo(gmo: Any, np: Any) -> dict[str, Any]:
    """Lightweight checks mirrored from test_acoustic_sensor.py."""
    issues: list[str] = []
    n = int(getattr(gmo, "numElements", 0) or 0)
    num_samples_per_sgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)

    modality_name = ""
    modality = getattr(gmo, "modality", None)
    if modality is not None:
        modality_name = str(getattr(modality, "name", modality))

    if n <= 0:
        issues.append("numElements<=0")
    if num_samples_per_sgw <= 0:
        issues.append("numSamplesPerSgw<=0")
    elif n > 0 and n % num_samples_per_sgw != 0:
        issues.append("numElements not multiple of numSamplesPerSgw")

    frame_start = int(getattr(getattr(gmo, "frameStart", None), "timestampNs", 0) or 0)
    frame_end = int(getattr(getattr(gmo, "frameEnd", None), "timestampNs", 0) or 0)
    if frame_end <= frame_start:
        issues.append("invalid frame timestamps")

    if n > 0:
        scalars = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
        if not np.all(np.isfinite(scalars)):
            issues.append("non-finite scalar samples")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "modality": modality_name,
        "num_elements": n,
        "num_samples_per_sgw": num_samples_per_sgw,
        "frame_start_ns": frame_start,
        "frame_end_ns": frame_end,
    }


def parse_signal_ways(gmo: Any, np: Any) -> list[SignalWayStats]:
    """Split GMO into per-(tx, rx, ch) signal ways using numSamplesPerSgw."""
    n = int(gmo.numElements)
    if n <= 0:
        return []

    tx_ids = np.ctypeslib.as_array(gmo.x, shape=(n,))
    rx_ids = np.ctypeslib.as_array(gmo.y, shape=(n,))
    ch_ids = np.ctypeslib.as_array(gmo.z, shape=(n,))
    amplitudes = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
    time_offsets = np.ctypeslib.as_array(gmo.timeOffsetNs, shape=(n,))

    num_samples_per_sgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    ways: list[SignalWayStats] = []

    if num_samples_per_sgw > 0 and n % num_samples_per_sgw == 0:
        for sgw_index in range(n // num_samples_per_sgw):
            start = sgw_index * num_samples_per_sgw
            end = start + num_samples_per_sgw
            amps = amplitudes[start:end]
            _, peak, mean, std = _finite_stats(amps, np)
            ways.append(
                SignalWayStats(
                    tx_id=int(tx_ids[start]),
                    rx_id=int(rx_ids[start]),
                    ch_id=int(ch_ids[start]),
                    sample_count=int(end - start),
                    peak_amplitude=peak,
                    mean_amplitude=mean,
                    std_amplitude=std,
                    early_energy=_early_energy(amps, np),
                    first_time_offset_ns=float(time_offsets[start]),
                )
            )
        return ways

    # Fallback: group by unique (tx, rx, ch) keys when structured stride is unavailable.
    keys: dict[tuple[int, int, int], list[int]] = {}
    for index in range(n):
        key = (int(tx_ids[index]), int(rx_ids[index]), int(ch_ids[index]))
        keys.setdefault(key, []).append(index)

    for (tx_id, rx_id, ch_id), indices in sorted(keys.items()):
        amps = amplitudes[indices]
        _, peak, mean, std = _finite_stats(amps, np)
        ways.append(
            SignalWayStats(
                tx_id=tx_id,
                rx_id=rx_id,
                ch_id=ch_id,
                sample_count=len(indices),
                peak_amplitude=peak,
                mean_amplitude=mean,
                std_amplitude=std,
                early_energy=_early_energy(amps, np),
                first_time_offset_ns=float(time_offsets[indices[0]]),
            )
        )
    return ways


def _pick_primary_way(ways: list[SignalWayStats]) -> SignalWayStats | None:
    if not ways:
        return None
    return max(ways, key=lambda way: way.peak_amplitude if math.isfinite(way.peak_amplitude) else -math.inf)


def _pick_reference_way(ways: list[SignalWayStats]) -> SignalWayStats | None:
    for way in ways:
        if way.key == REFERENCE_SIGNAL_WAY:
            return way
    return _pick_primary_way(ways)


def summarize_gmo_frame(gmo: Any, np: Any) -> dict[str, Any]:
    """Flatten GMO into CSV-friendly fields including signal-way aggregates."""
    validation = validate_acoustic_gmo(gmo, np)
    ways = parse_signal_ways(gmo, np)
    primary = _pick_primary_way(ways)
    reference = _pick_reference_way(ways)

    n = int(gmo.numElements)
    amplitudes = np.ctypeslib.as_array(gmo.scalar, shape=(n,)) if n > 0 else np.asarray([], dtype=float)
    amp_min, amp_max, amp_mean, amp_std = _finite_stats(amplitudes, np)

    peak_values = [way.peak_amplitude for way in ways if math.isfinite(way.peak_amplitude)]
    if peak_values:
        all_sgw_peak_mean = float(np.mean(peak_values))
        all_sgw_peak_std = float(np.std(peak_values)) if len(peak_values) > 1 else 0.0
    else:
        all_sgw_peak_mean = math.nan
        all_sgw_peak_std = math.nan

    def _way_fields(prefix: str, way: SignalWayStats | None) -> dict[str, Any]:
        if way is None:
            return {
                f"{prefix}_tx": math.nan,
                f"{prefix}_rx": math.nan,
                f"{prefix}_ch": math.nan,
                f"{prefix}_peak": math.nan,
                f"{prefix}_mean": math.nan,
                f"{prefix}_early_energy": math.nan,
                f"{prefix}_first_time_offset_ns": math.nan,
            }
        return {
            f"{prefix}_tx": way.tx_id,
            f"{prefix}_rx": way.rx_id,
            f"{prefix}_ch": way.ch_id,
            f"{prefix}_peak": way.peak_amplitude,
            f"{prefix}_mean": way.mean_amplitude,
            f"{prefix}_early_energy": way.early_energy,
            f"{prefix}_first_time_offset_ns": way.first_time_offset_ns,
        }

    summary: dict[str, Any] = {
        "timestamp_ns": int(getattr(gmo, "timestampNs", 0) or 0),
        "num_elements": n,
        "num_signal_ways": len(ways),
        "num_samples_per_sgw": int(getattr(gmo, "numSamplesPerSgw", 0) or 0),
        "gmo_valid": bool(validation["valid"]),
        "gmo_modality": validation["modality"],
        "gmo_validation_issues": ";".join(validation["issues"]),
        "amplitude_min": amp_min,
        "amplitude_max": amp_max,
        "amplitude_mean": amp_mean,
        "amplitude_std": amp_std,
        "all_sgw_peak_mean": all_sgw_peak_mean,
        "all_sgw_peak_std": all_sgw_peak_std,
        "signal_way_keys": ";".join(way.as_key_str() for way in ways),
    }
    summary.update(_way_fields("primary_sgw", primary))
    summary.update(_way_fields("ref_sgw", reference))
    return summary


def _parse_bool_field(value: Any) -> bool | None:
    if value is None:
        return None
    token = str(value).strip().lower()
    if token in ("", "nan"):
        return None
    return token in ("1", "true", "yes")


def assess_gmo_capture_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize capture-level GMO validation for PASS/FAIL gates."""
    if not rows:
        return {
            "sample_count": 0,
            "gmo_valid_rate": 0.0,
            "all_gmo_valid": False,
            "all_modality_acoustic": False,
            "num_samples_per_sgw_consistent": False,
            "num_signal_ways_consistent": False,
            "valid": False,
            "issues": ["no_captured_rows"],
        }

    valid_flags = [_parse_bool_field(row.get("gmo_valid")) for row in rows]
    modalities = [str(row.get("gmo_modality", "")).strip().upper() for row in rows]
    samples_per_sgw = [int(float(row.get("num_samples_per_sgw", 0) or 0)) for row in rows]
    signal_way_counts = [int(float(row.get("num_signal_ways", 0) or 0)) for row in rows]

    counted_valid = [flag for flag in valid_flags if flag is not None]
    gmo_valid_rate = float(sum(1 for flag in counted_valid if flag) / len(counted_valid)) if counted_valid else 0.0
    all_gmo_valid = bool(counted_valid) and all(counted_valid)
    all_modality_acoustic = bool(modalities) and all(mod == "ACOUSTIC" for mod in modalities)
    unique_samples_per_sgw = sorted({value for value in samples_per_sgw if value > 0})
    unique_signal_ways = sorted({value for value in signal_way_counts if value > 0})
    num_samples_per_sgw_consistent = len(unique_samples_per_sgw) == 1 and unique_samples_per_sgw[0] > 0
    num_signal_ways_consistent = len(unique_signal_ways) == 1 and unique_signal_ways[0] > 0

    issues: list[str] = []
    if not all_gmo_valid:
        issues.append("gmo_valid_not_all_true")
    if not all_modality_acoustic:
        issues.append("gmo_modality_not_acoustic")
    if not num_samples_per_sgw_consistent:
        issues.append("num_samples_per_sgw_inconsistent")
    if not num_signal_ways_consistent:
        issues.append("num_signal_ways_inconsistent")

    return {
        "sample_count": len(rows),
        "gmo_valid_rate": gmo_valid_rate,
        "all_gmo_valid": all_gmo_valid,
        "all_modality_acoustic": all_modality_acoustic,
        "num_samples_per_sgw": unique_samples_per_sgw[0] if num_samples_per_sgw_consistent else None,
        "num_signal_ways": unique_signal_ways[0] if num_signal_ways_consistent else None,
        "num_samples_per_sgw_consistent": num_samples_per_sgw_consistent,
        "num_signal_ways_consistent": num_signal_ways_consistent,
        "valid": len(issues) == 0,
        "issues": issues,
    }