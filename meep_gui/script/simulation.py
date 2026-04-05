from __future__ import annotations

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
            if medium.kind != "constant":
                raise ValueError(f"Unsupported medium kind for script export: {medium.kind}")
            if medium.name and medium.constant_index_expr:
                line(lines, f"{medium.name} = mp.Medium(index={medium.constant_index_expr})")
                line(lines, f"materials['{medium.name}'] = {medium.name}")
        line(lines)
    else:
        line(lines, "materials = {}")
        line(lines)


def emit_geometry(lines: list[str], var_name: str, objects) -> None:
    line(lines, f"{var_name} = []")
    for idx, obj in enumerate(objects, start=1):
        name = f"{var_name}_shape_{idx}"
        material = obj.spatial_material.medium_name or "None"
        center_x = obj.transform.center_x_expr
        center_y = obj.transform.center_y_expr
        if obj.geometry.kind == "block":
            if obj.geometry.block is None:
                raise ValueError(f"Geometry '{obj.name}': missing block parameters.")
            size_x = obj.geometry.block.size_x_expr
            size_y = obj.geometry.block.size_y_expr
            line(
                lines,
                f"{name} = mp.Block(size=mp.Vector3({size_x}, {size_y}, mp.inf), "
                f"center=mp.Vector3({center_x}, {center_y}), material=materials.get('{material}'))",
            )
            line(lines, f"{var_name}.append({name})")
        elif obj.geometry.kind == "circle":
            if obj.geometry.circle is None:
                raise ValueError(f"Geometry '{obj.name}': missing circle parameters.")
            radius = obj.geometry.circle.radius_expr
            line(
                lines,
                f"{name} = mp.Cylinder(radius={radius}, height=mp.inf, "
                f"center=mp.Vector3({center_x}, {center_y}), material=materials.get('{material}'))",
            )
            line(lines, f"{var_name}.append({name})")


def emit_sources(lines: list[str], var_name: str, sources) -> None:
    line(lines, f"{var_name} = []")
    for idx, src in enumerate(sources, start=1):
        name = f"{var_name}_{idx}"
        fcen = src.frequency_expr
        df = src.bandwidth_expr
        size_x = src.size_x_expr
        size_y = src.size_y_expr
        center_x = src.center_x_expr
        center_y = src.center_y_expr
        src_init = (
            f"mp.GaussianSource(frequency={fcen}, fwidth={df})"
            if src.kind == "gaussian"
            else f"mp.ContinuousSource(frequency={fcen})"
        )
        line(
            lines,
            f"{name} = mp.Source({src_init}, component=mp.{src.component}, "
            f"center=mp.Vector3({center_x}, {center_y}), "
            f"size=mp.Vector3({size_x}, {size_y}, 0))",
        )
        line(lines, f"{var_name}.append({name})")


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
            f"{handles_var}['{mon.name}'] = {sim_var}.add_flux({mon.fcen_expr}, {mon.df_expr}, int({mon.nfreq_expr}), "
            f"mp.FluxRegion(center=mp.Vector3({mon.center_x_expr}, {mon.center_y_expr}, 0), "
            f"size=mp.Vector3({mon.size_x_expr}, {mon.size_y_expr}, 0)))",
        )
