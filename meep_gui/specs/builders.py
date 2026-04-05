from __future__ import annotations

from ..model import ProjectState
from ..scene import CompilationContext, compile_project_scene, scene_to_flux_specs, scene_to_sim_params
from ..specs.simulation import FluxMonitorSpec, SimParams
from ..validation import evaluate_numeric_expression


def _eval_required(expr: str, values: dict[str, float], label: str) -> float:
    try:
        return evaluate_numeric_expression(expr, values)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def build_sim_params(state: ProjectState) -> SimParams:
    compiled = compile_project_scene(state)
    return scene_to_sim_params(compiled.scene, compiled.context)


def build_flux_specs(state: ProjectState, values: dict[str, float]) -> list[FluxMonitorSpec]:
    compiled = compile_project_scene(state, parameter_values=values)
    context = CompilationContext(parameter_values=dict(values))
    return scene_to_flux_specs(compiled.scene, context)
