from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable, Literal

if TYPE_CHECKING:
    from ..scene import CompiledScene, TransmissionSceneBundle

LogFn = Callable[[str], None]
CancelFn = Callable[[], bool]
PublishFn = Callable[["RunResult"], None]

AnalysisTarget = Literal["runtime", "script"]
AnalysisBackend = Literal["meep_fdtd", "mpb"]
IssueSeverity = Literal["warning", "error"]


class SupportStatus(str, Enum):
    SUPPORTED = "supported"
    IGNORED = "ignored"
    FORBIDDEN = "forbidden"


class SceneFeature(str, Enum):
    CONTINUOUS_SOURCES = "continuous_sources"
    GAUSSIAN_SOURCES = "gaussian_sources"
    FLUX_MONITORS = "flux_monitors"
    DOMAIN_SYMMETRIES = "domain_symmetries"
    TRANSMISSION_REFERENCE_SCENE = "transmission_reference_scene"


@dataclass(frozen=True)
class ValidationIssue:
    severity: IssueSeverity
    message: str
    code: str = ""
    feature: str = ""


@dataclass(frozen=True)
class ValidationReport:
    warnings: tuple[ValidationIssue, ...] = ()
    errors: tuple[ValidationIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, *issues: ValidationIssue) -> "ValidationReport":
        warning_items = list(self.warnings)
        error_items = list(self.errors)
        for issue in issues:
            if issue.severity == "error":
                error_items.append(issue)
            else:
                warning_items.append(issue)
        return ValidationReport(warnings=tuple(warning_items), errors=tuple(error_items))

    def messages(self, severity: IssueSeverity | None = None) -> tuple[str, ...]:
        if severity == "warning":
            return tuple(item.message for item in self.warnings)
        if severity == "error":
            return tuple(item.message for item in self.errors)
        return tuple(item.message for item in (*self.warnings, *self.errors))


@dataclass(frozen=True)
class RuntimePlan:
    recipe_id: str
    backend: AnalysisBackend
    scene: "CompiledScene | None" = None
    transmission: "TransmissionSceneBundle | None" = None


@dataclass(frozen=True)
class ScriptPlan:
    recipe_id: str
    backend: AnalysisBackend
    scene: "CompiledScene | None" = None
    transmission: "TransmissionSceneBundle | None" = None


@dataclass
class ArtifactResult:
    kind: str
    label: str
    path: str
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class PlotResult:
    title: str
    x_label: str
    y_label: str
    csv_path: str = ""
    png_path: str = ""
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class RunResult:
    run_id: str = ""
    status: str = "completed"
    message: str = ""
    artifacts: list[ArtifactResult] = field(default_factory=list)
    plots: list[PlotResult] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)
