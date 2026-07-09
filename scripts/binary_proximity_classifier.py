"""Binary acoustic proximity detection: oracle_distance_m < THRESHOLD vs >= THRESHOLD.

Leave-One-Trial-Out (LOTO) cross-validation.
Goal: detect whether the arm has crossed the standoff boundary acoustically.

Usage:
    python3 scripts/binary_proximity_classifier.py
    python3 scripts/binary_proximity_classifier.py --threshold 0.40 --csv <path>
"""

from __future__ import annotations

import argparse
import csv
import math
import pathlib
import sys
from typing import Any

# 感測器接近板手的停止距離門檻（m）
DEFAULT_THRESHOLD = 0.35

# 所有可用的特徵欄位（WPM 輸出）
ALL_FEATURES = [
    "primary_sgw_early_energy",
    "primary_sgw_ultra_early_energy",
    "primary_sgw_peak_sample_idx",
    "primary_sgw_early_peak_sample_idx",
    "ref_sgw_early_energy",
    "rx_energy_balance",
    "waveform_early_fraction",
    "amplitude_std",
    "diff_early_energy",
    "diff_ultra_early_energy",
    "diff_peak_sample_idx",
    "diff_early_peak_sample_idx",
    "mf_tof_sample_idx",
    "global_diff_early_energy",
    "global_diff_ultra_early_energy",
    "global_diff_early_peak_sample_idx",
]

# 特徵子集
FEATURE_SETS = {
    "A_energy":       ["primary_sgw_early_energy", "primary_sgw_ultra_early_energy",
                       "waveform_early_fraction", "amplitude_std"],
    "B_plus_diff":    ["primary_sgw_early_energy", "primary_sgw_ultra_early_energy",
                       "waveform_early_fraction", "amplitude_std",
                       "diff_ultra_early_energy", "diff_early_energy"],
    "C_plus_tof":     ["primary_sgw_early_energy", "primary_sgw_ultra_early_energy",
                       "waveform_early_fraction", "amplitude_std",
                       "diff_ultra_early_energy", "diff_early_energy",
                       "mf_tof_sample_idx", "primary_sgw_peak_sample_idx"],
    "D_all":          ALL_FEATURES,
}


