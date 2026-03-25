from __future__ import annotations

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


@dataclass
class SourceSpec:
    kind: str
    center_x: float
    center_y: float
    width_x: float = 0.0
    width_y: float = 0.0
    frequency: float = 0.15
    bandwidth: float = 0.0
    component: str = "Ez"


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
    symmetries: list[SymmetrySpec] = field(default_factory=list)
    shapes: list[Shape] = field(default_factory=list)
    sources: list[SourceSpec] = field(default_factory=list)
