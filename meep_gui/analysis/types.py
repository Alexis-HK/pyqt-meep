from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

LogFn = Callable[[str], None]
CancelFn = Callable[[], bool]
PublishFn = Callable[["RunResult"], None]


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
