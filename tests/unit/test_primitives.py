from __future__ import annotations

import cmath

import pytest

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
from meep_gui.analysis.mpb_support import build_mpb_geometry
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
    assert tuple(GEOMETRY_REGISTRY) == ("circle", "ring", "block")
    assert tuple(SOURCE_REGISTRY) == (
        "continuous",
        "gaussian",
        "custom",
        "chirped_pulse",
        "gaussian_beam",
        "eigenmode",
    )
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


def test_ring_geometry_lowers_to_outer_and_inner_runtime_shapes() -> None:
    state = ProjectState(
        materials=[
            Material(name="si", index_expr="3"),
            Material(name="air", index_expr="1"),
        ],
        geometries=[
            GeometryItem(
                name="ring",
                kind="ring",
                material="si",
                props={
                    "inner_material": "air",
                    "radius": "2",
                    "width": "0.4",
                    "center_x": "0.5",
                    "center_y": "-0.25",
                },
            )
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    ring = compiled.scene.objects[0].geometry.ring
    assert compiled.scene.objects[0].geometry.kind == "ring"
    assert ring is not None
    assert ring.inner_medium_name == "air"
    assert len(params.shapes) == 2
    assert [shape.kind for shape in params.shapes] == ["circle", "circle"]
    assert [shape.radius for shape in params.shapes] == [2.2, 1.8]
    assert [shape.eps for shape in params.shapes] == [9.0, 1.0]
    assert [(shape.center_x, shape.center_y) for shape in params.shapes] == [
        (0.5, -0.25),
        (0.5, -0.25),
    ]


@pytest.mark.parametrize(
    ("props", "message"),
    [
        (
            {"inner_material": "", "radius": "2", "width": "0.4"},
            "inner material is required",
        ),
        (
            {"inner_material": "air", "radius": "2", "width": "0"},
            "width must be positive",
        ),
        (
            {"inner_material": "air", "radius": "0.1", "width": "0.4"},
            "inner radius must be positive",
        ),
    ],
)
def test_ring_geometry_runtime_validation(props: dict[str, str], message: str) -> None:
    state = ProjectState(
        materials=[
            Material(name="si", index_expr="3"),
            Material(name="air", index_expr="1"),
        ],
        geometries=[
            GeometryItem(
                name="ring",
                kind="ring",
                material="si",
                props={**props, "center_x": "0", "center_y": "0"},
            )
        ],
    )

    compiled = compile_project_scene(state)
    with pytest.raises(ValueError, match=message):
        scene_to_sim_params(compiled.scene, compiled.context)


def test_ring_geometry_lowers_to_two_mpb_objects() -> None:
    class _FakeMP:
        inf = "inf"

        @staticmethod
        def Medium(index=1):
            return ("Medium", index)

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return (x, y, z)

        @staticmethod
        def Cylinder(**kwargs):
            return ("Cylinder", kwargs)

    state = ProjectState(
        materials=[
            Material(name="si", index_expr="3"),
            Material(name="air", index_expr="1"),
        ],
        geometries=[
            GeometryItem(
                name="ring",
                kind="ring",
                material="si",
                props={
                    "inner_material": "air",
                    "radius": "2",
                    "width": "0.4",
                    "center_x": "0",
                    "center_y": "0",
                },
            )
        ],
    )

    geometry = build_mpb_geometry(state, _FakeMP(), {}, deps=None)

    assert len(geometry) == 2
    assert [item[1]["radius"] for item in geometry] == [2.2, 1.8]
    assert [item[1]["material"] for item in geometry] == [("Medium", 3.0), ("Medium", 1.0)]


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


def test_custom_source_compiles_runtime_functions_and_optional_amp_func() -> None:
    state = ProjectState(
        parameters=[Parameter(name="scale", expr="2")],
        sources=[
            SourceItem(
                name="custom_src",
                kind="custom",
                component="Ez",
                props={
                    "center_x": "0",
                    "center_y": "1",
                    "size_x": "2",
                    "size_y": "0",
                    "amplitude": "scale * (1 + 1j)",
                    "amp_func": "x - 1j*y",
                    "src_func": "exp(-t*t) * (1 + 1j)",
                    "start_time": "-5",
                    "end_time": "6",
                    "is_integrated": True,
                    "center_frequency": "0.25",
                    "fwidth": "0.05",
                },
            )
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    assert compiled.scene.sources[0].source_time_kind == "custom"
    assert params.sources[0].kind == "custom"
    assert params.sources[0].source_time_kind == "custom"
    assert params.sources[0].source_time is not None
    assert params.sources[0].source_time.is_integrated is True
    assert params.sources[0].source_time.center_frequency == 0.25
    assert params.sources[0].source_time.fwidth == 0.05
    assert params.sources[0].amplitude == complex(2, 2)
    assert params.sources[0].amp_func is not None
    assert abs(params.sources[0].amp_func(3, 4).real - 3) < 1e-9
    assert abs(params.sources[0].amp_func(3, 4).imag + 4) < 1e-9
    assert params.sources[0].source_time.src_func is not None
    assert abs(params.sources[0].source_time.src_func(0).real - 1) < 1e-9
    assert abs(params.sources[0].source_time.src_func(0).imag - 1) < 1e-9


def test_custom_source_allows_blank_amp_func() -> None:
    state = ProjectState(
        sources=[
            SourceItem(
                name="custom_src",
                kind="custom",
                component="Ez",
                props={"src_func": "1", "amp_func": ""},
            )
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    assert params.sources[0].amp_func is None


def test_custom_source_can_inherit_optional_temporal_source() -> None:
    state = ProjectState(
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
                enabled=False,
            ),
            SourceItem(
                name="custom_src",
                kind="custom",
                component="Ez",
                props={
                    "src": "pulse",
                    "src_func": "t",
                    "center_frequency": "0.3",
                    "fwidth": "0.07",
                },
            ),
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    assert compiled.scene.sources[1].source_time_kind == "gaussian"
    assert params.sources[0].kind == "custom"
    assert params.sources[0].source_time_kind == "gaussian"
    assert params.sources[0].frequency == 0.2
    assert params.sources[0].bandwidth == 0.1


def test_chirped_pulse_source_compiles_runtime_callback() -> None:
    state = ProjectState(
        parameters=[Parameter(name="shift", expr="2")],
        sources=[
            SourceItem(
                name="chirp",
                kind="chirped_pulse",
                component="Ez",
                props={
                    "center_x": "1",
                    "center_y": "-1",
                    "size_x": "0",
                    "size_y": "3",
                    "v0": "0.4",
                    "a": "0.2",
                    "b": "-0.5",
                    "t0": "10 + shift",
                },
            )
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    assert compiled.scene.sources[0].kind == "chirped_pulse"
    assert compiled.scene.sources[0].source_time_kind == "chirped_pulse"
    assert compiled.scene.sources[0].source_time is not None
    assert compiled.scene.sources[0].source_time.chirp_v0_expr == "0.4"
    assert compiled.scene.sources[0].source_time.chirp_t0_expr == "10 + shift"
    assert compiled.scene.sources[0].source_time.center_frequency_expr == "0.4"
    assert params.sources[0].kind == "chirped_pulse"
    assert params.sources[0].source_time_kind == "chirped_pulse"
    assert params.sources[0].source_time is not None
    assert params.sources[0].source_time.center_frequency == 0.4
    assert params.sources[0].source_time.chirp_v0 == 0.4
    assert params.sources[0].source_time.chirp_a == 0.2
    assert params.sources[0].source_time.chirp_b == -0.5
    assert params.sources[0].source_time.chirp_t0 == 12.0
    assert params.sources[0].source_time.src_func is not None
    expected = cmath.exp(1j * 6.283185307179586 * 0.4 * 1.0) * cmath.exp(
        (-0.2 - 0.5j) * 1.0
    )
    assert abs(params.sources[0].source_time.src_func(13.0) - expected) < 1e-9


def test_gaussian_beam_resolves_custom_temporal_source() -> None:
    state = ProjectState(
        parameters=[Parameter(name="phase", expr="2")],
        sources=[
            SourceItem(
                name="custom_time",
                kind="custom",
                component="Ez",
                props={
                    "src_func": "t + phase*1j",
                    "center_frequency": "0.3",
                    "fwidth": "0.07",
                },
                enabled=False,
            ),
            SourceItem(
                name="beam",
                kind="gaussian_beam",
                component="Ez",
                props={"src": "custom_time"},
            ),
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    assert compiled.scene.sources[1].source_time_kind == "custom"
    assert len(params.sources) == 1
    assert params.sources[0].kind == "gaussian_beam"
    assert params.sources[0].source_time_kind == "custom"
    assert params.sources[0].source_time is not None
    assert abs(params.sources[0].source_time.src_func(1).real - 1) < 1e-9
    assert abs(params.sources[0].source_time.src_func(1).imag - 2) < 1e-9


def test_gaussian_beam_resolves_chirped_pulse_source_time() -> None:
    state = ProjectState(
        sources=[
            SourceItem(
                name="chirp_time",
                kind="chirped_pulse",
                component="Ez",
                props={"v0": "0.25", "a": "0.1", "b": "0.3", "t0": "4"},
                enabled=False,
            ),
            SourceItem(
                name="beam",
                kind="gaussian_beam",
                component="Ez",
                props={"src": "chirp_time"},
            ),
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    assert compiled.scene.sources[1].source_time_kind == "chirped_pulse"
    assert len(params.sources) == 1
    assert params.sources[0].kind == "gaussian_beam"
    assert params.sources[0].source_time_kind == "chirped_pulse"
    assert params.sources[0].source_time is not None
    assert params.sources[0].source_time.center_frequency == 0.25
    assert params.sources[0].source_time.chirp_t0 == 4.0
    assert params.sources[0].source_time.src_func is not None
    assert abs(params.sources[0].source_time.src_func(4.0) - (1 + 0j)) < 1e-9


def test_eigenmode_resolves_source_time_and_optional_regions() -> None:
    state = ProjectState(
        parameters=[Parameter(name="amp", expr="2")],
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
                enabled=False,
            ),
            SourceItem(
                name="mode",
                kind="eigenmode",
                component="Ez",
                props={
                    "src": "pulse",
                    "center_x": "1",
                    "center_y": "2",
                    "size_x": "0",
                    "size_y": "4",
                    "eig_component": "ALL_COMPONENTS",
                    "eig_direction": "X",
                    "eig_band": "2",
                    "eig_kpoint_x": "0.1",
                    "eig_kpoint_y": "0.2",
                    "eig_kpoint_z": "0.3",
                    "eig_match_freq": False,
                    "eig_parity": "EVEN_Y+ODD_Z",
                    "eig_resolution": "16",
                    "eig_tolerance": "1e-9",
                    "eig_lattice_size_x": "6",
                    "eig_lattice_size_y": "7",
                    "eig_lattice_center_x": "0.5",
                    "eig_lattice_center_y": "-0.5",
                    "eig_vol_size_x": "0",
                    "eig_vol_size_y": "3",
                    "eig_vol_center_x": "1.5",
                    "eig_vol_center_y": "0",
                    "amplitude": "amp * (1 + 1j)",
                    "amp_func": "x - y*1j",
                },
            ),
        ],
    )

    compiled = compile_project_scene(state)
    params = scene_to_sim_params(compiled.scene, compiled.context)

    assert compiled.scene.sources[1].source_time_kind == "gaussian"
    assert len(params.sources) == 1
    source = params.sources[0]
    assert source.kind == "eigenmode"
    assert source.component == "ALL_COMPONENTS"
    assert source.source_time_kind == "gaussian"
    assert source.eig_direction == "X"
    assert source.eig_band == 2
    assert source.eig_kpoint == (0.1, 0.2, 0.3)
    assert source.eig_match_freq is False
    assert source.eig_parity == "EVEN_Y+ODD_Z"
    assert source.eig_resolution == 16
    assert source.eig_tolerance == 1e-9
    assert source.eig_lattice_size == (6.0, 7.0)
    assert source.eig_lattice_center == (0.5, -0.5)
    assert source.eig_vol_size == (0.0, 3.0)
    assert source.eig_vol_center == (1.5, 0.0)
    assert source.amplitude == complex(2, 2)
    assert source.amp_func is not None
    assert source.amp_func(3, 4) == complex(3, -4)
