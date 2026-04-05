from __future__ import annotations

from ..model import FIELD_COMPONENTS, ProjectState, normalize_domain
from ..primitives import (
    DEFAULT_MATERIAL_KIND,
    DEFAULT_MONITOR_KIND,
    geometry_kind,
    material_kind,
    monitor_kind,
    source_kind,
)
from ..validation import evaluate_parameters
from .types import (
    CompilationContext,
    CompiledScene,
    DomainSpec,
    ParameterSpec,
    SceneSpec,
    SymmetrySpec,
    TransmissionSceneBundle,
)


def evaluate_compilation_context(parameters) -> CompilationContext:
    values, results = evaluate_parameters(parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")
    return CompilationContext(parameter_values=values)


def compile_project_scene(
    state: ProjectState,
    *,
    parameter_values: dict[str, float] | None = None,
) -> CompiledScene:
    context = (
        CompilationContext(parameter_values=dict(parameter_values))
        if parameter_values is not None
        else evaluate_compilation_context(state.parameters)
    )
    scene = _compile_scene_spec(
        name="scattering",
        parameters=state.parameters,
        domain=state.domain,
        materials=state.materials,
        geometries=state.geometries,
        sources=state.sources,
        monitors=state.flux_monitors,
    )
    return CompiledScene(scene=scene, context=context)


def compile_transmission_scenes(
    state: ProjectState,
    *,
    parameter_values: dict[str, float] | None = None,
) -> TransmissionSceneBundle:
    context = (
        CompilationContext(parameter_values=dict(parameter_values))
        if parameter_values is not None
        else evaluate_compilation_context(state.parameters)
    )
    scattering = CompiledScene(
        scene=_compile_scene_spec(
            name="scattering",
            parameters=state.parameters,
            domain=state.domain,
            materials=state.materials,
            geometries=state.geometries,
            sources=state.sources,
            monitors=state.flux_monitors,
        ),
        context=context,
    )
    reference_state = state.analysis.transmission_spectrum.reference_state
    reference = CompiledScene(
        scene=_compile_scene_spec(
            name="reference",
            parameters=state.parameters,
            domain=reference_state.domain,
            materials=state.materials,
            geometries=reference_state.geometries,
            sources=reference_state.sources,
            monitors=reference_state.flux_monitors,
        ),
        context=context,
    )
    return TransmissionSceneBundle(scattering=scattering, reference=reference)


def _compile_scene_spec(
    *,
    name: str,
    parameters,
    domain,
    materials,
    geometries,
    sources,
    monitors,
) -> SceneSpec:
    normalized_domain = normalize_domain(domain)
    scene_parameters = tuple(
        ParameterSpec(name=item.name, expr=item.expr)
        for item in parameters
        if getattr(item, "name", "")
    )
    scene_media = tuple(
        material_kind(DEFAULT_MATERIAL_KIND).compile_scene_medium(item)
        for item in materials
        if getattr(item, "name", "")
    )

    scene_objects = []
    for item in geometries:
        scene_objects.append(geometry_kind(item.kind).compile_scene_object(item))

    scene_sources = []
    for item in sources:
        if item.component not in FIELD_COMPONENTS:
            raise ValueError(f"Unsupported field component: {item.component}")
        scene_sources.append(source_kind(item.kind).compile_scene_source(item))

    scene_monitors_list = []
    for item in monitors:
        if not getattr(item, "name", ""):
            raise ValueError("Flux monitor name is required.")
        scene_monitors_list.append(monitor_kind(DEFAULT_MONITOR_KIND).compile_scene_monitor(item))

    scene_symmetries = tuple(
        SymmetrySpec(
            name=item.name,
            kind=item.kind,
            direction=item.direction,
            phase_expr=item.phase,
        )
        for item in normalized_domain.symmetries
    )

    return SceneSpec(
        name=name,
        parameters=scene_parameters,
        domain=DomainSpec(
            cell_x_expr=normalized_domain.cell_x,
            cell_y_expr=normalized_domain.cell_y,
            resolution_expr=normalized_domain.resolution,
            pml_width_expr=normalized_domain.pml_width,
            pml_mode=normalized_domain.pml_mode,
        ),
        symmetries=scene_symmetries if normalized_domain.symmetry_enabled else (),
        media=scene_media,
        objects=tuple(scene_objects),
        sources=tuple(scene_sources),
        monitors=tuple(scene_monitors_list),
    )
