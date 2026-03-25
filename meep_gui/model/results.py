from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResultArtifact:
    kind: str
    label: str
    path: str
    meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PlotRecord:
    title: str
    x_label: str
    y_label: str
    csv_path: str = ""
    png_path: str = ""
    meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    analysis_kind: str
    status: str = "completed"
    created_at: str = ""
    message: str = ""
    artifacts: list[ResultArtifact] = field(default_factory=list)
    plots: list[PlotRecord] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)
