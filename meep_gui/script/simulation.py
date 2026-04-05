from __future__ import annotations

from ..primitives import geometry_kind, material_kind, monitor_kind, source_kind
from ..validation import parse_complex_literal
from .common import line


def emit_parameters(lines: list[str], scene) -> None:
    if not scene.parameters:
        return
    line(lines, "# Parameters")
    for param in scene.parameters:
        if param.name and param.expr:
            line(lines, f"{param.name} = {param.expr}")
    line(lines)


def emit_materials(lines: list[str], scene) -> None:
    if scene.media:
        line(lines, "# Materials")
        line(lines, "materials = {}")
        for medium in scene.media:
            for statement in material_kind(medium.kind).emit_script_medium(medium):
                line(lines, statement)
        line(lines)
    else:
        line(lines, "materials = {}")
        line(lines)


def emit_geometry(lines: list[str], var_name: str, objects) -> None:
    line(lines, f"{var_name} = []")
    for idx, obj in enumerate(objects, start=1):
        for statement in geometry_kind(obj.geometry.kind).emit_script_object(var_name, idx, obj):
            line(lines, statement)


def emit_sources(lines: list[str], var_name: str, sources) -> None:
    line(lines, f"{var_name} = []")
    for idx, src in enumerate(sources, start=1):
        for statement in source_kind(src.kind).emit_script_source(var_name, idx, src):
            line(lines, statement)


def emit_boundary_layers(lines: list[str], var_name: str, domain) -> None:
    line(lines, f"{var_name} = []")
    if domain.pml_mode in {"x", "both"}:
        line(lines, f"{var_name}.append(mp.PML(thickness={domain.pml_width_expr}, direction=mp.X))")
    if domain.pml_mode in {"y", "both"}:
        line(lines, f"{var_name}.append(mp.PML(thickness={domain.pml_width_expr}, direction=mp.Y))")


def emit_symmetries(lines: list[str], var_name: str, symmetries) -> None:
    line(lines, f"{var_name} = []")
    for symmetry in symmetries:
        kind = symmetry.kind.lower()
        ctor = {"mirror": "Mirror", "rotate2": "Rotate2", "rotate4": "Rotate4"}.get(kind)
        if ctor:
            phase = symmetry.phase_expr.strip()
            try:
                parse_complex_literal(phase)
            except ValueError as exc:
                raise ValueError(f"symmetry '{symmetry.name}' phase: {exc}") from exc
            line(
                lines,
                f"{var_name}.append(mp.{ctor}(mp.{symmetry.direction.upper()}, "
                f"phase={phase}))",
            )


def emit_flux_handles(lines: list[str], handles_var: str, sim_var: str, monitors) -> None:
    line(lines, f"{handles_var} = {{}}")
    for mon in monitors:
        line(
            lines,
            f"{handles_var}['{mon.name}'] = {monitor_kind(mon.kind).script_add_flux_expr(sim_var, mon)}",
        )
