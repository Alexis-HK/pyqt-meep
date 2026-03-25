from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Parameter:
    name: str
    expr: str


@dataclass(frozen=True)
class Material:
    name: str
    index_expr: str


@dataclass(frozen=True)
class GeometryItem:
    name: str
    kind: str
    material: str
    props: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceItem:
    name: str
    kind: str
    component: str
    props: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SymmetryItem:
    name: str
    kind: str
    direction: str
    phase: str


@dataclass(frozen=True)
class FluxMonitorConfig:
    name: str = "flux1"
    center_x: str = "0"
    center_y: str = "0"
    size_x: str = "0"
    size_y: str = "1"
    fcen: str = "0.15"
    df: str = "0.1"
    nfreq: str = "50"


@dataclass(frozen=True)
class KPoint:
    kx: str
    ky: str


@dataclass(frozen=True)
class SweepParameter:
    name: str
    start: str
    stop: str
    steps: str
