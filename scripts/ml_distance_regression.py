"""ML-based distance regression from RTX Acoustic GMO features.

Leave-One-Trial-Out (LOTO) cross-validation: train on 6 trials, test on 1.
Compares RandomForest, SVR, MLP, and baseline (mean prediction).

Usage:
    python3 scripts/ml_distance_regression.py
    python3 scripts/ml_distance_regression.py --csv <path_to_combined_csv>
"""

from __future__ import annotations

import argparse
import csv
import math
import pathlib
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Feature sets (from simple to complex)
# ---------------------------------------------------------------------------
FEATURE_SETS = {
    "A_raw_energy": [
        "primary_sgw_early_energy",
        "primary_sgw_ultra_early_energy",
        "waveform_early_fraction",
        "amplitude_std",
    ],
    "B_plus_diff": [
        "primary_sgw_early_energy",
        "primary_sgw_ultra_early_energy",
        "waveform_early_fraction",
        "amplitude_std",
        "diff_ultra_early_energy",
        "diff_early_energy",
        "diff_early_peak_sample_idx",
    ],
    "C_plus_mf_global": [
        "primary_sgw_early_energy",
        "primary_sgw_ultra_early_energy",
        "waveform_early_fraction",
        "amplitude_std",
        "diff_ultra_early_energy",
        "diff_early_energy",
        "diff_early_peak_sample_idx",
        "mf_tof_sample_idx",
        "global_diff_ultra_early_energy",
        "global_diff_early_energy",
        "global_diff_early_peak_sample_idx",
    ],
    "D_all": [
        "primary_sgw_early_energy",
        "primary_sgw_ultra_early_energy",
        "ref_sgw_early_energy",
        "rx_energy_balance",
        "waveform_early_fraction",
        "amplitude_std",
        "primary_sgw_peak_sample_idx",
        "primary_sgw_early_peak_sample_idx",
        "diff_early_energy",
        "diff_ultra_early_energy",
        "diff_peak_sample_idx",
        "diff_early_peak_sample_idx",
        "mf_tof_sample_idx",
        "global_diff_early_energy",
        "global_diff_ultra_early_energy",
        "global_diff_early_peak_sample_idx",
    ],
}


def load_csv(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_float(value: Any) -> float | None:
    try:
        v = float(value)
        if math.isfinite(v):
            return v
        return None
    except (TypeError, ValueError):
        return None


def build_Xy(
    rows: list[dict[str, Any]],
    feature_names: list[str],
    valid_features: list[str],
) -> tuple[list[list[float]], list[float], list[int]]:
    """Return (X, y, trial_ids) with rows where all features AND target are valid."""
    X, y, tids = [], [], []
    for row in rows:
        target = safe_float(row.get("oracle_distance_m"))
        if target is None:
            continue
        feat_vals = []
        ok = True
        for f in valid_features:
            val = safe_float(row.get(f))
            if val is None:
                # invalid sentinel values
                raw = str(row.get(f, "")).strip()
                if raw in ("-1", "nan", ""):
                    ok = False
                    break
                ok = False
                break
            feat_vals.append(val)
        if not ok or len(feat_vals) != len(valid_features):
            continue
        X.append(feat_vals)
        y.append(target)
        tids.append(int(float(row.get("trial_id", -1))))
    return X, y, tids


def pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(
        sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)
    )
    return num / den if den > 0 else float("nan")


def rmse(preds: list[float], targets: list[float]) -> float:
    if not preds:
        return float("nan")
    return math.sqrt(sum((p - t) ** 2 for p, t in zip(preds, targets)) / len(preds))


def loto_cv(
    X: list[list[float]],
    y: list[float],
    trial_ids: list[int],
    model_factory,
) -> tuple[list[float], list[float]]:
    """Leave-One-Trial-Out cross-validation. Returns (all_preds, all_targets)."""
    import numpy as np

    unique_trials = sorted(set(trial_ids))
    all_preds: list[float] = []
    all_targets: list[float] = []

    Xarr = np.array(X, dtype=float)
    yarr = np.array(y, dtype=float)
    tids = np.array(trial_ids)

    for held_out in unique_trials:
        train_mask = tids != held_out
        test_mask = tids == held_out
        if test_mask.sum() == 0 or train_mask.sum() == 0:
            continue

        X_train, y_train = Xarr[train_mask], yarr[train_mask]
        X_test, y_test = Xarr[test_mask], yarr[test_mask]

        # Feature standardization (fit on train only)
        mu = X_train.mean(axis=0)
        sigma = X_train.std(axis=0)
        sigma[sigma == 0] = 1.0
        X_train_n = (X_train - mu) / sigma
        X_test_n = (X_test - mu) / sigma

        model = model_factory()
        model.fit(X_train_n, y_train)
        preds = model.predict(X_test_n).tolist()

        all_preds.extend(preds)
        all_targets.extend(y_test.tolist())

    return all_preds, all_targets


def run_single_feature_baseline(
    rows: list[dict[str, Any]],
    trial_ids_all: list[int],
) -> None:
    """Print Pearson r for each single feature (reference baseline)."""
    import numpy as np

    print("\n=== 單特徵 Pearson r 基準 ===")
    single_feats = [
        "primary_sgw_early_energy",
        "primary_sgw_ultra_early_energy",
        "diff_ultra_early_energy",
        "diff_early_peak_sample_idx",
        "global_diff_ultra_early_energy",
        "mf_tof_sample_idx",
        "waveform_early_fraction",
        "amplitude_std",
    ]
    for feat in single_feats:
        pairs = [
            (safe_float(r.get(feat)), safe_float(r.get("oracle_distance_m")))
            for r in rows
            if safe_float(r.get(feat)) is not None
            and safe_float(r.get("oracle_distance_m")) is not None
            and str(r.get(feat, "")).strip() not in ("-1", "nan", "")
        ]
        if pairs:
            xs, ys = zip(*pairs)
            r = pearson_r(list(xs), list(ys))
            print(f"  {feat:<42} r = {r:+.4f}  (n={len(pairs)})")


