#!/usr/bin/env python3
"""Generate the 52 S1 sensing-envelope cell JSONs.

Spec source: docs/plan_v2/V2_HANDOFF_FOR_NEXT_AI.md §5.2 (cell schema) and §6
(S1 block definitions). Re-runnable: overwrites the *.json siblings of this
script (never touches this generator itself).

Block definitions (§6):
    D = {0.15, 0.3, 0.5, 0.8, 1.2}   distance levels (m)
    Z = {0.04, 0.10, 0.20}           target size levels (m)
    P = {0, 30, 60}                 sensor pitch levels (deg)

    Block A (baseline):    P=0,  C=none,      D x Z            -> 15 cells
    Block B (pitch):       Z=0.10, C=none,    D x {30,60}       -> 10 cells
    Block C (table):       Z=0.10, C=table,   D x P (all 3)     -> 15 cells
    Block D (table+arm):   C=table_arm, D={0.3,0.5,0.8},
                            Z={0.10,0.20} x P={0,60}            -> 12 cells
    Total: 52

cell_id format: <Block>_d<distance>_z<size>_p<pitch>_c<clutter-abbrev>
    - distance keeps its "natural" decimal form (0.15 -> "0.15", 0.5 -> "0.5")
    - size is always rendered with 2 decimals (0.04, 0.10, 0.20)
    - pitch is an integer with no decimals (0, 30, 60)
    - clutter abbreviation: none -> cnone, table -> ctable, table_arm -> ctablearm
"""
from __future__ import annotations

import json
import pathlib

OUT_DIR = pathlib.Path(__file__).resolve().parent

D_LEVELS = [0.15, 0.3, 0.5, 0.8, 1.2]
Z_LEVELS = [0.04, 0.10, 0.20]
P_LEVELS = [0, 30, 60]

SENSOR_POS_M = [0, 0, 0.65]

CLUTTER_ABBREV = {
    "none": "cnone",
    "table": "ctable",
    "table_arm": "ctablearm",
}


def fmt_distance(d: float) -> str:
    """Natural decimal form: strip a spurious trailing zero introduced by
    formatting to 2 decimals, but keep genuine 2-decimal values (e.g. 0.15)."""
    s = f"{d:.2f}"
    if s.endswith("0") and not s.endswith(".00"):
        s = s[:-1]
    return s


def fmt_size(z: float) -> str:
    return f"{z:.2f}"


def fmt_pitch(p: float) -> str:
    return str(int(round(p)))


def make_cell(block: str, d: float, z: float, p: float, clutter: str, notes: str) -> dict:
    cell_id = (
        f"{block}_d{fmt_distance(d)}_z{fmt_size(z)}_p{fmt_pitch(p)}_{CLUTTER_ABBREV[clutter]}"
    )
    return {
        "cell_id": cell_id,
        "target_distance_m": d,
        "target_size_m": z,
        "sensor_pitch_deg": p,
        "clutter": clutter,
        "sensor_pos_m": list(SENSOR_POS_M),
        "notes": notes,
    }


def build_cells() -> list[dict]:
    cells: list[dict] = []

    # Block A (baseline): P=0, C=none, D x Z -> 15 cells
    for d in D_LEVELS:
        for z in Z_LEVELS:
            cells.append(make_cell("A", d, z, 0, "none", "block A"))

    # Block B (pitch effect): Z=0.10, C=none, D x {30,60} -> 10 cells
    for d in D_LEVELS:
        for p in (30, 60):
            cells.append(make_cell("B", d, 0.10, p, "none", "block B"))

    # Block C (table effect): Z=0.10, C=table, D x P (all 3 levels) -> 15 cells
    for d in D_LEVELS:
        for p in P_LEVELS:
            cells.append(make_cell("C", d, 0.10, p, "table", "block C"))

    # Block D (table+arm): C=table_arm, D={0.3,0.5,0.8}, Z x P -> 12 cells
    for d in (0.3, 0.5, 0.8):
        for z in (0.10, 0.20):
            for p in (0, 60):
                cells.append(make_cell("D", d, z, p, "table_arm", "block D"))

    return cells


def main() -> None:
    cells = build_cells()

    ids = [c["cell_id"] for c in cells]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"duplicate cell_id(s) generated: {sorted(dupes)}")

    counts: dict[str, int] = {}
    for cell in cells:
        block = cell["cell_id"].split("_", 1)[0]
        counts[block] = counts.get(block, 0) + 1
        out_path = OUT_DIR / f"{cell['cell_id']}.json"
        with out_path.open("w") as f:
            json.dump(cell, f, indent=2)
            f.write("\n")

    print(f"Wrote {len(cells)} cell JSONs to {OUT_DIR}")
    for block in sorted(counts):
        print(f"  block {block}: {counts[block]} cells")


if __name__ == "__main__":
    main()
