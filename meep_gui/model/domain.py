from __future__ import annotations

from dataclasses import dataclass, field

from .constants import PML_MODES, SYMMETRY_DIRECTIONS, SYMMETRY_KINDS
from .objects import FluxMonitorConfig, GeometryItem, SourceItem, SymmetryItem


@dataclass(frozen=True)
class Domain:
    cell_x: str = "10"
    cell_y: str = "10"
    resolution: str = "20"
    pml_width: str = "1"
    pml_mode: str = "both"
    symmetry_enabled: bool = False
    symmetries: list[SymmetryItem] = field(default_factory=list)


@dataclass
class TransmissionDomainState:
    domain: Domain = field(default_factory=Domain)
    geometries: list[GeometryItem] = field(default_factory=list)
    sources: list[SourceItem] = field(default_factory=list)
    flux_monitors: list[FluxMonitorConfig] = field(default_factory=list)


def normalize_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def normalize_domain(domain: Domain) -> Domain:
    pml_mode = domain.pml_mode if domain.pml_mode in PML_MODES else "both"
    normalized_symmetries = [
        SymmetryItem(
            name=item.name,
            kind=item.kind if item.kind in SYMMETRY_KINDS else "mirror",
            direction=item.direction if item.direction in SYMMETRY_DIRECTIONS else "x",
            phase=item.phase,
        )
        for item in domain.symmetries
    ]
    return Domain(
        cell_x=domain.cell_x,
        cell_y=domain.cell_y,
        resolution=domain.resolution,
        pml_width=domain.pml_width,
        pml_mode=pml_mode,
        symmetry_enabled=normalize_bool(domain.symmetry_enabled, False),
        symmetries=normalized_symmetries,
    )
