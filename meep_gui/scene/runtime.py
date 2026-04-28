from __future__ import annotations

from ..primitives import geometry_kind, material_kind, monitor_kind, source_kind
from ..specs.simulation import FluxMonitorSpec, Shape, SimParams, SourceSpec, SymmetrySpec
from ..validation import evaluate_numeric_expression, parse_complex_literal
from .types import CompilationContext, SceneSpec


def eval_required(expr: str, context: CompilationContext, label: str) -> float:
    try:
        return evaluate_numeric_expression(expr, context.parameter_values)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def scene_to_sim_params(scene: SceneSpec, context: CompilationContext) -> SimParams:
    eps_by_material: dict[str, float] = {}
    for medium in scene.media:
        index = material_kind(medium.kind).resolve_index(
            medium,
            context,
            eval_required,
        )
        eps_by_material[medium.name] = index**2

    shapes: list[Shape] = []
    for obj in scene.objects:
        if obj.spatial_material.kind != "uniform":
            raise ValueError(f"Geometry '{obj.name}': unsupported spatial material kind.")
        lowered = geometry_kind(obj.geometry.kind).to_shape(
            obj,
            eps_by_material,
            context,
            eval_required,
        )
        if isinstance(lowered, (list, tuple)):
            shapes.extend(lowered)
        else:
            shapes.append(lowered)

    sources: list[SourceSpec] = [
        source_kind(item.kind).to_runtime_source(item, context, eval_required)
        for item in scene.sources
        if item.enabled
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

    k_point = None
    if scene.domain.periodic_enabled:
        k_point = (
            eval_required(scene.domain.k_point_x_expr, context, "k_point_x"),
            eval_required(scene.domain.k_point_y_expr, context, "k_point_y"),
            eval_required(scene.domain.k_point_z_expr, context, "k_point_z"),
        )

    return SimParams(
        cell_x=eval_required(scene.domain.cell_x_expr, context, "cell_x"),
        cell_y=eval_required(scene.domain.cell_y_expr, context, "cell_y"),
        resolution=int(eval_required(scene.domain.resolution_expr, context, "resolution")),
        pml=eval_required(scene.domain.pml_width_expr, context, "pml_width"),
        pml_x=scene.domain.pml_mode in {"x", "both"},
        pml_y=scene.domain.pml_mode in {"y", "both"},
        k_point=k_point,
        cylindrical_enabled=scene.domain.cylindrical_enabled,
        cylindrical_m=(
            eval_required(scene.domain.cylindrical_m_expr, context, "cylindrical_m")
            if scene.domain.cylindrical_enabled
            else 0.0
        ),
        symmetries=symmetries,
        shapes=shapes,
        sources=sources,
    )


def scene_to_flux_specs(scene: SceneSpec, context: CompilationContext) -> list[FluxMonitorSpec]:
    return [
        monitor_kind(item.kind).to_flux_spec(item, context, eval_required)
        for item in scene.monitors
    ]
