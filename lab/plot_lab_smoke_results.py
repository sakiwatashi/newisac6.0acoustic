"""Post-process Lab Phase 4 smoke CSV into thesis figures."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Lab dynamic smoke outputs.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/home/lab109/song/isaacsim6.0/runtime/outputs/lab_dynamic_smoke_v1"),
    )
    return parser.parse_args()


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return math.nan
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return math.nan
    return num / (den_x * den_y)


def main() -> None:
    args = parse_args()
    csv_path = args.output_dir / "lab_dynamic_obs_timeseries.csv"
    summary_path = args.output_dir / "lab_dynamic_obs_summary.json"
    if not csv_path.exists():
        raise SystemExit(f"Missing CSV: {csv_path}")

    rows = read_rows(csv_path)
    gmo_rows = [row for row in rows if row.get("gmo_captured", "").lower() in ("true", "1")]

    import matplotlib.pyplot as plt

    steps = [int(row["step_index"]) for row in rows]
    gt = [float(row["target_distance_m_gt"]) for row in rows]
    target_y = [float(row["target_y_m"]) for row in rows]
    target_z = [float(row["target_z_m"]) for row in rows]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(steps, gt, label="GT distance (m)", color="#1f77b4")
    ax.set_xlabel("step_index")
    ax.set_ylabel("target_distance_m_gt")
    ax.set_title("Lab dynamic target trajectory (sensor +X)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    traj_path = args.output_dir / "lab_target_trajectory_xy.png"
    fig.savefig(traj_path, dpi=150)
    plt.close(fig)

    fig2, ax2 = plt.subplots(figsize=(7, 4))
    ax2.scatter(target_y, target_z, c=steps, cmap="viridis", s=12)
    ax2.set_xlabel("target_y_m")
    ax2.set_ylabel("target_z_m")
    ax2.set_title("Target position slice (color=step)")
    fig2.tight_layout()
    slice_path = args.output_dir / "lab_target_position_slice.png"
    fig2.savefig(slice_path, dpi=150)
    plt.close(fig2)

    obs_gt = [float(row["target_distance_m_gt"]) for row in gmo_rows]
    obs_energy = []
    for row in gmo_rows:
        try:
            obs_energy.append(float(row["primary_sgw_early_energy"]))
        except ValueError:
            pass

    fig3, ax3 = plt.subplots(figsize=(7, 4))
    if obs_gt and obs_energy and len(obs_gt) == len(obs_energy):
        ax3.scatter(obs_gt, obs_energy, color="#ff6600", alpha=0.8)
        rho = pearson_r(obs_gt, obs_energy)
        ax3.set_title(f"early_energy vs GT distance (rho={rho:.3f}, n={len(obs_gt)})")
    else:
        ax3.set_title("early_energy vs GT distance (no GMO rows)")
    ax3.set_xlabel("target_distance_m_gt")
    ax3.set_ylabel("primary_sgw_early_energy")
    ax3.grid(True, alpha=0.3)
    fig3.tight_layout()
    obs_path = args.output_dir / "lab_obs_vs_gt_distance.png"
    fig3.savefig(obs_path, dpi=150)
    plt.close(fig3)

    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["figures"] = {
            "lab_target_trajectory_xy": str(traj_path),
            "lab_target_position_slice": str(slice_path),
            "lab_obs_vs_gt_distance": str(obs_path),
        }
        if obs_gt and obs_energy and len(obs_gt) == len(obs_energy):
            summary["early_energy_vs_gt_pearson_r"] = pearson_r(obs_gt, obs_energy)
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote {traj_path}")
    print(f"Wrote {slice_path}")
    print(f"Wrote {obs_path}")


if __name__ == "__main__":
    main()