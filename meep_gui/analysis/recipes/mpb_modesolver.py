from __future__ import annotations

from ...model import ProjectState
from ...scene import compile_project_scene
from ...script.mpb import emit_mpb as emit_mpb_script
from ..mpb import run_mpb_modesolver_impl
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


class MpbModeSolverRecipe(BaseRecipe):
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
            SceneFeature.CONTINUOUS_SOURCES: SupportStatus.IGNORED,
            SceneFeature.GAUSSIAN_SOURCES: SupportStatus.IGNORED,
            SceneFeature.FLUX_MONITORS: SupportStatus.IGNORED,
            SceneFeature.DOMAIN_SYMMETRIES: SupportStatus.IGNORED,
        }

    def validate(
        self,
        state: ProjectState,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> tuple[ValidationIssue, ...]:
        cfg = state.analysis.mpb_modesolver
        if cfg.run_tm or cfg.run_te:
            return ()
        return (
            ValidationIssue(
                severity="error",
                message="Select at least one polarization (TM and/or TE).",
                code="mpb:polarization",
            ),
        )

    def run(
        self,
        state: ProjectState,
        plan: RuntimePlan,
        log: LogFn,
        cancel_requested: CancelFn,
        *,
        deps,
    ) -> RunResult:
        return run_mpb_modesolver_impl(state, log, cancel_requested, deps=deps)

    def emit_script(self, state: ProjectState, plan: ScriptPlan, lines: list[str]) -> None:
        emit_mpb_script(lines, state)

    def uses_fdtd_script_setup(self, plan: ScriptPlan) -> bool:
        return False

    def script_include_flux_exports(self, plan: ScriptPlan) -> bool:
        return False