def safe_float(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def load_and_label(path: str, threshold: float) -> tuple[list[dict], list[int], list[float], list[int]]:
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    X_raw, y, dists, tids = [], [], [], []
    for r in rows:
        d = safe_float(r.get("oracle_distance_m"))
        if d is None:
            continue
        label = 1 if d < threshold else 0
        tid = int(float(r.get("trial_id", -1)))
        X_raw.append(r)
        y.append(label)
        dists.append(d)
        tids.append(tid)
    return X_raw, y, dists, tids


def build_X(rows: list[dict], features: list[str]) -> list[list[float]] | None:
    X = []
    for r in rows:
        vals = []
        ok = True
        for f in features:
            v = safe_float(r.get(f))
            if v is None or str(r.get(f, "")).strip() in ("-1", "nan", ""):
                ok = False
                break
            vals.append(v)
        if not ok:
            return None  # caller will skip this row
        X.append(vals)
    return X


def loto_binary_cv(X_rows, y, tids, features, model_factory):
    import numpy as np

    unique_trials = sorted(set(tids))
    all_preds, all_probas, all_true = [], [], []

    tids_arr = np.array(tids)
    y_arr = np.array(y)

    for held in unique_trials:
        train_mask = tids_arr != held
        test_mask = tids_arr == held
        if test_mask.sum() == 0 or train_mask.sum() == 0:
            continue

        X_train_rows = [r for r, m in zip(X_rows, train_mask) if m]
        X_test_rows = [r for r, m in zip(X_rows, test_mask) if m]

        X_train_list = build_X(X_train_rows, features)
        X_test_list = build_X(X_test_rows, features)
        if X_train_list is None or X_test_list is None:
            continue

        X_tr = np.array(X_train_list, dtype=float)
        X_te = np.array(X_test_list, dtype=float)
        y_tr = y_arr[train_mask]
        y_te = y_arr[test_mask]

        # Standardize
        mu = X_tr.mean(axis=0)
        sigma = X_tr.std(axis=0)
        sigma[sigma == 0] = 1.0
        X_tr = (X_tr - mu) / sigma
        X_te = (X_te - mu) / sigma

        clf = model_factory()
        clf.fit(X_tr, y_tr)
        preds = clf.predict(X_te).tolist()
        try:
            probas = clf.predict_proba(X_te)[:, 1].tolist()
        except AttributeError:
            probas = preds

        all_preds.extend(preds)
        all_probas.extend(probas)
        all_true.extend(y_te.tolist())

    return all_preds, all_probas, all_true


def f1_precision_recall(preds, true, pos_label=1):
    tp = sum(1 for p, t in zip(preds, true) if p == pos_label and t == pos_label)
    fp = sum(1 for p, t in zip(preds, true) if p == pos_label and t != pos_label)
    fn = sum(1 for p, t in zip(preds, true) if p != pos_label and t == pos_label)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return f1, prec, rec


def auc_roc(probas, true):
    """Simple AUC-ROC via trapezoidal rule."""
    pairs = sorted(zip(probas, true), key=lambda x: -x[0])
    P = sum(true)
    N = len(true) - P
    if P == 0 or N == 0:
        return float("nan")
    tprs, fprs = [0.0], [0.0]
    tp = fp = 0
    for _, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tprs.append(tp / P)
        fprs.append(fp / N)
    tprs.append(1.0)
    fprs.append(1.0)
    auc = sum(
        (fprs[i + 1] - fprs[i]) * (tprs[i + 1] + tprs[i]) / 2
        for i in range(len(fprs) - 1)
    )
    return auc


def main():
    parser = argparse.ArgumentParser(description="Binary acoustic proximity classifier (LOTO-CV).")
    parser.add_argument("--csv", type=str,
        default="/home/lab109/song/isaacsim6.0/runtime/outputs/global_baseline_diff_v1/global_baseline_diff_combined.csv")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
        help=f"Proximity threshold in metres (default {DEFAULT_THRESHOLD}m)")
    parser.add_argument("--feature-set", choices=list(FEATURE_SETS.keys()), default=None)
    args = parser.parse_args()

    try:
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.svm import SVC
        from sklearn.linear_model import LogisticRegression
        from sklearn.dummy import DummyClassifier
    except ImportError:
        print("ERROR: pip install scikit-learn")
        sys.exit(1)

    import numpy as np

    print(f"CSV: {args.csv}")
    print(f"Threshold: oracle_distance_m < {args.threshold}m → class 1 (NEAR)")

    X_rows, y, dists, tids = load_and_label(args.csv, args.threshold)
    n_near = sum(y)
    n_far = len(y) - n_near
    print(f"Samples: {len(y)} total  ({n_near} NEAR / {n_far} FAR)")
    print(f"Unique trials: {sorted(set(tids))}")
    print()

    # baseline: always predict majority
    majority = 0 if n_far >= n_near else 1
    base_preds = [majority] * len(y)
    base_f1, base_prec, base_rec = f1_precision_recall(base_preds, y)
    print(f"=== Baseline (majority class = {'FAR' if majority==0 else 'NEAR'}) ===")
    print(f"  F1={base_f1:.4f}  Prec={base_prec:.4f}  Rec={base_rec:.4f}")
    print()

    models = {
        "RandomForest":  lambda: RandomForestClassifier(n_estimators=200, max_depth=5,
                                                         class_weight="balanced", random_state=42),
        "GradBoost":     lambda: GradientBoostingClassifier(n_estimators=100, max_depth=3,
                                                             learning_rate=0.1, random_state=42),
        "SVM_rbf":       lambda: SVC(kernel="rbf", C=10.0, gamma="scale",
                                      class_weight="balanced", probability=True),
        "LogisticReg":   lambda: LogisticRegression(C=1.0, class_weight="balanced",
                                                      max_iter=500, random_state=42),
    }

    fs_to_run = {args.feature_set: FEATURE_SETS[args.feature_set]} if args.feature_set else FEATURE_SETS

    # filter features to only those present in CSV
    if X_rows:
        avail = set(X_rows[0].keys())
    else:
        print("ERROR: empty CSV")
        sys.exit(1)

    print("=== Leave-One-Trial-Out 二元分類結果 ===")
    print(f"{'特徵集':<16} {'模型':<14} {'F1':>6} {'Prec':>6} {'Rec':>6} {'AUC':>6} {'n_feat':>7}")
    print("-" * 65)

    best_f1 = -1.0
    best_label = ""
    best_result = None

    for fs_name, feat_list in fs_to_run.items():
        valid_feats = [f for f in feat_list if f in avail]
        if not valid_feats:
            print(f"{fs_name}: 無可用特徵")
            continue

        for model_name, mf in models.items():
            try:
                preds, probas, true = loto_binary_cv(X_rows, y, tids, valid_feats, mf)
                if not preds:
                    continue
                f1, prec, rec = f1_precision_recall(preds, true)
                auc = auc_roc(probas, true)
                label = f"{fs_name}/{model_name}"
                print(f"{fs_name:<16} {model_name:<14} {f1:>6.4f} {prec:>6.4f} {rec:>6.4f} {auc:>6.4f} {len(valid_feats):>7}")
                if f1 > best_f1:
                    best_f1 = f1
                    best_label = label
                    best_result = (preds, true, probas)
            except Exception as e:
                print(f"{fs_name:<16} {model_name:<14} ERROR: {e}")

    print("-" * 65)
    print(f"Baseline F1 = {base_f1:.4f}")

    if best_result:
        preds, true, probas = best_result
        f1, prec, rec = f1_precision_recall(preds, true)
        auc = auc_roc(probas, true)
        print(f"\n最佳: {best_label}")
        print(f"  F1={f1:.4f}  Prec={prec:.4f}  Rec={rec:.4f}  AUC={auc:.4f}")

        # Confusion matrix
        tp = sum(1 for p, t in zip(preds, true) if p == 1 and t == 1)
        tn = sum(1 for p, t in zip(preds, true) if p == 0 and t == 0)
        fp = sum(1 for p, t in zip(preds, true) if p == 1 and t == 0)
        fn = sum(1 for p, t in zip(preds, true) if p == 0 and t == 1)
        print(f"\n混淆矩陣 (LOTO):")
        print(f"           予測NEAR  予測FAR")
        print(f"  真NEAR     {tp:4d}      {fn:4d}   (recall={tp/(tp+fn):.3f})")
        print(f"  真FAR      {fp:4d}      {tn:4d}   (specificity={tn/(tn+fp):.3f})")

        # Threshold sensitivity analysis
        print(f"\n=== 不同門檻值的 F1 ===")
        for thr in [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
            X2, y2, _, tids2 = load_and_label(args.csv, thr)
            n2 = sum(y2)
            if n2 < 5 or len(y2) - n2 < 5:
                continue
            from sklearn.ensemble import RandomForestClassifier
            preds2, probas2, true2 = loto_binary_cv(
                X2, y2, tids2, valid_feats,
                lambda: RandomForestClassifier(n_estimators=200, max_depth=5,
                                               class_weight="balanced", random_state=42))
            f1_t, _, _ = f1_precision_recall(preds2, true2)
            auc_t = auc_roc(probas2, true2)
            n_near_t = sum(y2)
            print(f"  thr={thr}m  near={n_near_t:3d}  far={len(y2)-n_near_t:3d}  F1={f1_t:.4f}  AUC={auc_t:.4f}")

    print(f"\n評估結論：")
    if best_f1 > 0.75:
        print("  ★★★ 強分類能力 (F1>0.75)：聲學接近偵測可行！")
    elif best_f1 > 0.60:
        print("  ★★  中等分類能力 (F1>0.60)：有限可行，論文需說明局限性")
    else:
        print("  ✗   弱分類能力 (F1<=0.60)：聲學特徵不足以區分接近/遠離")


if __name__ == "__main__":
    main()
