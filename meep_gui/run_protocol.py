from __future__ import annotations

from dataclasses import asdict
import importlib
import inspect
import json
from typing import Any, Callable

from .analysis.types import ArtifactResult, PlotResult, RunResult
from .model import ProjectState
from .persistence import state_from_dict

RUN_WORKSPACE_ENV = "MEEP_GUI_RUN_WORKSPACE"


def resolve_run_target(func: Callable[..., object]) -> tuple[str, str] | None:
    module_name = getattr(func, "__module__", "")
    qualname = getattr(func, "__qualname__", "")
    if not module_name or not qualname or "<locals>" in qualname or "<lambda>" in qualname:
        return None
    try:
        target = load_run_target(module_name, qualname)
    except Exception:
        return None
    if target is not func:
        return None
    return module_name, qualname


def load_run_target(module_name: str, qualname: str) -> Callable[..., object]:
    module = importlib.import_module(module_name)
    target: Any = module
    for part in qualname.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise TypeError(f"Run target '{module_name}:{qualname}' is not callable.")
    return target


def supports_publish_result(func: Callable[..., object]) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    return "publish_result" in signature.parameters or any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    )


def invoke_run_target(
    func: Callable[..., object],
    state: ProjectState,
    log: Callable[[str], None],
    cancel_requested: Callable[[], bool],
    *,
    publish_result: Callable[[RunResult], None] | None = None,
) -> object:
    if publish_result is not None and supports_publish_result(func):
        return func(state, log, cancel_requested, publish_result=publish_result)
    return func(state, log, cancel_requested)


def project_state_to_json(state: ProjectState) -> str:
    return json.dumps(asdict(state), separators=(",", ":"), ensure_ascii=False)


def project_state_from_json(text: str) -> ProjectState:
    return state_from_dict(json.loads(text or "{}"))


def artifact_result_to_dict(item: ArtifactResult) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "label": item.label,
        "path": item.path,
        "meta": dict(item.meta),
    }


def artifact_result_from_dict(raw: dict[str, Any]) -> ArtifactResult:
    return ArtifactResult(
        kind=str(raw.get("kind", "artifact")),
        label=str(raw.get("label", "")),
        path=str(raw.get("path", "")),
        meta={str(k): str(v) for k, v in (raw.get("meta", {}) or {}).items()},
    )


def plot_result_to_dict(item: PlotResult) -> dict[str, Any]:
    return {
        "title": item.title,
        "x_label": item.x_label,
        "y_label": item.y_label,
        "csv_path": item.csv_path,
        "png_path": item.png_path,
        "meta": dict(item.meta),
    }


def plot_result_from_dict(raw: dict[str, Any]) -> PlotResult:
    return PlotResult(
        title=str(raw.get("title", "Plot")),
        x_label=str(raw.get("x_label", "x")),
        y_label=str(raw.get("y_label", "y")),
        csv_path=str(raw.get("csv_path", "")),
        png_path=str(raw.get("png_path", "")),
        meta={str(k): str(v) for k, v in (raw.get("meta", {}) or {}).items()},
    )


def run_result_to_dict(result: RunResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "message": result.message,
        "artifacts": [artifact_result_to_dict(item) for item in result.artifacts],
        "plots": [plot_result_to_dict(item) for item in result.plots],
        "meta": dict(result.meta),
    }


def run_result_from_dict(raw: dict[str, Any]) -> RunResult:
    return RunResult(
        run_id=str(raw.get("run_id", "")),
        status=str(raw.get("status", "completed")),
        message=str(raw.get("message", "")),
        artifacts=[
            artifact_result_from_dict(item)
            for item in raw.get("artifacts", [])
            if isinstance(item, dict)
        ],
        plots=[
            plot_result_from_dict(item)
            for item in raw.get("plots", [])
            if isinstance(item, dict)
        ],
        meta={str(k): str(v) for k, v in (raw.get("meta", {}) or {}).items()},
    )


def encode_event(event_type: str, **payload: Any) -> str:
    return json.dumps(
        {
            "type": event_type,
            **payload,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
