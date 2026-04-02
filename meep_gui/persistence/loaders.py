from __future__ import annotations

from typing import Any

from ..model import (
    AnalysisConfig,
    Domain,
    FieldAnimationConfig,
    FrequencyDomainSolverConfig,
    FluxMonitorConfig,
    GeometryItem,
    HarminvConfig,
    KPoint,
    Material,
    MeepKPointsConfig,
    MpbModeSolverConfig,
    Parameter,
    PlotRecord,
    ProjectState,
    ResultArtifact,
    RunRecord,
    SourceItem,
    SweepConfig,
    SweepParameter,
    SymmetryItem,
    TransmissionDomainState,
    TransmissionSpectrumConfig,
    normalize_bool,
)


def as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def load_parameters(raw: list[dict]) -> list[Parameter]:
    return [Parameter(name=item.get("name", ""), expr=item.get("expr", "")) for item in raw]


def load_materials(raw: list[dict]) -> list[Material]:
    return [
        Material(name=item.get("name", ""), index_expr=item.get("index_expr", ""))
        for item in raw
    ]


def load_geometries(raw: list[dict]) -> list[GeometryItem]:
    return [
        GeometryItem(
            name=item.get("name", ""),
            kind=item.get("kind", ""),
            material=item.get("material", ""),
            props=item.get("props", {}) or {},
        )
        for item in raw
    ]


def load_sources(raw: list[dict]) -> list[SourceItem]:
    return [
        SourceItem(
            name=item.get("name", ""),
            kind=item.get("kind", ""),
            component=item.get("component", "Ez"),
            props=item.get("props", {}) or {},
        )
        for item in raw
    ]


def load_domain(raw: dict | None) -> Domain:
    raw = raw or {}
    return Domain(
        cell_x=as_str(raw.get("cell_x", "10"), "10"),
        cell_y=as_str(raw.get("cell_y", "10"), "10"),
        resolution=as_str(raw.get("resolution", "20"), "20"),
        pml_width=as_str(raw.get("pml_width", "1"), "1"),
        pml_mode=as_str(raw.get("pml_mode", "both"), "both"),
        symmetry_enabled=normalize_bool(raw.get("symmetry_enabled", False), False),
        symmetries=load_symmetries(raw.get("symmetries", [])),
    )


def load_flux_monitors(raw: list[dict] | None) -> list[FluxMonitorConfig]:
    raw = raw or []
    return [
        FluxMonitorConfig(
            name=as_str(item.get("name", "flux1"), "flux1"),
            center_x=as_str(item.get("center_x", "0"), "0"),
            center_y=as_str(item.get("center_y", "0"), "0"),
            size_x=as_str(item.get("size_x", "0"), "0"),
            size_y=as_str(item.get("size_y", "1"), "1"),
            fcen=as_str(item.get("fcen", "0.15"), "0.15"),
            df=as_str(item.get("df", "0.1"), "0.1"),
            nfreq=as_str(item.get("nfreq", "50"), "50"),
        )
        for item in raw
        if isinstance(item, dict)
    ]


def load_symmetries(raw: list[dict] | None) -> list[SymmetryItem]:
    raw = raw or []
    return [
        SymmetryItem(
            name=as_str(item.get("name", ""), ""),
            kind=as_str(item.get("kind", "mirror"), "mirror"),
            direction=as_str(item.get("direction", "x"), "x"),
            phase=as_str(item.get("phase", "1"), "1"),
        )
        for item in raw
        if isinstance(item, dict)
    ]


def load_field_animation(raw: dict | None) -> FieldAnimationConfig:
    raw = raw or {}
    return FieldAnimationConfig(
        component=as_str(raw.get("component", "Ez"), "Ez"),
        duration=as_str(raw.get("duration", "200"), "200"),
        interval=as_str(raw.get("interval", "1"), "1"),
        fps=as_str(raw.get("fps", "20"), "20"),
        output_dir=as_str(raw.get("output_dir", ""), ""),
        output_name=as_str(raw.get("output_name", "animation.mp4"), "animation.mp4"),
    )


def load_harminv(raw: dict | None) -> HarminvConfig:
    raw = raw or {}
    return HarminvConfig(
        component=as_str(raw.get("component", "Ez"), "Ez"),
        point_x=as_str(raw.get("point_x", "0"), "0"),
        point_y=as_str(raw.get("point_y", "0"), "0"),
        fcen=as_str(raw.get("fcen", "0.15"), "0.15"),
        df=as_str(raw.get("df", "0.1"), "0.1"),
        until_after_sources=as_str(raw.get("until_after_sources", "200"), "200"),
        animation_interval=as_str(raw.get("animation_interval", "1"), "1"),
        animation_fps=as_str(raw.get("animation_fps", "20"), "20"),
        output_dir=as_str(raw.get("output_dir", ""), ""),
        output_name=as_str(raw.get("output_name", "harminv_animation.mp4"), "harminv_animation.mp4"),
        harminv_log_path=as_str(raw.get("harminv_log_path", "harminv.txt"), "harminv.txt"),
    )


