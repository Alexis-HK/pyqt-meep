from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..scene.types import CompilationContext, MediumSpec, MonitorSpec, SceneObject, SourceSpec

SceneEvalFn = Callable[[str, "CompilationContext", str], float]


@dataclass(frozen=True)
class PrimitiveField:
    field_id: str
    label: str
    default: str = ""


@dataclass(frozen=True)
class MaterialKindSpec:
    kind_id: str
    display_name: str
    fields: tuple[PrimitiveField, ...]
    compile_scene_medium: Callable[[Any], "MediumSpec"]
    resolve_index: Callable[["MediumSpec", "CompilationContext", SceneEvalFn], float]
    emit_script_medium: Callable[["MediumSpec"], tuple[str, ...]]


@dataclass(frozen=True)
class GeometryKindSpec:
    kind_id: str
    display_name: str
    fields: tuple[PrimitiveField, ...]
    compile_scene_object: Callable[[Any], "SceneObject"]
    to_shape: Callable[["SceneObject", float, "CompilationContext", SceneEvalFn], Any]
    emit_script_object: Callable[[str, int, "SceneObject"], tuple[str, ...]]
    build_mpb_object: Callable[["SceneObject", Any, Any, "CompilationContext", SceneEvalFn], Any]


@dataclass(frozen=True)
class SourceKindSpec:
    kind_id: str
    display_name: str
    fields: tuple[PrimitiveField, ...]
    compile_scene_source: Callable[[Any], "SourceSpec"]
    to_runtime_source: Callable[["SourceSpec", "CompilationContext", SceneEvalFn], Any]
    emit_script_source: Callable[[str, int, "SourceSpec"], tuple[str, ...]]


@dataclass(frozen=True)
class MonitorKindSpec:
    kind_id: str
    display_name: str
    fields: tuple[PrimitiveField, ...]
    compile_scene_monitor: Callable[[Any], "MonitorSpec"]
    to_flux_spec: Callable[["MonitorSpec", "CompilationContext", SceneEvalFn], Any]
    script_add_flux_expr: Callable[[str, "MonitorSpec"], str]

