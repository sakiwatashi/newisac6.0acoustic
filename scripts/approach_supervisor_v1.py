"""Rule-based approach supervisor — real-time fusion/oracle arbitration (Tier B).

Not a neural policy: evaluates each sense step, publishes live status, and can
recommend early standoff when RTX fusion saturates but geometry says we are close.

Oracle distance is evaluation-only for the closed-loop controller; the supervisor
uses it as a safety envelope to prevent max_steps stalls (claim boundary in summary).
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SupervisorAction(str, Enum):
    CONTINUE = "continue"
    HOLD = "hold"
    FORCE_STANDOFF = "force_standoff"
    WARN_FUSION_SATURATED = "warn_fusion_saturated"
    WARN_REACH_CAP = "warn_reach_cap"


@dataclass
class SupervisorVerdict:
    action: SupervisorAction
    message: str
    recommended_exit: str | None = None
    fusion_trust: str = "normal"
    oracle_distance_m: float = math.nan
    fused_distance_m: float = math.nan
    sensor_x_m: float = math.nan
    at_forward_cap: bool = False


@dataclass
class ApproachSupervisor:
    """Lightweight step supervisor for GUI / logging (v1 rule engine)."""

    standoff_m: float = 0.35
    forward_cap_slack_m: float = 0.01
    oracle_slack_m: float = 0.12
    fusion_saturation_gap_m: float = 0.20
    live_status_path: Path | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)

    def evaluate(
        self,
        *,
        obs: dict[str, Any],
        features: Any,
        controller_state: str,
        tool0_x_m: float,
        wrench_x_m: float,
        step_index: int,
    ) -> SupervisorVerdict:
        from grasp_passport_v1 import max_tool0_x_before_wrench_center_m

        oracle_m = float(obs.get("oracle_distance_m", math.nan))
        fused_m = float(getattr(features, "fused_distance_m", math.nan))
        sensor_x = float(obs.get("sensor_position", (math.nan,))[0])
        max_x = max_tool0_x_before_wrench_center_m(wrench_x_m)
        at_cap = math.isfinite(tool0_x_m) and float(tool0_x_m) >= float(max_x) - self.forward_cap_slack_m

        fusion_saturated = (
            at_cap
            and math.isfinite(oracle_m)
            and oracle_m <= self.standoff_m + 0.08
            and math.isfinite(fused_m)
            and fused_m > oracle_m + self.fusion_saturation_gap_m
        )
        oracle_close = math.isfinite(oracle_m) and oracle_m <= self.standoff_m + self.oracle_slack_m

        if at_cap and oracle_close:
            verdict = SupervisorVerdict(
                action=SupervisorAction.FORCE_STANDOFF,
                message=f"前進上限 (tool0≈{tool0_x_m:.2f}m)，oracle {oracle_m:.2f}m 已夠近 → 建議進入夾取",
                recommended_exit="standoff_reached_forward_cap",
                fusion_trust="bypass_cap",
                oracle_distance_m=oracle_m,
                fused_distance_m=fused_m,
                sensor_x_m=sensor_x,
                at_forward_cap=True,
            )
        elif fusion_saturated and oracle_close and at_cap:
            verdict = SupervisorVerdict(
                action=SupervisorAction.FORCE_STANDOFF,
                message=(
                    f"前進上限 + 融合飽和 (fused={fused_m:.2f}m, oracle={oracle_m:.2f}m) → "
                    "建議忽略 fusion，進入夾取"
                ),
                recommended_exit="standoff_reached_fusion_saturation",
                fusion_trust="saturated",
                oracle_distance_m=oracle_m,
                fused_distance_m=fused_m,
                sensor_x_m=sensor_x,
                at_forward_cap=at_cap,
            )
        elif fusion_saturated:
            verdict = SupervisorVerdict(
                action=SupervisorAction.WARN_FUSION_SATURATED,
                message=f"融合飽和 fused={fused_m:.2f}m vs oracle={oracle_m:.2f}m，繼續觀察",
                fusion_trust="saturated",
                oracle_distance_m=oracle_m,
                fused_distance_m=fused_m,
                sensor_x_m=sensor_x,
                at_forward_cap=at_cap,
            )
        elif at_cap:
            verdict = SupervisorVerdict(
                action=SupervisorAction.WARN_REACH_CAP,
                message=f"已到前進上限 tool0≈{tool0_x_m:.2f}m，oracle={oracle_m:.2f}m 仍偏遠",
                fusion_trust="cap_no_oracle",
                oracle_distance_m=oracle_m,
                fused_distance_m=fused_m,
                sensor_x_m=sensor_x,
                at_forward_cap=True,
            )
        else:
            verdict = SupervisorVerdict(
                action=SupervisorAction.CONTINUE,
                message=(
                    f"接近中 step={step_index} state={controller_state} "
                    f"oracle={oracle_m:.2f}m fused={fused_m:.2f}m sensor_x={sensor_x:.2f}m"
                ),
                oracle_distance_m=oracle_m,
                fused_distance_m=fused_m,
                sensor_x_m=sensor_x,
                at_forward_cap=at_cap,
            )

        self._record(step_index, controller_state, tool0_x_m, verdict)
        return verdict

    def _record(self, step_index: int, controller_state: str, tool0_x_m: float, verdict: SupervisorVerdict) -> None:
        row = {
            "ts": time.time(),
            "step_index": step_index,
            "controller_state": controller_state,
            "tool0_x_m": tool0_x_m,
            "action": verdict.action.value,
            "message": verdict.message,
            "recommended_exit": verdict.recommended_exit,
            "fusion_trust": verdict.fusion_trust,
            "oracle_distance_m": verdict.oracle_distance_m,
            "fused_distance_m": verdict.fused_distance_m,
            "sensor_x_m": verdict.sensor_x_m,
            "at_forward_cap": verdict.at_forward_cap,
        }
        self.trace.append(row)
        if self.live_status_path is not None:
            payload = {
                "updated_at": row["ts"],
                "latest": row,
                "step_count": len(self.trace),
            }
            self.live_status_path.parent.mkdir(parents=True, exist_ok=True)
            self.live_status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def publish_console(self, verdict: SupervisorVerdict, *, gui_only: bool = False) -> None:
        if gui_only:
            print(f"[監管] {verdict.message}", flush=True)
        else:
            print(f"[supervisor] {verdict.action.value}: {verdict.message}", flush=True)

    def summary(self) -> dict[str, Any]:
        force_count = sum(1 for r in self.trace if r["action"] == SupervisorAction.FORCE_STANDOFF.value)
        return {
            "supervisor_version": "v1",
            "supervisor_type": "rule_based_fusion_oracle_arbitrator",
            "step_count": len(self.trace),
            "force_standoff_count": force_count,
            "claim_boundary": (
                "Supervisor uses oracle distance only for safety envelope / fusion saturation recovery. "
                "Closed-loop controller still does not consume oracle for forward steps."
            ),
            "trace_tail": self.trace[-5:],
        }