def load_mpb(raw: dict | None) -> MpbModeSolverConfig:
    raw = raw or {}
    kpoints = [
        KPoint(kx=as_str(item.get("kx", "0"), "0"), ky=as_str(item.get("ky", "0"), "0"))
        for item in raw.get("kpoints", [])
        if isinstance(item, dict)
    ]
    field_kpoints = [
        KPoint(kx=as_str(item.get("kx", "0"), "0"), ky=as_str(item.get("ky", "0"), "0"))
        for item in raw.get("field_kpoints", [])
        if isinstance(item, dict)
    ]
    return MpbModeSolverConfig(
        lattice_x=as_str(raw.get("lattice_x", "1"), "1"),
        lattice_y=as_str(raw.get("lattice_y", "1"), "1"),
        basis1_x=as_str(raw.get("basis1_x", "1"), "1"),
        basis1_y=as_str(raw.get("basis1_y", "0"), "0"),
        basis2_x=as_str(raw.get("basis2_x", "0"), "0"),
        basis2_y=as_str(raw.get("basis2_y", "1"), "1"),
        num_bands=as_str(raw.get("num_bands", "1"), "1"),
        resolution=as_str(raw.get("resolution", "16"), "16"),
        unit_cells=as_str(raw.get("unit_cells", "1"), "1"),
        kpoint_interp=as_str(raw.get("kpoint_interp", "10"), "10"),
        max_mode_images=as_str(raw.get("max_mode_images", "64"), "64"),
        run_tm=normalize_bool(raw.get("run_tm", True), True),
        run_te=normalize_bool(raw.get("run_te", False), False),
        kpoints=kpoints,
        field_kpoints=field_kpoints,
    )


def load_frequency_domain_solver(raw: dict | None) -> FrequencyDomainSolverConfig:
    raw = raw or {}
    return FrequencyDomainSolverConfig(
        component=as_str(raw.get("component", "Ez"), "Ez"),
        tolerance=as_str(raw.get("tolerance", "1e-8"), "1e-8"),
        max_iters=as_str(raw.get("max_iters", "10000"), "10000"),
        bicgstab_l=as_str(raw.get("bicgstab_l", "10"), "10"),
        output_dir=as_str(raw.get("output_dir", ""), ""),
        output_name=as_str(
            raw.get("output_name", "frequency_domain_field.png"),
            "frequency_domain_field.png",
        ),
    )


def load_meep_k_points(raw: dict | None) -> MeepKPointsConfig:
    raw = raw or {}
    kpoints = [
        KPoint(kx=as_str(item.get("kx", "0"), "0"), ky=as_str(item.get("ky", "0"), "0"))
        for item in raw.get("kpoints", [])
        if isinstance(item, dict)
    ]
    return MeepKPointsConfig(
        kpoint_interp=as_str(raw.get("kpoint_interp", "19"), "19"),
        run_time=as_str(raw.get("run_time", "300"), "300"),
        kpoints=kpoints,
        output_dir=as_str(raw.get("output_dir", ""), ""),
        output_prefix=as_str(raw.get("output_prefix", "meep_k_points"), "meep_k_points"),
    )


def load_transmission(raw: dict | None) -> TransmissionSpectrumConfig:
    raw = raw or {}
    return TransmissionSpectrumConfig(
        incident_monitor=as_str(raw.get("incident_monitor", ""), ""),
        transmission_monitor=as_str(raw.get("transmission_monitor", ""), ""),
        reflection_monitor=as_str(raw.get("reflection_monitor", ""), ""),
        reference_reflection_monitor=as_str(raw.get("reference_reflection_monitor", ""), ""),
        until_after_sources=as_str(raw.get("until_after_sources", "200"), "200"),
        animate_reference=normalize_bool(raw.get("animate_reference", False), False),
        animate_scattering=normalize_bool(raw.get("animate_scattering", False), False),
        animation_component=as_str(raw.get("animation_component", "Ez"), "Ez"),
        animation_interval=as_str(raw.get("animation_interval", "1"), "1"),
        animation_fps=as_str(raw.get("animation_fps", "20"), "20"),
        output_dir=as_str(raw.get("output_dir", ""), ""),
        output_prefix=as_str(raw.get("output_prefix", "transmission"), "transmission"),
        reuse_reference_run_id=as_str(raw.get("reuse_reference_run_id", ""), ""),
        reuse_reference_csv_name=as_str(
            raw.get("reuse_reference_csv_name", "transmission_spectrum.csv"),
            "transmission_spectrum.csv",
        ),
        preview_domain=as_str(raw.get("preview_domain", "scattering"), "scattering"),
        reference_state=load_transmission_domain_state(raw.get("reference_state", {})),
    )


def load_transmission_domain_state(raw: dict | None) -> TransmissionDomainState:
    raw = raw or {}
    return TransmissionDomainState(
        domain=load_domain(raw.get("domain", {})),
        geometries=load_geometries(raw.get("geometries", [])),
        sources=load_sources(raw.get("sources", [])),
        flux_monitors=load_flux_monitors(raw.get("flux_monitors", [])),
    )


