from __future__ import annotations

from ..analysis.preparation import (
    emit_validation_warnings,
    prepare_script_analysis,
    raise_for_validation_errors,
)
from ..analysis.types import LogFn, ScriptPlan
from ..model import ProjectState
from .analyses import emit_flux_exports
from .common import line
from .simulation import (
    emit_geometry,
    emit_materials,
    emit_parameters,
    emit_sources,
    emit_symmetries,
)


def _emit_header(lines: list[str], plan: ScriptPlan) -> None:
    line(lines, "from math import sqrt, exp, sin, cos, tan, log, log10")
    line(lines, "import csv")
    line(lines, "import os")
    line(lines, "import meep as mp")
    if plan.backend == "mpb":
        line(lines, "from meep import mpb")
    line(lines)
    line(lines, "script_dir = os.path.dirname(os.path.abspath(__file__))")
    line(lines)


def _primary_scene(plan: ScriptPlan):
    if plan.transmission is not None:
        return plan.transmission.scattering.scene
    if plan.scene is not None:
        return plan.scene.scene
    raise ValueError("Script plan does not include a compiled scene.")


def _emit_geometry_and_sources(lines: list[str], scene) -> None:
    line(lines, "# Geometry")
    if scene.objects:
        emit_geometry(lines, "geometry", scene.objects)
        line(lines)
    else:
        line(lines, "geometry = []")
        line(lines)

    line(lines, "# Sources")
    if scene.sources:
        emit_sources(lines, "sources", scene.sources)
        line(lines)
    else:
        line(lines, "sources = []")
        line(lines)


def _emit_fdtd_setup(
    lines: list[str],
    scene,
    *,
    enabled: bool,
    force_complex_fields: bool = False,
    include_flux_monitors: bool = True,
) -> None:
    if not enabled:
        return

    line(lines, "# Simulation")
    line(lines, "boundary_layers = []")
    pml = scene.domain.pml_width_expr
    if scene.domain.pml_mode in {"x", "both"}:
        line(lines, f"boundary_layers.append(mp.PML(thickness={pml}, direction=mp.X))")
    if scene.domain.pml_mode in {"y", "both"}:
        line(lines, f"boundary_layers.append(mp.PML(thickness={pml}, direction=mp.Y))")
    emit_symmetries(lines, "symmetries", scene.symmetries)
    force_complex_arg = ", force_complex_fields=True" if force_complex_fields else ""
    line(
        lines,
        "sim = mp.Simulation("
        f"cell_size=mp.Vector3({scene.domain.cell_x_expr}, {scene.domain.cell_y_expr}, 0), "
        "boundary_layers=boundary_layers, geometry=geometry, sources=sources, "
        "symmetries=symmetries, "
        f"resolution={scene.domain.resolution_expr}{force_complex_arg})",
    )
    line(lines)

    if include_flux_monitors and scene.monitors:
        line(lines, "# Flux monitors")
        line(lines, "flux_monitors = []")
        for mon in scene.monitors:
            line(
                lines,
                "flux_monitors.append(("
                f"'{mon.name}', "
                f"sim.add_flux({mon.fcen_expr}, {mon.df_expr}, int({mon.nfreq_expr}), "
                f"mp.FluxRegion(center=mp.Vector3({mon.center_x_expr}, {mon.center_y_expr}, 0), "
                f"size=mp.Vector3({mon.size_x_expr}, {mon.size_y_expr}, 0)))"
                "))",
            )
        line(lines)


def generate_script(state: ProjectState, log: LogFn | None = None) -> str:
    prepared = prepare_script_analysis(state)
    if log is not None:
        emit_validation_warnings(prepared.validation, log)
    raise_for_validation_errors(prepared.validation)

    scene = _primary_scene(prepared.plan)
    lines: list[str] = []
    _emit_header(lines, prepared.plan)
    emit_parameters(lines, scene)
    emit_materials(lines, scene)
    _emit_geometry_and_sources(lines, scene)
    _emit_fdtd_setup(
        lines,
        scene,
        enabled=prepared.recipe.uses_fdtd_script_setup(prepared.plan),
        force_complex_fields=prepared.recipe.script_force_complex_fields(prepared.plan),
        include_flux_monitors=prepared.recipe.script_include_flux_monitors(prepared.plan),
    )
    prepared.recipe.emit_script(state, prepared.plan, lines)

    if scene.monitors and prepared.recipe.script_include_flux_exports(prepared.plan):
        emit_flux_exports(lines)

    line(lines)
    line(lines, f"# Analysis type: {prepared.recipe.display_name}")
    if state.sweep.enabled and state.sweep.params:
        line(lines, "# Sweep configured in GUI; run manually in Python if needed.")
    return "\n".join(lines)
