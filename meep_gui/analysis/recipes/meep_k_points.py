from __future__ import annotations

from ...model import ProjectState
from ...scene import compile_project_scene
from ...script.meep_k_points import emit_meep_k_points as emit_meep_k_points_script
from ..meep_k_points import run_meep_k_points_impl
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


class MeepKPointsRecipe(BaseRecipe):
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
            SceneFeature.CONTINUOUS_SOURCES: SupportStatus.FORBIDDEN,
            SceneFeature.FLUX_MONITORS: SupportStatus.IGNORED,
        }

    def validate(
        self,
        state: ProjectState,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        if not state.sources:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Meep k points requires at least one Gaussian (pulsed) source.",
                    code="meep_k_points:sources",
                )
            )
        elif any(src.kind == "continuous" for src in state.sources):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=(
                        "Meep k points requires Gaussian (pulsed) sources. "
                        "Continuous sources are not supported."
                    ),
                    code="meep_k_points:source_kind",
                    feature=SceneFeature.CONTINUOUS_SOURCES.value,
                )
            )
        if len(state.analysis.meep_k_points.kpoints) < 2:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Meep k points requires at least two input k-points.",
                    code="meep_k_points:kpoints",
                )
            )
        return tuple(issues)

    def run(
        self,
        state: ProjectState,
        plan: RuntimePlan,
        log: LogFn,
        cancel_requested: CancelFn,
        *,
        deps,
    ) -> RunResult:
        return run_meep_k_points_impl(state, log, cancel_requested, deps=deps)

    def emit_script(self, state: ProjectState, plan: ScriptPlan, lines: list[str]) -> None:
        emit_meep_k_points_script(lines, state)

    def script_include_flux_monitors(self, plan: ScriptPlan) -> bool:
        return False

    def script_include_flux_exports(self, plan: ScriptPlan) -> bool:
        return False
