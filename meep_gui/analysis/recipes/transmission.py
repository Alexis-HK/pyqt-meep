from __future__ import annotations

from ...model import ProjectState
from ...scene import compile_transmission_scenes
from ...script.transmission import emit_transmission as emit_transmission_script
from ..transmission import run_transmission_spectrum_impl
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


class TransmissionSpectrumRecipe(BaseRecipe):
    def build_runtime_plan(self, state: ProjectState) -> RuntimePlan:
        return RuntimePlan(
            recipe_id=self.recipe_id,
            backend=self.backend,
            transmission=compile_transmission_scenes(state),
        )

    def build_script_plan(self, state: ProjectState) -> ScriptPlan:
        return ScriptPlan(
            recipe_id=self.recipe_id,
            backend=self.backend,
            transmission=compile_transmission_scenes(state),
        )

    def required_capabilities(
        self,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> dict[SceneFeature, SupportStatus]:
        return {
            SceneFeature.CONTINUOUS_SOURCES: SupportStatus.FORBIDDEN,
        }

    def validate(
        self,
        state: ProjectState,
        plan: RuntimePlan | ScriptPlan,
        *,
        target: AnalysisTarget,
    ) -> tuple[ValidationIssue, ...]:
        cfg = state.analysis.transmission_spectrum
        issues: list[ValidationIssue] = []
        if any(src.kind == "continuous" for src in state.sources) or any(
            src.kind == "continuous" for src in cfg.reference_state.sources
        ):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=(
                        "Transmission spectrum requires Gaussian (pulsed) sources for broadband normalization. "
                        "Continuous sources are not supported."
                    ),
                    code="transmission:source_kind",
                    feature=SceneFeature.CONTINUOUS_SOURCES.value,
                )
            )
        if not cfg.incident_monitor.strip():
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Incident monitor is required for transmission spectrum.",
                    code="transmission:incident_monitor",
                )
            )
        if not cfg.transmission_monitor.strip():
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Transmission monitor is required for transmission spectrum.",
                    code="transmission:transmission_monitor",
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
        return run_transmission_spectrum_impl(state, log, cancel_requested, deps=deps)

    def emit_script(self, state: ProjectState, plan: ScriptPlan, lines: list[str]) -> None:
        if plan.transmission is None:
            raise ValueError("Transmission script plan is missing the compiled scene bundle.")
        emit_transmission_script(
            lines,
            state,
            plan.transmission.scattering.scene,
            plan.transmission.reference.scene,
        )

    def uses_fdtd_script_setup(self, plan: ScriptPlan) -> bool:
        return False

    def script_include_flux_exports(self, plan: ScriptPlan) -> bool:
        return False
