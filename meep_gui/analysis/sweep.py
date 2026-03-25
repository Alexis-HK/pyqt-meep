from __future__ import annotations

import copy
from dataclasses import dataclass

from ..model import Parameter, ProjectState, SweepParameter
from .types import ArtifactResult, CancelFn, LogFn, PlotResult, PublishFn, RunResult


@dataclass(frozen=True)
class SweepQueueItem:
    name: str
    value: float
    point_index: int
    point_total: int
    queue_index: int
    queue_total: int


def _format_sweep_value(value: float) -> str:
    return f"{value:.12g}"


def _sweep_label(name: str, value: float) -> str:
    return f"{name}={_format_sweep_value(value)}"


def _expand_sweep_values(
    state: ProjectState,
    spec: SweepParameter,
    *,
    deps,
) -> list[float]:
    values, results = deps.evaluate_parameters(state.parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")

    available = {param.name for param in state.parameters if param.name}
    if spec.name not in available:
        raise ValueError(f"Sweep parameter '{spec.name}' is not defined in Parameters.")

    start = deps._eval_required(spec.start, values, f"sweep.{spec.name}.start")
    stop = deps._eval_required(spec.stop, values, f"sweep.{spec.name}.stop")
    step_size = deps._eval_required(spec.steps, values, f"sweep.{spec.name}.steps")
    eps = 1e-12 * max(1.0, abs(start), abs(stop), abs(step_size))

    if abs(start - stop) <= eps:
        return [float(stop)]
    if abs(step_size) <= eps:
        raise ValueError(f"sweep.{spec.name}.steps: step size must be non-zero.")
    if stop > start and step_size <= 0:
        raise ValueError(
            f"sweep.{spec.name}.steps: step size must be positive when stop > start."
        )
    if stop < start and step_size >= 0:
        raise ValueError(
            f"sweep.{spec.name}.steps: step size must be negative when stop < start."
        )

    items: list[float] = []
    current = start
    while True:
        if step_size > 0 and current > stop + eps:
            break
        if step_size < 0 and current < stop - eps:
            break
        if abs(current - stop) <= eps:
            items.append(float(stop))
        else:
            items.append(float(current))
        current += step_size

    if not items:
        raise ValueError(f"Sweep parameter '{spec.name}' produced no sweep points.")
    return items


def _build_sweep_queue(state: ProjectState, *, deps) -> list[SweepQueueItem]:
    seen: set[str] = set()
    expanded: list[tuple[str, list[float]]] = []
    for spec in state.sweep.params:
        if spec.name in seen:
            raise ValueError(f"Sweep parameter '{spec.name}' is already configured.")
        seen.add(spec.name)
        expanded.append((spec.name, _expand_sweep_values(state, spec, deps=deps)))

    queue_total = sum(len(values) for _, values in expanded)
    queue: list[SweepQueueItem] = []
    queue_index = 1
    for name, values in expanded:
        point_total = len(values)
        for point_index, value in enumerate(values, start=1):
            queue.append(
                SweepQueueItem(
                    name=name,
                    value=value,
                    point_index=point_index,
                    point_total=point_total,
                    queue_index=queue_index,
                    queue_total=queue_total,
                )
            )
            queue_index += 1
    return queue


def _apply_sweep_value(state: ProjectState, item: SweepQueueItem) -> ProjectState:
    updated = copy.deepcopy(state)
    updated.sweep = type(updated.sweep)(enabled=False, params=list(updated.sweep.params))

    param_map = {param.name: idx for idx, param in enumerate(updated.parameters)}
    if item.name not in param_map:
        raise ValueError(f"Sweep parameter '{item.name}' is not defined in Parameters.")

    updated.parameters[param_map[item.name]] = Parameter(
        name=item.name,
        expr=_format_sweep_value(item.value),
    )
    return updated


def _decorate_sweep_result(result: RunResult, item: SweepQueueItem) -> RunResult:
    label = _sweep_label(item.name, item.value)
    sweep_meta = {
        "sweep_label": label,
        "sweep_param_name": item.name,
        "sweep_param_value": _format_sweep_value(item.value),
        "sweep_index": str(item.point_index),
        "sweep_total": str(item.point_total),
        "sweep_queue_index": str(item.queue_index),
        "sweep_queue_total": str(item.queue_total),
    }

    artifacts = [
        ArtifactResult(
            kind=artifact.kind,
            label=f"{label} | {artifact.label or artifact.kind}",
            path=artifact.path,
            meta=dict(artifact.meta),
        )
        for artifact in result.artifacts
    ]
    plots = [
        PlotResult(
            title=f"{label} | {plot.title or 'Plot'}",
            x_label=plot.x_label,
            y_label=plot.y_label,
            csv_path=plot.csv_path,
            png_path=plot.png_path,
            meta=dict(plot.meta),
        )
        for plot in result.plots
    ]

    meta = dict(result.meta)
    meta.update(sweep_meta)
    return RunResult(
        run_id=result.run_id,
        status=result.status,
        message=result.message,
        artifacts=artifacts,
        plots=plots,
        meta=meta,
    )


def _summary_result(status: str, message: str, queue_total: int, completed: int) -> RunResult:
    return RunResult(
        status=status,
        message=message,
        meta={
            "skip_store": "1",
            "sweep_queue_total": str(queue_total),
            "sweep_completed": str(completed),
        },
    )


def run_sweep_impl(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    *,
    deps,
    publish_result: PublishFn | None = None,
) -> RunResult:
    if not state.sweep.enabled or not state.sweep.params:
        return RunResult(status="failed", message="Sweep is enabled without any sweep parameters.")

    runner = {
        "field_animation": deps.run_field_animation,
        "harminv": deps.run_harminv,
        "transmission_spectrum": deps.run_transmission_spectrum,
        "frequency_domain_solver": deps.run_frequency_domain_solver,
        "meep_k_points": deps.run_meep_k_points,
        "mpb_modesolver": deps.run_mpb_modesolver,
    }.get(state.analysis.kind)
    if runner is None:
        return RunResult(status="failed", message=f"Unsupported analysis kind: {state.analysis.kind}")

    queue = _build_sweep_queue(state, deps=deps)
    if not queue:
        return RunResult(status="failed", message="Sweep produced no points.")

    publish = publish_result or (lambda _result: None)
    completed = 0

    for item in queue:
        if cancel_requested():
            return _summary_result(
                "canceled",
                f"Sweep canceled after {completed} completed points.",
                len(queue),
                completed,
            )

        label = _sweep_label(item.name, item.value)
        log(
            f"Sweep {item.queue_index}/{item.queue_total}: {label} "
            f"({item.point_index}/{item.point_total} for {item.name})"
        )

        try:
            run_state = _apply_sweep_value(state, item)
            result = runner(run_state, log, cancel_requested)
        except Exception as exc:
            failed = _decorate_sweep_result(
                RunResult(status="failed", message=str(exc)),
                item,
            )
            publish(failed)
            return _summary_result(
                "failed",
                f"Sweep stopped after {label} failed.",
                len(queue),
                completed,
            )

        if result.status == "canceled":
            return _summary_result(
                "canceled",
                f"Sweep canceled after {completed} completed points.",
                len(queue),
                completed,
            )

        decorated = _decorate_sweep_result(result, item)
        publish(decorated)

        if decorated.status == "failed":
            return _summary_result(
                "failed",
                f"Sweep stopped after {label} failed.",
                len(queue),
                completed,
            )

        completed += 1
        if cancel_requested():
            return _summary_result(
                "canceled",
                f"Sweep canceled after {completed} completed points.",
                len(queue),
                completed,
            )

    return _summary_result("completed", "Sweep completed.", len(queue), completed)
