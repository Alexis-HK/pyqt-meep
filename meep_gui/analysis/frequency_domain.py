from __future__ import annotations

import copy
import os
import shutil

from ..model import ProjectState
from .images import (
    save_field_array_csv,
    save_field_overlay_image,
    save_plot2d_field_image,
)
from .types import ArtifactResult, CancelFn, LogFn, RunResult
from .workspace import create_run_output_dir


def _eval_positive_int(expr: str, values: dict[str, float], label: str, *, deps) -> int:
    value = deps._eval_required(expr, values, label)
    rounded = int(round(value))
    if abs(value - rounded) > 1e-9:
        raise ValueError(f"{label} must be an integer.")
    if rounded <= 0:
        raise ValueError(f"{label} must be > 0.")
    return rounded


def run_frequency_domain_solver_impl(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    *,
    deps,
) -> RunResult:
    state = copy.deepcopy(state)
    cfg = state.analysis.frequency_domain_solver
    deps._requires_continuous_sources(state, "frequency_domain_solver")

    values, results = deps.evaluate_parameters(state.parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")

    tolerance = deps._eval_required(cfg.tolerance, values, "tolerance")
    if tolerance <= 0:
        raise ValueError("tolerance must be > 0.")
    max_iters = _eval_positive_int(cfg.max_iters, values, "max_iters", deps=deps)
    bicgstab_l = _eval_positive_int(cfg.bicgstab_l, values, "bicgstab_l", deps=deps)

    if not state.sources:
        log("Warning: no sources are configured; frequency-domain solve may produce a zero field.")

    params = deps._build_sim_params(state)
    sim = deps.build_sim(params, log, force_complex_fields=True)
    mp = deps._import_meep()

    component = getattr(mp, cfg.component, None)
    if component is None:
        raise ValueError(f"Unsupported field component: {cfg.component}")
    if not hasattr(mp, "Dielectric"):
        raise ValueError("Meep dielectric component is unavailable. Check your Meep installation.")
    if not hasattr(sim, "init_sim"):
        raise RuntimeError("Meep Simulation.init_sim() is unavailable.")
    if not hasattr(sim, "solve_cw"):
        raise RuntimeError("Meep Simulation.solve_cw() is unavailable.")
    if not hasattr(sim, "get_array"):
        raise RuntimeError("Meep Simulation.get_array() is unavailable.")

    output_dir = create_run_output_dir("meep_gui_frequency_domain_")
    output_name = cfg.output_name.strip() or "frequency_domain_field.png"
    output_path = os.path.join(output_dir, output_name)
    csv_name = f"{os.path.splitext(output_name)[0] or 'frequency_domain_field'}.csv"
    csv_path = os.path.join(output_dir, csv_name)

    if cancel_requested():
        shutil.rmtree(output_dir, ignore_errors=True)
        return deps._run_canceled()

    log("Initializing frequency-domain simulation...")
    sim.init_sim()

    if cancel_requested():
        shutil.rmtree(output_dir, ignore_errors=True)
        return deps._run_canceled()

    log("Running frequency-domain solver...")
    sim.solve_cw(tolerance, max_iters, bicgstab_l)

    if cancel_requested():
        shutil.rmtree(output_dir, ignore_errors=True)
        return deps._run_canceled()

    volume_center = mp.Vector3()
    volume_size = mp.Vector3(params.cell_x, params.cell_y, 0)
    epsilon = sim.get_array(
        center=volume_center,
        size=volume_size,
        component=mp.Dielectric,
    )
    try:
        field = sim.get_array(
            center=volume_center,
            size=volume_size,
            component=component,
            cmplx=True,
        )
    except TypeError:
        field = sim.get_array(
            center=volume_center,
            size=volume_size,
            component=component,
        )

    save_field_array_csv(csv_path, field)
    title = f"Frequency-Domain {cfg.component} (real)"
    if hasattr(sim, "plot2D"):
        save_plot2d_field_image(output_path, sim, component, title)
    else:
        save_field_overlay_image(output_path, field, epsilon, title)
    log("Frequency-domain field image and CSV are ready. Use Export in the Output window to save them.")

    common_meta = {
        "export_dir": cfg.output_dir.strip(),
        "component": cfg.component,
        "field_part": "real",
    }
    return RunResult(
        status="completed",
        message="Frequency-domain solver completed.",
        artifacts=[
            ArtifactResult(
                kind="frequency_domain_field_png",
                label=output_name,
                path=output_path,
                meta={
                    **common_meta,
                    "export_name": output_name,
                },
            ),
            ArtifactResult(
                kind="frequency_domain_field_csv",
                label=csv_name,
                path=csv_path,
                meta={
                    **common_meta,
                    "export_name": csv_name,
                },
            ),
        ],
        plots=[],
    )
