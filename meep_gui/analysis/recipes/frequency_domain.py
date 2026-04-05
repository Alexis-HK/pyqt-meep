from __future__ import annotations

from ...model import ProjectState
from ...scene import compile_project_scene
from ...script.frequency_domain import emit_frequency_domain as emit_frequency_domain_script
from ..frequency_domain import run_frequency_domain_solver_impl
from ..types import (
    AnalysisTarget,
    CancelFn,
    LogFn,
    RunResult,
    RuntimePlan,
    SceneFeature,
    ScriptPlan,
    SupportStatus,
    ValidationIssue,
)
from .base import BaseRecipe


class FrequencyDomainSolverRecipe(BaseRecipe):
    def build_runtime_plan(self, state: ProjectState) -> RuntimePlan:
        return RuntimePlan(
            recipe_id=self.recipe_id,
            backend=self.backend,
            scene=compile_project_scene(state),
        )

    def build_script_plan(self, state: ProjectState) -> ScriptPlan:
        return ScriptPlan(
            recipe_id=self.recipe_id,
            backend=self.backend,
            scene=compile_project_scene(state),
        )

    def required_capabilities(
        self,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> dict[SceneFeature, SupportStatus]:
        return {
            SceneFeature.GAUSSIAN_SOURCES: SupportStatus.FORBIDDEN,
            SceneFeature.FLUX_MONITORS: SupportStatus.IGNORED,
        }

    def validate(
        self,
        state: ProjectState,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> tuple[ValidationIssue, ...]:
        if any(src.kind != "continuous" for src in state.sources):
            return (
                ValidationIssue(
                    severity="error",
                    message=(
                        "Frequency-domain solver supports only continuous sources. "
                        "Gaussian (pulsed) sources are not supported."
                    ),
                    code="frequency_domain:source_kind",
                    feature=SceneFeature.GAUSSIAN_SOURCES.value,
                ),
            )
        return ()

    def run(
        self,
        state: ProjectState,
        plan: RuntimePlan,
        log: LogFn,
        cancel_requested: CancelFn,
        *,
        deps,
    ) -> RunResult:
        return run_frequency_domain_solver_impl(state, log, cancel_requested, deps=deps)

    def emit_script(self, state: ProjectState, plan: ScriptPlan, lines: list[str]) -> None:
        emit_frequency_domain_script(lines, state)

    def script_force_complex_fields(self, plan: ScriptPlan) -> bool:
        return True

    def script_include_flux_monitors(self, plan: ScriptPlan) -> bool:
        return False

    def script_include_flux_exports(self, plan: ScriptPlan) -> bool:
        return False
