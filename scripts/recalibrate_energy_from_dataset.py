#!/usr/bin/env python3
"""
Recalibrate energy-to-distance table from v9 dataset.
Outputs analysis report and proposed calibration.

Usage:
  python3 scripts/recalibrate_energy_from_dataset.py [--output FILE]
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any

def interpolate_distance(energy: float, calibration_table: list[tuple[float, float]]) -> float | None:
    """Linear interpolation to estimate distance from energy."""
    if not calibration_table:
        return None
    cal_sorted = sorted(calibration_table, key=lambda x: x[0], reverse=True)

    if energy >= cal_sorted[0][0]:
        return cal_sorted[0][1]
    if energy <= cal_sorted[-1][0]:
        return cal_sorted[-1][1]

    for i in range(len(cal_sorted) - 1):
        e1, d1 = cal_sorted[i]
        e2, d2 = cal_sorted[i + 1]
        if e2 <= energy <= e1:
            frac = (energy - e2) / (e1 - e2) if e1 != e2 else 0
            return d2 + frac * (d1 - d2)
    return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='/home/lab109/song/isaacsim6.0/scripts/CALIBRATION_ANALYSIS_REPORT.txt',
                        help='Output report file')
    parser.add_argument('--csv', default='/home/lab109/song/isaacsim6.0/runtime/outputs/physical_ai_v9_skip_lift_clean_dataset/physical_ai_acoustic_steps.csv',
                        help='Input CSV file')
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found at {csv_path}")
        sys.exit(1)

    # Load and filter data
    print(f"Loading data from {csv_path}...")
    rows = []
    raw_count = 0
    valid_count = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_count += 1
            try:
                # Parse fields
                gmo_valid = row.get('gmo_valid', '').lower() == 'true'
                early_energy = float(row.get('early_energy', 'nan'))
                oracle_distance_m = float(row.get('oracle_distance_m', 'nan'))

                # Filter
                if not gmo_valid:
                    continue
                if not (math.isfinite(early_energy) and math.isfinite(oracle_distance_m)):
                    continue
                if not (0.05 < oracle_distance_m < 1.5):
                    continue
                if early_energy <= 0:
                    continue

                rows.append({
                    'early_energy': early_energy,
                    'oracle_distance_m': oracle_distance_m,
                    'gmo_valid': gmo_valid,
                })
                valid_count += 1
            except (ValueError, KeyError):
                continue

    print(f"Loaded {raw_count} total rows, {valid_count} valid rows")

    if valid_count == 0:
        print("ERROR: No valid data found")
        sys.exit(1)

    # Bin analysis
    bin_size_m = 0.05
    bins = defaultdict(list)
    for row in rows:
        dist = row['oracle_distance_m']
        bin_center = round(dist / bin_size_m) * bin_size_m
        bins[bin_center].append(row['early_energy'])

    # Build calibration from bins with n >= 3
    print(f"\nAnalyzing {len(bins)} distance bins...")
    calibration_points = []

    for dist_bin in sorted(bins.keys(), reverse=True):
        energies = bins[dist_bin]
        if len(energies) < 3:
            continue

        median_energy = sorted(energies)[len(energies) // 2]
        mean_energy = sum(energies) / len(energies)
        std_energy = (sum((e - mean_energy) ** 2 for e in energies) / len(energies)) ** 0.5

        calibration_points.append({
            'distance_m': dist_bin,
            'count': len(energies),
            'median_energy': median_energy,
            'mean_energy': mean_energy,
            'std_energy': std_energy,
            'min_energy': min(energies),
            'max_energy': max(energies),
        })

    # Sort by energy descending
    calibration_points.sort(key=lambda x: x['median_energy'], reverse=True)

    # Build calibration tuple (energy, distance)
    cal_tuple = [(p['median_energy'], p['distance_m']) for p in calibration_points]

    # Existing calibration (from grasp_passport_v1.py)
    EXISTING_CALIBRATION = [
        (221.0, 0.85),
        (155.0, 0.72),
        (148.0, 0.65),
        (140.0, 0.50),
        (136.0, 0.40),
        (132.0, 0.30),
        (128.0, 0.25),
        (95.0, 0.22),
    ]

    # Evaluate calibrations
    old_errors = []
    new_errors = []

    for row in rows:
        energy = row['early_energy']
        true_dist = row['oracle_distance_m']

        old_est = interpolate_distance(energy, EXISTING_CALIBRATION)
        if old_est is not None:
            old_errors.append(abs(old_est - true_dist))

        new_est = interpolate_distance(energy, cal_tuple)
        if new_est is not None:
            new_errors.append(abs(new_est - true_dist))

    # Statistics
    def stats(errors):
        if not errors:
            return {}
        sorted_err = sorted(errors)
        return {
            'mean': sum(errors) / len(errors),
            'median': sorted_err[len(errors) // 2],
            'max': max(errors),
            'min': min(errors),
            'std': (sum((e - sum(errors)/len(errors))**2 for e in errors) / len(errors)) ** 0.5,
            'count': len(errors),
        }

    old_stats = stats(old_errors)
    new_stats = stats(new_errors)

    # Generate report
    report_lines = [
        "=" * 80,
        "ENERGY CALIBRATION ANALYSIS REPORT",
        "=" * 80,
        "",
        f"Dataset: {csv_path.name}",
        f"Total rows: {raw_count}",
        f"Valid rows (gmo_valid=True, oracle [0.05-1.5m]): {valid_count}",
        "",
        "[DATA SUMMARY]",
        f"Oracle distance range: {min(r['oracle_distance_m'] for r in rows):.3f} - {max(r['oracle_distance_m'] for r in rows):.3f} m",
        f"Early energy range: {min(r['early_energy'] for r in rows):.1f} - {max(r['early_energy'] for r in rows):.1f}",
        f"Distance bins (n>=3): {len(calibration_points)}",
        "",
        "[BINNED DATA (0.05m bins, sorted by distance)]",
    ]

    for p in calibration_points:
        report_lines.append(
            f"  {p['distance_m']:.2f}m: n={p['count']:3d}, "
            f"median={p['median_energy']:6.1f}, mean={p['mean_energy']:6.1f}, std={p['std_energy']:6.1f}"
        )

    report_lines.extend([
        "",
        "[NEW CALIBRATION TABLE]",
        f"DEFAULT_CALIBRATION = {repr(tuple(cal_tuple))}",
        "",
        "[PERFORMANCE COMPARISON]",
        "Existing calibration (from grasp_passport_v1.py):",
    ])

    for key in ['mean', 'median', 'max', 'std']:
        if key in old_stats:
            report_lines.append(f"  {key:6s}: {old_stats[key]:.4f} m")

    report_lines.extend([
        "",
        "New calibration (data-derived):",
    ])

    for key in ['mean', 'median', 'max', 'std']:
        if key in new_stats:
            report_lines.append(f"  {key:6s}: {new_stats[key]:.4f} m")

    report_lines.append("")

    if old_stats.get('mean') and new_stats.get('mean'):
        improvement_mean = (old_stats['mean'] - new_stats['mean']) / old_stats['mean'] * 100
        improvement_median = (old_stats['median'] - new_stats['median']) / old_stats['median'] * 100
        improvement_max = (old_stats['max'] - new_stats['max']) / old_stats['max'] * 100

        report_lines.extend([
            "[IMPROVEMENT]",
            f"Mean error:   {improvement_mean:+.1f}%",
            f"Median error: {improvement_median:+.1f}%",
            f"Max error:    {improvement_max:+.1f}%",
            "",
        ])

    # Edge case analysis
    report_lines.extend([
        "[EDGE CASE: oracle ~0.43m (problem statement)]",
    ])

    subset_edge = [r for r in rows if 0.40 <= r['oracle_distance_m'] <= 0.46]
    if subset_edge:
        energies_edge = [r['early_energy'] for r in subset_edge]
        report_lines.extend([
            f"Samples found: {len(subset_edge)}",
            f"Early energy range: {min(energies_edge):.1f} - {max(energies_edge):.1f}",
            f"Early energy median: {sorted(energies_edge)[len(energies_edge)//2]:.1f}",
            "",
        ])

        test_energy = 130.0  # From problem statement
        old_est = interpolate_distance(test_energy, EXISTING_CALIBRATION)
        new_est = interpolate_distance(test_energy, cal_tuple)

        report_lines.extend([
            f"For early_energy={test_energy}:",
            f"  Old calibration: {old_est:.3f}m (error from 0.43m: {abs(old_est - 0.43):.3f}m)",
            f"  New calibration: {new_est:.3f}m (error from 0.43m: {abs(new_est - 0.43):.3f}m)",
            "",
        ])
    else:
        report_lines.append("No samples found in oracle 0.40-0.46m range")
        report_lines.append("")

    report_lines.extend([
        "=" * 80,
        "RECOMMENDATION",
        "=" * 80,
        "",
        "Update grasp_passport_v1.py line 139-148 with:",
        "",
        f"DEFAULT_CALIBRATION: tuple[tuple[float, float], ...] = {repr(tuple(cal_tuple))}",
        "",
    ])

    # Write report
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        f.write('\n'.join(report_lines))

    print(f"\nReport written to: {output_path}")
    print('\n'.join(report_lines[:50]))  # Print first 50 lines

if __name__ == '__main__':
    main()
