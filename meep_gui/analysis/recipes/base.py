from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from ...model import ProjectState
from ..types import (
    AnalysisBackend,
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


class AnalysisRecipe(Protocol):
    recipe_id: str
    display_name: str
    backend: AnalysisBackend

    def build_runtime_plan(self, state: ProjectState) -> RuntimePlan: ...

    def build_script_plan(self, state: ProjectState) -> ScriptPlan: ...

    def required_capabilities(
        self,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> Mapping[SceneFeature, SupportStatus]: ...

    def validate(
        self,
        state: ProjectState,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> Sequence[ValidationIssue]: ...

    def run(
        self,
        state: ProjectState,
        plan: RuntimePlan,
        log: LogFn,
        cancel_requested: CancelFn,
        *,
        deps,
    ) -> RunResult: ...

    def emit_script(self, state: ProjectState, plan: ScriptPlan, lines: list[str]) -> None: ...

    def uses_fdtd_script_setup(self, plan: ScriptPlan) -> bool: ...

    def script_force_complex_fields(self, plan: ScriptPlan) -> bool: ...

    def script_include_flux_monitors(self, plan: ScriptPlan) -> bool: ...

    def script_include_flux_exports(self, plan: ScriptPlan) -> bool: ...


@dataclass(frozen=True)
class BaseRecipe:
    recipe_id: str
    display_name: str
    backend: AnalysisBackend

    def required_capabilities(
        self,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> Mapping[SceneFeature, SupportStatus]:
        return {}

    def validate(
        self,
        state: ProjectState,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> Sequence[ValidationIssue]:
        return ()

    def uses_fdtd_script_setup(self, plan: ScriptPlan) -> bool:
        return self.backend == "meep_fdtd"

    def script_force_complex_fields(self, plan: ScriptPlan) -> bool:
        return False

    def script_include_flux_monitors(self, plan: ScriptPlan) -> bool:
        return self.uses_fdtd_script_setup(plan)

    def script_include_flux_exports(self, plan: ScriptPlan) -> bool:
        return self.script_include_flux_monitors(plan)
