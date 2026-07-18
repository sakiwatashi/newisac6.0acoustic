"""D4 Track B: acoustic-obs grasp DirectRLEnv (skeleton + pure reward/obs helpers).

Full GMO+arm integration reuses distance-env bootstrap patterns. Until the
robot+gripper scene is fully wired for lift, ``_setup_scene`` builds the same
fixed-TCP acoustic stage as the distance env and actions only update internal
state + optional TCP lock — suitable for **obs/reward smoke** and PPO plumbing.

Lift physics with Robotiq is Track A (SM) first; this env learns approach +
close timing from acoustic features without object xyz (D4-5).
"""
from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import torch

from isaaclab.assets import Articulation
from isaaclab.envs import DirectRLEnv
from isaaclab_assets.robots.universal_robots import UR10_CFG

LAB_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
REPO_ROOT = LAB_DIR.parent
for path in (str(SCRIPTS_DIR), str(LAB_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from geometry_passport_v1 import (  # noqa: E402
    ROBOT_PRIM_PATH,
    TARGET_PRIM_PATH,
    target_inside_room,
    target_position_from_sensor,
)
from simulation_app_ref import get_simulation_app  # noqa: E402
from scene_bootstrap import (  # noqa: E402
    RtxSceneHandles,
    RtxSceneStage,
    bootstrap_rtx_stage,
    capture_rtx_gmo,
    finalize_rtx_robot_handles,
    rebind_rtx_gmo_writer,
    set_target_pose,
    vec_norm,
    vec_sub,
)

if TYPE_CHECKING:
    from .ur10_rtx_acoustic_grasp_env_cfg import Ur10RtxAcousticGraspEnvCfg


# ── pure helpers (unit-testable, no sim) ─────────────────────────────────────
def pack_policy_obs(
    *,
    energy_scaled: float,
    peak_scaled: float,
    gmo_valid: float,
    d_hat_xy: float,
    gripper_open: float,
    ee_x: float,
    prev_a0: float,
    prev_a1: float,
    blind_acoustic: bool = False,
    true_range_scaled: float = 0.0,
    include_true_range: bool = False,
) -> list[float]:
    """Build policy obs.

    Base 8-D is acoustic + proprio (no target xyz). Optional 9th channel is
    **train scaffold** true_range (scalar distance only — still no xyz).
    """
    if blind_acoustic:
        energy_scaled, peak_scaled, gmo_valid, d_hat_xy = 0.0, 0.0, 0.0, 0.0
    row = [
        float(energy_scaled),
        float(peak_scaled),
        float(gmo_valid),
        float(d_hat_xy),
        float(gripper_open),
        float(ee_x),
        float(prev_a0),
        float(prev_a1),
    ]
    if include_true_range:
        row.append(float(true_range_scaled))
    return row


def compute_reward(
    *,
    d_hat_xy: float,
    standoff_m: float,
    gripper_cmd: float,
    gmo_valid: float,
    action_l2: float,
    cfg_approach: float,
    cfg_standoff: float,
    cfg_close: float,
    cfg_alive: float,
    cfg_invalid: float,
    cfg_act: float,
    true_range_m: float | None = None,
    prev_true_range_m: float | None = None,
    prev_d_hat_xy: float | None = None,
    gripper_open: float = 1.0,
    cfg_true_approach: float = 0.0,
    cfg_false_close: float = 0.0,
    cfg_progress: float = 0.0,
    cfg_hold_closed: float = 0.0,
    cfg_open_when_near: float = 0.0,
    near_tol_m: float = 0.05,
    use_true_scaffold: bool = True,
) -> float:
    """Reward for approach + close timing.

    - Acoustic term via ``d_hat_xy``.
    - Optional train scaffold via ``true_range_m`` (set ``use_true_scaffold=False`` for pure acoustic reward).
    - When near: reward **holding closed**, penalize **staying open**.
    """
    if not math.isfinite(d_hat_xy):
        d_hat_xy = 10.0
    thr = float(standoff_m) + float(near_tol_m)
    approach_err = abs(d_hat_xy - standoff_m)
    r = -cfg_approach * approach_err + cfg_alive

    true_ok = (
        use_true_scaffold
        and true_range_m is not None
        and math.isfinite(float(true_range_m))
    )
    true_r = float(true_range_m) if true_ok else float("nan")
    if true_ok and cfg_true_approach > 0.0:
        r -= cfg_true_approach * abs(true_r - standoff_m)

    # Dense progress: true-range reduction (scaffold) or d_hat reduction (pure acoustic).
    if true_ok and cfg_progress > 0.0 and prev_true_range_m is not None and math.isfinite(
        float(prev_true_range_m)
    ):
        r += cfg_progress * (float(prev_true_range_m) - true_r)
    elif (
        (not true_ok)
        and cfg_progress > 0.0
        and prev_d_hat_xy is not None
        and math.isfinite(float(prev_d_hat_xy))
        and float(prev_d_hat_xy) < 5.0
        and d_hat_xy < 5.0
    ):
        r += cfg_progress * (float(prev_d_hat_xy) - d_hat_xy)

    # Near-standoff: true when scaffold, else acoustic estimate.
    if true_ok and cfg_true_approach > 0.0:
        near = true_r <= thr
        far = true_r > thr
    else:
        near = d_hat_xy <= thr
        far = d_hat_xy > thr
    closed_state = float(gripper_open) < 0.5
    if near:
        r += cfg_standoff
        if closed_state:
            r += cfg_hold_closed
        else:
            r -= cfg_open_when_near
        if gripper_cmd < 0.0:
            r += cfg_close * (-gripper_cmd)

    # Penalize close when still far (true scaffold or d_hat).
    if cfg_false_close > 0.0 and gripper_cmd < -0.1 and far:
        r -= cfg_false_close * (-gripper_cmd)

    r -= cfg_invalid * (1.0 - gmo_valid)
    r -= cfg_act * action_l2
    return float(r)


def peak_to_d_hat_xy(peak: float, slope: float, intercept: float, height_diff: float) -> float:
    if not math.isfinite(peak) or slope == 0.0:
        return float("nan")
    d3 = (peak - intercept) / slope
    return math.sqrt(max(d3 * d3 - height_diff * height_diff, 1e-6))


# ToF sample-index keys only. NEVER use primary_sgw_peak (amplitude) for range.
#
# Full-waveform argmax (primary_sgw_peak_sample_idx) is often room-reflection
# dominated (see rtx_acoustic_factory.SignalWayStats). Prefer early-window
# peak (first ~10% of samples) for target echo; then full peak as fallback.
# bar_calibration OLS was fit on multi-frame mean argmax in D3 — early peak is
# the same physical sample index when the target is the first strong return.
PEAK_SAMPLE_IDX_KEYS: tuple[str, ...] = (
    "primary_sgw_early_peak_sample_idx",
    "tof_primary_sgw_early_peak_sample_idx",
    "primary_sgw_peak_sample_idx",
    "tof_primary_sgw_peak_sample_idx",
    "peak_sample_idx",
)


def extract_peak_sample_idx(gmo: dict | None) -> tuple[float, str]:
    """Return (peak_sample_idx, source_key). NaN + empty key if unavailable.

    Intentionally skips amplitude fields such as ``primary_sgw_peak``.
    """
    if not gmo:
        return float("nan"), ""
    for key in PEAK_SAMPLE_IDX_KEYS:
        if key not in gmo or gmo[key] is None:
            continue
        try:
            val = float(gmo[key])
        except (TypeError, ValueError):
            continue
        if math.isfinite(val):
            return val, key
    return float("nan"), ""


def gated_peak_sample_idx(
    amps,
    *,
    slope: float,
    intercept: float,
    range_lo_m: float,
    range_hi_m: float,
    margin_samples: int = 2,
) -> tuple[float, str]:
    """Peak sample index inside the distance gate [range_lo, range_hi].

    Prefers the **first local max** above a noise floor (target first return),
    falling back to argmax in the gate. Avoids:
    - full-waveform room multipath (often far peak ~constant, e.g. idx 64)
    - 10% early-window clipping (too short for 0.4–1.1 m corridor)
    """
    if amps is None:
        return float("nan"), ""
    try:
        n = len(amps)
    except TypeError:
        return float("nan"), ""
    if n <= 0 or not math.isfinite(slope) or slope == 0.0:
        return float("nan"), ""
    lo = int(math.floor(slope * float(range_lo_m) + intercept)) - int(margin_samples)
    hi = int(math.ceil(slope * float(range_hi_m) + intercept)) + int(margin_samples)
    lo = max(1, lo)
    hi = min(n - 2, hi)
    if hi <= lo:
        return float("nan"), ""

    def _abs(i: int) -> float:
        try:
            return abs(float(amps[i]))
        except (TypeError, ValueError, IndexError):
            return 0.0

    # Noise floor from samples before the gate (TX bleed / baseline).
    pre_lo = max(0, lo - 12)
    pre = [_abs(i) for i in range(pre_lo, lo)]
    noise = (sum(pre) / len(pre)) if pre else 0.0
    thr = max(noise * 4.0, 1e-9)

    # First local maximum above threshold = earliest target-like return.
    for i in range(lo, hi + 1):
        v = _abs(i)
        if v < thr:
            continue
        if v >= _abs(i - 1) and v >= _abs(i + 1):
            return float(i), f"gated_first[{lo},{hi}]"

    # Fallback: strongest sample in gate
    best_i = lo
    best_v = -1.0
    for i in range(lo, hi + 1):
        v = _abs(i)
        if v > best_v:
            best_v = v
            best_i = i
    if best_v < 0.0:
        return float("nan"), ""
    return float(best_i), f"gated_max[{lo},{hi}]"


class Ur10RtxAcousticGraspDirectEnv(DirectRLEnv):
    cfg: Ur10RtxAcousticGraspEnvCfg

    def __init__(self, cfg: Ur10RtxAcousticGraspEnvCfg, render_mode: str | None = None, **kwargs):
        self._rtx: RtxSceneHandles | None = None
        self._rtx_stage: RtxSceneStage | None = None
        self._ur10: Articulation | None = None
        self._obs = torch.zeros(cfg.scene.num_envs, cfg.observation_space, device=cfg.sim.device)
        self._prev_action = torch.zeros(cfg.scene.num_envs, cfg.action_space, device=cfg.sim.device)
        self._gripper_open = torch.ones(cfg.scene.num_envs, device=cfg.sim.device)
        self._d_hat = torch.zeros(cfg.scene.num_envs, device=cfg.sim.device)
        self._ee_x = torch.zeros(cfg.scene.num_envs, device=cfg.sim.device)
        # Internal range for target placement only — NEVER exposed in policy obs (D4-5).
        self._true_range_m = 0.7
        self._prev_true_range_m = 0.7
        self._prev_d_hat = 0.7
        self._gmo_valid_f = 0.0
        self._last_peak_sample_idx = float("nan")
        self._last_peak_source = ""
        self._d_hat_valid = False
        self._calib_slope = float("nan")
        self._calib_intercept = float("nan")
        self._load_calib(cfg)
        super().__init__(cfg, render_mode, **kwargs)
        if self._rtx_stage is not None and self._ur10 is not None:
            rebind_rtx_gmo_writer(self._rtx_stage)
            self._rtx = finalize_rtx_robot_handles(
                self._rtx_stage,
                articulation=self._ur10,
                settle_steps=int(self.cfg.settle_steps),
                step_fn=self._physics_step,
            )
            self._capture_gmo()
            print(
                "Ur10RtxAcousticGraspDirectEnv: ready "
                f"obs_dim={self.cfg.observation_space} act_dim={self.cfg.action_space} "
                f"blind={self.cfg.blind_acoustic} "
                f"calib_slope={self._calib_slope}",
                flush=True,
            )

    def _load_calib(self, cfg: Ur10RtxAcousticGraspEnvCfg) -> None:
        path = REPO_ROOT / cfg.bar_calib_json
        if not path.exists():
            # fallback S2-like placeholders; still no oracle in control
            self._calib_slope = 57.866
            self._calib_intercept = -4.986
            return
        import json

        cal = json.loads(path.read_text())
        self._calib_slope = float(cal["slope_smp_per_m"])
        self._calib_intercept = float(cal["intercept_smp"])

    def _setup_scene(self) -> None:
        import numpy as np

        simulation_app = get_simulation_app()
        if simulation_app is None:
            raise RuntimeError(
                "SimulationApp not registered. Call simulation_app_ref.set_simulation_app "
                "after AppLauncher."
            )
        from isaacsim.storage.native import get_assets_root_path

        assets_root = get_assets_root_path()
        official_ur10_usd = f"{assets_root}/Isaac/Robots/UniversalRobots/ur10/ur10.usd"
        ur10_cfg = UR10_CFG.replace(prim_path=ROBOT_PRIM_PATH)
        ur10_cfg.spawn.usd_path = official_ur10_usd
        self._ur10 = Articulation(ur10_cfg)
        self.scene.articulations["ur10"] = self._ur10
        self._rtx_stage = bootstrap_rtx_stage(
            simulation_app=simulation_app,
            material_condition=str(self.cfg.material_condition),
            tick_rate_hz=float(self.cfg.tick_rate_hz),
            stage=self.sim.stage,
            spawn_robot=False,
        )
        from isaacsim.core.experimental.objects import Cube

        self._np = np
        self._Cube = Cube

    def _physics_step(self, render: bool = False) -> None:
        if self._ur10 is not None:
            self._ur10.write_data_to_sim()
        self.sim.forward()
        self.sim.step(render=render)
        import omni.kit.app

        omni.kit.app.get_app().update()
        if self._ur10 is not None:
            self.scene.update(dt=self.physics_dt)

    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        self._actions = torch.clamp(actions, -1.0, 1.0)
        # gripper: negative → close
        self._gripper_open = torch.where(
            self._actions[:, 1] < -0.1,
            torch.zeros_like(self._gripper_open),
            torch.where(
                self._actions[:, 1] > 0.1,
                torch.ones_like(self._gripper_open),
                self._gripper_open,
            ),
        )
        # action[0]: +1 = approach (shrink range), -1 = retreat. TCP fixed;
        # we move the TARGET along the boresight (same acoustic scene as D1/S2).
        a0 = float(self._actions[0, 0].item())
        delta = -a0 * float(self.cfg.max_forward_step_m)
        lo = float(self.cfg.range_min_m)
        hi = float(self.cfg.range_max_m)
        self._prev_true_range_m = float(self._true_range_m)
        self._true_range_m = float(min(hi, max(lo, self._true_range_m + delta)))

    def _apply_action(self) -> None:
        if self._rtx is None or self._ur10 is None:
            return
        self._place_target_at_distance(self._true_range_m)
        self._ur10.write_joint_position_to_sim_index(
            position=self._rtx.locked_q_tensor,
            joint_ids=self._rtx.joint_ids,
        )

    def _get_observations(self) -> dict:
        return {"policy": self._obs.clone()}

    def _get_rewards(self) -> torch.Tensor:
        # Always re-measure after the approach move so d_hat tracks action.
        if (int(self.episode_length_buf[0].item()) % max(1, int(self.cfg.gmo_capture_interval))) == 0:
            self._capture_gmo()
        rewards = torch.zeros(self.num_envs, device=self.device)
        use_true_rew = bool(getattr(self.cfg, "reward_use_true_range", True))
        d_hat_now = float(self._d_hat[0].item())
        for i in range(self.num_envs):
            a0 = float(self._actions[i, 0].item()) if hasattr(self, "_actions") else 0.0
            a1 = float(self._actions[i, 1].item()) if hasattr(self, "_actions") else 0.0
            # Use real GMO validity (not blind-zeroed obs channel) for reward.
            gmo_v = float(getattr(self, "_gmo_valid_f", 0.0))
            r = compute_reward(
                d_hat_xy=float(self._d_hat[i].item()),
                standoff_m=float(self.cfg.standoff_m),
                gripper_cmd=a1,
                gmo_valid=gmo_v,
                action_l2=a0 * a0 + a1 * a1,
                cfg_approach=float(self.cfg.rew_approach),
                cfg_standoff=float(self.cfg.rew_standoff_bonus),
                cfg_close=float(self.cfg.rew_close_near),
                cfg_alive=float(self.cfg.rew_alive),
                cfg_invalid=float(self.cfg.rew_gmo_invalid),
                cfg_act=float(self.cfg.rew_action_l2),
                true_range_m=float(self._true_range_m) if use_true_rew else None,
                prev_true_range_m=float(self._prev_true_range_m) if use_true_rew else None,
                prev_d_hat_xy=float(self._prev_d_hat),
                gripper_open=float(self._gripper_open[i].item()),
                cfg_true_approach=float(self.cfg.rew_true_approach) if use_true_rew else 0.0,
                cfg_false_close=float(self.cfg.rew_false_close),
                cfg_progress=float(getattr(self.cfg, "rew_progress", 0.0)),
                cfg_hold_closed=float(getattr(self.cfg, "rew_hold_closed", 0.0)),
                cfg_open_when_near=float(getattr(self.cfg, "rew_open_when_near", 0.0)),
                near_tol_m=0.05,
                use_true_scaffold=use_true_rew,
            )
            rewards[i] = r
        self._prev_d_hat = d_hat_now
        if hasattr(self, "_actions"):
            self._prev_action = self._actions.detach().clone()
        self.extras.setdefault("log", {})
        d_hat = float(self._d_hat.mean().item())
        true_r = float(self._true_range_m)
        self.extras["log"]["Metrics/d_hat_xy"] = d_hat
        self.extras["log"]["Metrics/true_range_m"] = true_r  # log only — not in policy obs
        self.extras["log"]["Metrics/peak_sample_idx"] = (
            float(self._last_peak_sample_idx)
            if math.isfinite(self._last_peak_sample_idx)
            else -1.0
        )
        self.extras["log"]["Metrics/d_hat_valid"] = 1.0 if self._d_hat_valid else 0.0
        # Diagnostic: how far acoustic estimate is from true range (oracle log only)
        self.extras["log"]["Metrics/d_hat_abs_err"] = (
            abs(d_hat - true_r) if self._d_hat_valid else -1.0
        )
        # Extra diagnostics from last GMO (log only)
        gmo_dbg = (
            self._rtx.writer_state.last_gmo_fields
            if self._rtx and self._rtx.writer_state.last_gmo_fields
            else {}
        )
        for mk, gk in (
            ("Metrics/peak_full_idx", "primary_sgw_peak_sample_idx"),
            ("Metrics/peak_early_idx", "primary_sgw_early_peak_sample_idx"),
            ("Metrics/early_energy", "primary_sgw_early_energy"),
        ):
            try:
                self.extras["log"][mk] = float(gmo_dbg.get(gk, -1.0) or -1.0)
            except (TypeError, ValueError):
                self.extras["log"][mk] = -1.0
        self.extras["log"]["Metrics/gripper_open"] = float(self._gripper_open.mean().item())
        thr = float(self.cfg.standoff_m) + 0.05
        closed = float(self._gripper_open[0].item()) < 0.5
        # Policy-internal success (acoustic estimate) — may false-positive if d_hat biased low.
        near_dhat = self._d_hat_valid and d_hat <= thr
        self.extras["log"]["Metrics/success_near_and_closed"] = 1.0 if (near_dhat and closed) else 0.0
        # Oracle success (log/eval only — true_range never enters policy obs).
        near_true = true_r <= thr
        self.extras["log"]["Metrics/success_true_near_and_closed"] = (
            1.0 if (near_true and closed) else 0.0
        )
        self.extras["log"]["Metrics/false_pos_dhat_success"] = (
            1.0 if (near_dhat and closed and not near_true) else 0.0
        )
        return rewards

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        terminated = torch.zeros_like(time_out)
        # Early success stop uses ORACLE true near + closed only.
        # (d_hat is systematically near-biased; early-stop on d_hat collapses episodes
        # into false-close open-loop. Termination may be privileged; reward can still
        # be pure acoustic when reward_use_true_range=False.)
        if bool(getattr(self.cfg, "early_stop_on_success", False)):
            thr = float(self.cfg.standoff_m) + 0.05
            near = float(self._true_range_m) <= thr
            closed = float(self._gripper_open[0].item()) < 0.5
            if near and closed:
                terminated[:] = True
        return terminated, time_out

    def _reset_idx(self, env_ids: Sequence[int] | None) -> None:
        if env_ids is None:
            env_ids = torch.arange(self.num_envs, device=self.device, dtype=torch.long)
        super()._reset_idx(env_ids)
        self._gripper_open[env_ids] = 1.0
        self._prev_action[env_ids] = 0.0
        self._d_hat_valid = False
        self._last_peak_sample_idx = float("nan")
        self._last_peak_source = ""
        if self._rtx is not None:
            # Random start range in [reset_min, reset_max] — value not in obs.
            lo = float(self.cfg.reset_range_min_m)
            hi = float(self.cfg.reset_range_max_m)
            # deterministic-ish from episode counter if available
            t = float(self.episode_length_buf[0].item()) if hasattr(self, "episode_length_buf") else 0.0
            u = (hash((int(t), id(self))) % 1000) / 1000.0
            self._true_range_m = lo + (hi - lo) * u
            self._prev_true_range_m = float(self._true_range_m)
            self._prev_d_hat = float(self._true_range_m)  # init until first GMO
            self._place_target_at_distance(self._true_range_m)
            self._capture_gmo()

    def _place_target_at_distance(self, distance_m: float) -> None:
        if self._rtx is None or self._ur10 is None:
            return
        target_position = target_position_from_sensor(
            self._rtx.sensor_position,
            self._rtx.sensor_forward,
            distance_m,
        )
        if not target_inside_room(target_position):
            return
        set_target_pose(
            self._Cube,
            self._np,
            TARGET_PRIM_PATH,
            target_position,
            self._rtx.target_scale,
        )
        self._ur10.write_joint_position_to_sim_index(
            position=self._rtx.locked_q_tensor,
            joint_ids=self._rtx.joint_ids,
        )
        for _ in range(max(1, int(self.cfg.target_settle_steps))):
            self._physics_step(render=False)

    def _advance_sim_for_gmo(self, render: bool = False) -> None:
        if self._ur10 is not None:
            self._ur10.write_data_to_sim()
        self.sim.forward()
        self.sim.step(render=render)

    def _capture_gmo(self) -> bool:
        if self._rtx is None:
            return False
        if self._ur10 is not None:
            self._ur10.write_joint_position_to_sim_index(
                position=self._rtx.locked_q_tensor,
                joint_ids=self._rtx.joint_ids,
            )
        # Multi-frame average of primary waveform (D3/S2 style) then gated peak.
        n_avg = max(1, int(getattr(self.cfg, "gmo_avg_frames", 1)))
        amps_acc = None
        n_ok = 0
        captured_any = False
        for _ in range(n_avg):
            ok = capture_rtx_gmo(
                writer_state=self._rtx.writer_state,
                simulation_app=self._rtx.simulation_app,
                advance_sim=self._advance_sim_for_gmo,
                substeps=int(self.cfg.substeps_per_capture),
                post_update_ticks=5,
                after_substeps=self.sim.render,
            )
            captured_any = captured_any or bool(ok)
            amps = self._rtx.writer_state.last_primary_amps
            if amps is None:
                continue
            try:
                if amps_acc is None:
                    amps_acc = [float(x) for x in amps]
                else:
                    for i, x in enumerate(amps):
                        if i < len(amps_acc):
                            amps_acc[i] += float(x)
                n_ok += 1
            except (TypeError, ValueError):
                continue
        if amps_acc is not None and n_ok > 0:
            self._avg_primary_amps = [v / float(n_ok) for v in amps_acc]
        else:
            self._avg_primary_amps = None
        if self._ur10 is not None:
            self.scene.update(dt=self.physics_dt)
        self._update_obs_from_gmo()
        return captured_any

    def _update_obs_from_gmo(self) -> None:
        gmo = self._rtx.writer_state.last_gmo_fields if self._rtx else None
        energy = float(gmo.get("primary_sgw_early_energy", 0.0)) if gmo else 0.0
        # Prefer gated peak on multi-frame mean waveform (matches D3 sample index scale).
        amps = getattr(self, "_avg_primary_amps", None)
        if amps is None and self._rtx is not None:
            amps = self._rtx.writer_state.last_primary_amps
        # Peak search floor ≥0.32 m to avoid TX/near-field ringing (samples ~12–16)
        # even when physical range_min is lower for standoff reachability.
        peak_lo = max(float(self.cfg.range_min_m), 0.32)
        peak_idx, peak_src = gated_peak_sample_idx(
            amps,
            slope=float(self._calib_slope),
            intercept=float(self._calib_intercept),
            # Tight gate = corridor only; do not widen into room multipath (~1.17 m / idx 64).
            range_lo_m=peak_lo,
            range_hi_m=float(self.cfg.range_max_m),
            margin_samples=2,
        )
        if not math.isfinite(peak_idx):
            peak_idx, peak_src = extract_peak_sample_idx(gmo)
        self._last_peak_sample_idx = peak_idx
        self._last_peak_source = peak_src
        gmo_struct_ok = bool(gmo and gmo.get("gmo_valid", False))
        if not math.isfinite(energy):
            energy = 0.0

        d_hat_raw = peak_to_d_hat_xy(
            peak_idx,
            self._calib_slope,
            self._calib_intercept,
            float(self.cfg.height_diff_m),
        )
        # Physical band for fixed-TCP corridor (~0.4–1.05 m) with headroom.
        d_hat_ok = math.isfinite(d_hat_raw) and 0.05 <= d_hat_raw <= 3.0
        if d_hat_ok:
            d_hat = float(d_hat_raw)
            self._d_hat_valid = True
        else:
            # Do NOT freeze forever on a stale constant (previous bug: amplitude
            # misread as sample idx → absurd d_hat → sticky 0.7). Hold last good
            # estimate only if we already had a valid ToF this session; else a
            # large sentinel so approach reward stays informative + gmo invalid.
            prev = float(self._d_hat[0].item())
            if self._d_hat_valid and math.isfinite(prev) and 0.05 <= prev <= 3.0:
                d_hat = prev
            else:
                d_hat = 10.0
                self._d_hat_valid = False

        # Policy gmo_valid: structure OK AND usable peak_sample_idx for range.
        valid = 1.0 if (gmo_struct_ok and d_hat_ok) else 0.0
        self._gmo_valid_f = float(valid)
        peak_for_obs = float(peak_idx) if math.isfinite(peak_idx) else 0.0

        self._d_hat[:] = d_hat
        sensor = self._rtx.sensor_position if self._rtx else (0.0, 0.0, 0.0)
        self._ee_x[:] = float(sensor[0])
        include_true = bool(getattr(self.cfg, "obs_include_true_range", False))
        row = pack_policy_obs(
            energy_scaled=energy * float(self.cfg.energy_scale),
            peak_scaled=peak_for_obs * float(self.cfg.peak_scale),
            gmo_valid=valid,
            d_hat_xy=d_hat * float(self.cfg.d_hat_scale),
            gripper_open=float(self._gripper_open[0].item()),
            ee_x=float(sensor[0]),
            prev_a0=float(self._prev_action[0, 0].item()),
            prev_a1=float(self._prev_action[0, 1].item()),
            blind_acoustic=bool(self.cfg.blind_acoustic),
            true_range_scaled=float(self._true_range_m),
            include_true_range=include_true,
        )
        # Pad/truncate to configured observation dim
        obs_dim = int(self.cfg.observation_space)
        if len(row) < obs_dim:
            row = row + [0.0] * (obs_dim - len(row))
        elif len(row) > obs_dim:
            row = row[:obs_dim]
        self._obs[0] = torch.tensor(row, device=self.device, dtype=torch.float32)
