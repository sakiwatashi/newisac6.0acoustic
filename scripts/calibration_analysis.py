#!/usr/bin/env python3
"""
Energy Calibration Analysis v1
Analyze experimental data to recalibrate early_energy vs oracle_distance_m

Usage:
  python3 /home/lab109/song/isaacsim6.0/scripts/calibration_analysis.py
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# ============================================================================
# STEP 1: Load and explore dataset
# ============================================================================
csv_path = Path("/home/lab109/song/isaacsim6.0/runtime/outputs/physical_ai_v9_skip_lift_clean_dataset/physical_ai_acoustic_steps.csv")
print("=" * 80)
print("CALIBRATION ANALYSIS: early_energy vs oracle_distance_m")
print("=" * 80)

if not csv_path.exists():
    print(f"ERROR: CSV not found at {csv_path}")
    sys.exit(1)

try:
    df = pd.read_csv(csv_path)
except Exception as e:
    print(f"ERROR reading CSV: {e}")
    sys.exit(1)

print(f"\n[DATASET] Total rows: {len(df)}")
print(f"[DATASET] Columns: {list(df.columns)}")

# Check required columns
required = ['gmo_valid', 'oracle_distance_m', 'early_energy']
missing = [c for c in required if c not in df.columns]
if missing:
    print(f"ERROR: Missing columns: {missing}")
    sys.exit(1)

# ============================================================================
# STEP 2: Filter valid approach data
# ============================================================================
print(f"\n--- Raw Data Statistics ---")
print(df[required].describe())

# Filter: gmo_valid=True, distances in [0.05, 1.5]m, positive energy
mask = (
    (df['gmo_valid'] == True) &
    df['oracle_distance_m'].notna() &
    df['early_energy'].notna() &
    (df['oracle_distance_m'] > 0.05) &
    (df['oracle_distance_m'] < 1.5) &
    (df['early_energy'] > 0)
)
approach = df[mask][['oracle_distance_m', 'early_energy']].copy()

print(f"\n--- Filtered Data (valid approach steps) ---")
print(f"Valid rows: {len(approach)}")
print(f"OracleDistance range: [{approach['oracle_distance_m'].min():.3f}, {approach['oracle_distance_m'].max():.3f}] m")
print(f"EarlyEnergy range: [{approach['early_energy'].min():.1f}, {approach['early_energy'].max():.1f}]")
print(f"Filtered data stats:")
print(approach.describe())

# ============================================================================
# STEP 3: Bin analysis by distance
# ============================================================================
print(f"\n--- Binned Analysis (0.05m bins) ---")
approach['dist_bin'] = (approach['oracle_distance_m'] * 20).round() / 20
stats = approach.groupby('dist_bin')['early_energy'].agg(['count', 'mean', 'median', 'std', 'min', 'max'])
stats = stats[stats['count'] > 0].sort_index(ascending=False)
print(stats.to_string())

# ============================================================================
# STEP 4: Build recalibration table (high energy → far, low energy → near)
# ============================================================================
print(f"\n--- Proposed New Calibration Table ---")
print("(Using median energy per distance bin, ensuring monotonic relationship)")

# Filter bins with sufficient data (count >= 3)
good_bins = stats[stats['count'] >= 3].copy()
good_bins = good_bins.sort_index(ascending=False)  # Far to near

calibration_points = []
for dist_bin, row in good_bins.iterrows():
    energy_median = row['median']
    count = int(row['count'])
    calibration_points.append((energy_median, dist_bin, count))
    print(f"  ({energy_median:6.1f}, {dist_bin:.3f}),  # count={count}, "
          f"mean={row['mean']:.1f}, std={row['std']:.1f}")

# Sort by energy descending for the calibration table
calibration_points.sort(key=lambda x: x[0], reverse=True)

print(f"\nCalibration tuple (energy, distance):")
cal_tuple = tuple((e, d) for e, d, _ in calibration_points)
print(repr(cal_tuple))

# ============================================================================
# STEP 5: Compare with existing calibration
# ============================================================================
print(f"\n--- Comparison with DEFAULT_CALIBRATION ---")

EXISTING_CALIBRATION = (
    (221.0, 0.85),
    (155.0, 0.72),
    (148.0, 0.65),
    (140.0, 0.50),
    (136.0, 0.40),
    (132.0, 0.30),
    (128.0, 0.25),
    (95.0, 0.22),
)

def interpolate_distance(energy, calibration_table):
    """Linear interpolation to estimate distance from energy."""
    if not calibration_table:
        return None
    # Sort by energy descending
    cal_sorted = sorted(calibration_table, key=lambda x: x[0], reverse=True)

    if energy >= cal_sorted[0][0]:
        return cal_sorted[0][1]
    if energy <= cal_sorted[-1][0]:
        return cal_sorted[-1][1]

    # Find bracketing pair
    for i in range(len(cal_sorted) - 1):
        e1, d1 = cal_sorted[i]
        e2, d2 = cal_sorted[i + 1]
        if e2 <= energy <= e1:
            # Interpolate
            frac = (energy - e2) / (e1 - e2) if e1 != e2 else 0
            return d2 + frac * (d1 - d2)
    return None

# Evaluate existing calibration on filtered data
approach['est_dist_old'] = approach['early_energy'].apply(
    lambda e: interpolate_distance(e, EXISTING_CALIBRATION)
)
approach['error_old_m'] = abs(approach['est_dist_old'] - approach['oracle_distance_m'])

old_error_stats = approach['error_old_m'].describe()
print("\nExisting calibration performance:")
print(f"  Mean error: {old_error_stats['mean']:.4f} m")
print(f"  Median error: {old_error_stats['50%']:.4f} m")
print(f"  Max error: {old_error_stats['max']:.4f} m")
print(f"  Std dev: {old_error_stats['std']:.4f} m")

# Evaluate new calibration
approach['est_dist_new'] = approach['early_energy'].apply(
    lambda e: interpolate_distance(e, cal_tuple)
)
approach['error_new_m'] = abs(approach['est_dist_new'] - approach['oracle_distance_m'])

new_error_stats = approach['error_new_m'].describe()
print(f"\nProposed calibration performance:")
print(f"  Mean error: {new_error_stats['mean']:.4f} m")
print(f"  Median error: {new_error_stats['50%']:.4f} m")
print(f"  Max error: {new_error_stats['max']:.4f} m")
print(f"  Std dev: {new_error_stats['std']:.4f} m")

# Improvement
improvement_mean = (old_error_stats['mean'] - new_error_stats['mean']) / old_error_stats['mean'] * 100
improvement_median = (old_error_stats['50%'] - new_error_stats['50%']) / old_error_stats['50%'] * 100
improvement_max = (old_error_stats['max'] - new_error_stats['max']) / old_error_stats['max'] * 100

print(f"\nImprovement with new calibration:")
print(f"  Mean error improvement: {improvement_mean:+.1f}%")
print(f"  Median error improvement: {improvement_median:+.1f}%")
print(f"  Max error improvement: {improvement_max:+.1f}%")

# ============================================================================
# STEP 6: Distance-specific analysis
# ============================================================================
print(f"\n--- Error Analysis by Distance Range ---")

distance_ranges = [
    (0.05, 0.25, "Near (0.05-0.25m)"),
    (0.25, 0.40, "Close (0.25-0.40m)"),
    (0.40, 0.60, "Mid (0.40-0.60m)"),
    (0.60, 1.50, "Far (0.60-1.50m)"),
]

for d_min, d_max, label in distance_ranges:
    subset = approach[(approach['oracle_distance_m'] >= d_min) & (approach['oracle_distance_m'] < d_max)]
    if len(subset) > 0:
        old_err = subset['error_old_m'].describe()
        new_err = subset['error_new_m'].describe()
        print(f"\n{label}: n={len(subset)}")
        print(f"  Old: mean={old_err['mean']:.4f}m, max={old_err['max']:.4f}m")
        print(f"  New: mean={new_err['mean']:.4f}m, max={new_err['max']:.4f}m")

# ============================================================================
# STEP 7: Edge case examination (the oracle=0.43m case from problem statement)
# ============================================================================
print(f"\n--- Edge Case Verification (oracle ~0.43m) ---")
subset_edge = approach[(approach['oracle_distance_m'] >= 0.40) & (approach['oracle_distance_m'] <= 0.46)]
if len(subset_edge) > 0:
    print(f"Found {len(subset_edge)} samples near oracle=0.43m")
    print(f"Early energy range: [{subset_edge['early_energy'].min():.1f}, {subset_edge['early_energy'].max():.1f}]")
    print(f"Early energy median: {subset_edge['early_energy'].median():.1f}")

    test_energy = 130  # From problem statement
    old_est = interpolate_distance(test_energy, EXISTING_CALIBRATION)
    new_est = interpolate_distance(test_energy, cal_tuple)
    print(f"\nFor early_energy={test_energy}:")
    print(f"  Old calibration estimates: {old_est:.3f}m (error from 0.43m: {abs(old_est - 0.43):.3f}m)")
    print(f"  New calibration estimates: {new_est:.3f}m (error from 0.43m: {abs(new_est - 0.43):.3f}m)")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print(f"\n" + "=" * 80)
print("FINAL RECOMMENDATION")
print("=" * 80)
print(f"\nUpdate grasp_passport_v1.py DEFAULT_CALIBRATION with:")
print(f"\nDEFAULT_CALIBRATION = {repr(cal_tuple)}")
print(f"\nExpected improvement:")
print(f"  - Mean error: {old_error_stats['mean']:.4f}m → {new_error_stats['mean']:.4f}m ({improvement_mean:+.1f}%)")
print(f"  - Median error: {old_error_stats['50%']:.4f}m → {new_error_stats['50%']:.4f}m ({improvement_median:+.1f}%)")
print(f"  - Max error: {old_error_stats['max']:.4f}m → {new_error_stats['max']:.4f}m ({improvement_max:+.1f}%)")
print()
