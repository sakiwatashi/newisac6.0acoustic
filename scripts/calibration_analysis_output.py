#!/usr/bin/env python3
"""Generate calibration analysis report to output file."""

import pandas as pd
import numpy as np
import sys
import json
from pathlib import Path

csv_path = "/home/lab109/song/isaacsim6.0/runtime/outputs/physical_ai_v9_skip_lift_clean_dataset/physical_ai_acoustic_steps.csv"
output_file = "/home/lab109/song/isaacsim6.0/scripts/calibration_analysis_report.txt"

try:
    # Load data
    df = pd.read_csv(csv_path)

    # Filter for valid approach data
    mask = (
        (df['gmo_valid'] == True) &
        df['oracle_distance_m'].notna() &
        df['early_energy'].notna() &
        (df['oracle_distance_m'] > 0.05) &
        (df['oracle_distance_m'] < 1.5) &
        (df['early_energy'] > 0)
    )
    approach = df[mask][['oracle_distance_m', 'early_energy']].copy()

    # Binned analysis
    approach['dist_bin'] = (approach['oracle_distance_m'] * 20).round() / 20
    stats = approach.groupby('dist_bin')['early_energy'].agg(['count', 'mean', 'median', 'std', 'min', 'max'])
    stats = stats[stats['count'] > 0].sort_index(ascending=False)

    # Build calibration from good bins
    good_bins = stats[stats['count'] >= 3].copy()
    good_bins = good_bins.sort_index(ascending=False)
    calibration_points = []
    for dist_bin, row in good_bins.iterrows():
        calibration_points.append((row['median'], dist_bin, int(row['count'])))
    calibration_points.sort(key=lambda x: x[0], reverse=True)
    cal_tuple = tuple((e, d) for e, d, _ in calibration_points)

    # Interpolation function
    def interpolate_distance(energy, calibration_table):
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

    # Compare calibrations
    EXISTING_CALIBRATION = (
        (221.0, 0.85), (155.0, 0.72), (148.0, 0.65), (140.0, 0.50),
        (136.0, 0.40), (132.0, 0.30), (128.0, 0.25), (95.0, 0.22),
    )

    approach['est_dist_old'] = approach['early_energy'].apply(
        lambda e: interpolate_distance(e, EXISTING_CALIBRATION)
    )
    approach['error_old_m'] = abs(approach['est_dist_old'] - approach['oracle_distance_m'])

    approach['est_dist_new'] = approach['early_energy'].apply(
        lambda e: interpolate_distance(e, cal_tuple)
    )
    approach['error_new_m'] = abs(approach['est_dist_new'] - approach['oracle_distance_m'])

    old_error_stats = approach['error_old_m'].describe()
    new_error_stats = approach['error_new_m'].describe()

    # Output
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("CALIBRATION ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"[DATASET]\n")
        f.write(f"Total rows: {len(df)}\n")
        f.write(f"Valid approach rows (gmo_valid=True, oracle [0.05-1.5m]): {len(approach)}\n\n")

        f.write(f"[DATA RANGE]\n")
        f.write(f"Oracle distance: {approach['oracle_distance_m'].min():.3f} - {approach['oracle_distance_m'].max():.3f} m\n")
        f.write(f"Early energy: {approach['early_energy'].min():.1f} - {approach['early_energy'].max():.1f}\n\n")

        f.write(f"[BINNED DATA (0.05m bins)]\n")
        for dist_bin in sorted(good_bins.index, reverse=True):
            row = good_bins.loc[dist_bin]
            f.write(f"  Bin {dist_bin:.2f}m: n={int(row['count'])}, median={row['median']:.1f}, mean={row['mean']:.1f}, std={row['std']:.1f}\n")
        f.write("\n")

        f.write(f"[NEW CALIBRATION TABLE]\n")
        f.write(f"DEFAULT_CALIBRATION = {repr(cal_tuple)}\n\n")

        f.write(f"[PERFORMANCE COMPARISON]\n")
        f.write(f"Existing calibration:\n")
        f.write(f"  Mean error: {old_error_stats['mean']:.4f} m\n")
        f.write(f"  Median error: {old_error_stats['50%']:.4f} m\n")
        f.write(f"  Max error: {old_error_stats['max']:.4f} m\n")
        f.write(f"  Std dev: {old_error_stats['std']:.4f} m\n\n")

        f.write(f"New calibration:\n")
        f.write(f"  Mean error: {new_error_stats['mean']:.4f} m\n")
        f.write(f"  Median error: {new_error_stats['50%']:.4f} m\n")
        f.write(f"  Max error: {new_error_stats['max']:.4f} m\n")
        f.write(f"  Std dev: {new_error_stats['std']:.4f} m\n\n")

        improvement_mean = (old_error_stats['mean'] - new_error_stats['mean']) / old_error_stats['mean'] * 100
        improvement_median = (old_error_stats['50%'] - new_error_stats['50%']) / old_error_stats['50%'] * 100
        improvement_max = (old_error_stats['max'] - new_error_stats['max']) / old_error_stats['max'] * 100

        f.write(f"Improvement:\n")
        f.write(f"  Mean error: {improvement_mean:+.1f}%\n")
        f.write(f"  Median error: {improvement_median:+.1f}%\n")
        f.write(f"  Max error: {improvement_max:+.1f}%\n\n")

        # Edge case analysis
        f.write(f"[EDGE CASE: oracle ~0.43m]\n")
        subset_edge = approach[(approach['oracle_distance_m'] >= 0.40) & (approach['oracle_distance_m'] <= 0.46)]
        if len(subset_edge) > 0:
            f.write(f"Samples found: {len(subset_edge)}\n")
            f.write(f"Early energy range: {subset_edge['early_energy'].min():.1f} - {subset_edge['early_energy'].max():.1f}\n")
            f.write(f"Early energy median: {subset_edge['early_energy'].median():.1f}\n")
            test_energy = 130
            old_est = interpolate_distance(test_energy, EXISTING_CALIBRATION)
            new_est = interpolate_distance(test_energy, cal_tuple)
            f.write(f"\nFor early_energy={test_energy}:\n")
            f.write(f"  Old calibration: {old_est:.3f}m (error from 0.43m: {abs(old_est - 0.43):.3f}m)\n")
            f.write(f"  New calibration: {new_est:.3f}m (error from 0.43m: {abs(new_est - 0.43):.3f}m)\n")
        else:
            f.write("No samples found in oracle 0.40-0.46m range\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("Done.\n")

    print("Analysis completed. Output written to:", output_file)

except Exception as e:
    import traceback
    with open("/home/lab109/song/isaacsim6.0/scripts/calibration_analysis_error.txt", 'w') as f:
        f.write(f"Error: {e}\n")
        f.write(traceback.format_exc())
    print(f"Error: {e}")
    sys.exit(1)
