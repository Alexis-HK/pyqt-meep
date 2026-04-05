from __future__ import annotations

from meep_gui.model import (
    AnalysisConfig,
    Domain,
    FluxMonitorConfig,
    GeometryItem,
    Material,
    Parameter,
    ProjectState,
    SourceItem,
    SymmetryItem,
    TransmissionDomainState,
    TransmissionSpectrumConfig,
)
from meep_gui.scene import compile_project_scene, compile_transmission_scenes, scene_to_sim_params


def test_project_state_compiles_to_typed_scene_ir() -> None:
    state = ProjectState(
        parameters=[Parameter(name="w", expr="2"), Parameter(name="h", expr="w + 1")],
        materials=[Material(name="si", index_expr="sqrt(12)")],
        geometries=[
            GeometryItem(
                name="core",
                kind="block",
                material="si",
                props={
                    "size_x": "w",
                    "size_y": "h",
                    "center_x": "w / 2",
                    "center_y": "0",
                },
            )
        ],
        sources=[
            SourceItem(
                name="src",
                kind="gaussian",
                component="Ez",
                props={
                    "center_x": "0",
                    "center_y": "0",
                    "size_x": "0",
                    "size_y": "1",
                    "fcen": "0.2",
                    "df": "0.05",
                },
            )
        ],
        domain=Domain(
            cell_x="2 * w",
            cell_y="10",
            resolution="20",
            pml_width="1",
            pml_mode="both",
            symmetry_enabled=True,
            symmetries=[SymmetryItem(name="mx", kind="mirror", direction="x", phase="-1")],
        ),
        flux_monitors=[
            FluxMonitorConfig(
                name="flux1",
                center_x="1",
                center_y="0",
                size_x="0",
                size_y="2",
                fcen="0.2",
                df="0.1",
                nfreq="40",
            )
        ],
        analysis=AnalysisConfig(kind="field_animation"),
    )

    compiled = compile_project_scene(state)
    scene = compiled.scene
    params = scene_to_sim_params(scene, compiled.context)

    assert scene.parameters[0].name == "w"
    assert scene.media[0].constant_index_expr == "sqrt(12)"
    assert scene.objects[0].geometry.kind == "block"
    assert scene.objects[0].geometry.block is not None
    assert scene.objects[0].geometry.block.size_x_expr == "w"
    assert scene.objects[0].transform.center_x_expr == "w / 2"
    assert scene.sources[0].frequency_expr == "0.2"
    assert scene.monitors[0].nfreq_expr == "40"
    assert scene.symmetries[0].phase_expr == "-1"
    assert compiled.context.parameter_values == {"w": 2.0, "h": 3.0}
    assert params.cell_x == 4.0
    assert params.shapes[0].size_x == 2.0
    assert params.shapes[0].size_y == 3.0
    assert params.symmetries[0].phase == complex(-1, 0)


def test_transmission_scene_bundle_keeps_scattering_and_reference_separate() -> None:
    state = ProjectState(
        materials=[Material(name="si", index_expr="2")],
        geometries=[
            GeometryItem(
                name="dev_core",
                kind="block",
                material="si",
                props={"size_x": "4", "size_y": "1", "center_x": "0", "center_y": "0"},
            )
        ],
        sources=[
            SourceItem(
                name="dev_src",
                kind="gaussian",
                component="Ez",
                props={"center_x": "0", "center_y": "0", "size_x": "0", "size_y": "0", "fcen": "0.2", "df": "0.1"},
            )
        ],
        flux_monitors=[FluxMonitorConfig(name="dev_flux", size_x="0", size_y="1")],
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="ref_flux",
                transmission_monitor="dev_flux",
                reference_state=TransmissionDomainState(
                    domain=Domain(cell_x="8", cell_y="6", resolution="10", pml_width="1", pml_mode="both"),
                    geometries=[
                        GeometryItem(
                            name="ref_core",
                            kind="circle",
                            material="si",
                            props={"radius": "1", "center_x": "0", "center_y": "0"},
                        )
                    ],
                    sources=[
                        SourceItem(
                            name="ref_src",
                            kind="gaussian",
                            component="Ez",
                            props={"center_x": "0", "center_y": "0", "size_x": "0", "size_y": "0", "fcen": "0.2", "df": "0.1"},
                        )
                    ],
                    flux_monitors=[FluxMonitorConfig(name="ref_flux", size_x="0", size_y="1")],
                ),
            ),
        ),
    )

    bundle = compile_transmission_scenes(state)

    assert bundle.scattering.scene.name == "scattering"
    assert bundle.reference.scene.name == "reference"
    assert bundle.scattering.scene.objects[0].name == "dev_core"
    assert bundle.reference.scene.objects[0].name == "ref_core"
    assert bundle.scattering.scene.objects[0].geometry.kind == "block"
    assert bundle.reference.scene.objects[0].geometry.kind == "circle"
    assert bundle.scattering.scene.monitors[0].name == "dev_flux"
    assert bundle.reference.scene.monitors[0].name == "ref_flux"
    assert bundle.scattering.context.parameter_values == bundle.reference.context.parameter_values
