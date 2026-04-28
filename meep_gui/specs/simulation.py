from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Shape:
    kind: str
    center_x: float = 0.0
    center_y: float = 0.0
    size_x: float = 1.0
    size_y: float = 1.0
    radius: float = 1.0
    eps: float = 12.0
    vertices: list[tuple[float, float]] = field(default_factory=list)
    priority: int = 0


@dataclass
class SourceTimeSpec:
    kind: str
    frequency: float = 0.15
    bandwidth: float = 0.0
    src_func: Callable[[float], complex] | None = None
    start_time: float = -1e20
    end_time: float = 1e20
    is_integrated: bool = False
    center_frequency: float = 0.0
    fwidth: float = 0.0
    chirp_v0: float = 1.0
    chirp_a: float = 0.2
    chirp_b: float = -0.5
    chirp_t0: float = 15.0


@dataclass
class SourceSpec:
    kind: str
    center_x: float
    center_y: float
    width_x: float = 0.0
    width_y: float = 0.0
    component: str = "Ez"
    amplitude: complex = 1 + 0j
    amp_func: Callable[[float, float], complex] | None = None
    source_time: SourceTimeSpec | None = None
    beam_x0_x: float = 0.0
    beam_x0_y: float = 0.0
    beam_kdir_x: float = 0.0
    beam_kdir_y: float = 1.0
    beam_w0: float = 1.0
    beam_e0_x: complex = 0j
    beam_e0_y: complex = 0j
    beam_e0_z: complex = 1 + 0j
    eig_lattice_size: tuple[float, float] | None = None
    eig_lattice_center: tuple[float, float] | None = None
    eig_vol_size: tuple[float, float] | None = None
    eig_vol_center: tuple[float, float] | None = None
    eig_direction: str = "AUTOMATIC"
    eig_band: int = 1
    eig_kpoint: tuple[float, float, float] = (0.0, 0.0, 0.0)
    eig_match_freq: bool = True
    eig_parity: str = "NO_PARITY"
    eig_resolution: int = 0
    eig_tolerance: float = 1e-12

    @property
    def frequency(self) -> float:
        if self.source_time is None:
            return 0.0
        return self.source_time.frequency

    @property
    def bandwidth(self) -> float:
        if self.source_time is None:
            return 0.0
        return self.source_time.bandwidth

    @property
    def source_time_kind(self) -> str:
        if self.source_time is None:
            return ""
        return self.source_time.kind


@dataclass
class HarminvSpec:
    component: str = "Ez"
    center_x: float = 0.0
    center_y: float = 0.0
    frequency: float = 0.15
    bandwidth: float = 0.1


@dataclass
class FluxMonitorSpec:
    name: str
    center_x: float
    center_y: float
    size_x: float
    size_y: float
    fcen: float
    df: float
    nfreq: int


@dataclass
class FluxMonitorResult:
    name: str
    freqs: list[float] = field(default_factory=list)
    values: list[float] = field(default_factory=list)


@dataclass
class SymmetrySpec:
    kind: str
    direction: str
    phase: complex


@dataclass
class SimParams:
    cell_x: float = 28.0
    cell_y: float = 9.0
    resolution: int = 30
    pml: float = 1.0
    pml_x: bool = True
    pml_y: bool = True
    k_point: tuple[float, float, float] | None = None
    cylindrical_enabled: bool = False
    cylindrical_m: float = 0.0
    symmetries: list[SymmetrySpec] = field(default_factory=list)
    shapes: list[Shape] = field(default_factory=list)
    sources: list[SourceSpec] = field(default_factory=list)
