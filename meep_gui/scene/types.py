from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MediumKind = Literal["constant", "lossy_narrowband", "dispersive", "nonlinear", "magnetic"]
GeometryKind = Literal["block", "circle", "polygon", "imported_polygon"]
SpatialMaterialKind = Literal["uniform", "function", "grid"]
EvolutionKind = Literal["static", "translate", "rotate", "keyframed", "scripted"]
SourceKind = Literal["continuous", "gaussian"]
MonitorKind = Literal["flux"]


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    expr: str


@dataclass(frozen=True)
class DomainSpec:
    cell_x_expr: str
    cell_y_expr: str
    resolution_expr: str
    pml_width_expr: str
    pml_mode: str


@dataclass(frozen=True)
class SymmetrySpec:
    name: str
    kind: str
    direction: str
    phase_expr: str


@dataclass(frozen=True)
class MediumSpec:
    name: str
    kind: MediumKind = "constant"
    constant_index_expr: str = ""


@dataclass(frozen=True)
class BlockGeometrySpec:
    size_x_expr: str
    size_y_expr: str


@dataclass(frozen=True)
class CircleGeometrySpec:
    radius_expr: str


@dataclass(frozen=True)
class GeometrySpec:
    kind: GeometryKind
    block: BlockGeometrySpec | None = None
    circle: CircleGeometrySpec | None = None


@dataclass(frozen=True)
class SpatialMaterialSpec:
    kind: SpatialMaterialKind = "uniform"
    medium_name: str = ""


@dataclass(frozen=True)
class TransformSpec:
    center_x_expr: str = "0"
    center_y_expr: str = "0"
    rotation_degrees_expr: str = "0"


@dataclass(frozen=True)
class EvolutionSpec:
    kind: EvolutionKind = "static"


@dataclass(frozen=True)
class SceneObject:
    name: str
    geometry: GeometrySpec
    spatial_material: SpatialMaterialSpec
    transform: TransformSpec = field(default_factory=TransformSpec)
    evolution: EvolutionSpec = field(default_factory=EvolutionSpec)


@dataclass(frozen=True)
class SourceSpec:
    name: str
    kind: SourceKind
    component: str
    center_x_expr: str
    center_y_expr: str
    size_x_expr: str
    size_y_expr: str
    frequency_expr: str
    bandwidth_expr: str = "0"


@dataclass(frozen=True)
class MonitorSpec:
    name: str
    kind: MonitorKind
    center_x_expr: str
    center_y_expr: str
    size_x_expr: str
    size_y_expr: str
    fcen_expr: str
    df_expr: str
    nfreq_expr: str


@dataclass(frozen=True)
class SceneSpec:
    name: str = ""
    parameters: tuple[ParameterSpec, ...] = ()
    domain: DomainSpec = field(
        default_factory=lambda: DomainSpec(
            cell_x_expr="10",
            cell_y_expr="10",
            resolution_expr="20",
            pml_width_expr="1",
            pml_mode="both",
        )
    )
    symmetries: tuple[SymmetrySpec, ...] = ()
    media: tuple[MediumSpec, ...] = ()
    objects: tuple[SceneObject, ...] = ()
    sources: tuple[SourceSpec, ...] = ()
    monitors: tuple[MonitorSpec, ...] = ()


@dataclass(frozen=True)
class CompilationContext:
    parameter_values: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CompiledScene:
    scene: SceneSpec
    context: CompilationContext


@dataclass(frozen=True)
class TransmissionSceneBundle:
    scattering: CompiledScene
    reference: CompiledScene
