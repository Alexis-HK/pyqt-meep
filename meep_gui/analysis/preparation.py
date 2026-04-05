from __future__ import annotations

from dataclasses import dataclass

from ..model import ProjectState
from .recipes import extract_scene_features, get_recipe, validate_capabilities
from .recipes.base import AnalysisRecipe
from .types import (
    AnalysisTarget,
    LogFn,
    RuntimePlan,
    ScriptPlan,
    ValidationIssue,
    ValidationReport,
)


@dataclass(frozen=True)
class PreparedRuntimeAnalysis:
    recipe: AnalysisRecipe
    plan: RuntimePlan
    validation: ValidationReport


@dataclass(frozen=True)
class PreparedScriptAnalysis:
    recipe: AnalysisRecipe
    plan: ScriptPlan
    validation: ValidationReport


def prepare_runtime_analysis(state: ProjectState) -> PreparedRuntimeAnalysis:
    return prepare_runtime_analysis_for_kind(state.analysis.kind, state)


def prepare_script_analysis(state: ProjectState) -> PreparedScriptAnalysis:
    return prepare_script_analysis_for_kind(state.analysis.kind, state)


def prepare_runtime_analysis_for_kind(
    kind: str,
    state: ProjectState,
) -> PreparedRuntimeAnalysis:
    recipe = get_recipe(kind)
    plan = recipe.build_runtime_plan(state)
    validation = _validate(state, recipe, plan, target="runtime")
    return PreparedRuntimeAnalysis(recipe=recipe, plan=plan, validation=validation)


def prepare_script_analysis_for_kind(
    kind: str,
    state: ProjectState,
) -> PreparedScriptAnalysis:
    recipe = get_recipe(kind)
    plan = recipe.build_script_plan(state)
    validation = _validate(state, recipe, plan, target="script")
    return PreparedScriptAnalysis(recipe=recipe, plan=plan, validation=validation)


def raise_for_validation_errors(report: ValidationReport) -> None:
    if report.ok:
        return
    raise ValueError(report.errors[0].message)


def emit_validation_warnings(report: ValidationReport, log: LogFn) -> None:
    seen: set[str] = set()
    for issue in report.warnings:
        if issue.message in seen:
            continue
        seen.add(issue.message)
        log(f"Warning: {issue.message}")


def _validate(
    state: ProjectState,
    recipe: AnalysisRecipe,
    plan: RuntimePlan | ScriptPlan,
    *,
    target: AnalysisTarget,
) -> ValidationReport:
    recipe_issues = _normalize_issues(recipe.validate(state, plan, target=target))
    report = ValidationReport().extend(*recipe_issues)
    capability_report = validate_capabilities(
        backend=plan.backend,
        target=target,
        features=extract_scene_features(scene=plan.scene, transmission=plan.transmission),
        recipe_profile=recipe.required_capabilities(plan, target=target),
    )
    return report.extend(
        *_filter_capability_issues(
            recipe_issues,
            (*capability_report.warnings, *capability_report.errors),
        )
    )


def _normalize_issues(issues) -> tuple[ValidationIssue, ...]:
    return tuple(issues or ())


def _filter_capability_issues(
    recipe_issues: tuple[ValidationIssue, ...],
    capability_issues: tuple[ValidationIssue, ...],
) -> tuple[ValidationIssue, ...]:
    covered_features = {issue.feature for issue in recipe_issues if issue.feature}
    if not covered_features:
        return capability_issues
    return tuple(issue for issue in capability_issues if issue.feature not in covered_features)
