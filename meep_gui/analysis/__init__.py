from __future__ import annotations

import sys

from ..model import ProjectState
from ..sim.builder import build_sim
from ..sim.imports import import_meep as _import_meep
from ..sim.runner import run_sim
from ..specs import FluxMonitorSpec, HarminvSpec, SimParams, build_flux_specs, build_sim_params
from ..validation import evaluate_parameters
from .common import (
    eval_required as _eval_required,
    export_flux_plots as _export_flux_plots,
    harminv_lines as _harminv_lines,
    run_canceled as _run_canceled,
)
from .mpb import _save_image
from .preparation import (
    emit_validation_warnings,
    prepare_runtime_analysis,
    prepare_runtime_analysis_for_kind,
    raise_for_validation_errors,
)
from .recipes import RECIPE_REGISTRY, get_recipe
from .sweep import run_sweep_impl
from .types import (
    ArtifactResult,
    CancelFn,
    LogFn,
    PlotResult,
    PublishFn,
    RunResult,
    RuntimePlan,
    SceneFeature,
    ScriptPlan,
    SupportStatus,
    ValidationIssue,
    ValidationReport,
)

_build_flux_specs = build_flux_specs
_build_sim_params = build_sim_params


def _import_mpb():
    mp = _import_meep()
    try:
        from meep import mpb
    except Exception as exc:
        raise RuntimeError(f"MPB import failed: {exc}") from exc
    return mp, mpb


def _run_prepared_analysis(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    *,
    prepared,
) -> RunResult:
    emit_validation_warnings(prepared.validation, log)
    raise_for_validation_errors(prepared.validation)
    return prepared.recipe.run(
        state,
        prepared.plan,
        log,
        cancel_requested,
        deps=sys.modules[__name__],
    )


def _run_named_recipe(
    kind: str,
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    prepared = prepare_runtime_analysis_for_kind(kind, state)
    return _run_prepared_analysis(
        state,
        log,
        cancel_requested,
        prepared=prepared,
    )


def run_field_animation(state: ProjectState, log: LogFn, cancel_requested: CancelFn) -> RunResult:
    return _run_named_recipe("field_animation", state, log, cancel_requested)


def run_harminv(state: ProjectState, log: LogFn, cancel_requested: CancelFn) -> RunResult:
    return _run_named_recipe("harminv", state, log, cancel_requested)


def run_transmission_spectrum(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    return _run_named_recipe("transmission_spectrum", state, log, cancel_requested)


def run_frequency_domain_solver(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    return _run_named_recipe("frequency_domain_solver", state, log, cancel_requested)


def run_mpb_modesolver(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    return _run_named_recipe("mpb_modesolver", state, log, cancel_requested)


def run_meep_k_points(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    return _run_named_recipe("meep_k_points", state, log, cancel_requested)


def run_sweep(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    publish_result: PublishFn | None = None,
) -> RunResult:
    return run_sweep_impl(
        state,
        log,
        cancel_requested,
        deps=sys.modules[__name__],
        publish_result=publish_result,
    )


def run_by_kind(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    publish_result: PublishFn | None = None,
) -> RunResult:
    if state.sweep.enabled and state.sweep.params:
        return run_sweep(state, log, cancel_requested, publish_result=publish_result)
    try:
        prepared = prepare_runtime_analysis(state)
    except ValueError as exc:
        message = str(exc)
        if message.startswith("Unsupported analysis kind:"):
            return RunResult(status="failed", message=message)
        raise
    return _run_prepared_analysis(state, log, cancel_requested, prepared=prepared)


__all__ = [
    "ArtifactResult",
    "CancelFn",
    "FluxMonitorSpec",
    "HarminvSpec",
    "LogFn",
    "PlotResult",
    "PublishFn",
    "RECIPE_REGISTRY",
    "RunResult",
    "RuntimePlan",
    "SceneFeature",
    "ScriptPlan",
    "SimParams",
    "SupportStatus",
    "ValidationIssue",
    "ValidationReport",
    "build_flux_specs",
    "build_sim_params",
    "build_sim",
    "emit_validation_warnings",
    "evaluate_parameters",
    "get_recipe",
    "prepare_runtime_analysis",
    "raise_for_validation_errors",
    "run_by_kind",
    "run_field_animation",
    "run_frequency_domain_solver",
    "run_harminv",
    "run_meep_k_points",
    "run_mpb_modesolver",
    "run_sweep",
    "run_transmission_spectrum",
    "_eval_required",
    "_build_flux_specs",
    "_build_sim_params",
    "_export_flux_plots",
    "_harminv_lines",
    "_import_meep",
    "_import_mpb",
    "_run_canceled",
    "_save_image",
    "run_sim",
]