def main() -> None:
    parser = argparse.ArgumentParser(description="ML distance regression from GMO features.")
    parser.add_argument(
        "--csv",
        type=str,
        default="/home/lab109/song/isaacsim6.0/runtime/outputs/global_baseline_diff_v1/global_baseline_diff_combined.csv",
    )
    parser.add_argument("--feature-set", choices=list(FEATURE_SETS.keys()), default=None,
                        help="Which feature set to use. If omitted, tries all sets.")
    args = parser.parse_args()

    try:
        from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
        from sklearn.svm import SVR
        from sklearn.neural_network import MLPRegressor
    except ImportError:
        print("ERROR: scikit-learn not found. Install with: pip install scikit-learn")
        sys.exit(1)

    import numpy as np

    print(f"Loading: {args.csv}")
    rows = load_csv(args.csv)
    print(f"Total rows: {len(rows)}")

    # Detect which feature columns actually exist in this CSV
    if rows:
        available_cols = set(rows[0].keys())
    else:
        print("ERROR: CSV is empty")
        sys.exit(1)

    run_single_feature_baseline(rows, [])

    feature_sets_to_run = (
        {args.feature_set: FEATURE_SETS[args.feature_set]}
        if args.feature_set
        else FEATURE_SETS
    )

    models = {
        "RandomForest":    lambda: RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42),
        "GradBoost":       lambda: GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42),
        "SVR_rbf":         lambda: SVR(kernel="rbf", C=10.0, epsilon=0.03, gamma="scale"),
        "MLP_32_16":       lambda: MLPRegressor(hidden_layer_sizes=(32, 16), max_iter=3000,
                                                 learning_rate_init=0.001, random_state=42),
    }

    print("\n=== Leave-One-Trial-Out 交叉驗證結果 ===")
    print(f"{'特徵集':<20} {'模型':<15} {'R²':>7} {'RMSE(m)':>9} {'n_feat':>7}")
    print("-" * 65)

    best_r2 = -999.0
    best_label = ""

    for fs_name, feat_list in feature_sets_to_run.items():
        # Only use features that exist in the CSV
        valid_features = [f for f in feat_list if f in available_cols]
        if not valid_features:
            print(f"{fs_name}: 無可用特徵，跳過")
            continue

        X, y, tids = build_Xy(rows, feat_list, valid_features)
        if len(X) < 20:
            print(f"{fs_name}: 有效樣本不足（{len(X)}），跳過")
            continue

        for model_name, model_factory in models.items():
            try:
                preds, targets = loto_cv(X, y, tids, model_factory)
                if not preds:
                    continue
                ss_res = sum((p - t) ** 2 for p, t in zip(preds, targets))
                mean_t = sum(targets) / len(targets)
                ss_tot = sum((t - mean_t) ** 2 for t in targets)
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
                err = rmse(preds, targets)
                label = f"{fs_name}/{model_name}"
                print(f"{fs_name:<20} {model_name:<15} {r2:>7.4f} {err:>9.4f} {len(valid_features):>7}")
                if math.isfinite(r2) and r2 > best_r2:
                    best_r2 = r2
                    best_label = label
                    best_preds = preds
                    best_targets = targets
            except Exception as e:
                print(f"{fs_name:<20} {model_name:<15} ERROR: {e}")

    print("-" * 65)
    if best_label:
        print(f"\n最佳組合: {best_label}")
        print(f"  R² = {best_r2:.4f}")
        print(f"  RMSE = {rmse(best_preds, best_targets):.4f} m")
        r = pearson_r(best_preds, best_targets)
        print(f"  Pearson r (pred vs actual) = {r:.4f}")

        # Distance range breakdown
        print("\n距離分段誤差分析:")
        bins = [(0.0, 0.35), (0.35, 0.55), (0.55, 0.85)]
        for lo, hi in bins:
            sub = [(p, t) for p, t in zip(best_preds, best_targets) if lo <= t < hi]
            if sub:
                ps, ts = zip(*sub)
                print(f"  oracle {lo:.2f}–{hi:.2f}m: n={len(sub)} RMSE={rmse(list(ps), list(ts)):.4f}m")

    # Compare to energy-only single-feature baseline
    print("\n=== 對比：energy-only 單特徵 LOTO ===")
    for single in ["primary_sgw_ultra_early_energy", "diff_ultra_early_energy"]:
        if single not in available_cols:
            continue
        valid = [f for f in [single] if f in available_cols]
        X1, y1, t1 = build_Xy(rows, [single], valid)
        if not X1:
            continue
        preds1, targets1 = loto_cv(X1, y1, t1, lambda: RandomForestRegressor(n_estimators=50, random_state=42))
        ss_res = sum((p - t) ** 2 for p, t in zip(preds1, targets1))
        mean_t = sum(targets1) / len(targets1)
        ss_tot = sum((t - mean_t) ** 2 for t in targets1)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        print(f"  RF on {single}: R²={r2:.4f} RMSE={rmse(preds1, targets1):.4f}m")


if __name__ == "__main__":
    main()
