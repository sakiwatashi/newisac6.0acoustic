"""Hold the active Isaac Sim SimulationApp for RTX GMO capture in DirectRLEnv."""

from __future__ import annotations

from typing import Any

_SIMULATION_APP: Any | None = None


def set_simulation_app(app: Any) -> None:
    global _SIMULATION_APP
    _SIMULATION_APP = app


def get_simulation_app() -> Any | None:
    return _SIMULATION_APP