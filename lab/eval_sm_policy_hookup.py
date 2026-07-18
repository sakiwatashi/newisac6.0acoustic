"""D4 ④ SM + Track-B policy hookup (episode-level).

Runs the trained approach+close policy inside an explicit Track-A SM state
machine (REST → ACOUSTIC_APPROACH → ACOUSTIC_ALIGN_STOP → CLOSE → LIFT_HANDOFF).

Physics boundary (honest):
  - This Lab env is fixed-TCP virtual approach (B). It does **not** execute
    Track-A physical descend/weld/lift.
  - ``LIFT_HANDOFF`` means: B phase succeeded (oracle true near + closed) and
    the episode is ready to hand to Track-A SM lift executor (weld-on-stall).
  - Lift success rates still come from Track A formal runs (e.g. n30).

Example:
  ACOUSTIC_ONLY=1 EPISODES=20 \\
  CHECKPOINT=runtime/outputs/v2_d4_ppo_grasp_acoustic_close_ft/rsl_rl_logs/model_49.pt \\
  bash lab/run_d4_sm_policy_hookup.sh
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = LAB_DIR.parent / "scripts"
REPO = LAB_DIR.parent
for path in (str(LAB_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from isaaclab.app import AppLauncher

NEAR_TOL_M = 0.05

# Mirror scripts/d4_grasp_common.SmState names (keep eval free of d3 imports).
SM_REST = "REST"
SM_APPROACH = "ACOUSTIC_APPROACH"
SM_ALIGN = "ACOUSTIC_ALIGN_STOP"
SM_CLOSE = "CLOSE"
SM_LIFT_HANDOFF = "LIFT_HANDOFF"  # virtual: B done → A owns weld/lift
SM_DONE = "DONE"
SM_FAILED = "FAILED"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="D4 ④ SM+policy hookup eval.")
    AppLauncher.add_app_launcher_args(parser)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--stochastic", action="store_true")
    parser.add_argument(
        "--acoustic-only-obs",
        action="store_true",
        help="8-D acoustic-only policy (canonical close_ft).",
    )
    parser.add_argument("--blind-acoustic", action="store_true")
    parser.set_defaults(headless=True)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    p = path.expanduser()
    if p.is_file():
        return p.resolve()
    host = (REPO / p).resolve()
    if host.is_file():
        return host
    return p.resolve()


def _policy_obs(obs):
    if hasattr(obs, "get") and "policy" in obs.keys():
        return obs["policy"]
    if isinstance(obs, dict):
        return obs.get("policy", obs.get("actor", obs))
    return obs


def _sm_step(
    state: str,
    *,
    true_r: float,
    d_hat: float,
    grip_open: float,
    a0: float,
    a1: float,
    thr: float,
    d_hat_valid: bool,
) -> str:
    """Advance SM from acoustic/policy signals (oracle true only for ALIGN/CLOSE success)."""
    closed = math.isfinite(grip_open) and grip_open < 0.5
    true_near = math.isfinite(true_r) and true_r <= thr
    # Policy-facing near (may be biased) — used only to leave pure approach.
    est_near = (d_hat_valid and math.isfinite(d_hat) and d_hat <= thr) or true_near
    closing = a1 < -0.1

    if state == SM_REST:
        return SM_APPROACH

    if state == SM_APPROACH:
        if true_near and closed:
            return SM_LIFT_HANDOFF
        if true_near and not closed:
            return SM_ALIGN
        if est_near and closing:
            return SM_CLOSE
        if est_near:
            return SM_ALIGN
        return SM_APPROACH

    if state == SM_ALIGN:
        if true_near and closed:
            return SM_LIFT_HANDOFF
        if closing or closed:
            return SM_CLOSE
        # still near but open → hold ALIGN
        if true_near or est_near:
            return SM_ALIGN
        return SM_APPROACH

    if state == SM_CLOSE:
        if true_near and closed:
            return SM_LIFT_HANDOFF
        if closed and not true_near:
            # false close far — stay CLOSE until timeout/end
            return SM_CLOSE
        if not closed and (true_near or est_near):
            return SM_ALIGN
        if not closed:
            return SM_APPROACH
        return SM_CLOSE

    if state == SM_LIFT_HANDOFF:
        return SM_DONE

    if state in (SM_DONE, SM_FAILED):
        return state

    return SM_APPROACH


def main() -> None:
    args = parse_args()
    ckpt = _resolve(args.checkpoint)
    if not ckpt.is_file():
        raise FileNotFoundError(f"checkpoint not found: {args.checkpoint} -> {ckpt}")

    out_dir = args.output_dir
    if out_dir is None:
        out_dir = ckpt.parent.parent if ckpt.parent.name == "rsl_rl_logs" else ckpt.parent
        out_dir = out_dir / "sm_policy_hookup"
    out_dir = out_dir if out_dir.is_absolute() else (REPO / out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app
    from simulation_app_ref import set_simulation_app

    set_simulation_app(simulation_app)

    import importlib.metadata as metadata

    import gymnasium as gym
    import torch
    from rsl_rl.runners import OnPolicyRunner

    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg

    import isaaclab_tasks_ext  # noqa: F401
    from isaaclab_tasks_ext.ur10_rtx_acoustic_grasp.agents.rsl_rl_ppo_cfg import (
        Ur10RtxAcousticGraspPPORunnerCfg,
    )
    from isaaclab_tasks_ext.ur10_rtx_acoustic_grasp.ur10_rtx_acoustic_grasp_env_cfg import (
        Ur10RtxAcousticGraspEnvCfg,
    )

    env_cfg = Ur10RtxAcousticGraspEnvCfg()
    env_cfg.scene.num_envs = 1
    env_cfg.seed = int(args.seed)
    acoustic_only = bool(args.acoustic_only_obs)
    env_cfg.obs_include_true_range = not acoustic_only
    env_cfg.observation_space = 8 if acoustic_only else 9
    env_cfg.blind_acoustic = bool(args.blind_acoustic)

    agent_cfg = Ur10RtxAcousticGraspPPORunnerCfg()
    agent_cfg.seed = int(args.seed)
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, metadata.version("rsl-rl-lib"))

    env = gym.make("Isaac-Ur10RtxAcousticGrasp-Direct-v0", cfg=env_cfg)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    print(f"[INFO] SM-hookup loading {ckpt}", flush=True)
    runner.load(str(ckpt))
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    unwrapped = env.unwrapped
    standoff = float(unwrapped.cfg.standoff_m)
    thr = standoff + NEAR_TOL_M
    max_ep_len = int(unwrapped.max_episode_length)
    max_steps = int(args.max_steps) if int(args.max_steps) > 0 else max_ep_len

    print(
        f"[INFO] episodes={args.episodes} max_steps={max_steps} thr={thr:.2f}m "
        f"acoustic_only={acoustic_only} blind={bool(args.blind_acoustic)}",
        flush=True,
    )

    episode_rows: list[dict] = []
    obs = env.get_observations()

    for ep in range(int(args.episodes)):
        if ep > 0 and not episode_rows[-1].get("_ended_on_done", False):
            with torch.inference_mode(False):
                if hasattr(env, "reset"):
                    reset_out = env.reset()
                    obs = reset_out[0] if isinstance(reset_out, tuple) else reset_out
            if hasattr(policy, "reset"):
                try:
                    policy.reset()
                except TypeError:
                    pass

        sm_state = SM_REST
        sm_hist: list[str] = [sm_state]
        true_hist: list[float] = []
        dhat_hist: list[float] = []
        grip_hist: list[float] = []
        rew_sum = 0.0
        steps = 0
        ever_true_near = False
        ever_true_success = False
        ever_lift_handoff = False
        min_true = float("inf")
        ended_on_done = False
        first_align_step = -1
        first_close_step = -1
        first_handoff_step = -1

        for _ in range(max_steps):
            with torch.no_grad():
                if args.stochastic:
                    actions = policy(obs, stochastic_output=True)
                else:
                    actions = policy(obs)
            # read action for SM (before step mutates)
            try:
                a0 = float(actions[0, 0].item()) if actions.ndim > 1 else float(actions[0].item())
                a1 = float(actions[0, 1].item()) if actions.ndim > 1 else float(actions[1].item())
            except Exception:
                a0, a1 = 0.0, 0.0

            obs, rewards, dones, extras = env.step(actions)
            if hasattr(dones, "any") and dones.any() and hasattr(policy, "reset"):
                try:
                    policy.reset(dones)
                except TypeError:
                    policy.reset()

            rew_sum += float(rewards.mean().item())
            log = extras.get("log", {}) if isinstance(extras, dict) else {}
            true_r = float(log.get("Metrics/true_range_m", float("nan")))
            d_hat = float(log.get("Metrics/d_hat_xy", float("nan")))
            grip = float(log.get("Metrics/gripper_open", float("nan")))
            d_hat_valid = float(log.get("Metrics/d_hat_valid", 0.0)) > 0.5

            if math.isfinite(true_r):
                true_hist.append(true_r)
                min_true = min(min_true, true_r)
                if true_r <= thr:
                    ever_true_near = True
            if math.isfinite(d_hat):
                dhat_hist.append(d_hat)
            if math.isfinite(grip):
                grip_hist.append(grip)
            closed = math.isfinite(grip) and grip < 0.5
            if math.isfinite(true_r) and true_r <= thr and closed:
                ever_true_success = True

            new_state = _sm_step(
                sm_state,
                true_r=true_r,
                d_hat=d_hat,
                grip_open=grip,
                a0=a0,
                a1=a1,
                thr=thr,
                d_hat_valid=d_hat_valid,
            )
            if new_state != sm_state:
                sm_hist.append(new_state)
                sm_state = new_state
                if sm_state == SM_ALIGN and first_align_step < 0:
                    first_align_step = steps
                if sm_state == SM_CLOSE and first_close_step < 0:
                    first_close_step = steps
                if sm_state == SM_LIFT_HANDOFF and first_handoff_step < 0:
                    first_handoff_step = steps
                    ever_lift_handoff = True

            steps += 1
            if sm_state in (SM_LIFT_HANDOFF, SM_DONE):
                # B phase complete; A would take weld/lift here.
                sm_state = SM_DONE
                if sm_hist[-1] != SM_DONE:
                    sm_hist.append(SM_DONE)
                ended_on_done = True
                break
            if hasattr(dones, "any") and bool(dones.any()):
                ended_on_done = True
                break

        final_true = true_hist[-1] if true_hist else float("nan")
        final_dhat = dhat_hist[-1] if dhat_hist else float("nan")
        final_grip = grip_hist[-1] if grip_hist else float("nan")
        final_closed = math.isfinite(final_grip) and final_grip < 0.5
        final_true_near = math.isfinite(final_true) and final_true <= thr
        final_true_success = final_true_near and final_closed
        final_dhat_success = (
            math.isfinite(final_dhat) and final_dhat <= thr and final_closed
        )
        handoff_ready = ever_lift_handoff or final_true_success
        if not handoff_ready and sm_state not in (SM_DONE, SM_LIFT_HANDOFF):
            sm_state = SM_FAILED
            sm_hist.append(SM_FAILED)

        row = {
            "episode": ep,
            "steps": steps,
            "return_sum": rew_sum,
            "final_true_range_m": final_true,
            "final_d_hat_m": final_dhat,
            "final_gripper_open": final_grip,
            "min_true_range_m": min_true if math.isfinite(min_true) else float("nan"),
            "ever_true_near": ever_true_near,
            "ever_true_success": ever_true_success,
            "final_true_near": final_true_near,
            "final_true_success": final_true_success,
            "final_dhat_success": final_dhat_success,
            "sm_final_state": sm_state,
            "sm_trace": sm_hist,
            "first_align_step": first_align_step,
            "first_close_step": first_close_step,
            "first_handoff_step": first_handoff_step,
            "lift_handoff_ready": handoff_ready,
            "lift_executed_here": False,  # A SM owns physical lift
            "_ended_on_done": ended_on_done,
        }
        episode_rows.append(row)
        print(
            f"[EP {ep:02d}] steps={steps:2d} sm={sm_state:16s} "
            f"true_f={final_true:.3f} closed={int(final_closed)} "
            f"handoff={int(handoff_ready)} true_succ={int(final_true_success)} "
            f"trace={'→'.join(sm_hist)}",
            flush=True,
        )

    n = len(episode_rows)

    def rate(key: str) -> float:
        return sum(1 for r in episode_rows if r[key]) / n if n else 0.0

    finals = [r["final_true_range_m"] for r in episode_rows if math.isfinite(r["final_true_range_m"])]
    mins = [r["min_true_range_m"] for r in episode_rows if math.isfinite(r["min_true_range_m"])]
    handoff_steps = [
        r["first_handoff_step"] for r in episode_rows if r["first_handoff_step"] >= 0
    ]

    # Optional: pull A formal lift column if present (offline, no re-run).
    a_n30 = REPO / "runtime" / "outputs" / "v2_d4_sm_grasp_n30"
    a_ref = None
    adj = a_n30 / "adjudication.json"
    if adj.is_file():
        try:
            a_ref = json.loads(adj.read_text())
        except Exception:
            a_ref = {"path": str(adj), "note": "parse_failed"}
    elif (a_n30 / "closed" / "episodes.csv").is_file():
        a_ref = {
            "path": str(a_n30),
            "note": "closed/episodes.csv present; run analyze_d4_sm_grasp for full adj",
        }

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "track": "D4_4_sm_policy_hookup",
        "checkpoint": str(ckpt),
        "n_episodes": n,
        "max_steps": max_steps,
        "seed": int(args.seed),
        "stochastic": bool(args.stochastic),
        "standoff_m": standoff,
        "near_threshold_m": thr,
        "obs_include_true_range": bool(env_cfg.obs_include_true_range),
        "acoustic_only_obs": acoustic_only,
        "blind_acoustic": bool(env_cfg.blind_acoustic),
        "sm_states": [
            SM_REST,
            SM_APPROACH,
            SM_ALIGN,
            SM_CLOSE,
            SM_LIFT_HANDOFF,
            SM_DONE,
            SM_FAILED,
        ],
        "claim_boundary": (
            "④ SM+policy hookup: B policy drives ACOUSTIC_APPROACH / ALIGN / CLOSE. "
            "LIFT_HANDOFF = oracle true near+closed (ready for Track A weld lift). "
            "Physical lift NOT executed in this Lab env. No object xyz in policy obs. "
            "Not a pure-acoustic-reward claim; not friction-only lift."
        ),
        "rate_final_true_near": rate("final_true_near"),
        "rate_final_true_success": rate("final_true_success"),
        "rate_final_dhat_success": rate("final_dhat_success"),
        "rate_ever_true_near": rate("ever_true_near"),
        "rate_ever_true_success": rate("ever_true_success"),
        "rate_lift_handoff_ready": rate("lift_handoff_ready"),
        "mean_final_true_range_m": sum(finals) / len(finals) if finals else float("nan"),
        "mean_min_true_range_m": sum(mins) / len(mins) if mins else float("nan"),
        "mean_handoff_step": (
            sum(handoff_steps) / len(handoff_steps) if handoff_steps else float("nan")
        ),
        "track_a_lift_reference": a_ref,
        "track_a_lift_note": (
            "P(lift|align) and weld rates: use Track A formal "
            "runtime/outputs/v2_d4_sm_grasp_n30 (closed arm). "
            "④ does not re-run A lift."
        ),
        "episodes": [{k: v for k, v in r.items() if not k.startswith("_")} for r in episode_rows],
    }

    out_path = out_dir / "sm_policy_hookup_summary.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n")

    print("\n=== D4 ④ SM+POLICY HOOKUP SUMMARY ===", flush=True)
    print(f"  n={n} checkpoint={ckpt.name}", flush=True)
    print(f"  final true near:      {100 * summary['rate_final_true_near']:.1f}%", flush=True)
    print(f"  final true success:   {100 * summary['rate_final_true_success']:.1f}%", flush=True)
    print(f"  LIFT_HANDOFF ready:   {100 * summary['rate_lift_handoff_ready']:.1f}%  << B→A", flush=True)
    print(f"  mean handoff step:    {summary['mean_handoff_step']}", flush=True)
    print(f"  physical lift here:   NO (Track A SM + weld)", flush=True)
    print(f"  wrote {out_path}", flush=True)

    env.close()
    simulation_app.close()
    print("PASS: D4 ④ SM+policy hookup eval complete", flush=True)


if __name__ == "__main__":
    main()
