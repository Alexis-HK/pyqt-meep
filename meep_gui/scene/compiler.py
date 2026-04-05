from __future__ import annotations

from ..model import FIELD_COMPONENTS, GEOMETRY_KINDS, SOURCE_KINDS, ProjectState, normalize_domain
from ..validation import evaluate_parameters
from .types import (
    BlockGeometrySpec,
    CircleGeometrySpec,
    CompilationContext,
    CompiledScene,
    DomainSpec,
    GeometrySpec,
    MediumSpec,
    MonitorSpec,
    ParameterSpec,
    SceneObject,
    SceneSpec,
    SourceSpec,
    SpatialMaterialSpec,
    SymmetrySpec,
    TransformSpec,
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
        MediumSpec(
            name=item.name,
            kind="constant",
            constant_index_expr=item.index_expr,
        )
        for item in materials
        if getattr(item, "name", "")
    )

    scene_objects: list[SceneObject] = []
    for item in geometries:
        if item.kind not in GEOMETRY_KINDS:
            raise ValueError(f"Unsupported geometry kind: {item.kind}")
        geometry = GeometrySpec(
            kind=item.kind,
            block=(
                BlockGeometrySpec(
                    size_x_expr=item.props.get("size_x", "0"),
                    size_y_expr=item.props.get("size_y", "0"),
                )
                if item.kind == "block"
                else None
            ),
            circle=(
                CircleGeometrySpec(radius_expr=item.props.get("radius", "0"))
                if item.kind == "circle"
                else None
            ),
        )
        scene_objects.append(
            SceneObject(
                name=item.name,
                geometry=geometry,
                spatial_material=SpatialMaterialSpec(kind="uniform", medium_name=item.material),
                transform=TransformSpec(
                    center_x_expr=item.props.get("center_x", "0"),
                    center_y_expr=item.props.get("center_y", "0"),
                ),
            )
        )

    scene_sources: list[SourceSpec] = []
    for item in sources:
        if item.kind not in SOURCE_KINDS:
            raise ValueError(f"Unsupported source kind: {item.kind}")
        if item.component not in FIELD_COMPONENTS:
            raise ValueError(f"Unsupported field component: {item.component}")
        scene_sources.append(
            SourceSpec(
                name=item.name,
                kind=item.kind,
                component=item.component,
                center_x_expr=item.props.get("center_x", "0"),
                center_y_expr=item.props.get("center_y", "0"),
                size_x_expr=item.props.get("size_x", "0"),
                size_y_expr=item.props.get("size_y", "0"),
                frequency_expr=item.props.get("fcen", "0.15"),
                bandwidth_expr=item.props.get("df", "0.1"),
            )
        )

    scene_monitors_list: list[MonitorSpec] = []
    for item in monitors:
        if not getattr(item, "name", ""):
            raise ValueError("Flux monitor name is required.")
        scene_monitors_list.append(
            MonitorSpec(
                name=item.name,
                kind="flux",
                center_x_expr=item.center_x,
                center_y_expr=item.center_y,
                size_x_expr=item.size_x,
                size_y_expr=item.size_y,
                fcen_expr=item.fcen,
                df_expr=item.df,
                nfreq_expr=item.nfreq,
            )
        )

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
