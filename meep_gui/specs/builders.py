from __future__ import annotations

from ..model import ProjectState
from ..specs.simulation import FluxMonitorSpec, Shape, SimParams, SourceSpec, SymmetrySpec
from ..validation import (
    evaluate_numeric_expression,
    evaluate_parameters,
    parse_complex_literal,
)


def _eval_required(expr: str, values: dict[str, float], label: str) -> float:
    try:
        return evaluate_numeric_expression(expr, values)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _build_symmetry_specs(state: ProjectState) -> list[SymmetrySpec]:
    if not state.domain.symmetry_enabled:
        return []

    specs: list[SymmetrySpec] = []
    for symmetry in state.domain.symmetries:
        try:
            phase = parse_complex_literal(symmetry.phase)
        except ValueError as exc:
            raise ValueError(f"symmetry '{symmetry.name}' phase: {exc}") from exc
        specs.append(
            SymmetrySpec(
                kind=symmetry.kind,
                direction=symmetry.direction,
                phase=phase,
            )
        )
    return specs


def build_sim_params(state: ProjectState) -> SimParams:
    values, results = evaluate_parameters(state.parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")

    materials: dict[str, float] = {}
    for mat in state.materials:
        if not mat.name:
            continue
        idx = _eval_required(mat.index_expr, values, f"material '{mat.name}'")
        materials[mat.name] = idx

    shapes = []
    for geo in state.geometries:
        if geo.material not in materials:
            raise ValueError(f"Geometry '{geo.name}': unknown material '{geo.material}'")
        eps = materials[geo.material] ** 2
        center_x = _eval_required(geo.props.get("center_x", "0"), values, "center_x")
        center_y = _eval_required(geo.props.get("center_y", "0"), values, "center_y")
        if geo.kind == "block":
            shapes.append(
                Shape(
                    kind="rect",
                    center_x=center_x,
                    center_y=center_y,
                    size_x=_eval_required(geo.props.get("size_x", "0"), values, "size_x"),
                    size_y=_eval_required(geo.props.get("size_y", "0"), values, "size_y"),
                    eps=eps,
                )
            )
        elif geo.kind == "circle":
            shapes.append(
                Shape(
                    kind="circle",
                    center_x=center_x,
                    center_y=center_y,
                    radius=_eval_required(geo.props.get("radius", "0"), values, "radius"),
                    eps=eps,
                )
            )

    sources = []
    for src in state.sources:
        sources.append(
            SourceSpec(
                kind=src.kind,
                center_x=_eval_required(src.props.get("center_x", "0"), values, "center_x"),
                center_y=_eval_required(src.props.get("center_y", "0"), values, "center_y"),
                width_x=_eval_required(src.props.get("size_x", "0"), values, "size_x"),
                width_y=_eval_required(src.props.get("size_y", "0"), values, "size_y"),
                frequency=_eval_required(src.props.get("fcen", "0.15"), values, "fcen"),
                bandwidth=(
                    _eval_required(src.props.get("df", "0.1"), values, "df")
                    if src.kind == "gaussian"
                    else 0.0
                ),
                component=src.component,
            )
        )

    return SimParams(
        cell_x=_eval_required(state.domain.cell_x, values, "cell_x"),
        cell_y=_eval_required(state.domain.cell_y, values, "cell_y"),
        resolution=int(_eval_required(state.domain.resolution, values, "resolution")),
        pml=_eval_required(state.domain.pml_width, values, "pml_width"),
        pml_x=state.domain.pml_mode in {"x", "both"},
        pml_y=state.domain.pml_mode in {"y", "both"},
        symmetries=_build_symmetry_specs(state),
        shapes=shapes,
        sources=sources,
    )


def build_flux_specs(state: ProjectState, values: dict[str, float]) -> list[FluxMonitorSpec]:
    specs: list[FluxMonitorSpec] = []
    for monitor in state.flux_monitors:
        size_x = _eval_required(monitor.size_x, values, f"{monitor.name}.size_x")
        size_y = _eval_required(monitor.size_y, values, f"{monitor.name}.size_y")
        if abs(size_x) > 1e-12 and abs(size_y) > 1e-12:
            raise ValueError(
                f"Flux monitor '{monitor.name}' must be a line in 2D. "
                "Set one of size_x or size_y to 0."
            )
        if abs(size_x) <= 1e-12 and abs(size_y) <= 1e-12:
            raise ValueError(
                f"Flux monitor '{monitor.name}' has zero area and undefined normal direction. "
                "Set exactly one of size_x or size_y to a non-zero value."
            )
        specs.append(
            FluxMonitorSpec(
                name=monitor.name,
                center_x=_eval_required(monitor.center_x, values, f"{monitor.name}.center_x"),
                center_y=_eval_required(monitor.center_y, values, f"{monitor.name}.center_y"),
                size_x=size_x,
                size_y=size_y,
                fcen=_eval_required(monitor.fcen, values, f"{monitor.name}.fcen"),
                df=_eval_required(monitor.df, values, f"{monitor.name}.df"),
                nfreq=max(1, int(_eval_required(monitor.nfreq, values, f"{monitor.name}.nfreq"))),
            )
        )
    return specs
