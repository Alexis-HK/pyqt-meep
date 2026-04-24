from __future__ import annotations

import pytest

from meep_gui.analysis import RECIPE_REGISTRY, get_recipe, prepare_runtime_analysis
from meep_gui.model import (
    AnalysisConfig,
    Domain,
    FluxMonitorConfig,
    KPoint,
    MeepKPointsConfig,
    ProjectState,
    SourceItem,
    SymmetryItem,
)
from meep_gui.script import generate_script


def test_recipe_registry_covers_all_current_analysis_kinds() -> None:
    assert sorted(RECIPE_REGISTRY) == [
        "field_animation",
        "frequency_domain_solver",
        "harminv",
        "meep_k_points",
        "mpb_modesolver",
        "transmission_spectrum",
    ]


def test_recipe_registry_rejects_unknown_analysis_kind() -> None:
    with pytest.raises(ValueError, match="Unsupported analysis kind: unknown"):
        get_recipe("unknown")


def test_prepare_runtime_analysis_supported_scene_has_no_capability_issues() -> None:
    prepared = prepare_runtime_analysis(ProjectState(analysis=AnalysisConfig(kind="field_animation")))

    assert prepared.recipe.recipe_id == "field_animation"
    assert prepared.validation.ok
    assert prepared.validation.warnings == ()


def test_prepare_runtime_analysis_reports_forbidden_feature() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
            )
        ],
    )

    prepared = prepare_runtime_analysis(state)

    assert prepared.validation.ok is False
    assert prepared.validation.errors
    assert "Gaussian (pulsed) sources" in prepared.validation.errors[0].message


def test_prepare_runtime_analysis_reports_custom_temporal_source_forbidden_feature() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        sources=[
            SourceItem(
                name="custom_src",
                kind="custom",
                component="Ez",
                props={"src_func": "t"},
            )
        ],
    )

    prepared = prepare_runtime_analysis(state)

    assert prepared.validation.ok is False
    assert [item.message for item in prepared.validation.errors] == [
        "Frequency-domain solver supports only continuous sources. Custom temporal sources are not supported."
    ]


def test_recipe_specific_error_message_wins_over_generic_capability_message() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="harminv"),
        sources=[
            SourceItem(
                name="cw",
                kind="continuous",
                component="Ez",
                props={"fcen": "0.2"},
            )
        ],
    )

    prepared = prepare_runtime_analysis(state)

    assert [item.message for item in prepared.validation.errors] == [
        "Harminv requires Gaussian (pulsed) sources. Continuous sources are not supported."
    ]


def test_harminv_rejects_custom_temporal_sources_with_specific_message() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="harminv"),
        sources=[
            SourceItem(
                name="custom_src",
                kind="custom",
                component="Ez",
                props={"src_func": "t"},
            )
        ],
    )

    prepared = prepare_runtime_analysis(state)

    assert [item.message for item in prepared.validation.errors] == [
        "Harminv requires Gaussian (pulsed) sources. Custom temporal sources are not supported."
    ]


def test_prepare_runtime_analysis_reports_ignored_features_for_mpb() -> None:
    state = ProjectState(
        domain=Domain(
            cylindrical_enabled=True,
            cylindrical_m="1",
            symmetry_enabled=True,
            symmetries=[SymmetryItem(name="mx", kind="mirror", direction="x", phase="-1")],
        ),
        analysis=AnalysisConfig(kind="mpb_modesolver"),
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
            )
        ],
        flux_monitors=[FluxMonitorConfig(name="tx")],
    )

    prepared = prepare_runtime_analysis(state)
    messages = prepared.validation.messages("warning")

    assert prepared.validation.ok
    assert any("Gaussian (pulsed) sources are ignored by this analysis." == msg for msg in messages)
    assert any("Flux monitors are ignored by this analysis." == msg for msg in messages)
    assert any("Domain symmetries are ignored by this analysis." == msg for msg in messages)
    assert any("Cylindrical coordinates are ignored by this analysis." == msg for msg in messages)


def test_prepare_runtime_analysis_reports_custom_sources_ignored_for_mpb() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="mpb_modesolver"),
        sources=[
            SourceItem(
                name="custom_src",
                kind="custom",
                component="Ez",
                props={"src_func": "t"},
            )
        ],
    )

    prepared = prepare_runtime_analysis(state)

    assert "Custom temporal sources are ignored by this analysis." in prepared.validation.messages(
        "warning"
    )


def test_generate_script_logs_capability_warnings_for_mpb() -> None:
    messages: list[str] = []
    state = ProjectState(
        domain=Domain(
            cylindrical_enabled=True,
            cylindrical_m="1",
            symmetry_enabled=True,
            symmetries=[SymmetryItem(name="mz", kind="mirror", direction="z", phase="1")],
        ),
        analysis=AnalysisConfig(kind="mpb_modesolver"),
    )

    code = generate_script(state, log=messages.append)

    assert "# Note: domain symmetries are FDTD-only and are not applied to MPB." in code
    assert "# Note: cylindrical coordinates are FDTD-only and are not applied to MPB." in code
    assert "Warning: Domain symmetries are ignored by this analysis." in messages
    assert "Warning: Cylindrical coordinates are ignored by this analysis." in messages


def test_prepare_runtime_analysis_for_meep_k_points_keeps_current_config_shape() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
            ),
        ),
        sources=[
            SourceItem(
                name="src",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.15", "df": "0.1"},
            )
        ],
    )

    prepared = prepare_runtime_analysis(state)

    assert prepared.recipe.recipe_id == state.analysis.kind
    assert prepared.validation.ok


def test_disabled_gaussian_source_does_not_block_frequency_domain_solver() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
                enabled=False,
            )
        ],
    )

    prepared = prepare_runtime_analysis(state)

    assert prepared.validation.ok


def test_gaussian_beam_inherits_temporal_source_capability() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
            ),
        ),
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
                enabled=False,
            ),
            SourceItem(
                name="beam",
                kind="gaussian_beam",
                component="Ez",
                props={"src": "pulse"},
            ),
        ],
    )

    prepared = prepare_runtime_analysis(state)

    assert prepared.validation.ok


def test_gaussian_beam_inherits_custom_temporal_source_capability() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        sources=[
            SourceItem(
                name="custom_time",
                kind="custom",
                component="Ez",
                props={"src_func": "t"},
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

    prepared = prepare_runtime_analysis(state)

    assert [item.message for item in prepared.validation.errors] == [
        "Frequency-domain solver supports only continuous sources. Custom temporal sources are not supported."
    ]
