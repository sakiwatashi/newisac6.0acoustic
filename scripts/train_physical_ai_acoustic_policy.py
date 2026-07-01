#!/usr/bin/env python3
"""Train/evaluate small Physical-AI acoustic policy baselines.

This is offline only. It reads acoustic sense-act rows exported by
build_physical_ai_acoustic_dataset.py and evaluates simple, interpretable models
with leave-one-trial-out validation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

FEATURE_COLUMNS = [
    "early_energy",
    "primary_sgw_early_energy",
    "ref_early_energy",
    "tof_ns",
    "ref_tof_ns",
    "peak_amplitude",
    "amplitude_mean",
    "amplitude_std",
    "all_sgw_peak_std",
    "rx_energy_balance",
    "rx_tof_delta_ns",
    "waveform_early_fraction",
    "estimated_distance_energy_m",
    "estimated_distance_tof_m",
    "fused_distance_m",
    "alignment_score",
    "sensor_x_m",
    "sensor_y_m",
    "num_signal_ways",
]

LABELS = ["near_label", "stop_region_label", "terminal_step_label"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Physical-AI acoustic policy baselines.")
    parser.add_argument(
        "--dataset-csv",
        type=Path,
        default=Path("runtime/outputs/physical_ai_acoustic_v7_strict/physical_ai_acoustic_steps.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runtime/outputs/physical_ai_acoustic_v7_policy"),
    )
    parser.add_argument(
        "--features",
        nargs="*",
        default=FEATURE_COLUMNS,
        help="Feature columns to use. Defaults to acoustic/state features only; oracle labels are never used as inputs.",
    )
    return parser.parse_args()


def f(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def b(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def model_specs(features: list[str]) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline(
            [
                ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(class_weight="balanced", max_iter=2000, random_state=0)),
            ]
        ),
        "decision_tree_depth2": Pipeline(
            [
                ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("model", DecisionTreeClassifier(max_depth=2, class_weight="balanced", min_samples_leaf=3, random_state=0)),
            ]
        ),
    }


def metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    if not y_true:
        return {}
    labels = [False, True]
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    tn, fp, fn, tp = [int(v) for v in cm.ravel()]
    specificity = tn / (tn + fp) if tn + fp else 0.0
    recall = recall_score(y_true, y_pred, zero_division=0)
    return {
        "n": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float((recall + specificity) / 2.0),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall),
        "specificity": float(specificity),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def make_matrix(rows: list[dict[str, Any]], features: list[str]) -> list[list[float]]:
    return [[f(row.get(feature)) for feature in features] for row in rows]


def constant_baseline(y_train: list[bool], n_test: int) -> list[bool]:
    majority = Counter(y_train).most_common(1)[0][0]
    return [majority] * n_test


def leave_one_trial_out(rows: list[dict[str, Any]], features: list[str], label: str) -> dict[str, Any]:
    groups = sorted({str(row.get("source_dir")) for row in rows})
    y_all = [b(row.get(label)) for row in rows]
    if len(set(y_all)) < 2 or len(groups) < 2:
        return {"label": label, "skipped": "requires at least two classes and two trial groups"}

    results: dict[str, dict[str, Any]] = {}
    predictions_csv_rows: list[dict[str, Any]] = []
    models = model_specs(features)
    for model_name, model in models.items():
        y_true_all: list[bool] = []
        y_pred_all: list[bool] = []
        for group in groups:
            train_rows = [row for row in rows if str(row.get("source_dir")) != group]
            test_rows = [row for row in rows if str(row.get("source_dir")) == group]
            y_train = [b(row.get(label)) for row in train_rows]
            y_test = [b(row.get(label)) for row in test_rows]
            if len(set(y_train)) < 2:
                y_pred = constant_baseline(y_train, len(test_rows))
            else:
                model.fit(make_matrix(train_rows, features), y_train)
                y_pred = [bool(v) for v in model.predict(make_matrix(test_rows, features))]
            y_true_all.extend(y_test)
            y_pred_all.extend(y_pred)
            for row, actual, pred in zip(test_rows, y_test, y_pred):
                predictions_csv_rows.append(
                    {
                        "label": label,
                        "model": model_name,
                        "source_dir": row.get("source_dir"),
                        "trial_id": row.get("trial_id"),
                        "step_index": row.get("step_index"),
                        "actual": actual,
                        "predicted": pred,
                        "oracle_distance_m": row.get("oracle_distance_m"),
                    }
                )
        results[model_name] = metrics(y_true_all, y_pred_all)

    y_majority = [Counter(y_all).most_common(1)[0][0]] * len(y_all)
    results["majority_baseline"] = metrics(y_all, y_majority)
    return {"label": label, "models": results, "predictions": predictions_csv_rows}


def fit_interpretability(rows: list[dict[str, Any]], features: list[str], label: str) -> dict[str, Any]:
    y = [b(row.get(label)) for row in rows]
    if len(set(y)) < 2:
        return {"skipped": "single-class label"}
    tree = model_specs(features)["decision_tree_depth2"]
    tree.fit(make_matrix(rows, features), y)
    model = tree.named_steps["model"]
    text = export_text(model, feature_names=list(features), decimals=4)
    importances = sorted(
        [
            {"feature": feature, "importance": float(importance)}
            for feature, importance in zip(features, model.feature_importances_)
            if importance > 0.0
        ],
        key=lambda row: row["importance"],
        reverse=True,
    )
    return {"decision_tree_depth2_rules": text, "feature_importances": importances}


def write_predictions(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["label", "model", "source_dir", "trial_id", "step_index", "actual", "predicted", "oracle_distance_m"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    rows = read_rows(args.dataset_csv)
    features = [feature for feature in args.features if feature in FEATURE_COLUMNS]
    if not rows:
        raise SystemExit(f"No rows found in {args.dataset_csv}")
    if not features:
        raise SystemExit("No valid feature columns selected")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    label_reports = []
    all_predictions: list[dict[str, Any]] = []
    for label in LABELS:
        label_report = leave_one_trial_out(rows, features, label)
        if "predictions" in label_report:
            all_predictions.extend(label_report.pop("predictions"))
        label_report["interpretability"] = fit_interpretability(rows, features, label)
        label_reports.append(label_report)

    prediction_csv = args.output_dir / "physical_ai_policy_predictions.csv"
    write_predictions(prediction_csv, all_predictions)

    report = {
        "dataset_csv": str(args.dataset_csv),
        "output_dir": str(args.output_dir),
        "row_count": len(rows),
        "trial_group_count": len({row.get("source_dir") for row in rows}),
        "features": features,
        "validation": "leave_one_trial_group_out",
        "labels": label_reports,
        "outputs": {"predictions_csv": str(prediction_csv)},
        "claim_boundary": (
            "This is an offline Physical-AI policy baseline over acoustic/state features. "
            "Oracle distance is used only to define labels and is not included in the input features. "
            "The dataset is small, so these numbers are pilot evidence rather than a final generalization claim."
        ),
    }
    report_json = args.output_dir / "physical_ai_policy_report.json"
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote {report_json}")
    print(f"Wrote {prediction_csv}")
    for label_report in label_reports:
        label = label_report["label"]
        if "models" not in label_report:
            print(f"{label}: skipped")
            continue
        best_name, best_metrics = max(
            ((name, data) for name, data in label_report["models"].items() if name != "majority_baseline"),
            key=lambda item: (item[1]["balanced_accuracy"], item[1]["f1"], item[1]["accuracy"]),
        )
        print(
            f"{label}: best={best_name} "
            f"f1={best_metrics['f1']:.3f} acc={best_metrics['accuracy']:.3f} "
            f"bal_acc={best_metrics['balanced_accuracy']:.3f} "
            f"precision={best_metrics['precision']:.3f} recall={best_metrics['recall']:.3f}"
        )


if __name__ == "__main__":
    main()