def load_sweep(raw: dict | None) -> SweepConfig:
    raw = raw or {}
    params = [
        SweepParameter(
            name=as_str(item.get("name", ""), ""),
            start=as_str(item.get("start", "0"), "0"),
            stop=as_str(item.get("stop", "1"), "1"),
            steps=as_str(item.get("steps", "3"), "3"),
        )
        for item in raw.get("params", [])
        if isinstance(item, dict)
    ]
    return SweepConfig(
        enabled=normalize_bool(raw.get("enabled", False), False),
        params=[item for item in params if item.name],
    )


def load_results(raw: list[dict] | None) -> list[RunRecord]:
    raw = raw or []
    records: list[RunRecord] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        artifacts = [
            ResultArtifact(
                kind=as_str(art.get("kind", "artifact"), "artifact"),
                label=as_str(art.get("label", "artifact"), "artifact"),
                path=as_str(art.get("path", ""), ""),
                meta={str(k): as_str(v) for k, v in (art.get("meta", {}) or {}).items()},
            )
            for art in item.get("artifacts", [])
            if isinstance(art, dict)
        ]
        plots = [
            PlotRecord(
                title=as_str(plot.get("title", "Plot"), "Plot"),
                x_label=as_str(plot.get("x_label", "x"), "x"),
                y_label=as_str(plot.get("y_label", "y"), "y"),
                csv_path=as_str(plot.get("csv_path", ""), ""),
                png_path=as_str(plot.get("png_path", ""), ""),
                meta={str(k): as_str(v) for k, v in (plot.get("meta", {}) or {}).items()},
            )
            for plot in item.get("plots", [])
            if isinstance(plot, dict)
        ]
        records.append(
            RunRecord(
                run_id=as_str(item.get("run_id", ""), ""),
                analysis_kind=as_str(item.get("analysis_kind", "analysis"), "analysis"),
                status=as_str(item.get("status", "completed"), "completed"),
                created_at=as_str(item.get("created_at", ""), ""),
                message=as_str(item.get("message", ""), ""),
                artifacts=artifacts,
                plots=plots,
                meta={str(k): as_str(v) for k, v in (item.get("meta", {}) or {}).items()},
            )
        )
    return records


def load_legacy_animations(raw: list[dict] | None) -> list[RunRecord]:
    raw = raw or []
    records: list[RunRecord] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        path = as_str(item.get("path", ""), "")
        if not path:
            continue
        kind = as_str(item.get("kind", "analysis"), "analysis")
        run_id = as_str(item.get("run_id", f"legacy-{idx}"), f"legacy-{idx}")
        artifacts = [
            ResultArtifact(
                kind="animation_mp4",
                label=as_str(item.get("export_name", path.split("/")[-1]), path.split("/")[-1]),
                path=path,
                meta={
                    "export_dir": as_str(item.get("export_dir", ""), ""),
                    "export_name": as_str(item.get("export_name", ""), ""),
                    "harminv_log_path": as_str(item.get("harminv_log_path", ""), ""),
                },
            )
        ]
        if item.get("harminv_lines"):
            artifacts.append(
                ResultArtifact(
                    kind="harminv_text",
                    label="Harminv Lines",
                    path="",
                    meta={"lines": "\n".join(str(x) for x in item.get("harminv_lines", []))},
                )
            )
        records.append(
            RunRecord(
                run_id=run_id,
                analysis_kind=kind,
                status="completed",
                created_at="",
                message="Imported from legacy result list",
                artifacts=artifacts,
                plots=[],
            )
        )
    return records


def load_state_dict(raw: dict) -> ProjectState:
    raw = raw if isinstance(raw, dict) else {}
    analysis_raw = raw.get("analysis", {}) if isinstance(raw, dict) else {}
    analysis = AnalysisConfig(
        kind=as_str(analysis_raw.get("kind", "field_animation"), "field_animation"),
        field_animation=load_field_animation(analysis_raw.get("field_animation", {})),
        harminv=load_harminv(analysis_raw.get("harminv", {})),
        transmission_spectrum=load_transmission(analysis_raw.get("transmission_spectrum", {})),
        frequency_domain_solver=load_frequency_domain_solver(
            analysis_raw.get("frequency_domain_solver", {})
        ),
        meep_k_points=load_meep_k_points(analysis_raw.get("meep_k_points", {})),
        mpb_modesolver=load_mpb(analysis_raw.get("mpb_modesolver", {})),
    )

    state = ProjectState(
        parameters=load_parameters(raw.get("parameters", [])),
        materials=load_materials(raw.get("materials", [])),
        geometries=load_geometries(raw.get("geometries", [])),
        sources=load_sources(raw.get("sources", [])),
        domain=load_domain(raw.get("domain", {})),
        flux_monitors=load_flux_monitors(raw.get("flux_monitors", [])),
        analysis=analysis,
        sweep=load_sweep(raw.get("sweep", {})),
        results=load_results(raw.get("results", [])),
    )
    state.normalize()
    return state
