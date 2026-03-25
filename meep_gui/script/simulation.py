from __future__ import annotations

from ..validation import parse_complex_literal
from .common import line


def emit_geometry(lines: list[str], var_name: str, geometries) -> None:
    line(lines, f"{var_name} = []")
    for idx, geo in enumerate(geometries, start=1):
        name = f"{var_name}_shape_{idx}"
        material = geo.material or "None"
        if geo.kind == "block":
            size_x = geo.props.get("size_x", "1")
            size_y = geo.props.get("size_y", "1")
            center_x = geo.props.get("center_x", "0")
            center_y = geo.props.get("center_y", "0")
            line(
                lines,
                f"{name} = mp.Block(size=mp.Vector3({size_x}, {size_y}, mp.inf), "
                f"center=mp.Vector3({center_x}, {center_y}), material=materials.get('{material}'))",
            )
            line(lines, f"{var_name}.append({name})")
        elif geo.kind == "circle":
            radius = geo.props.get("radius", "1")
            center_x = geo.props.get("center_x", "0")
            center_y = geo.props.get("center_y", "0")
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
        fcen = src.props.get("fcen", "0.15")
        df = src.props.get("df", "0.1")
        size_x = src.props.get("size_x", "0")
        size_y = src.props.get("size_y", "0")
        center_x = src.props.get("center_x", "0")
        center_y = src.props.get("center_y", "0")
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
        line(lines, f"{var_name}.append(mp.PML(thickness={domain.pml_width}, direction=mp.X))")
    if domain.pml_mode in {"y", "both"}:
        line(lines, f"{var_name}.append(mp.PML(thickness={domain.pml_width}, direction=mp.Y))")


def emit_symmetries(lines: list[str], var_name: str, domain) -> None:
    line(lines, f"{var_name} = []")
    if not domain.symmetry_enabled:
        return
    for symmetry in domain.symmetries:
        kind = symmetry.kind.lower()
        ctor = {"mirror": "Mirror", "rotate2": "Rotate2", "rotate4": "Rotate4"}.get(kind)
        if ctor:
            phase = symmetry.phase.strip()
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
            f"{handles_var}['{mon.name}'] = {sim_var}.add_flux({mon.fcen}, {mon.df}, int({mon.nfreq}), "
            f"mp.FluxRegion(center=mp.Vector3({mon.center_x}, {mon.center_y}, 0), "
            f"size=mp.Vector3({mon.size_x}, {mon.size_y}, 0)))",
        )
