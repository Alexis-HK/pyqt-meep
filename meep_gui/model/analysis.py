from __future__ import annotations

from dataclasses import dataclass, field

from .domain import TransmissionDomainState
from .objects import KPoint, SweepParameter


@dataclass(frozen=True)
class FieldAnimationConfig:
    component: str = "Ez"
    duration: str = "200"
    interval: str = "1"
    fps: str = "20"
    output_dir: str = ""
    output_name: str = "animation.mp4"


@dataclass(frozen=True)
class HarminvConfig:
    component: str = "Ez"
    point_x: str = "0"
    point_y: str = "0"
    fcen: str = "0.15"
    df: str = "0.1"
    until_after_sources: str = "200"
    animation_interval: str = "1"
    animation_fps: str = "20"
    output_dir: str = ""
    output_name: str = "harminv_animation.mp4"
    harminv_log_path: str = "harminv.txt"


@dataclass(frozen=True)
class TransmissionSpectrumConfig:
    incident_monitor: str = ""
    transmission_monitor: str = ""
    reflection_monitor: str = ""
    reference_reflection_monitor: str = ""
    until_after_sources: str = "200"
    animate_reference: bool = False
    animate_scattering: bool = False
    animation_component: str = "Ez"
    animation_interval: str = "1"
    animation_fps: str = "20"
    output_dir: str = ""
    output_prefix: str = "transmission"
    reuse_reference_run_id: str = ""
    reuse_reference_csv_name: str = "transmission_spectrum.csv"
    preview_domain: str = "scattering"
    reference_state: TransmissionDomainState = field(default_factory=TransmissionDomainState)


@dataclass(frozen=True)
class FrequencyDomainSolverConfig:
    component: str = "Ez"
    tolerance: str = "1e-8"
    max_iters: str = "10000"
    bicgstab_l: str = "10"
    output_dir: str = ""
    output_name: str = "frequency_domain_field.png"


@dataclass(frozen=True)
class MeepKPointsConfig:
    kpoint_interp: str = "19"
    run_time: str = "300"
    kpoints: list[KPoint] = field(default_factory=list)
    output_dir: str = ""
    output_prefix: str = "meep_k_points"


@dataclass(frozen=True)
class MpbModeSolverConfig:
    lattice_x: str = "1"
    lattice_y: str = "1"
    basis1_x: str = "1"
    basis1_y: str = "0"
    basis2_x: str = "0"
    basis2_y: str = "1"
    num_bands: str = "1"
    resolution: str = "16"
    unit_cells: str = "1"
    kpoint_interp: str = "10"
    max_mode_images: str = "64"
    run_tm: bool = True
    run_te: bool = False
    kpoints: list[KPoint] = field(default_factory=list)
    field_kpoints: list[KPoint] = field(default_factory=list)


@dataclass(frozen=True)
class SweepConfig:
    enabled: bool = False
    params: list[SweepParameter] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisConfig:
    kind: str = "field_animation"
    field_animation: FieldAnimationConfig = field(default_factory=FieldAnimationConfig)
    harminv: HarminvConfig = field(default_factory=HarminvConfig)
    transmission_spectrum: TransmissionSpectrumConfig = field(
        default_factory=TransmissionSpectrumConfig
    )
    frequency_domain_solver: FrequencyDomainSolverConfig = field(
        default_factory=FrequencyDomainSolverConfig
    )
    meep_k_points: MeepKPointsConfig = field(default_factory=MeepKPointsConfig)
    mpb_modesolver: MpbModeSolverConfig = field(default_factory=MpbModeSolverConfig)
