from __future__ import annotations

from ..specs.simulation import FluxMonitorSpec, Shape, SimParams, SourceSpec, SymmetrySpec
from ..validation import evaluate_numeric_expression, parse_complex_literal
from .types import CompilationContext, SceneSpec


def eval_required(expr: str, context: CompilationContext, label: str) -> float:
    try:
        return evaluate_numeric_expression(expr, context.parameter_values)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def scene_to_sim_params(scene: SceneSpec, context: CompilationContext) -> SimParams:
    media_index: dict[str, float] = {}
    for medium in scene.media:
        if medium.kind != "constant":
            raise ValueError(f"Unsupported medium kind: {medium.kind}")
        media_index[medium.name] = eval_required(
            medium.constant_index_expr,
            context,
            f"material '{medium.name}'",
        )

    shapes: list[Shape] = []
    for obj in scene.objects:
        if obj.spatial_material.kind != "uniform":
            raise ValueError(f"Geometry '{obj.name}': unsupported spatial material kind.")
        medium_name = obj.spatial_material.medium_name
        if medium_name not in media_index:
            raise ValueError(f"Geometry '{obj.name}': unknown material '{medium_name}'")
        eps = media_index[medium_name] ** 2
        center_x = eval_required(obj.transform.center_x_expr, context, "center_x")
        center_y = eval_required(obj.transform.center_y_expr, context, "center_y")
        if obj.geometry.kind == "block":
            if obj.geometry.block is None:
                raise ValueError(f"Geometry '{obj.name}': missing block parameters.")
            shapes.append(
                Shape(
                    kind="rect",
                    center_x=center_x,
                    center_y=center_y,
                    size_x=eval_required(obj.geometry.block.size_x_expr, context, "size_x"),
                    size_y=eval_required(obj.geometry.block.size_y_expr, context, "size_y"),
                    eps=eps,
                )
            )
        elif obj.geometry.kind == "circle":
            if obj.geometry.circle is None:
                raise ValueError(f"Geometry '{obj.name}': missing circle parameters.")
            shapes.append(
                Shape(
                    kind="circle",
                    center_x=center_x,
                    center_y=center_y,
                    radius=eval_required(obj.geometry.circle.radius_expr, context, "radius"),
                    eps=eps,
                )
            )

    sources = [
        SourceSpec(
            kind=item.kind,
            center_x=eval_required(item.center_x_expr, context, "center_x"),
            center_y=eval_required(item.center_y_expr, context, "center_y"),
            width_x=eval_required(item.size_x_expr, context, "size_x"),
            width_y=eval_required(item.size_y_expr, context, "size_y"),
            frequency=eval_required(item.frequency_expr, context, "fcen"),
            bandwidth=(
                eval_required(item.bandwidth_expr, context, "df")
                if item.kind == "gaussian"
                else 0.0
            ),
            component=item.component,
        )
        for item in scene.sources
    ]

    symmetries: list[SymmetrySpec] = []
    for item in scene.symmetries:
        try:
            phase = parse_complex_literal(item.phase_expr)
        except ValueError as exc:
            raise ValueError(f"symmetry '{item.name}' phase: {exc}") from exc
        symmetries.append(
            SymmetrySpec(
                kind=item.kind,
                direction=item.direction,
                phase=phase,
            )
        )

    return SimParams(
        cell_x=eval_required(scene.domain.cell_x_expr, context, "cell_x"),
        cell_y=eval_required(scene.domain.cell_y_expr, context, "cell_y"),
        resolution=int(eval_required(scene.domain.resolution_expr, context, "resolution")),
        pml=eval_required(scene.domain.pml_width_expr, context, "pml_width"),
        pml_x=scene.domain.pml_mode in {"x", "both"},
        pml_y=scene.domain.pml_mode in {"y", "both"},
        symmetries=symmetries,
        shapes=shapes,
        sources=sources,
    )


def scene_to_flux_specs(scene: SceneSpec, context: CompilationContext) -> list[FluxMonitorSpec]:
    specs: list[FluxMonitorSpec] = []
    for item in scene.monitors:
        size_x = eval_required(item.size_x_expr, context, f"{item.name}.size_x")
        size_y = eval_required(item.size_y_expr, context, f"{item.name}.size_y")
        if abs(size_x) > 1e-12 and abs(size_y) > 1e-12:
            raise ValueError(
                f"Flux monitor '{item.name}' must be a line in 2D. "
                "Set one of size_x or size_y to 0."
            )
        if abs(size_x) <= 1e-12 and abs(size_y) <= 1e-12:
            raise ValueError(
                f"Flux monitor '{item.name}' has zero area and undefined normal direction. "
                "Set exactly one of size_x or size_y to a non-zero value."
            )
        specs.append(
            FluxMonitorSpec(
                name=item.name,
                center_x=eval_required(item.center_x_expr, context, f"{item.name}.center_x"),
                center_y=eval_required(item.center_y_expr, context, f"{item.name}.center_y"),
                size_x=size_x,
                size_y=size_y,
                fcen=eval_required(item.fcen_expr, context, f"{item.name}.fcen"),
                df=eval_required(item.df_expr, context, f"{item.name}.df"),
                nfreq=max(1, int(eval_required(item.nfreq_expr, context, f"{item.name}.nfreq"))),
            )
        )
    return specs
