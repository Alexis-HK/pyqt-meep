from __future__ import annotations

from ...model import ProjectState
from ...scene import compile_project_scene
from ...script.analyses import emit_harminv as emit_harminv_script
from ..harminv import run_harminv_impl
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
from .capabilities import extract_scene_features


class HarminvRecipe(BaseRecipe):
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
            SceneFeature.CUSTOM_TEMPORAL_SOURCES: SupportStatus.FORBIDDEN,
        }

    def validate(
        self,
        state: ProjectState,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        if not state.analysis.harminv.monitors:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Harminv requires at least one monitor.",
                    code="harminv:monitors",
                )
            )
        features = extract_scene_features(scene=plan.scene, transmission=plan.transmission)
        if SceneFeature.CUSTOM_TEMPORAL_SOURCES in features:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=(
                        "Harminv requires Gaussian (pulsed) sources. "
                        "Custom temporal sources are not supported."
                    ),
                    code="harminv:custom_source",
                    feature=SceneFeature.CUSTOM_TEMPORAL_SOURCES.value,
                ),
            )
        if SceneFeature.CONTINUOUS_SOURCES in features:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Harminv requires Gaussian (pulsed) sources. Continuous sources are not supported.",
                    code="harminv:source_kind",
                    feature=SceneFeature.CONTINUOUS_SOURCES.value,
                ),
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
        return run_harminv_impl(state, log, cancel_requested, deps=deps)

    def emit_script(self, state: ProjectState, plan: ScriptPlan, lines: list[str]) -> None:
        emit_harminv_script(lines, state.analysis.harminv)
