from __future__ import annotations

from ...model import ProjectState
from ...scene import compile_project_scene
from ...script.analyses import emit_field_animation as emit_field_animation_script
from ..field_animation import run_field_animation_impl
from ..types import CancelFn, LogFn, RunResult, RuntimePlan, ScriptPlan
from .base import BaseRecipe


class FieldAnimationRecipe(BaseRecipe):
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

    def run(
        self,
        state: ProjectState,
        plan: RuntimePlan,
        log: LogFn,
        cancel_requested: CancelFn,
        *,
        deps,
    ) -> RunResult:
        return run_field_animation_impl(state, log, cancel_requested, deps=deps)

    def emit_script(self, state: ProjectState, plan: ScriptPlan, lines: list[str]) -> None:
        emit_field_animation_script(lines, state.analysis.field_animation)
