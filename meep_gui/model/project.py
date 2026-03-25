from __future__ import annotations

from dataclasses import dataclass, field

from .analysis import (
    AnalysisConfig,
    FrequencyDomainSolverConfig,
    MpbModeSolverConfig,
    SweepConfig,
    TransmissionSpectrumConfig,
)
from .constants import FIELD_COMPONENTS, GEOMETRY_KINDS, RUN_STATUS_VALUES, SOURCE_KINDS
from .domain import Domain, normalize_domain
from .objects import FluxMonitorConfig, GeometryItem, Material, Parameter, SourceItem
from .results import RunRecord


@dataclass
class ProjectState:
    parameters: list[Parameter] = field(default_factory=list)
    materials: list[Material] = field(default_factory=list)
    geometries: list[GeometryItem] = field(default_factory=list)
    sources: list[SourceItem] = field(default_factory=list)
    domain: Domain = field(default_factory=Domain)
    flux_monitors: list[FluxMonitorConfig] = field(default_factory=list)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    sweep: SweepConfig = field(default_factory=SweepConfig)
    results: list[RunRecord] = field(default_factory=list)

    def normalize(self) -> None:
        self.domain = normalize_domain(self.domain)

        if self.analysis.kind not in {
            "field_animation",
            "harminv",
            "transmission_spectrum",
            "frequency_domain_solver",
            "meep_k_points",
            "mpb_modesolver",
        }:
            self.analysis = AnalysisConfig()
        elif self.analysis.transmission_spectrum.preview_domain not in {"scattering", "reference"}:
            tx = self.analysis.transmission_spectrum
            self.analysis = AnalysisConfig(
                kind=self.analysis.kind,
                field_animation=self.analysis.field_animation,
                harminv=self.analysis.harminv,
                transmission_spectrum=TransmissionSpectrumConfig(
                    incident_monitor=tx.incident_monitor,
                    transmission_monitor=tx.transmission_monitor,
                    reflection_monitor=tx.reflection_monitor,
                    reference_reflection_monitor=tx.reference_reflection_monitor,
                    until_after_sources=tx.until_after_sources,
                    animate_reference=tx.animate_reference,
                    animate_scattering=tx.animate_scattering,
                    animation_component=tx.animation_component,
                    animation_interval=tx.animation_interval,
                    animation_fps=tx.animation_fps,
                    output_dir=tx.output_dir,
                    output_prefix=tx.output_prefix,
                    reuse_reference_run_id=tx.reuse_reference_run_id,
                    reuse_reference_csv_name=tx.reuse_reference_csv_name,
                    preview_domain="scattering",
                    reference_state=tx.reference_state,
                ),
                frequency_domain_solver=self.analysis.frequency_domain_solver,
                meep_k_points=self.analysis.meep_k_points,
                mpb_modesolver=self.analysis.mpb_modesolver,
            )

        tx = self.analysis.transmission_spectrum
        if tx.animation_component not in FIELD_COMPONENTS:
            self.analysis = AnalysisConfig(
                kind=self.analysis.kind,
                field_animation=self.analysis.field_animation,
                harminv=self.analysis.harminv,
                transmission_spectrum=TransmissionSpectrumConfig(
                    incident_monitor=tx.incident_monitor,
                    transmission_monitor=tx.transmission_monitor,
                    reflection_monitor=tx.reflection_monitor,
                    reference_reflection_monitor=tx.reference_reflection_monitor,
                    until_after_sources=tx.until_after_sources,
                    animate_reference=tx.animate_reference,
                    animate_scattering=tx.animate_scattering,
                    animation_component="Ez",
                    animation_interval=tx.animation_interval,
                    animation_fps=tx.animation_fps,
                    output_dir=tx.output_dir,
                    output_prefix=tx.output_prefix,
                    reuse_reference_run_id=tx.reuse_reference_run_id,
                    reuse_reference_csv_name=tx.reuse_reference_csv_name,
                    preview_domain=tx.preview_domain,
                    reference_state=tx.reference_state,
                ),
                frequency_domain_solver=self.analysis.frequency_domain_solver,
                meep_k_points=self.analysis.meep_k_points,
                mpb_modesolver=self.analysis.mpb_modesolver,
            )
            tx = self.analysis.transmission_spectrum

        fd = self.analysis.frequency_domain_solver
        if fd.component not in FIELD_COMPONENTS:
            self.analysis = AnalysisConfig(
                kind=self.analysis.kind,
                field_animation=self.analysis.field_animation,
                harminv=self.analysis.harminv,
                transmission_spectrum=self.analysis.transmission_spectrum,
                frequency_domain_solver=FrequencyDomainSolverConfig(
                    component="Ez",
                    tolerance=fd.tolerance,
                    max_iters=fd.max_iters,
                    bicgstab_l=fd.bicgstab_l,
                    output_dir=fd.output_dir,
                    output_name=fd.output_name,
                ),
                meep_k_points=self.analysis.meep_k_points,
                mpb_modesolver=self.analysis.mpb_modesolver,
            )
            fd = self.analysis.frequency_domain_solver

        tx.reference_state.domain = normalize_domain(tx.reference_state.domain)

        for item in self.geometries:
            if item.kind not in GEOMETRY_KINDS:
                raise ValueError(f"Unsupported geometry kind: {item.kind}")

        for item in self.sources:
            if item.kind not in SOURCE_KINDS:
                raise ValueError(f"Unsupported source kind: {item.kind}")
            if item.component not in FIELD_COMPONENTS:
                raise ValueError(f"Unsupported field component: {item.component}")

        for monitor in self.flux_monitors:
            if not monitor.name:
                raise ValueError("Flux monitor name is required.")

        for item in tx.reference_state.geometries:
            if item.kind not in GEOMETRY_KINDS:
                raise ValueError(f"Reference geometry '{item.name}': unsupported kind '{item.kind}'.")

        for item in tx.reference_state.sources:
            if item.kind not in SOURCE_KINDS:
                raise ValueError(f"Reference source '{item.name}': unsupported kind '{item.kind}'.")
            if item.component not in FIELD_COMPONENTS:
                raise ValueError(
                    f"Reference source '{item.name}': unsupported component '{item.component}'."
                )

        for monitor in tx.reference_state.flux_monitors:
            if not monitor.name:
                raise ValueError("Reference flux monitor name is required.")

        self.results = [
            RunRecord(
                run_id=record.run_id,
                analysis_kind=record.analysis_kind,
                status=record.status if record.status in RUN_STATUS_VALUES else "completed",
                created_at=record.created_at,
                message=record.message,
                artifacts=list(record.artifacts),
                plots=list(record.plots),
                meta=dict(record.meta),
            )
            for record in self.results
        ]
