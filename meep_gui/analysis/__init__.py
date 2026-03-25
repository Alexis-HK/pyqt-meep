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
    require_continuous_sources as _requires_continuous_sources,
    require_gaussian_sources as _requires_gaussian_sources,
    run_canceled as _run_canceled,
)
from .frequency_domain import run_frequency_domain_solver_impl
from .field_animation import run_field_animation_impl
from .harminv import run_harminv_impl
from .meep_k_points import run_meep_k_points_impl
from .mpb import _save_image, run_mpb_modesolver_impl
from .sweep import run_sweep_impl
from .transmission import run_transmission_spectrum_impl
from .types import ArtifactResult, CancelFn, LogFn, PlotResult, PublishFn, RunResult

_build_flux_specs = build_flux_specs
_build_sim_params = build_sim_params


def _import_mpb():
    mp = _import_meep()
    try:
        from meep import mpb
    except Exception as exc:
        raise RuntimeError(f"MPB import failed: {exc}") from exc
    return mp, mpb


def run_field_animation(state: ProjectState, log: LogFn, cancel_requested: CancelFn) -> RunResult:
    return run_field_animation_impl(state, log, cancel_requested, deps=sys.modules[__name__])


def run_harminv(state: ProjectState, log: LogFn, cancel_requested: CancelFn) -> RunResult:
    return run_harminv_impl(state, log, cancel_requested, deps=sys.modules[__name__])


def run_transmission_spectrum(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    return run_transmission_spectrum_impl(state, log, cancel_requested, deps=sys.modules[__name__])


def run_frequency_domain_solver(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    return run_frequency_domain_solver_impl(state, log, cancel_requested, deps=sys.modules[__name__])


def run_mpb_modesolver(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    return run_mpb_modesolver_impl(state, log, cancel_requested, deps=sys.modules[__name__])


def run_meep_k_points(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
) -> RunResult:
    return run_meep_k_points_impl(state, log, cancel_requested, deps=sys.modules[__name__])


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
    if state.analysis.kind == "field_animation":
        return run_field_animation(state, log, cancel_requested)
    if state.analysis.kind == "harminv":
        return run_harminv(state, log, cancel_requested)
    if state.analysis.kind == "transmission_spectrum":
        return run_transmission_spectrum(state, log, cancel_requested)
    if state.analysis.kind == "frequency_domain_solver":
        return run_frequency_domain_solver(state, log, cancel_requested)
    if state.analysis.kind == "meep_k_points":
        return run_meep_k_points(state, log, cancel_requested)
    if state.analysis.kind == "mpb_modesolver":
        return run_mpb_modesolver(state, log, cancel_requested)
    return RunResult(status="failed", message=f"Unsupported analysis kind: {state.analysis.kind}")


__all__ = [
    "ArtifactResult",
    "CancelFn",
    "FluxMonitorSpec",
    "HarminvSpec",
    "LogFn",
    "PlotResult",
    "PublishFn",
    "RunResult",
    "SimParams",
    "build_flux_specs",
    "build_sim_params",
    "evaluate_parameters",
    "build_sim",
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
    "_requires_continuous_sources",
    "_requires_gaussian_sources",
    "_run_canceled",
    "_save_image",
    "run_sim",
]
