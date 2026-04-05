from __future__ import annotations

from collections.abc import Mapping

from ...scene import CompiledScene, TransmissionSceneBundle
from ..types import (
    AnalysisBackend,
    AnalysisTarget,
    SceneFeature,
    SupportStatus,
    ValidationIssue,
    ValidationReport,
)

_SEVERITY_ORDER: dict[SupportStatus, int] = {
    SupportStatus.SUPPORTED: 0,
    SupportStatus.IGNORED: 1,
    SupportStatus.FORBIDDEN: 2,
}

_FEATURE_LABELS: dict[SceneFeature, str] = {
    SceneFeature.CONTINUOUS_SOURCES: "continuous sources",
    SceneFeature.GAUSSIAN_SOURCES: "Gaussian (pulsed) sources",
    SceneFeature.FLUX_MONITORS: "flux monitors",
    SceneFeature.DOMAIN_SYMMETRIES: "domain symmetries",
    SceneFeature.TRANSMISSION_REFERENCE_SCENE: "a transmission reference scene",
}

_BACKEND_LABELS: dict[AnalysisBackend, str] = {
    "meep_fdtd": "Meep FDTD",
    "mpb": "MPB",
}

_BACKEND_CAPABILITIES: dict[
    tuple[AnalysisBackend, AnalysisTarget],
    dict[SceneFeature, SupportStatus],
] = {
    ("meep_fdtd", "runtime"): {
        SceneFeature.CONTINUOUS_SOURCES: SupportStatus.SUPPORTED,
        SceneFeature.GAUSSIAN_SOURCES: SupportStatus.SUPPORTED,
        SceneFeature.FLUX_MONITORS: SupportStatus.SUPPORTED,
        SceneFeature.DOMAIN_SYMMETRIES: SupportStatus.SUPPORTED,
        SceneFeature.TRANSMISSION_REFERENCE_SCENE: SupportStatus.SUPPORTED,
    },
    ("meep_fdtd", "script"): {
        SceneFeature.CONTINUOUS_SOURCES: SupportStatus.SUPPORTED,
        SceneFeature.GAUSSIAN_SOURCES: SupportStatus.SUPPORTED,
        SceneFeature.FLUX_MONITORS: SupportStatus.SUPPORTED,
        SceneFeature.DOMAIN_SYMMETRIES: SupportStatus.SUPPORTED,
        SceneFeature.TRANSMISSION_REFERENCE_SCENE: SupportStatus.SUPPORTED,
    },
    ("mpb", "runtime"): {
        SceneFeature.CONTINUOUS_SOURCES: SupportStatus.IGNORED,
        SceneFeature.GAUSSIAN_SOURCES: SupportStatus.IGNORED,
        SceneFeature.FLUX_MONITORS: SupportStatus.IGNORED,
        SceneFeature.DOMAIN_SYMMETRIES: SupportStatus.IGNORED,
        SceneFeature.TRANSMISSION_REFERENCE_SCENE: SupportStatus.FORBIDDEN,
    },
    ("mpb", "script"): {
        SceneFeature.CONTINUOUS_SOURCES: SupportStatus.IGNORED,
        SceneFeature.GAUSSIAN_SOURCES: SupportStatus.IGNORED,
        SceneFeature.FLUX_MONITORS: SupportStatus.IGNORED,
        SceneFeature.DOMAIN_SYMMETRIES: SupportStatus.IGNORED,
        SceneFeature.TRANSMISSION_REFERENCE_SCENE: SupportStatus.FORBIDDEN,
    },
}


def backend_capabilities(
    backend: AnalysisBackend,
    *,
    target: AnalysisTarget,
) -> Mapping[SceneFeature, SupportStatus]:
    return _BACKEND_CAPABILITIES[(backend, target)]


def extract_scene_features(
    *,
    scene: CompiledScene | None = None,
    transmission: TransmissionSceneBundle | None = None,
) -> set[SceneFeature]:
    features: set[SceneFeature] = set()
    scenes = []
    if scene is not None:
        scenes.append(scene.scene)
    if transmission is not None:
        scenes.append(transmission.scattering.scene)
        scenes.append(transmission.reference.scene)
        features.add(SceneFeature.TRANSMISSION_REFERENCE_SCENE)

    for compiled_scene in scenes:
        if any(source.kind == "continuous" for source in compiled_scene.sources):
            features.add(SceneFeature.CONTINUOUS_SOURCES)
        if any(source.kind == "gaussian" for source in compiled_scene.sources):
            features.add(SceneFeature.GAUSSIAN_SOURCES)
        if compiled_scene.monitors:
            features.add(SceneFeature.FLUX_MONITORS)
        if compiled_scene.symmetries:
            features.add(SceneFeature.DOMAIN_SYMMETRIES)
    return features


def validate_capabilities(
    *,
    backend: AnalysisBackend,
    target: AnalysisTarget,
    features: set[SceneFeature],
    recipe_profile: Mapping[SceneFeature, SupportStatus],
) -> ValidationReport:
    report = ValidationReport()
    backend_profile = backend_capabilities(backend, target=target)
    target_label = "runtime" if target == "runtime" else "script export"

    for feature in sorted(features, key=lambda item: item.value):
        backend_status = backend_profile.get(feature, SupportStatus.SUPPORTED)
        recipe_status = recipe_profile.get(feature, SupportStatus.SUPPORTED)
        status = _most_restrictive_status(backend_status, recipe_status)
        if status == SupportStatus.SUPPORTED:
            continue
        owner = _issue_owner(
            backend=backend,
            target=target_label,
            feature=feature,
            backend_status=backend_status,
            recipe_status=recipe_status,
        )
        message = f"{_FEATURE_LABELS[feature].capitalize()} {owner}."
        issue = ValidationIssue(
            severity="error" if status == SupportStatus.FORBIDDEN else "warning",
            message=message,
            code=f"capability:{feature.value}",
            feature=feature.value,
        )
        report = report.extend(issue)
    return report


def _most_restrictive_status(*statuses: SupportStatus) -> SupportStatus:
    return max(statuses, key=_SEVERITY_ORDER.__getitem__)


def _issue_owner(
    *,
    backend: AnalysisBackend,
    target: str,
    feature: SceneFeature,
    backend_status: SupportStatus,
    recipe_status: SupportStatus,
) -> str:
    if recipe_status == SupportStatus.FORBIDDEN:
        return "are not supported by this analysis"
    if recipe_status == SupportStatus.IGNORED:
        return "are ignored by this analysis"
    backend_label = _BACKEND_LABELS[backend]
    if backend_status == SupportStatus.FORBIDDEN:
        return f"are not supported by the {backend_label} {target} path"
    if backend_status == SupportStatus.IGNORED:
        return f"are ignored by the {backend_label} {target} path"
    return "are not supported"
