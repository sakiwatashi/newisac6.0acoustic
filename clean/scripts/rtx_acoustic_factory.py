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
    peak_sample_idx: int = 0        # argmax within full signal way; dominated by room reflections
    ultra_early_energy: float = math.nan  # sum of first 10% samples; closer to target echo window
    early_peak_sample_idx: int = 0  # argmax within first 10% of signal way; target-echo-window peak

    @property
    def key(self) -> tuple[int, int, int]:
        return (self.tx_id, self.rx_id, self.ch_id)

    def as_key_str(self) -> str:
        return f"tx={self.tx_id},rx={self.rx_id},ch={self.ch_id}"


def default_wpm_attributes(
    *,
    center_frequency_hz: float,
    mount_spacing_m: float,
    az_span_deg: float = 90.0,
    el_span_deg: float = 90.0,
    trace_tree_depth: int = 2,
    close_indirect_ampl: float | None = None,
    close_direct_ampl: float | None = None,
    close_range: float | None = None,
    close_range_decay: float | None = None,
    close_direct_ampl_base: float | None = None,
    close_indirect_ampl_base: float | None = None,
) -> dict[str, Any]:
    """WPM acoustic attributes for the passport dual-mount receiver group.

    az_span_deg / el_span_deg: beam span in degrees (default 90° = omnidirectional).
        Set to 45° to approximate CH201 ±22.5° directional beam.
    trace_tree_depth: max ray bounces (default 2). Set to 1 for direct-echo only.

    Parametric room model (WPM does NOT ray-trace Cube prims):
      close_indirect_ampl: indirect (room) echo amplitude multiplier. Schema default 17.64.
          Set near 0 to suppress parametric room echoes and let direct echo dominate.
      close_direct_ampl: direct echo amplitude multiplier. Schema default 12.66.
          Boost to make target echo stronger relative to room model.
      close_range: near-field threshold in metres. Schema default 1.42m.
      close_range_decay: amplitude decay factor. Schema default 1.26.
      close_direct_ampl_base / close_indirect_ampl_base: base amplitudes.
    """
    attrs: dict[str, Any] = {
        "omni:sensor:WpmAcoustic:centerFrequency": float(center_frequency_hz),
        "omni:sensor:WpmAcoustic:azSpanDeg": float(az_span_deg),
        "omni:sensor:WpmAcoustic:elSpanDeg": float(el_span_deg),
        "omni:sensor:WpmAcoustic:traceTreeDepth": int(trace_tree_depth),
        "omni:sensor:WpmAcoustic:sensorMount:m001:position": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m001:rotation": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:position": (float(mount_spacing_m), 0.0, 0.0),
        "omni:sensor:WpmAcoustic:sensorMount:m002:rotation": (0.0, 0.0, 0.0),
        "omni:sensor:WpmAcoustic:rxGroup:g001:receiverIndices": [0, 1],
    }
    if close_indirect_ampl is not None:
        attrs["omni:sensor:WpmAcoustic:closeIndirectAmpl"] = float(close_indirect_ampl)
    if close_direct_ampl is not None:
        attrs["omni:sensor:WpmAcoustic:closeDirectAmpl"] = float(close_direct_ampl)
    if close_range is not None:
        attrs["omni:sensor:WpmAcoustic:closeRange"] = float(close_range)
    if close_range_decay is not None:
        attrs["omni:sensor:WpmAcoustic:closeRangeDecay"] = float(close_range_decay)
    if close_direct_ampl_base is not None:
        attrs["omni:sensor:WpmAcoustic:closeDirectAmplBase"] = float(close_direct_ampl_base)
    if close_indirect_ampl_base is not None:
        attrs["omni:sensor:WpmAcoustic:closeIndirectAmplBase"] = float(close_indirect_ampl_base)
    return attrs


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
    az_span_deg: float = 90.0,
    el_span_deg: float = 90.0,
    trace_tree_depth: int = 2,
    close_indirect_ampl: float | None = None,
    close_direct_ampl: float | None = None,
    close_range: float | None = None,
    close_range_decay: float | None = None,
    close_direct_ampl_base: float | None = None,
    close_indirect_ampl_base: float | None = None,
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
            az_span_deg=az_span_deg,
            el_span_deg=el_span_deg,
            trace_tree_depth=trace_tree_depth,
            close_indirect_ampl=close_indirect_ampl,
            close_direct_ampl=close_direct_ampl,
            close_range=close_range,
            close_range_decay=close_range_decay,
            close_direct_ampl_base=close_direct_ampl_base,
            close_indirect_ampl_base=close_indirect_ampl_base,
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
            early_count = max(4, int(math.ceil(len(amps) * 0.10)))
            early_count = min(early_count, len(amps))
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
                    peak_sample_idx=int(np.argmax(amps)),
                    ultra_early_energy=_early_energy(amps, np, fraction=0.10),
                    early_peak_sample_idx=int(np.argmax(amps[:early_count])),
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
        early_count = max(4, int(math.ceil(len(amps) * 0.10)))
        early_count = min(early_count, len(amps))
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
                peak_sample_idx=int(np.argmax(amps)),
                ultra_early_energy=_early_energy(amps, np, fraction=0.10),
                early_peak_sample_idx=int(np.argmax(amps[:early_count])),
            )
        )
    return ways


