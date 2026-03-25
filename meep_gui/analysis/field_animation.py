from __future__ import annotations

import copy
import os
import shutil
import tempfile

from ..model import ProjectState
from .types import ArtifactResult, CancelFn, LogFn, RunResult


def run_field_animation_impl(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    *,
    deps,
) -> RunResult:
    if deps.run_sim is None:
        raise RuntimeError("Meep runner is not available")

    state = copy.deepcopy(state)
    cfg = state.analysis.field_animation

    values, results = deps.evaluate_parameters(state.parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")

    duration = deps._eval_required(cfg.duration, values, "duration")
    interval = deps._eval_required(cfg.interval, values, "interval")
    fps = int(deps._eval_required(cfg.fps, values, "fps"))

    output_dir = cfg.output_dir.strip()
    output_name = cfg.output_name.strip() or "animation.mp4"

    temp_dir = tempfile.mkdtemp(prefix="meep_gui_field_")
    output_path = os.path.join(temp_dir, output_name)

    params = deps._build_sim_params(state)
    flux_specs = deps._build_flux_specs(state, values)

    mp = deps._import_meep()

    def _component(name: str):
        return getattr(mp, name, getattr(mp, "Ez", None))

    anim_comp = _component(cfg.component)
    if anim_comp is None:
        raise ValueError("Meep field components are unavailable. Check your Meep installation.")

    if cancel_requested():
        shutil.rmtree(temp_dir, ignore_errors=True)
        return deps._run_canceled()

    animate = mp.Animate2D(fields=anim_comp, realtime=False)

    log("Running field animation...")
    sim_result = deps.run_sim(
        params,
        log,
        until_time=duration,
        step_funcs=[mp.at_every(interval, animate)],
        stop_flag=cancel_requested,
        flux_monitors=flux_specs,
    )

    if sim_result.canceled or cancel_requested():
        shutil.rmtree(temp_dir, ignore_errors=True)
        return deps._run_canceled()

    animate.to_mp4(fps, output_path)
    plots = deps._export_flux_plots(sim_result.flux_results, temp_dir, log)
    log("Animation ready. Use Export in the Output window to save it.")

    artifact = ArtifactResult(
        kind="animation_mp4",
        label=output_name,
        path=output_path,
        meta={"export_dir": output_dir, "export_name": output_name},
    )
    return RunResult(
        status="completed",
        message="Field animation completed.",
        artifacts=[artifact],
        plots=plots,
    )
