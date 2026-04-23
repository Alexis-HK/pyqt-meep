from __future__ import annotations

from meep_gui.model import (
    GEOMETRY_FIELDS,
    GEOMETRY_KINDS,
    SOURCE_FIELDS,
    SOURCE_KINDS,
    FluxMonitorConfig,
    GeometryItem,
    Material,
    ProjectState,
    SourceItem,
    Parameter,
)
from meep_gui.primitives import (
    DEFAULT_MATERIAL_KIND,
    DEFAULT_MONITOR_KIND,
    GEOMETRY_REGISTRY,
    MATERIAL_REGISTRY,
    MONITOR_REGISTRY,
    SOURCE_REGISTRY,
)
from meep_gui.scene import compile_project_scene, scene_to_flux_specs, scene_to_sim_params


def test_primitive_registries_cover_current_builtin_kinds() -> None:
    assert tuple(GEOMETRY_REGISTRY) == ("circle", "block")
    assert tuple(SOURCE_REGISTRY) == ("continuous", "gaussian", "gaussian_beam")
    assert tuple(MATERIAL_REGISTRY) == ("constant",)
    assert tuple(MONITOR_REGISTRY) == ("flux",)
    assert DEFAULT_MATERIAL_KIND == "constant"
    assert DEFAULT_MONITOR_KIND == "flux"


def test_model_constants_remain_registry_derived_compatibility_views() -> None:
    assert GEOMETRY_KINDS == tuple(GEOMETRY_REGISTRY)
    assert SOURCE_KINDS == tuple(SOURCE_REGISTRY)
    assert GEOMETRY_FIELDS == {
        kind: tuple(field.field_id for field in spec.fields)
        for kind, spec in GEOMETRY_REGISTRY.items()
    }
    assert SOURCE_FIELDS == {
        kind: tuple(field.field_id for field in spec.fields)
        for kind, spec in SOURCE_REGISTRY.items()
    }


def test_scene_compilation_and_runtime_lowering_use_registry_hooks() -> None:
    state = ProjectState(
        materials=[Material(name="glass", index_expr="2")],
        geometries=[
            GeometryItem(
                name="disk",
                kind="circle",
                material="glass",
                props={"radius": "1.5", "center_x": "0.5", "center_y": "-0.25"},
            )
        ],
        sources=[
            SourceItem(
                name="cw",
                kind="continuous",
                component="Ez",
                props={"center_x": "0", "center_y": "0", "size_x": "1", "size_y": "0", "fcen": "0.2"},
            )
        ],
        flux_monitors=[
            FluxMonitorConfig(
                name="flux1",
                center_x="0",
                center_y="0",
                size_x="0",
                size_y="2",
                fcen="0.2",
                df="0.1",
                nfreq="32",
            )
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)
    flux_specs = scene_to_flux_specs(compiled.scene, compiled.context)

    assert compiled.scene.media[0].kind == "constant"
    assert compiled.scene.objects[0].geometry.kind == "circle"
    assert compiled.scene.sources[0].kind == "continuous"
    assert compiled.scene.monitors[0].kind == "flux"
    assert params.shapes[0].kind == "circle"
    assert params.shapes[0].eps == 4.0
    assert params.sources[0].kind == "continuous"
    assert params.sources[0].bandwidth == 0.0
    assert flux_specs[0].name == "flux1"
    assert flux_specs[0].nfreq == 32


def test_gaussian_beam_resolves_disabled_temporal_source_and_filters_runtime_sources() -> None:
    state = ProjectState(
        parameters=[Parameter(name="amp", expr="2")],
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={
                    "center_x": "0",
                    "center_y": "0",
                    "size_x": "0",
                    "size_y": "1",
                    "fcen": "0.2",
                    "df": "0.1",
                },
                enabled=False,
            ),
            SourceItem(
                name="beam",
                kind="gaussian_beam",
                component="Ez",
                props={
                    "src": "pulse",
                    "center_x": "1",
                    "center_y": "2",
                    "size_x": "3",
                    "size_y": "0",
                    "beam_x0_x": "0",
                    "beam_x0_y": "4",
                    "beam_kdir_x": "0",
                    "beam_kdir_y": "1",
                    "beam_w0": "0.8",
                    "beam_e0_x": "0",
                    "beam_e0_y": "0",
                    "beam_e0_z": "amp * (1 + 1j) / sqrt(2)",
                },
            ),
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    assert compiled.scene.sources[0].enabled is False
    assert compiled.scene.sources[1].source_time_kind == "gaussian"
    assert compiled.scene.sources[1].frequency_expr == "0.2"
    assert len(params.sources) == 1
    assert params.sources[0].kind == "gaussian_beam"
    assert params.sources[0].source_time_kind == "gaussian"
    assert params.sources[0].beam_w0 == 0.8
    assert abs(params.sources[0].beam_e0_z.real - 2**0.5) < 1e-9
    assert abs(params.sources[0].beam_e0_z.imag - 2**0.5) < 1e-9