def extract_primary_raw_amplitudes(gmo: Any, np: Any) -> Any | None:
    """Return raw amplitude array for the highest-energy signal way (primary way).

    Mirrors the selection logic of _pick_primary_way but returns the raw amplitude
    samples instead of a SignalWayStats object. Used for differential waveform analysis.
    Returns None if GMO is empty or malformed.
    """
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n <= 0:
        return None
    amplitudes = np.ctypeslib.as_array(gmo.scalar, shape=(n,))
    num_spsgw = int(getattr(gmo, "numSamplesPerSgw", 0) or 0)
    if num_spsgw > 0 and n % num_spsgw == 0:
        best_start = 0
        best_peak = -math.inf
        for sgw_idx in range(n // num_spsgw):
            start = sgw_idx * num_spsgw
            peak = float(np.max(amplitudes[start : start + num_spsgw]))
            if peak > best_peak:
                best_peak = peak
                best_start = start
        return np.array(amplitudes[best_start : best_start + num_spsgw], dtype=float)
    return np.array(amplitudes, dtype=float)


def matched_filter_tof(
    amplitudes: Any,
    center_frequency_hz: float,
    sample_period_s: float,
    np: Any,
    pulse_duration_periods: float = 3.0,
) -> tuple[int, float]:
    """Estimate ToF sample index via matched filter (cross-correlation with reference pulse).

    Builds a Gaussian-windowed sinusoidal reference pulse at center_frequency_hz and
    cross-correlates it with the received amplitude waveform. The peak of the absolute
    cross-correlation corresponds to the direct-path echo arrival time.

    Returns:
        (peak_sample_idx, peak_correlation_value)
        Distance estimate: peak_sample_idx * sample_period_s * 343.0 / 2.0

    This approach bypasses the timeOffsetNs=0 API limitation by operating directly on
    the raw amplitude waveform from the GMO GenericModelOutput.
    """
    amps = np.asarray(amplitudes, dtype=float)
    if amps.size == 0:
        return 0, 0.0

    f = float(center_frequency_hz)
    dt = float(sample_period_s)
    if f <= 0 or dt <= 0:
        return 0, 0.0

    # Reference Gaussian-windowed sinusoid (matched to transmitted pulse shape)
    period_samples = 1.0 / (f * dt)
    pulse_len = max(4, int(round(float(pulse_duration_periods) * period_samples)))
    pulse_len = min(pulse_len, amps.size)
    t = np.arange(pulse_len, dtype=float) * dt
    t_mid = t[len(t) // 2]
    sigma = float(pulse_duration_periods) / (2.0 * math.pi * f)
    ref_pulse = np.exp(-0.5 * ((t - t_mid) / sigma) ** 2) * np.sin(2.0 * math.pi * f * t)

    # Normalise reference pulse
    ref_norm = float(np.sqrt(np.sum(ref_pulse ** 2)))
    if ref_norm > 0:
        ref_pulse = ref_pulse / ref_norm

    # Full cross-correlation (valid mode: output length = len(amps) - len(ref_pulse) + 1)
    if amps.size < len(ref_pulse):
        return 0, 0.0
    xcorr = np.correlate(amps, ref_pulse, mode="valid")
    xcorr_abs = np.abs(xcorr)
    peak_idx = int(np.argmax(xcorr_abs))
    peak_val = float(xcorr_abs[peak_idx])
    return peak_idx, peak_val


def _pick_primary_way(ways: list[SignalWayStats]) -> SignalWayStats | None:
    """Pick the signal way with the highest peak amplitude (best for energy-based distance)."""
    if not ways:
        return None
    return max(ways, key=lambda way: way.peak_amplitude if math.isfinite(way.peak_amplitude) else -math.inf)


def _pick_tof_primary_way(ways: list[SignalWayStats]) -> SignalWayStats | None:
    """Pick the signal way with the earliest first arrival (best for TOF-based distance).

    The direct acoustic path arrives first (minimum time offset). Selecting by earliest
    arrival rather than peak amplitude avoids confusing multipath reflections with the
    direct path when estimating distance from time-of-flight.
    Falls back to _pick_primary_way if no valid TOF data is available.
    """
    valid = [w for w in ways if math.isfinite(w.first_time_offset_ns) and w.first_time_offset_ns > 0]
    if not valid:
        return _pick_primary_way(ways)
    return min(valid, key=lambda way: way.first_time_offset_ns)


def _pick_reference_way(ways: list[SignalWayStats]) -> SignalWayStats | None:
    for way in ways:
        if way.key == REFERENCE_SIGNAL_WAY:
            return way
    return _pick_primary_way(ways)


def summarize_gmo_frame(gmo: Any, np: Any) -> dict[str, Any]:
    """Flatten GMO into CSV-friendly fields including signal-way aggregates.

    primary_sgw: highest peak amplitude (energy-based distance estimation).
    tof_primary_sgw: earliest first arrival (TOF-based distance estimation).
    ref_sgw: reference signal way at (tx=0, rx=0, ch=0) for cross-frame normalization.
    """
    validation = validate_acoustic_gmo(gmo, np)
    ways = parse_signal_ways(gmo, np)
    primary = _pick_primary_way(ways)
    tof_primary = _pick_tof_primary_way(ways)
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
                f"{prefix}_peak_sample_idx": math.nan,
                f"{prefix}_ultra_early_energy": math.nan,
                f"{prefix}_early_peak_sample_idx": math.nan,
            }
        return {
            f"{prefix}_tx": way.tx_id,
            f"{prefix}_rx": way.rx_id,
            f"{prefix}_ch": way.ch_id,
            f"{prefix}_peak": way.peak_amplitude,
            f"{prefix}_mean": way.mean_amplitude,
            f"{prefix}_early_energy": way.early_energy,
            f"{prefix}_first_time_offset_ns": way.first_time_offset_ns,
            f"{prefix}_peak_sample_idx": way.peak_sample_idx,
            f"{prefix}_ultra_early_energy": way.ultra_early_energy,
            f"{prefix}_early_peak_sample_idx": way.early_peak_sample_idx,
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
    summary.update(_way_fields("tof_primary_sgw", tof_primary))
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


@dataclass(frozen=True)
class AcousticFeatureFrame:
    """Tier-B fused RTX GMO features for closed-loop approach/grasp."""

    gmo_valid: bool
    early_energy: float
    ref_early_energy: float
    tof_ns: float
    ref_tof_ns: float
    peak_amplitude: float
    ref_peak_amplitude: float
    amplitude_mean: float
    amplitude_std: float
    all_sgw_peak_mean: float
    all_sgw_peak_std: float
    num_signal_ways: int
    rx_early_energy_0: float
    rx_early_energy_1: float
    rx_tof_ns_0: float
    rx_tof_ns_1: float
    rx_energy_balance: float
    rx_tof_delta_ns: float
    waveform_early_fraction: float
    estimated_distance_energy_m: float
    estimated_distance_tof_m: float
    fused_distance_m: float
    alignment_score: float
    primary_sgw_peak_sample_idx: int = 0   # argmax of full signal way (room-reflection dominated)
    ultra_early_energy: float = math.nan   # sum of first 10% samples; target-echo window
    early_peak_sample_idx: int = 0         # argmax within first 10% of signal way

    def as_log_dict(self) -> dict[str, float | int | bool]:
        return {
            "gmo_valid": self.gmo_valid,
            "early_energy": self.early_energy,
            "ref_early_energy": self.ref_early_energy,
            "tof_ns": self.tof_ns,
            "ref_tof_ns": self.ref_tof_ns,
            "peak_amplitude": self.peak_amplitude,
            "amplitude_mean": self.amplitude_mean,
            "amplitude_std": self.amplitude_std,
            "all_sgw_peak_std": self.all_sgw_peak_std,
            "num_signal_ways": self.num_signal_ways,
            "rx_energy_balance": self.rx_energy_balance,
            "rx_tof_delta_ns": self.rx_tof_delta_ns,
            "waveform_early_fraction": self.waveform_early_fraction,
            "estimated_distance_energy_m": self.estimated_distance_energy_m,
            "estimated_distance_tof_m": self.estimated_distance_tof_m,
            "fused_distance_m": self.fused_distance_m,
            "alignment_score": self.alignment_score,
            "primary_sgw_peak_sample_idx": self.primary_sgw_peak_sample_idx,
            "ultra_early_energy": self.ultra_early_energy,
            "early_peak_sample_idx": self.early_peak_sample_idx,
        }


def _safe_float(value: Any, default: float = math.nan, *, reject_zero: bool = False) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    if reject_zero and out == 0.0:
        # GMO timeOffsetNs all-zero means Isaac Sim did not populate ToF data;
        # treat as missing rather than propagating 0.0 into distance fusion.
        return default
    return out


def _interp_monotonic_table(
    value: float,
    points: tuple[tuple[float, float], ...],
    *,
    ascending_key: bool,
) -> float:
    if not math.isfinite(value) or not points:
        return math.nan
    ordered = sorted(points, key=lambda p: p[0], reverse=not ascending_key)
    if ascending_key:
        if value <= ordered[0][0]:
            return ordered[0][1]
        if value >= ordered[-1][0]:
            return ordered[-1][1]
        for (k_lo, d_lo), (k_hi, d_hi) in zip(ordered, ordered[1:]):
            if k_lo <= value <= k_hi:
                if abs(k_hi - k_lo) < 1e-12:
                    return d_lo
                t = (value - k_lo) / (k_hi - k_lo)
                return d_lo + t * (d_hi - d_lo)
    else:
        if value >= ordered[0][0]:
            return ordered[0][1]
        if value <= ordered[-1][0]:
            return ordered[-1][1]
        for (k_hi, d_hi), (k_lo, d_lo) in zip(ordered, ordered[1:]):
            if k_lo <= value <= k_hi:
                if abs(k_hi - k_lo) < 1e-12:
                    return d_hi
                t = (value - k_lo) / (k_hi - k_lo)
                return d_lo + t * (d_hi - d_lo)
    return math.nan


def estimate_distance_from_energy(early_energy: float, points: tuple[tuple[float, float], ...]) -> float:
    return _interp_monotonic_table(float(early_energy), points, ascending_key=False)


def estimate_distance_from_tof(tof_ns: float, points: tuple[tuple[float, float], ...]) -> float:
    return _interp_monotonic_table(float(tof_ns), points, ascending_key=True)


def fuse_distance_estimates(
    distance_energy_m: float,
    distance_tof_m: float,
    *,
    energy_weight: float,
    tof_ns: float | None = None,
    min_valid_tof_ns: float = 1.0e5,
) -> float:
    weight = min(1.0, max(0.0, float(energy_weight)))
    values: list[tuple[float, float]] = []
    if math.isfinite(distance_energy_m):
        values.append((distance_energy_m, weight))
    tof_usable = math.isfinite(distance_tof_m)
    if tof_ns is not None:
        tof_usable = tof_usable and math.isfinite(tof_ns) and float(tof_ns) >= float(min_valid_tof_ns)
    if tof_usable:
        values.append((distance_tof_m, 1.0 - weight))
    if not values:
        return math.nan
    denom = sum(w for _, w in values)
    if denom <= 0.0:
        return math.nan
    return float(sum(d * w for d, w in values) / denom)


def _rx_channel_stats(ways: list[SignalWayStats]) -> tuple[float, float, float, float, float, float]:
    rx_energy: dict[int, list[float]] = {}
    rx_tof: dict[int, list[float]] = {}
    for way in ways:
        if not math.isfinite(way.early_energy):
            continue
        rx_energy.setdefault(int(way.rx_id), []).append(float(way.early_energy))
        if math.isfinite(way.first_time_offset_ns):
            rx_tof.setdefault(int(way.rx_id), []).append(float(way.first_time_offset_ns))
    e0 = float(sum(rx_energy.get(0, [])) / max(1, len(rx_energy.get(0, [])))) if 0 in rx_energy else math.nan
    e1 = float(sum(rx_energy.get(1, [])) / max(1, len(rx_energy.get(1, [])))) if 1 in rx_energy else math.nan
    t0 = float(sum(rx_tof.get(0, [])) / max(1, len(rx_tof.get(0, [])))) if 0 in rx_tof else math.nan
    t1 = float(sum(rx_tof.get(1, [])) / max(1, len(rx_tof.get(1, [])))) if 1 in rx_tof else math.nan
    denom = (abs(e0) + abs(e1)) if math.isfinite(e0) and math.isfinite(e1) else math.nan
    balance = (e0 - e1) / denom if math.isfinite(denom) and denom > 1e-9 else 0.0
    tof_delta = (t0 - t1) if math.isfinite(t0) and math.isfinite(t1) else math.nan
    return e0, e1, t0, t1, balance, tof_delta


def _waveform_early_fraction(gmo: Any, np: Any, *, fraction: float = 0.25) -> float:
    n = int(getattr(gmo, "numElements", 0) or 0)
    if n <= 0:
        return math.nan
    amps = np.abs(np.asarray(np.ctypeslib.as_array(gmo.scalar, shape=(n,)), dtype=float))
    amps = amps[np.isfinite(amps)]
    if amps.size == 0:
        return math.nan
    total = float(np.sum(amps))
    if total <= 1e-12:
        return math.nan
    count = max(4, int(math.ceil(amps.size * fraction)))
    return float(np.sum(amps[:count]) / total)


def build_acoustic_features(
    *,
    gmo_valid: bool,
    early_energy: float,
    ref_early_energy: float,
    tof_ns: float,
    ref_tof_ns: float,
    peak_amplitude: float,
    ref_peak_amplitude: float,
    amplitude_mean: float,
    amplitude_std: float,
    all_sgw_peak_mean: float,
    all_sgw_peak_std: float,
    num_signal_ways: int,
    rx_early_energy_0: float,
    rx_early_energy_1: float,
    rx_tof_ns_0: float,
    rx_tof_ns_1: float,
    rx_energy_balance: float,
    rx_tof_delta_ns: float,
    waveform_early_fraction: float,
    energy_calibration: tuple[tuple[float, float], ...],
    tof_calibration: tuple[tuple[float, float], ...],
    fusion_energy_weight: float,
    primary_sgw_peak_sample_idx: int = 0,
    ultra_early_energy: float = math.nan,
    early_peak_sample_idx: int = 0,
) -> AcousticFeatureFrame:
    distance_energy = estimate_distance_from_energy(early_energy, energy_calibration)
    distance_tof = estimate_distance_from_tof(tof_ns, tof_calibration)
    fused = fuse_distance_estimates(
        distance_energy,
        distance_tof,
        energy_weight=fusion_energy_weight,
        tof_ns=tof_ns,
    )
    ref_component = ref_early_energy if math.isfinite(ref_early_energy) else 0.0
    balance_penalty = abs(rx_energy_balance) if math.isfinite(rx_energy_balance) else 0.0
    alignment_score = (
        (early_energy if math.isfinite(early_energy) else 0.0)
        + 0.35 * ref_component
        + 0.20 * (peak_amplitude if math.isfinite(peak_amplitude) else 0.0)
        - 25.0 * balance_penalty
    )
    return AcousticFeatureFrame(
        gmo_valid=bool(gmo_valid),
        early_energy=float(early_energy),
        ref_early_energy=float(ref_early_energy),
        tof_ns=float(tof_ns),
        ref_tof_ns=float(ref_tof_ns),
        peak_amplitude=float(peak_amplitude),
        ref_peak_amplitude=float(ref_peak_amplitude),
        amplitude_mean=float(amplitude_mean),
        amplitude_std=float(amplitude_std),
        all_sgw_peak_mean=float(all_sgw_peak_mean),
        all_sgw_peak_std=float(all_sgw_peak_std),
        num_signal_ways=int(num_signal_ways),
        rx_early_energy_0=float(rx_early_energy_0),
        rx_early_energy_1=float(rx_early_energy_1),
        rx_tof_ns_0=float(rx_tof_ns_0),
        rx_tof_ns_1=float(rx_tof_ns_1),
        rx_energy_balance=float(rx_energy_balance),
        rx_tof_delta_ns=float(rx_tof_delta_ns),
        waveform_early_fraction=float(waveform_early_fraction),
        estimated_distance_energy_m=float(distance_energy),
        estimated_distance_tof_m=float(distance_tof),
        fused_distance_m=float(fused),
        alignment_score=float(alignment_score),
        primary_sgw_peak_sample_idx=int(primary_sgw_peak_sample_idx),
        ultra_early_energy=float(ultra_early_energy),
        early_peak_sample_idx=int(early_peak_sample_idx),
    )


def acoustic_features_from_gmo(
    gmo: Any,
    np: Any,
    *,
    energy_calibration: tuple[tuple[float, float], ...],
    tof_calibration: tuple[tuple[float, float], ...],
    fusion_energy_weight: float,
) -> AcousticFeatureFrame:
    summary = summarize_gmo_frame(gmo, np)
    ways = parse_signal_ways(gmo, np)
    e0, e1, t0, t1, balance, tof_delta = _rx_channel_stats(ways)
    waveform_frac = _waveform_early_fraction(gmo, np)
    return build_acoustic_features(
        gmo_valid=bool(summary.get("gmo_valid")),
        early_energy=_safe_float(summary.get("primary_sgw_early_energy")),
        ref_early_energy=_safe_float(summary.get("ref_sgw_early_energy")),
        # Use earliest-arrival way for TOF (direct path), not max-amplitude way.
        # reject_zero=True: Isaac Sim 6.0 returns timeOffsetNs=0 when ToF data is
        # unavailable; treat 0 as missing so fusion falls back to energy-only.
        tof_ns=_safe_float(summary.get("tof_primary_sgw_first_time_offset_ns"), reject_zero=True),
        ref_tof_ns=_safe_float(summary.get("ref_sgw_first_time_offset_ns"), reject_zero=True),
        peak_amplitude=_safe_float(summary.get("primary_sgw_peak")),
        ref_peak_amplitude=_safe_float(summary.get("ref_sgw_peak")),
        amplitude_mean=_safe_float(summary.get("amplitude_mean")),
        amplitude_std=_safe_float(summary.get("amplitude_std")),
        all_sgw_peak_mean=_safe_float(summary.get("all_sgw_peak_mean")),
        all_sgw_peak_std=_safe_float(summary.get("all_sgw_peak_std")),
        num_signal_ways=int(summary.get("num_signal_ways", 0) or 0),
        rx_early_energy_0=e0,
        rx_early_energy_1=e1,
        rx_tof_ns_0=t0,
        rx_tof_ns_1=t1,
        rx_energy_balance=balance,
        rx_tof_delta_ns=tof_delta,
        waveform_early_fraction=waveform_frac,
        energy_calibration=energy_calibration,
        tof_calibration=tof_calibration,
        fusion_energy_weight=fusion_energy_weight,
        primary_sgw_peak_sample_idx=int(summary.get("primary_sgw_peak_sample_idx") or 0),
        ultra_early_energy=_safe_float(summary.get("primary_sgw_ultra_early_energy")),
        early_peak_sample_idx=int(summary.get("primary_sgw_early_peak_sample_idx") or 0),
    )


def acoustic_features_from_summary(
    summary: dict[str, Any] | None,
    *,
    energy_calibration: tuple[tuple[float, float], ...],
    tof_calibration: tuple[tuple[float, float], ...],
    fusion_energy_weight: float,
) -> AcousticFeatureFrame:
    if not summary:
        return build_acoustic_features(
            gmo_valid=False,
            early_energy=math.nan,
            ref_early_energy=math.nan,
            tof_ns=math.nan,
            ref_tof_ns=math.nan,
            peak_amplitude=math.nan,
            ref_peak_amplitude=math.nan,
            amplitude_mean=math.nan,
            amplitude_std=math.nan,
            all_sgw_peak_mean=math.nan,
            all_sgw_peak_std=math.nan,
            num_signal_ways=0,
            rx_early_energy_0=math.nan,
            rx_early_energy_1=math.nan,
            rx_tof_ns_0=math.nan,
            rx_tof_ns_1=math.nan,
            rx_energy_balance=math.nan,
            rx_tof_delta_ns=math.nan,
            waveform_early_fraction=math.nan,
            energy_calibration=energy_calibration,
            tof_calibration=tof_calibration,
            fusion_energy_weight=fusion_energy_weight,
        )
    return build_acoustic_features(
        gmo_valid=bool(summary.get("gmo_valid")),
        early_energy=_safe_float(summary.get("primary_sgw_early_energy")),
        ref_early_energy=_safe_float(summary.get("ref_sgw_early_energy")),
        tof_ns=_safe_float(summary.get("primary_sgw_first_time_offset_ns")),
        ref_tof_ns=_safe_float(summary.get("ref_sgw_first_time_offset_ns")),
        peak_amplitude=_safe_float(summary.get("primary_sgw_peak")),
        ref_peak_amplitude=_safe_float(summary.get("ref_sgw_peak")),
        amplitude_mean=_safe_float(summary.get("amplitude_mean")),
        amplitude_std=_safe_float(summary.get("amplitude_std")),
        all_sgw_peak_mean=_safe_float(summary.get("all_sgw_peak_mean")),
        all_sgw_peak_std=_safe_float(summary.get("all_sgw_peak_std")),
        num_signal_ways=int(summary.get("num_signal_ways", 0) or 0),
        rx_early_energy_0=_safe_float(summary.get("rx_early_energy_0")),
        rx_early_energy_1=_safe_float(summary.get("rx_early_energy_1")),
        rx_tof_ns_0=_safe_float(summary.get("rx_tof_ns_0")),
        rx_tof_ns_1=_safe_float(summary.get("rx_tof_ns_1")),
        rx_energy_balance=_safe_float(summary.get("rx_energy_balance")),
        rx_tof_delta_ns=_safe_float(summary.get("rx_tof_delta_ns")),
        waveform_early_fraction=_safe_float(summary.get("waveform_early_fraction")),
        energy_calibration=energy_calibration,
        tof_calibration=tof_calibration,
        fusion_energy_weight=fusion_energy_weight,
        primary_sgw_peak_sample_idx=int(summary.get("primary_sgw_peak_sample_idx") or 0),
        ultra_early_energy=_safe_float(summary.get("primary_sgw_ultra_early_energy")),
        early_peak_sample_idx=int(summary.get("primary_sgw_early_peak_sample_idx") or 0),
    )


def enrich_gmo_summary(summary: dict[str, Any], gmo: Any, np: Any) -> dict[str, Any]:
    """Attach dual-RX and waveform features to a summarize_gmo_frame dict."""
    ways = parse_signal_ways(gmo, np)
    e0, e1, t0, t1, balance, tof_delta = _rx_channel_stats(ways)
    waveform_frac = _waveform_early_fraction(gmo, np)
    enriched = dict(summary)
    enriched.update(
        {
            "rx_early_energy_0": e0,
            "rx_early_energy_1": e1,
            "rx_tof_ns_0": t0,
            "rx_tof_ns_1": t1,
            "rx_energy_balance": balance,
            "rx_tof_delta_ns": tof_delta,
            "waveform_early_fraction": waveform_frac,
        }
    )
    return enriched