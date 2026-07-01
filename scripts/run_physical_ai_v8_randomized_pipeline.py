#!/usr/bin/env python3
"""v8 Physical-AI randomized data pipeline.

Runs separate Isaac processes through run_grasp_comparison_batch.sh while varying
search-start pose and wrench lateral position. The goal is to reduce pose
shortcuts in offline Physical-AI policy ablations.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ISAACSIM_ROOT = SCRIPT_DIR.parent

ACOUSTIC_ONLY_FEATURES = [
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
    "num_signal_ways",
]
POSE_ONLY_FEATURES = ["sensor_x_m", "sensor_y_m"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v8 randomized Physical-AI acoustic pipeline.")
    parser.add_argument("--batch-id", default=os.environ.get("BATCH_ID", "physical_ai_v8_randomized"))
    parser.add_argument("--config-start", type=int, default=int(os.environ.get("CONFIG_START", "0")))
    parser.add_argument("--config-count", type=int, default=int(os.environ.get("CONFIG_COUNT", "5")))
    parser.add_argument("--trials-per-config", type=int, default=int(os.environ.get("TRIALS_PER_CONFIG", "5")))
    parser.add_argument("--base-seed", type=int, default=int(os.environ.get("BASE_SEED", "20260629")))
    parser.add_argument("--claim-mode", default=os.environ.get("CLAIM_MODE", "scaffold"), choices=("scaffold", "acoustic_only"))
    parser.add_argument("--gui", default=os.environ.get("GUI", "0"), choices=("0", "1"))
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--scene-root", type=Path, default=None)
    parser.add_argument("--skip-batch", action="store_true", help="Only run offline analysis on existing output-root.")
    parser.add_argument("--skip-analysis", action="store_true", help="Only run randomized Isaac batch.")
    return parser.parse_args()


def config_rows(config_start: int, config_count: int, trials_per_config: int, base_seed: int) -> list[dict[str, Any]]:
    search_x_values = [0.50, 0.53, 0.56, 0.59, 0.62, 0.65, 0.52, 0.60]
    search_y_values = [0.10, 0.16, 0.22, 0.13, 0.19, 0.25, 0.07, 0.28]
    wrench_y_values = [0.16, 0.22, 0.10, 0.19, 0.13, 0.25, 0.07, 0.28]
    rows: list[dict[str, Any]] = []
    for config_idx in range(config_start, config_start + config_count):
        rows.append(
            {
                "config_idx": config_idx,
                "trial_start": config_idx * 100 + 1,
                "trial_count": trials_per_config,
                "spawn_seed": base_seed + config_idx * 9973,
                "grasp_search_start_x_m": search_x_values[config_idx % len(search_x_values)],
                "grasp_search_start_y_m": search_y_values[config_idx % len(search_y_values)],
                "grasp_wrench_y_m": wrench_y_values[config_idx % len(wrench_y_values)],
            }
        )
    return rows


def write_manifest(output_root: Path, rows: list[dict[str, Any]]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_json = output_root / "v8_randomized_manifest.json"
    manifest_csv = output_root / "v8_randomized_manifest.csv"
    manifest_json.write_text(json.dumps({"configs": rows}, indent=2), encoding="utf-8")
    with manifest_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {manifest_json}")
    print(f"Wrote {manifest_csv}")


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    printable = " ".join(cmd)
    print(f"$ {printable}", flush=True)
    subprocess.run(cmd, cwd=str(ISAACSIM_ROOT), env=env, check=True)


def run_batch(args: argparse.Namespace, output_root: Path, scene_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        env = os.environ.copy()
        env.update(
            {
                "BATCH_ID": f"{args.batch_id}_cfg_{row['config_idx']}",
                "CLAIM_MODE": args.claim_mode,
                "GUI": args.gui,
                "TRIAL_START": str(row["trial_start"]),
                "TRIAL_COUNT": str(row["trial_count"]),
                "SPAWN_SEED": str(row["spawn_seed"]),
                "OUTPUT_ROOT": str(output_root),
                "SCENE_ROOT": str(scene_root),
                "GRASP_SEARCH_START_X_M": str(row["grasp_search_start_x_m"]),
                "GRASP_SEARCH_START_Y_M": str(row["grasp_search_start_y_m"]),
                "GRASP_WRENCH_Y_M": str(row["grasp_wrench_y_m"]),
            }
        )
        end = int(row["trial_start"]) + int(row["trial_count"]) - 1
        print(
            f"--- config={row['config_idx']} trials={row['trial_start']}..{end} "
            f"seed={row['spawn_seed']} start=({row['grasp_search_start_x_m']},{row['grasp_search_start_y_m']}) "
            f"wrench_y={row['grasp_wrench_y_m']} ---",
            flush=True,
        )
        try:
            run(["bash", str(SCRIPT_DIR / "run_grasp_comparison_batch.sh")], env=env)
        except subprocess.CalledProcessError as exc:
            failure = {
                "config_idx": row["config_idx"],
                "returncode": exc.returncode,
                "trial_start": row["trial_start"],
                "trial_count": row["trial_count"],
                "note": "run_grasp_comparison_batch failed; continuing with available per-trial histories",
            }
            failures.append(failure)
            print(f"WARN config failed but continuing: {failure}", flush=True)
    failure_path = output_root / "v8_pipeline_failures.json"
    failure_path.write_text(json.dumps(failures, indent=2), encoding="utf-8")
    if failures:
        print(f"Wrote {failure_path} failures={len(failures)}", flush=True)
    return failures


def run_policy(dataset_csv: Path, output_dir: Path, features: list[str] | None = None) -> None:
    cmd = [
        "python3",
        str(SCRIPT_DIR / "train_physical_ai_acoustic_policy.py"),
        "--dataset-csv",
        str(dataset_csv),
        "--output-dir",
        str(output_dir),
    ]
    if features:
        cmd.append("--features")
        cmd.extend(features)
    run(cmd)


def summarize_ablation(report_paths: dict[str, Path], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "runs": {},
        "claim_boundary": "v8 randomized feature ablation. Oracle distance is labels/evaluation only.",
    }
    for run_name, path in report_paths.items():
        report = json.loads(path.read_text(encoding="utf-8"))
        summary["runs"][run_name] = {"path": str(path), "features": report["features"], "labels": {}}
        for label_report in report["labels"]:
            label = label_report["label"]
            if "models" not in label_report:
                summary["runs"][run_name]["labels"][label] = {"skipped": label_report.get("skipped", "no models")}
                continue
            models = {k: v for k, v in label_report["models"].items() if k != "majority_baseline"}
            if not models:
                summary["runs"][run_name]["labels"][label] = {"skipped": "no non-majority models"}
                continue
            best_name, best = max(
                models.items(),
                key=lambda item: (item[1]["balanced_accuracy"], item[1]["f1"], item[1]["accuracy"]),
            )
            row = {
                "feature_set": run_name,
                "label": label,
                "best_model": best_name,
                "n": best["n"],
                "accuracy": best["accuracy"],
                "balanced_accuracy": best["balanced_accuracy"],
                "precision": best["precision"],
                "recall": best["recall"],
                "specificity": best["specificity"],
                "f1": best["f1"],
                "tp": best["tp"],
                "fp": best["fp"],
                "tn": best["tn"],
                "fn": best["fn"],
            }
            rows.append(row)
            summary["runs"][run_name]["labels"][label] = row
    csv_path = output_dir / "feature_ablation_summary.csv"
    json_path = output_dir / "feature_ablation_summary.json"
    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {csv_path}")
    else:
        csv_path.write_text("feature_set,label,best_model,n,accuracy,balanced_accuracy,precision,recall,specificity,f1,tp,fp,tn,fn\n", encoding="utf-8")
        print(f"Wrote empty {csv_path}")
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")
    for row in rows:
        print(
            f"{row['feature_set']:13s} {row['label']:20s} {row['best_model']:22s} "
            f"bal_acc={row['balanced_accuracy']:.3f} f1={row['f1']:.3f}"
        )


def run_analysis(args: argparse.Namespace, output_root: Path) -> None:
    dataset_dir = ISAACSIM_ROOT / "runtime" / "outputs" / f"{args.batch_id}_dataset"
    policy_all_dir = ISAACSIM_ROOT / "runtime" / "outputs" / f"{args.batch_id}_policy_all"
    policy_acoustic_dir = ISAACSIM_ROOT / "runtime" / "outputs" / f"{args.batch_id}_policy_acoustic_only"
    policy_pose_dir = ISAACSIM_ROOT / "runtime" / "outputs" / f"{args.batch_id}_policy_pose_only"
    ablation_dir = ISAACSIM_ROOT / "runtime" / "outputs" / f"{args.batch_id}_ablation"

    run(
        [
            "python3",
            str(SCRIPT_DIR / "build_physical_ai_acoustic_dataset.py"),
            "--input-root",
            str(output_root),
            "--output-dir",
            str(dataset_dir),
        ]
    )
    dataset_csv = dataset_dir / "physical_ai_acoustic_steps.csv"
    run_policy(dataset_csv, policy_all_dir)
    run_policy(dataset_csv, policy_acoustic_dir, ACOUSTIC_ONLY_FEATURES)
    run_policy(dataset_csv, policy_pose_dir, POSE_ONLY_FEATURES)
    summarize_ablation(
        {
            "all_features": policy_all_dir / "physical_ai_policy_report.json",
            "acoustic_only": policy_acoustic_dir / "physical_ai_policy_report.json",
            "pose_only": policy_pose_dir / "physical_ai_policy_report.json",
        },
        ablation_dir,
    )


def main() -> None:
    args = parse_args()
    output_root = args.output_root or (ISAACSIM_ROOT / "runtime" / "outputs" / args.batch_id)
    scene_root = args.scene_root or (ISAACSIM_ROOT / "runtime" / "scenes" / args.batch_id)
    output_root.mkdir(parents=True, exist_ok=True)
    scene_root.mkdir(parents=True, exist_ok=True)
    rows = config_rows(args.config_start, args.config_count, args.trials_per_config, args.base_seed)
    write_manifest(output_root, rows)
    print(
        f"v8 randomized pipeline: batch_id={args.batch_id} config_start={args.config_start} configs={args.config_count} "
        f"trials_per_config={args.trials_per_config} output_root={output_root}"
    )
    if not args.skip_batch:
        run_batch(args, output_root, scene_root, rows)
    if not args.skip_analysis:
        run_analysis(args, output_root)
    print("v8 randomized pipeline complete")
    print(f"  output_root={output_root}")
    print(f"  dataset={ISAACSIM_ROOT / 'runtime' / 'outputs' / (args.batch_id + '_dataset')}")
    print(f"  ablation={ISAACSIM_ROOT / 'runtime' / 'outputs' / (args.batch_id + '_ablation')}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
