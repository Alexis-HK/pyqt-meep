from __future__ import annotations

import copy
import os
import shutil

from ..model import ProjectState
from .types import ArtifactResult, CancelFn, LogFn, RunResult
from .workspace import create_run_output_dir


def run_harminv_impl(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    *,
    deps,
) -> RunResult:
    if deps.run_sim is None:
        raise RuntimeError("Meep runner is not available")

    state = copy.deepcopy(state)
    cfg = state.analysis.harminv
    deps._requires_gaussian_sources(state, "harminv")

    values, results = deps.evaluate_parameters(state.parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")

    until_after_sources = deps._eval_required(cfg.until_after_sources, values, "until_after_sources")
    interval = deps._eval_required(cfg.animation_interval, values, "animation_interval")
    fps = int(deps._eval_required(cfg.animation_fps, values, "animation_fps"))

    output_dir = cfg.output_dir.strip()
    output_name = cfg.output_name.strip() or "harminv_animation.mp4"
    harminv_log_path = cfg.harminv_log_path.strip() or "harminv.txt"

    temp_dir = create_run_output_dir("meep_gui_harminv_")
    output_path = os.path.join(temp_dir, output_name)
    temp_harminv_txt = os.path.join(temp_dir, "harminv.txt")

    params = deps._build_sim_params(state)
    flux_specs = deps._build_flux_specs(state, values)

    mp = deps._import_meep()

    def _component(name: str):
        return getattr(mp, name, getattr(mp, "Ez", None))

    anim_comp = _component(cfg.component)
    if anim_comp is None:
        raise ValueError("Meep field components are unavailable. Check your Meep installation.")
    animate = mp.Animate2D(fields=anim_comp, realtime=False)

    hspec = deps.HarminvSpec(
        component=cfg.component,
        center_x=deps._eval_required(cfg.point_x, values, "point_x"),
        center_y=deps._eval_required(cfg.point_y, values, "point_y"),
        frequency=deps._eval_required(cfg.fcen, values, "fcen"),
        bandwidth=deps._eval_required(cfg.df, values, "df"),
    )

    harminv_lines: list[str] = []

    def handle_harminv(hobj) -> None:
        harminv_lines.extend(deps._harminv_lines(hobj))

    if cancel_requested():
        shutil.rmtree(temp_dir, ignore_errors=True)
        return deps._run_canceled()

    log("Running harminv analysis...")
    sim_result = deps.run_sim(
        params,
        log,
        until_after_sources=until_after_sources,
        step_funcs=[mp.at_every(interval, animate)],
        harminv_spec=hspec,
        harminv_cb=handle_harminv,
        stop_flag=cancel_requested,
        flux_monitors=flux_specs,
    )

    if sim_result.canceled or cancel_requested():
        shutil.rmtree(temp_dir, ignore_errors=True)
        return deps._run_canceled()

    animate.to_mp4(fps, output_path)
    plots = deps._export_flux_plots(sim_result.flux_results, temp_dir, log)

    with open(temp_harminv_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(harminv_lines) + ("\n" if harminv_lines else ""))

    log("Harminv results ready. Use Export in the Output window to save files.")

    artifacts = [
        ArtifactResult(
            kind="animation_mp4",
            label=output_name,
            path=output_path,
            meta={"export_dir": output_dir, "export_name": output_name},
        ),
        ArtifactResult(
            kind="harminv_text",
            label=os.path.basename(harminv_log_path),
            path=temp_harminv_txt,
            meta={"export_path": harminv_log_path},
        ),
    ]
    return RunResult(
        status="completed",
        message="Harminv analysis completed.",
        artifacts=artifacts,
        plots=plots,
        meta={"harminv_line_count": str(len(harminv_lines))},
    )
