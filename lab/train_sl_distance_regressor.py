"""Supervised distance regression from RTX acoustic features (Lab Phase 4 → §4.6).

Trains simple sklearn regressors and evaluates:
  1) lab_internal — K-fold CV on Lab dynamic GMO rows only
  2) sim_to_lab   — train on Sim fixed-TCP timeseries (material B), test on Lab dynamic

Canonical input:
  runtime/outputs/lab_dynamic_smoke_v1/lab_dynamic_obs_timeseries.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ISAACSIM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAB_CSV = ISAACSIM_ROOT / "runtime/outputs/lab_dynamic_smoke_v1/lab_dynamic_obs_timeseries.csv"
DEFAULT_SIM_ROOT = ISAACSIM_ROOT / "runtime/outputs/fixed_tcp_repeatability_v1"
DEFAULT_OUTPUT_DIR = ISAACSIM_ROOT / "runtime/outputs/lab_sl_distance_v1"

FEATURE_PRESETS: dict[str, list[str]] = {
    "early_energy_only": ["primary_sgw_early_energy"],
    "early_energy_peak": ["primary_sgw_early_energy", "primary_sgw_peak"],
}


@dataclass(frozen=True)
class Sample:
    source: str
    distance_m: float
    features: dict[str, float]
    step_index: int | None = None
    repeat_id: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SL distance regression (Lab + optional Sim transfer).")
    parser.add_argument("--lab-csv", type=Path, default=DEFAULT_LAB_CSV)
    parser.add_argument("--sim-root", type=Path, default=DEFAULT_SIM_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--feature-preset", choices=sorted(FEATURE_PRESETS), default="early_energy_only")
    parser.add_argument("--material-condition", default="B")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: object) -> float:
    if value is None:
        return math.nan
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return math.nan
    try:
        return float(text)
    except ValueError:
        return math.nan


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2:
        return float("nan")
    x = x.astype(float)
    y = y.astype(float)
    if np.std(x) == 0.0 or np.std(y) == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return {
        "mae_m": mae,
        "rmse_m": rmse,
        "r2": r2,
        "pearson_r": pearson_r(y_true, y_pred),
        "n_samples": int(y_true.size),
    }


def load_lab_gmo_samples(csv_path: Path, feature_names: list[str]) -> list[Sample]:
    rows = read_csv_rows(csv_path)
    samples: list[Sample] = []
    for row in rows:
        if not parse_bool(row.get("gmo_captured", "")):
            continue
        if not parse_bool(row.get("gmo_valid", "")):
            continue
        features = {name: parse_float(row.get(name)) for name in feature_names}
        if any(not math.isfinite(v) for v in features.values()):
            continue
        samples.append(
            Sample(
                source="lab_dynamic",
                distance_m=parse_float(row.get("target_distance_m_gt")),
                features=features,
                step_index=int(parse_float(row.get("step_index"))),
            )
        )
    return samples


def load_sim_timeseries_samples(sim_root: Path, feature_names: list[str], material: str) -> list[Sample]:
    pattern = "official_asset_ur10_fixed_tcp_distance_sweep_timeseries.csv"
    samples: list[Sample] = []
    for csv_path in sorted(sim_root.glob(f"**/{pattern}")):
        for row in read_csv_rows(csv_path):
            if str(row.get("material_condition", "")).upper() != str(material).upper():
                continue
            if not parse_bool(row.get("gmo_valid", "")):
                continue
            features = {name: parse_float(row.get(name)) for name in feature_names}
            if any(not math.isfinite(v) for v in features.values()):
                continue
            distance = parse_float(row.get("target_distance_m"))
            if not math.isfinite(distance):
                distance = parse_float(row.get("planned_distance_m"))
            if not math.isfinite(distance):
                continue
            samples.append(
                Sample(
                    source="sim_fixed_tcp",
                    distance_m=distance,
                    features=features,
                    repeat_id=str(row.get("repeat_id", "")),
                )
            )
    return samples


def samples_to_xy(samples: list[Sample], feature_names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([[sample.features[name] for name in feature_names] for sample in samples], dtype=float)
    y = np.array([sample.distance_m for sample in samples], dtype=float)
    return x, y


def fit_predict_linear(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> np.ndarray:
    from sklearn.linear_model import LinearRegression

    model = LinearRegression()
    model.fit(x_train, y_train)
    return model.predict(x_test)


def fit_predict_ridge(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> np.ndarray:
    from sklearn.linear_model import RidgeCV

    model = RidgeCV(alphas=np.logspace(-3, 3, 13))
    model.fit(x_train, y_train)
    return model.predict(x_test)


def cross_validate_lab(samples: list[Sample], feature_names: list[str]) -> dict[str, Any]:
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import KFold

    x, y = samples_to_xy(samples, feature_names)
    n = x.shape[0]
    k = min(5, n)
    if k < 2:
        return {"valid": False, "reason": "insufficient_lab_samples", "n_samples": n}

    kf = KFold(n_splits=k, shuffle=True, random_state=42)
    preds = np.zeros(n, dtype=float)
    for train_idx, test_idx in kf.split(x):
        model = LinearRegression()
        model.fit(x[train_idx], y[train_idx])
        preds[test_idx] = model.predict(x[test_idx])

    return {
        "valid": True,
        "cv_folds": k,
        "model": "linear_regression",
        "metrics": regression_metrics(y, preds),
        "predictions": preds.tolist(),
    }


def evaluate_sim_to_lab(
    sim_samples: list[Sample],
    lab_samples: list[Sample],
    feature_names: list[str],
) -> dict[str, Any]:
    x_train, y_train = samples_to_xy(sim_samples, feature_names)
    x_test, y_test = samples_to_xy(lab_samples, feature_names)

    results: dict[str, Any] = {
        "train_source": "sim_fixed_tcp",
        "test_source": "lab_dynamic",
        "train_n": int(x_train.shape[0]),
        "test_n": int(x_test.shape[0]),
        "feature_names": feature_names,
    }

    if x_train.shape[0] < 3 or x_test.shape[0] < 3:
        results["valid"] = False
        results["reason"] = "insufficient_samples"
        return results

    model_outputs: dict[str, Any] = {}
    for model_name, predict_fn in (
        ("linear_regression", fit_predict_linear),
        ("ridge_cv", fit_predict_ridge),
    ):
        preds = predict_fn(x_train, y_train, x_test)
        model_outputs[model_name] = {
            "metrics": regression_metrics(y_test, preds),
            "predictions": preds.tolist(),
        }

    results["valid"] = True
    results["models"] = model_outputs
    results["y_true"] = y_test.tolist()
    return results


def write_predictions_csv(
    path: Path,
    lab_samples: list[Sample],
    preds: list[float],
    model_name: str,
) -> None:
    fieldnames = [
        "step_index",
        "target_distance_m_gt",
        "predicted_distance_m",
        "residual_m",
        "primary_sgw_early_energy",
        "primary_sgw_peak",
        "model",
    ]
    rows: list[dict[str, object]] = []
    for sample, pred in zip(lab_samples, preds):
        gt = sample.distance_m
        rows.append(
            {
                "step_index": sample.step_index,
                "target_distance_m_gt": gt,
                "predicted_distance_m": pred,
                "residual_m": pred - gt,
                "primary_sgw_early_energy": sample.features.get("primary_sgw_early_energy", math.nan),
                "primary_sgw_peak": sample.features.get("primary_sgw_peak", math.nan),
                "model": model_name,
            }
        )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_results(
    output_dir: Path,
    lab_samples: list[Sample],
    lab_cv: dict[str, Any],
    sim_to_lab: dict[str, Any],
) -> dict[str, str]:
    import matplotlib.pyplot as plt

    figures: dict[str, str] = {}
    y_true = np.array([s.distance_m for s in lab_samples], dtype=float)

    if lab_cv.get("valid"):
        preds = np.array(lab_cv["predictions"], dtype=float)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(y_true, preds, color="#1f77b4", alpha=0.85)
        lo = min(float(np.min(y_true)), float(np.min(preds)))
        hi = max(float(np.max(y_true)), float(np.max(preds)))
        ax.plot([lo, hi], [lo, hi], "k--", linewidth=1)
        m = lab_cv["metrics"]
        ax.set_title(f"Lab-only 5-fold CV (linear)\nMAE={m['mae_m']:.3f} m, r={m['pearson_r']:.3f}")
        ax.set_xlabel("GT distance (m)")
        ax.set_ylabel("Predicted distance (m)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = output_dir / "sl_lab_cv_pred_vs_gt.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        figures["sl_lab_cv_pred_vs_gt"] = str(path)

    if sim_to_lab.get("valid"):
        best_name = "linear_regression"
        best = sim_to_lab["models"][best_name]
        preds = np.array(best["predictions"], dtype=float)
        y_test = np.array(sim_to_lab["y_true"], dtype=float)

        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(y_test, preds, color="#ff6600", alpha=0.85)
        lo = min(float(np.min(y_test)), float(np.min(preds)))
        hi = max(float(np.max(y_test)), float(np.max(preds)))
        ax.plot([lo, hi], [lo, hi], "k--", linewidth=1)
        m = best["metrics"]
        ax.set_title(
            f"Sim train → Lab test ({best_name})\n"
            f"MAE={m['mae_m']:.3f} m, r={m['pearson_r']:.3f}, n_train={sim_to_lab['train_n']}"
        )
        ax.set_xlabel("GT distance (m)")
        ax.set_ylabel("Predicted distance (m)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = output_dir / "sl_sim_to_lab_pred_vs_gt.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        figures["sl_sim_to_lab_pred_vs_gt"] = str(path)

        fig2, ax2 = plt.subplots(figsize=(7, 4))
        order = np.argsort(y_test)
        ax2.plot(y_test[order], label="GT", color="#333333", linewidth=2)
        ax2.plot(preds[order], label="Predicted", color="#ff6600", linewidth=2, alpha=0.9)
        ax2.set_xlabel("Lab GMO sample (sorted by GT distance)")
        ax2.set_ylabel("Distance (m)")
        ax2.set_title("Sim→Lab transfer: trajectory comparison")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        fig2.tight_layout()
        path2 = output_dir / "sl_sim_to_lab_trajectory.png"
        fig2.savefig(path2, dpi=150)
        plt.close(fig2)
        figures["sl_sim_to_lab_trajectory"] = str(path2)

    return figures


def main() -> None:
    args = parse_args()
    feature_names = FEATURE_PRESETS[args.feature_preset]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = args.output_dir / "sl_distance_summary.json"
    if summary_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {summary_path}; pass --overwrite")

    lab_samples = load_lab_gmo_samples(args.lab_csv, feature_names)
    sim_samples = load_sim_timeseries_samples(args.sim_root, feature_names, args.material_condition)

    if len(lab_samples) < 3:
        raise SystemExit(f"Too few Lab GMO samples: {len(lab_samples)} in {args.lab_csv}")

    lab_cv = cross_validate_lab(lab_samples, feature_names)
    sim_to_lab = evaluate_sim_to_lab(sim_samples, lab_samples, feature_names)

    figures = plot_results(args.output_dir, lab_samples, lab_cv, sim_to_lab)

    if sim_to_lab.get("valid"):
        write_predictions_csv(
            args.output_dir / "sl_sim_to_lab_predictions.csv",
            lab_samples,
            sim_to_lab["models"]["linear_regression"]["predictions"],
            "linear_regression_sim_to_lab",
        )

    baseline_r = pearson_r(
        np.array([s.features[feature_names[0]] for s in lab_samples]),
        np.array([s.distance_m for s in lab_samples]),
    )

    passed = bool(sim_to_lab.get("valid")) and float(
        sim_to_lab["models"]["linear_regression"]["metrics"].get("pearson_r", 0.0)
    ) >= 0.3

    summary: dict[str, Any] = {
        "pass": passed,
        "claim_boundary": "trend_level_distance_proxy; not deployment-grade ranging",
        "feature_preset": args.feature_preset,
        "feature_names": feature_names,
        "lab_csv": str(args.lab_csv),
        "sim_root": str(args.sim_root),
        "material_condition": args.material_condition,
        "lab_gmo_sample_count": len(lab_samples),
        "sim_timeseries_sample_count": len(sim_samples),
        "lab_feature_vs_gt_pearson_r": baseline_r,
        "lab_internal_cv": lab_cv,
        "sim_to_lab_transfer": sim_to_lab,
        "figures": figures,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Lab GMO samples: {len(lab_samples)}")
    print(f"Sim training samples: {len(sim_samples)}")
    print(f"Lab feature vs GT Pearson r ({feature_names[0]}): {baseline_r:.4f}")
    if lab_cv.get("valid"):
        m = lab_cv["metrics"]
        print(f"Lab-only CV: MAE={m['mae_m']:.4f} m RMSE={m['rmse_m']:.4f} m r={m['pearson_r']:.4f}")
    if sim_to_lab.get("valid"):
        m = sim_to_lab["models"]["linear_regression"]["metrics"]
        print(f"Sim→Lab linear: MAE={m['mae_m']:.4f} m RMSE={m['rmse_m']:.4f} m r={m['pearson_r']:.4f}")
    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print(f"Wrote {summary_path}")
    for fig_path in figures.values():
        print(f"Wrote {fig_path}")


if __name__ == "__main__":
    main()