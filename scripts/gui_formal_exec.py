#!/usr/bin/env python3
"""GUI launcher for formal (headless-only) experiment runners — originals untouched.

Why a plain headless→False flip is NOT enough (S1 smoke 2026-07-19):
  - Kit *did* start without ``--no-window`` (window path is live).
  - Formal runners finish in a few seconds and call ``simulation_app.close()``
    immediately → window flashes / never settles where a human can see it.
  - No Camera Light / camera framing → viewport often pure black (looks “not open”).
  - Working references (``demo_gui_showcase.py``, fixed-TCP ``--gui``) always:
      wait_for_viewport → set_camera_view → Camera Light → hold / continuous update.

This tool **does not edit** formal scripts. It rewrites a temp copy under
``runtime/cache/gui_formal/`` then execs it.

Env (optional)::
  GUI_HOLD_S=15          seconds to keep the window open after the experiment
                         finishes (default 15; set 0 to disable)
  GUI_PREVIEW_S=10       seconds of continuous update right after SimApp so the
                         window paints before work starts (default 10; 0=skip)
  GUI_FOCUS=1.0,0.0,0.55 camera look-at (x,y,z metres)

Usage::

    ./app/python.sh scripts/gui_formal_exec.py scripts/paired_capture_runner.py \\
        --cell-json docs/plan_v2/s1_cells/<cell>.json \\
        --output-dir runtime/outputs/v2_s1_envelope_gui
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CACHE = REPO / "runtime" / "cache" / "gui_formal"

# Injected immediately after SimulationApp(...) — pattern from demo_gui_showcase
# + official fixed-TCP GUI (viewport / Camera Light / keep-open).
#
# S1 note: formal paired_capture is nearly empty (sensor + 4cm cube), and it
# *deletes* the cube for without_target before close(). Pre-hold right after
# SimApp is also empty. That looks like "black + grid, cube flash only" — not a
# GPU failure. GUI-only fixes: stage lights, closer camera, defer 10s wait until
# first update (scene already built), re-spawn display cube for post-hold.
_GUI_BOOT_SNIPPET = r'''
# --- injected by gui_formal_exec (do not copy into formal headless scripts) ---
import os as _os_gui_formal  # noqa: E402
import time as _time_gui_formal  # noqa: E402
import carb.settings as _carb_settings_gui_formal  # noqa: E402

_st_gui_formal = _carb_settings_gui_formal.get_settings()
_st_gui_formal.set("/app/player/useFixedTimeStepping", True)
try:
    _st_gui_formal.set("/exts/omni.kit.renderer.core/present/enabled", True)
except Exception as _e_present:
    print(f"[gui_formal_exec] present.enable soft-fail: {_e_present}", flush=True)
try:
    _st_gui_formal.set("/app/window/hideUi", False)
except Exception:
    pass

print(
    "[gui_formal_exec] SimulationApp headless=False hide_ui=False; "
    f"useFixedTimeStepping={_st_gui_formal.get('/app/player/useFixedTimeStepping')}; "
    f"DISPLAY={_os_gui_formal.environ.get('DISPLAY')!r}",
    flush=True,
)
print(
    "[gui_formal_exec] S1 tip: formal scene is sensor + tiny cube only; "
    "without_target deletes the cube. GUI will re-frame/re-light for visibility.",
    flush=True,
)

_gui_formal_state = {
    "pre_hold_done": False,
    "in_hold": False,  # prevent update-hook recursion during holds
    "lights_ok": False,
}


def _gui_formal_focus_xyz():
    raw = _os_gui_formal.environ.get("GUI_FOCUS", "1.0,0.0,0.55")
    try:
        parts = [float(x.strip()) for x in raw.split(",")]
        if len(parts) == 3:
            return parts
    except Exception:
        pass
    return [1.0, 0.0, 0.55]


def _gui_formal_cam_dist():
    # Robot workspace default ~2.5m; S1 4cm cube needs ~0.45–0.7m or it is a speck.
    try:
        return max(0.15, float(_os_gui_formal.environ.get("GUI_CAM_DIST", "2.5")))
    except Exception:
        return 2.5


def _gui_formal_ensure_lights():
    """Add stage lights so the viewport is not pure black (Camera Light alone is weak on empty stages)."""
    if _gui_formal_state["lights_ok"]:
        return
    try:
        import omni.usd
        from pxr import Gf, Sdf, UsdGeom, UsdLux
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        if not stage.GetPrimAtPath("/World"):
            UsdGeom.Xform.Define(stage, "/World")
        # Distant sun
        if not stage.GetPrimAtPath("/World/GuiFormalDistantLight"):
            light = UsdLux.DistantLight.Define(stage, "/World/GuiFormalDistantLight")
            light.CreateIntensityAttr(3000.0)
            light.CreateAngleAttr(1.0)
            UsdGeom.Xformable(light).AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 30.0, 0.0))
        # Soft dome fill
        if not stage.GetPrimAtPath("/World/GuiFormalDomeLight"):
            dome = UsdLux.DomeLight.Define(stage, "/World/GuiFormalDomeLight")
            dome.CreateIntensityAttr(800.0)
        _gui_formal_state["lights_ok"] = True
        print("[gui_formal_exec] stage DistantLight + DomeLight added (GUI-only)", flush=True)
    except Exception as _e_light:
        print(f"[gui_formal_exec] stage lights soft-fail: {_e_light}", flush=True)


def _gui_formal_setup_viewport(tag="boot"):
    """Frame look-at + Camera Light. GUI_CAM_DIST controls eye distance."""
    fx, fy, fz = _gui_formal_focus_xyz()
    dist = _gui_formal_cam_dist()
    _gui_formal_ensure_lights()
    try:
        from isaacsim.core.rendering_manager import ViewportManager
        ready, frames = ViewportManager.wait_for_viewport(max_frames=120, sleep_time=0.02)
        print(
            f"[gui_formal_exec] viewport({tag}): ready={ready} frames={frames} "
            f"focus=({fx:.2f},{fy:.2f},{fz:.2f}) cam_dist={dist:.2f}m",
            flush=True,
        )
        # Look from front-right-above toward focus (not the robot-scale -2.8/look-ahead).
        eye = [fx - dist * 0.85, fy + dist * 0.55, fz + dist * 0.40]
        tgt = [fx, fy, fz]
        ViewportManager.set_camera_view("/OmniverseKit_Persp", eye=eye, target=tgt)
    except Exception as _e_vp:
        print(f"[gui_formal_exec] viewport setup failed ({tag}): {_e_vp}", flush=True)
    try:
        import omni.usd as _omni_usd_gui
        from omni.kit.viewport.menubar.lighting.actions import _set_lighting_mode
        _set_lighting_mode("camera", usd_context=_omni_usd_gui.get_context())
        print(f"[gui_formal_exec] Camera Light ON ({tag})", flush=True)
    except Exception as _e_lt:
        print(f"[gui_formal_exec] Camera Light failed ({tag}): {_e_lt}", flush=True)


def _gui_formal_hold(seconds, tag="hold"):
    """Continuous update loop so the OS window stays mapped and paints."""
    hold = max(0.0, float(seconds))
    if hold <= 0.0:
        return
    print(
        f"[gui_formal_exec] {tag}: keeping Isaac Sim window open for {hold:.0f}s "
        f"(GUI_PREVIEW_S / GUI_HOLD_S override; 0=skip)…",
        flush=True,
    )
    _gui_formal_state["in_hold"] = True
    try:
        t0 = _time_gui_formal.time()
        last = int(hold)
        while _time_gui_formal.time() - t0 < hold:
            try:
                if hasattr(simulation_app, "is_running") and not simulation_app.is_running():
                    break
            except Exception:
                pass
            # Call original update to avoid re-entering pre-hold hook.
            _gui_formal_orig_update()
            left = int(hold - (_time_gui_formal.time() - t0))
            if left != last and left > 0 and left % 5 == 0:
                last = left
                print(f"[gui_formal_exec] {tag}: {left}s remaining", flush=True)
            _time_gui_formal.sleep(0.02)
    finally:
        _gui_formal_state["in_hold"] = False


def _gui_formal_spawn_display_cube():
    """If formal without_target deleted /World/target, put a bright cube back for post-hold only."""
    try:
        import omni.usd
        from pxr import Gf, UsdGeom, UsdShade, Sdf
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        path = "/World/GuiFormalDisplayTarget"
        fx, fy, fz = _gui_formal_focus_xyz()
        # Prefer real target pose if it still exists
        tgt = stage.GetPrimAtPath("/World/target")
        if tgt and tgt.IsValid():
            print("[gui_formal_exec] /World/target still present for post-hold", flush=True)
            return
        if stage.GetPrimAtPath(path):
            return
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(0.08)  # 8cm — slightly larger than S1 4cm for visibility
        xf = UsdGeom.Xformable(cube)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(fx, fy, fz))
        # Bright display color (GUI-only prim; never used in formal metrics)
        try:
            cube.GetDisplayColorAttr().Set([Gf.Vec3f(1.0, 0.35, 0.05)])
        except Exception:
            pass
        print(
            f"[gui_formal_exec] spawned GUI display cube at ({fx:.2f},{fy:.2f},{fz:.2f}) "
            f"for post-run hold (not part of formal data)",
            flush=True,
        )
    except Exception as _e_cube:
        print(f"[gui_formal_exec] display cube soft-fail: {_e_cube}", flush=True)


_gui_formal_orig_update = simulation_app.update
_gui_formal_orig_close = simulation_app.close


def _gui_formal_update(*_a, **_k):
    """On first real frame after scene build: reframe + 10s pre-run wait (cube visible)."""
    out = _gui_formal_orig_update(*_a, **_k)
    if _gui_formal_state["in_hold"] or _gui_formal_state["pre_hold_done"]:
        return out
    # Scene construction in formal runners happens before timeline.play / first updates.
    try:
        import omni.usd
        stage = omni.usd.get_context().get_stage()
        has_content = False
        if stage is not None:
            for p in ("/World/target", "/World/ur10e", "/World/ur10", "/World/table", "/World/bar"):
                prim = stage.GetPrimAtPath(p)
                if prim and prim.IsValid():
                    has_content = True
                    break
            if not has_content:
                w = stage.GetPrimAtPath("/World")
                if w and w.IsValid() and any(True for _ in w.GetChildren()):
                    has_content = True
        if not has_content:
            return out
    except Exception:
        return out
    _gui_formal_state["pre_hold_done"] = True
    print("[gui_formal_exec] scene content detected — pre-run observation wait", flush=True)
    _gui_formal_setup_viewport("pre-run")
    _gui_formal_hold(
        float(_os_gui_formal.environ.get("GUI_PREVIEW_S", "10")),
        tag="pre-run preview (10s, scene ready)",
    )
    return out


def _gui_formal_close(*_a, **_k):
    try:
        _gui_formal_spawn_display_cube()
        _gui_formal_setup_viewport("pre-close")
        _gui_formal_hold(
            float(_os_gui_formal.environ.get("GUI_HOLD_S", "15")),
            tag="post-run hold (15s)",
        )
    except Exception as _e_hold:
        print(f"[gui_formal_exec] post-run hold error: {_e_hold}", flush=True)
    return _gui_formal_orig_close(*_a, **_k)


simulation_app.update = _gui_formal_update  # type: ignore[method-assign]
simulation_app.close = _gui_formal_close  # type: ignore[method-assign]

# Boot: map window + lights only (do NOT hold 10s on empty stage).
_gui_formal_ensure_lights()
_gui_formal_setup_viewport("boot")
for _ in range(8):
    _gui_formal_orig_update()
print(
    "[gui_formal_exec] boot painted; 10s pre-run wait deferred until scene exists; "
    "15s post-run hold on close (GUI_PREVIEW_S / GUI_HOLD_S)",
    flush=True,
)
# --- end inject ---
'''

_SIMAPP_TRUE = re.compile(
    r"""SimulationApp\s*\(\s*\{\s*["']headless["']\s*:\s*True\s*\}\s*\)"""
)
# hide_ui=False is required when kit would otherwise hide chrome; headless False alone
# was not enough for a *usable* observation path on formal runners.
_SIMAPP_FALSE = 'SimulationApp({"headless": False, "hide_ui": False})'


def transform_source(src: str, source_path: pathlib.Path) -> str:
    """Force GUI window + fixed dt + viewport-updating render flags + hold-open."""
    n_app = len(_SIMAPP_TRUE.findall(src))
    if n_app == 0:
        print(
            f"[gui_formal_exec] WARNING: no SimulationApp({{headless: True}}) in "
            f"{source_path.name}; only render/lab flips (if any).",
            flush=True,
        )
        transformed = src
    else:
        def _repl_once(m: re.Match[str]) -> str:
            return _SIMAPP_FALSE + "\n" + _GUI_BOOT_SNIPPET

        transformed, n = _SIMAPP_TRUE.subn(_repl_once, src, count=1)
        if n != 1:
            raise SystemExit(
                f"[gui_formal_exec] expected one SimulationApp headless rewrite, got n={n}"
            )
        transformed = _SIMAPP_TRUE.sub(_SIMAPP_FALSE, transformed)

    n_render = transformed.count("render=False")
    transformed = transformed.replace("render=False", "render=True")

    n_lab = transformed.count("parser.set_defaults(headless=True)")
    transformed = transformed.replace(
        "parser.set_defaults(headless=True)",
        "parser.set_defaults(headless=False)",
    )
    print(
        f"[gui_formal_exec] source={source_path} "
        f"simapp_headless_True_hits={n_app} "
        f"render_False→True={n_render} "
        f"lab_set_defaults_headless_flip={n_lab}",
        flush=True,
    )
    banner = (
        f"# AUTO-GENERATED by scripts/gui_formal_exec.py from {source_path}\n"
        f"# DO NOT EDIT; regenerate by re-running gui_formal_exec.\n"
        f"# Original formal headless script is unchanged.\n\n"
    )
    return banner + transformed


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("Usage: gui_formal_exec.py <formal_script.py> [script args...]")
        return 0 if argv and argv[0] in ("-h", "--help") else 2

    target = pathlib.Path(argv[0])
    if not target.is_file():
        alt = REPO / target
        if alt.is_file():
            target = alt
        else:
            raise SystemExit(f"[gui_formal_exec] script not found: {argv[0]}")

    target = target.resolve()
    src = target.read_text(encoding="utf-8")
    out_src = transform_source(src, target)

    CACHE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"{target}:{out_src}".encode("utf-8")).hexdigest()[:12]
    out_path = CACHE / f"{target.stem}_gui_{digest}.py"
    out_path.write_text(out_src, encoding="utf-8")
    print(f"[gui_formal_exec] wrote {out_path}", flush=True)
    print(
        f"[gui_formal_exec] GUI_PREVIEW_S={__import__('os').environ.get('GUI_PREVIEW_S', '10')} "
        f"GUI_HOLD_S={__import__('os').environ.get('GUI_HOLD_S', '15')}",
        flush=True,
    )

    rest = argv[1:]
    scripts_dir = str(REPO / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    lab_dir = str(REPO / "lab")
    if lab_dir not in sys.path:
        sys.path.insert(0, lab_dir)

    sys.argv = [str(out_path), *rest]
    code = compile(out_src, str(out_path), "exec")
    glb = {
        "__name__": "__main__",
        "__file__": str(target),
        "__package__": None,
        "__builtins__": __builtins__,
    }
    exec(code, glb)  # noqa: S102
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
