from __future__ import annotations

import os

from ..model import ProjectState
from .analyses import emit_field_animation, emit_flux_exports, emit_harminv
from .common import analysis_label, line
from .frequency_domain import emit_frequency_domain
from .meep_k_points import emit_meep_k_points
from .mpb import emit_mpb
from .simulation import (
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


def _emit_parameters(lines: list[str], state: ProjectState) -> None:
    if not state.parameters:
        return
    line(lines, "# Parameters")
    for param in state.parameters:
        if param.name and param.expr:
            line(lines, f"{param.name} = {param.expr}")
    line(lines)


def _emit_materials(lines: list[str], state: ProjectState) -> None:
    if state.materials:
        line(lines, "# Materials")
        line(lines, "materials = {}")
        for mat in state.materials:
            if mat.name and mat.index_expr:
                line(lines, f"{mat.name} = mp.Medium(index={mat.index_expr})")
                line(lines, f"materials['{mat.name}'] = {mat.name}")
        line(lines)
    else:
        line(lines, "materials = {}")
        line(lines)


def _emit_geometry_and_sources(lines: list[str], state: ProjectState) -> None:
    line(lines, "# Geometry")
    if state.geometries:
        emit_geometry(lines, "geometry", state.geometries)
        line(lines)
    else:
        line(lines, "geometry = []")
        line(lines)

    line(lines, "# Sources")
    if state.sources:
        emit_sources(lines, "sources", state.sources)
        line(lines)
    else:
        line(lines, "sources = []")
        line(lines)


def _emit_fdtd_setup(
    lines: list[str],
    state: ProjectState,
    *,
    force_complex_fields: bool = False,
    include_flux_monitors: bool = True,
) -> None:
    if state.analysis.kind in {"mpb_modesolver", "transmission_spectrum"}:
        return

    line(lines, "# Simulation")
    line(lines, "boundary_layers = []")
    pml = state.domain.pml_width
    if state.domain.pml_mode in {"x", "both"}:
        line(lines, f"boundary_layers.append(mp.PML(thickness={pml}, direction=mp.X))")
    if state.domain.pml_mode in {"y", "both"}:
        line(lines, f"boundary_layers.append(mp.PML(thickness={pml}, direction=mp.Y))")
    emit_symmetries(lines, "symmetries", state.domain)
    force_complex_arg = ", force_complex_fields=True" if force_complex_fields else ""
    line(
        lines,
        "sim = mp.Simulation("
        f"cell_size=mp.Vector3({state.domain.cell_x}, {state.domain.cell_y}, 0), "
        "boundary_layers=boundary_layers, geometry=geometry, sources=sources, "
        "symmetries=symmetries, "
        f"resolution={state.domain.resolution}{force_complex_arg})",
    )
    line(lines)

    if include_flux_monitors and state.flux_monitors:
        line(lines, "# Flux monitors")
        line(lines, "flux_monitors = []")
        for mon in state.flux_monitors:
            line(
                lines,
                "flux_monitors.append(("
                f"'{mon.name}', "
                f"sim.add_flux({mon.fcen}, {mon.df}, int({mon.nfreq}), "
                f"mp.FluxRegion(center=mp.Vector3({mon.center_x}, {mon.center_y}, 0), "
                f"size=mp.Vector3({mon.size_x}, {mon.size_y}, 0)))"
                "))",
            )
        line(lines)


def _emit_analysis(lines: list[str], state: ProjectState) -> None:
    kind = state.analysis.kind
    if kind == "field_animation":
        emit_field_animation(lines, state.analysis.field_animation)
    elif kind == "harminv":
        emit_harminv(lines, state.analysis.harminv)
    elif kind == "transmission_spectrum":
        emit_transmission(lines, state)
    elif kind == "frequency_domain_solver":
        emit_frequency_domain(lines, state)
    elif kind == "meep_k_points":
        emit_meep_k_points(lines, state)
    elif kind == "mpb_modesolver":
        emit_mpb(lines, state)


def generate_script(state: ProjectState) -> str:
    lines: list[str] = []
    _emit_header(lines, state)
    _emit_parameters(lines, state)
    _emit_materials(lines, state)
    _emit_geometry_and_sources(lines, state)
    _emit_fdtd_setup(
        lines,
        state,
        force_complex_fields=state.analysis.kind == "frequency_domain_solver",
        include_flux_monitors=state.analysis.kind
        not in {"frequency_domain_solver", "meep_k_points"},
    )
    _emit_analysis(lines, state)

    if state.flux_monitors and state.analysis.kind not in {
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
