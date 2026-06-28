"""DirectRLEnv for in-sim RSL-RL distance estimation with RTX acoustic GMO."""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import torch

from isaaclab.assets import Articulation
from isaaclab.envs import DirectRLEnv
from isaaclab_assets.robots.universal_robots import UR10_CFG

LAB_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
for path in (str(SCRIPTS_DIR), str(LAB_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from geometry_passport_v1 import (  # noqa: E402
    EE_FRAME,
    ROBOT_PRIM_PATH,
    SENSOR_PRIM_NAME,
    TARGET_PRIM_PATH,
    target_inside_room,
    target_position_from_sensor,
)
from moving_target_controller import SinusoidalDistanceTrajectory  # noqa: E402
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
    from .ur10_rtx_acoustic_distance_env_cfg import Ur10RtxAcousticDistanceEnvCfg


class Ur10RtxAcousticDirectEnv(DirectRLEnv):
    """Fixed-TCP UR10 with sinusoidal target; policy predicts distance from acoustic obs."""

    cfg: Ur10RtxAcousticDistanceEnvCfg

    def __init__(self, cfg: Ur10RtxAcousticDistanceEnvCfg, render_mode: str | None = None, **kwargs):
        self._rtx: RtxSceneHandles | None = None
        self._rtx_stage: RtxSceneStage | None = None
        self._ur10: Articulation | None = None
        self._trajectory = SinusoidalDistanceTrajectory(
            center_distance_m=float(cfg.center_distance_m),
            amplitude_m=float(cfg.amplitude_m),
            period_steps=int(cfg.period_steps),
        )
        self._dist_min, self._dist_max = self._trajectory.distance_bounds_m()
        self._step_counter = 0
        self._gt_distance = torch.zeros(cfg.scene.num_envs, device=cfg.sim.device)
        self._predicted_distance = torch.zeros(cfg.scene.num_envs, device=cfg.sim.device)
        self._prev_gt_distance = torch.zeros(cfg.scene.num_envs, device=cfg.sim.device)
        self._prev_predicted_distance = torch.zeros(cfg.scene.num_envs, device=cfg.sim.device)
        self._obs_features = torch.zeros(cfg.scene.num_envs, 6, device=cfg.sim.device)
        super().__init__(cfg, render_mode, **kwargs)
        if self._rtx_stage is not None and self._ur10 is not None:
            rebind_rtx_gmo_writer(self._rtx_stage)
            self._rtx = finalize_rtx_robot_handles(
                self._rtx_stage,
                articulation=self._ur10,
                settle_steps=int(self.cfg.settle_steps),
                step_fn=self._physics_step,
            )
            self._obs_features[:, 3:6] = torch.tensor(
                self._rtx.sensor_position, device=self.device, dtype=torch.float32
            ).unsqueeze(0)
            captured = self._capture_gmo()
            obs_row = self._obs_features[0].detach().cpu().tolist()
            ws = self._rtx.writer_state
            print(
                "Ur10RtxAcousticDirectEnv: locked TCP "
                f"distance=[{self._dist_min:.2f}, {self._dist_max:.2f}] m "
                f"episode_steps={self.max_episode_length} "
                f"gmo_init_captured={captured} obs0={obs_row[:3]} "
                f"gmo_writer_frames={ws.writer_frame} "
                f"gmo_empty_frames={ws.raw_empty_frames} gmo_parse_errors={len(ws.parse_errors)}",
                flush=True,
            )

    def _setup_scene(self) -> None:
        import numpy as np  # noqa: WPS433
        import omni.kit.app  # noqa: WPS433

        simulation_app = get_simulation_app()
        if simulation_app is None:
            raise RuntimeError(
                "SimulationApp not registered. Call simulation_app_ref.set_simulation_app(app_launcher.app) "
                "after AppLauncher in train/play/smoke entry points."
            )

        from isaacsim.storage.native import get_assets_root_path  # noqa: WPS433

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
        from isaacsim.core.experimental.objects import Cube  # noqa: WPS433

        self._np = np
        self._Cube = Cube

    def _physics_step(self, render: bool = False) -> None:
        if self._ur10 is not None:
            self._ur10.write_data_to_sim()
        self.sim.forward()
        self.sim.step(render=render)
        import omni.kit.app  # noqa: WPS433

        omni.kit.app.get_app().update()
        if self._ur10 is not None:
            self.scene.update(dt=self.physics_dt)

    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        clipped = torch.clamp(actions, -self.cfg.action_clip, self.cfg.action_clip)
        normalized = (clipped[:, 0] + 1.0) * 0.5
        self._predicted_distance = self._dist_min + normalized * (self._dist_max - self._dist_min)
        self._advance_target(self._step_counter)

    def _apply_action(self) -> None:
        if self._rtx is None or self._ur10 is None:
            return
        self._ur10.write_joint_position_to_sim_index(
            position=self._rtx.locked_q_tensor,
            joint_ids=self._rtx.joint_ids,
        )

    def _get_observations(self) -> dict:
        return {"policy": self._obs_features.clone()}

    def _energy_prior_distance(self) -> torch.Tensor:
        raw_energy = self._obs_features[:, 0] / float(self.cfg.energy_scale)
        normalized = (raw_energy - float(self.cfg.energy_prior_ref)) / max(
            float(self.cfg.energy_prior_scale), 1.0e-6
        )
        prior = float(self.cfg.center_distance_m) + float(self.cfg.energy_prior_slope) * normalized
        return torch.clamp(prior, min=self._dist_min, max=self._dist_max)

    def _get_rewards(self) -> torch.Tensor:
        error = torch.abs(self._predicted_distance - self._gt_distance)
        reward = -self.cfg.rew_scale_distance * error + self.cfg.rew_alive_bonus

        energy_prior = self._energy_prior_distance()
        energy_align_error = torch.abs(self._predicted_distance - energy_prior)
        if float(self.cfg.rew_scale_energy_align) > 0.0:
            reward -= self.cfg.rew_scale_energy_align * energy_align_error

        move_align = torch.zeros_like(error)
        if float(self.cfg.rew_scale_tracking) > 0.0:
            gt_delta = self._gt_distance - self._prev_gt_distance
            pred_delta = self._predicted_distance - self._prev_predicted_distance
            significant = torch.abs(gt_delta) > 0.02
            move_align = torch.sign(gt_delta) * torch.sign(pred_delta) * significant.float()
            reward += self.cfg.rew_scale_tracking * move_align

        valid = self._obs_features[:, 2]
        if float(self.cfg.rew_gmo_invalid_penalty) > 0.0:
            reward -= self.cfg.rew_gmo_invalid_penalty * (1.0 - valid)

        if (int(self.episode_length_buf[0].item()) % max(1, int(self.cfg.gmo_capture_interval))) == 0:
            self._capture_gmo()

        self.extras.setdefault("log", {})
        self.extras["log"]["Metrics/distance_error_m"] = error.mean().item()
        self.extras["log"]["Metrics/gt_distance_m"] = self._gt_distance.mean().item()
        self.extras["log"]["Metrics/pred_distance_m"] = self._predicted_distance.mean().item()
        self.extras["log"]["Metrics/energy_prior_distance_m"] = energy_prior.mean().item()
        self.extras["log"]["Metrics/energy_align_error_m"] = energy_align_error.mean().item()
        self.extras["log"]["Metrics/tracking_align"] = move_align.mean().item()
        gmo = self._rtx.writer_state.last_gmo_fields if self._rtx else None
        if gmo:
            self.extras["log"]["Metrics/raw_early_energy"] = float(gmo.get("primary_sgw_early_energy", 0.0))
            self.extras["log"]["Metrics/raw_peak"] = float(gmo.get("primary_sgw_peak", 0.0))
            self.extras["log"]["Metrics/gmo_valid_flag"] = 1.0 if gmo.get("gmo_valid", False) else 0.0

        self._prev_gt_distance = self._gt_distance.clone()
        self._prev_predicted_distance = self._predicted_distance.clone()
        return reward

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        terminated = torch.zeros_like(time_out)
        return terminated, time_out

    def _reset_idx(self, env_ids: Sequence[int] | None) -> None:
        if env_ids is None:
            env_ids = torch.arange(self.num_envs, device=self.device, dtype=torch.long)
        super()._reset_idx(env_ids)
        self._step_counter = 0
        self._prev_gt_distance[env_ids] = self._gt_distance[env_ids]
        self._prev_predicted_distance[env_ids] = self._predicted_distance[env_ids]
        if self._rtx is not None:
            self._advance_target(0)
            self._capture_gmo()

    def _advance_target(self, step_index: int) -> None:
        if self._rtx is None or self._ur10 is None:
            return

        desired_distance = self._trajectory.distance_at_step(step_index)
        target_position = target_position_from_sensor(
            self._rtx.sensor_position,
            self._rtx.sensor_forward,
            desired_distance,
        )
        if not target_inside_room(target_position):
            raise RuntimeError(f"Target outside room at distance {desired_distance:.3f} m")

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

        obs = self._rtx.observe_pose(self._rtx.locked_q, 1, render=False)
        sensor_pos = obs["sensor_position"]
        self._gt_distance[:] = float(vec_norm(vec_sub(target_position, sensor_pos)))
        self._step_counter = step_index + 1

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
        captured = capture_rtx_gmo(
            writer_state=self._rtx.writer_state,
            simulation_app=self._rtx.simulation_app,
            advance_sim=self._advance_sim_for_gmo,
            substeps=int(self.cfg.substeps_per_capture),
            post_update_ticks=5,
            after_substeps=self.sim.render,
        )
        if self._ur10 is not None:
            self.scene.update(dt=self.physics_dt)
        self._update_obs_from_gmo()
        return captured

    def _update_obs_from_gmo(self) -> None:
        gmo = self._rtx.writer_state.last_gmo_fields if self._rtx else None
        energy = float(gmo.get("primary_sgw_early_energy", 0.0)) if gmo else 0.0
        peak = float(gmo.get("primary_sgw_peak", 0.0)) if gmo else 0.0
        valid = 1.0 if gmo and gmo.get("gmo_valid", False) else 0.0
        if not math.isfinite(energy):
            energy = 0.0
        if not math.isfinite(peak):
            peak = 0.0

        sensor = self._rtx.sensor_position if self._rtx else (0.0, 0.0, 0.0)
        self._obs_features[0, 0] = energy * float(self.cfg.energy_scale)
        self._obs_features[0, 1] = peak * float(self.cfg.peak_scale)
        self._obs_features[0, 2] = valid
        self._obs_features[0, 3] = sensor[0]
        self._obs_features[0, 4] = sensor[1]
        self._obs_features[0, 5] = sensor[2]