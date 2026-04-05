from __future__ import annotations

import os

from ..model import ProjectState
from ..scene import compile_project_scene, compile_transmission_scenes
from .analyses import emit_field_animation, emit_flux_exports, emit_harminv
from .common import analysis_label, line
from .frequency_domain import emit_frequency_domain
from .meep_k_points import emit_meep_k_points
from .mpb import emit_mpb
from .simulation import (
    emit_materials,
    emit_parameters,
    emit_boundary_layers,
    emit_flux_handles,
    emit_geometry,
    emit_sources,
    emit_symmetries,
)
from .transmission import emit_transmission


def _emit_header(lines: list[str], state: ProjectState) -> None:
    line(lines, "from math import sqrt, exp, sin, cos, tan, log, log10")
    line(lines, "import csv")
    line(lines, "import os")
    line(lines, "import meep as mp")
    if state.analysis.kind == "mpb_modesolver":
        line(lines, "from meep import mpb")
    line(lines)
    line(lines, "script_dir = os.path.dirname(os.path.abspath(__file__))")
    line(lines)


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


def _emit_analysis(lines: list[str], state: ProjectState, scene, reference_scene) -> None:
    kind = state.analysis.kind
    if kind == "field_animation":
        emit_field_animation(lines, state.analysis.field_animation)
    elif kind == "harminv":
        emit_harminv(lines, state.analysis.harminv)
    elif kind == "transmission_spectrum":
        emit_transmission(lines, state, scene, reference_scene)
    elif kind == "frequency_domain_solver":
        emit_frequency_domain(lines, state)
    elif kind == "meep_k_points":
        emit_meep_k_points(lines, state)
    elif kind == "mpb_modesolver":
        emit_mpb(lines, state)


def generate_script(state: ProjectState) -> str:
    if state.analysis.kind == "transmission_spectrum":
        bundle = compile_transmission_scenes(state)
        scene = bundle.scattering.scene
        reference_scene = bundle.reference.scene
    else:
        compiled = compile_project_scene(state)
        scene = compiled.scene
        reference_scene = None

    lines: list[str] = []
    _emit_header(lines, state)
    emit_parameters(lines, scene)
    emit_materials(lines, scene)
    _emit_geometry_and_sources(lines, scene)
    _emit_fdtd_setup(
        lines,
        scene,
        enabled=state.analysis.kind not in {"mpb_modesolver", "transmission_spectrum"},
        force_complex_fields=state.analysis.kind == "frequency_domain_solver",
        include_flux_monitors=state.analysis.kind
        not in {"frequency_domain_solver", "meep_k_points"},
    )
    _emit_analysis(lines, state, scene, reference_scene)

    if scene.monitors and state.analysis.kind not in {
        "mpb_modesolver",
        "transmission_spectrum",
        "frequency_domain_solver",
        "meep_k_points",
    }:
        emit_flux_exports(lines)

    line(lines)
    line(lines, f"# Analysis type: {analysis_label(state.analysis.kind)}")
    if state.sweep.enabled and state.sweep.params:
        line(lines, "# Sweep configured in GUI; run manually in Python if needed.")
    return "\n".join(lines)
