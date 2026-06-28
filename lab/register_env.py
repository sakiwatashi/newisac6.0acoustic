"""External callback for Isaac Lab train/play to register custom tasks."""

from __future__ import annotations

import sys
from pathlib import Path


def register_lab_tasks() -> list[str]:
    """Register lab task extensions and return unconsumed CLI args."""
    lab_dir = Path(__file__).resolve().parent
    if str(lab_dir) not in sys.path:
        sys.path.insert(0, str(lab_dir))
    scripts_dir = lab_dir.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    import isaaclab_tasks_ext  # noqa: F401

    return sys.argv[1:]