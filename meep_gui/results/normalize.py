from __future__ import annotations

import json
import os

from ..analysis.types import ArtifactResult, PlotResult, RunResult
from ..model.results import PlotRecord, ResultArtifact, RunRecord
from .types import (
    AnimationArtifact,
    ArtifactDisplayEntry,
    CurveArtifact,
    GeneratedScriptArtifact,
    ImageArtifact,
    MetadataArtifact,
    RawDataArtifact,
    ScalarMetricArtifact,
    TableArtifact,
    TextArtifact,
    TypedArtifact,
)

_ANIMATION_KINDS = {"animation_mp4"}
_IMAGE_KINDS = {
    "plot_png",
    "frequency_domain_field_png",
    "mpb_band_png",
    "mpb_epsilon_png",
    "mpb_mode_png",
    "domain_preview_png",
}
_TABLE_KINDS = {"plot_csv", "transmission_csv", "frequency_domain_field_csv", "mpb_band_csv"}
_TEXT_KINDS = {"text", "harminv_text"}
_SCRIPT_KINDS = {"generated_script"}


def typed_artifacts_from_run_record(run: RunRecord) -> tuple[TypedArtifact, ...]:
    return _normalize_legacy_outputs(run.artifacts, run.plots)


def typed_artifacts_from_run_result(result: RunResult) -> tuple[TypedArtifact, ...]:
    return _normalize_legacy_outputs(result.artifacts, result.plots)


def display_entries_from_run_record(run: RunRecord) -> tuple[ArtifactDisplayEntry, ...]:
    return display_entries_from_typed_artifacts(typed_artifacts_from_run_record(run))


def display_entries_from_run_result(result: RunResult) -> tuple[ArtifactDisplayEntry, ...]:
    return display_entries_from_typed_artifacts(typed_artifacts_from_run_result(result))


def display_entries_from_typed_artifacts(
    artifacts: tuple[TypedArtifact, ...] | list[TypedArtifact],
) -> tuple[ArtifactDisplayEntry, ...]:
    seen_paths: set[str] = set()
    entries: list[ArtifactDisplayEntry] = []
    for artifact in artifacts:
        for entry in _display_entries_for_artifact(artifact):
            if entry.path:
                normalized = os.path.abspath(entry.path)
                if normalized in seen_paths:
                    continue
                seen_paths.add(normalized)
            entries.append(entry)
    return tuple(entries)


def _normalize_legacy_outputs(
    artifacts: list[ResultArtifact | ArtifactResult],
    plots: list[PlotRecord | PlotResult],
) -> tuple[TypedArtifact, ...]:
    normalized: list[TypedArtifact] = []
    for idx, artifact in enumerate(artifacts):
        normalized.append(_normalize_legacy_artifact(artifact, idx))
    for idx, plot in enumerate(plots):
        normalized.append(_normalize_plot(plot, idx))
    return tuple(normalized)


def _normalize_legacy_artifact(
    artifact: ResultArtifact | ArtifactResult,
    index: int,
) -> TypedArtifact:
    artifact_id = f"artifact:{index}"
    kind = getattr(artifact, "kind", "").strip()
    path = getattr(artifact, "path", "").strip()
    meta = dict(getattr(artifact, "meta", {}) or {})
    label = getattr(artifact, "label", "").strip() or os.path.basename(path) or kind or artifact_id
    inline_text = meta.get("lines", "")
    meta.setdefault("legacy_kind", kind)

    if kind in _ANIMATION_KINDS or path.lower().endswith(".mp4"):
        return AnimationArtifact(artifact_id, label, path=path, meta=meta)
    if kind in _IMAGE_KINDS or path.lower().endswith(".png"):
        return ImageArtifact(artifact_id, label, path=path, meta=meta)
    if kind in _SCRIPT_KINDS:
        return GeneratedScriptArtifact(artifact_id, label, path=path, text=inline_text, meta=meta)
    if kind in _TEXT_KINDS:
        return TextArtifact(artifact_id, label, path=path, text=inline_text, meta=meta)
    if kind in _TABLE_KINDS or path.lower().endswith((".csv", ".tsv")):
        return TableArtifact(artifact_id, label, path=path, text=inline_text, meta=meta)
    if path.lower().endswith((".txt", ".log", ".out", ".dat")):
        return TextArtifact(artifact_id, label, path=path, text=inline_text, meta=meta)
    if path.lower().endswith(".py"):
        return GeneratedScriptArtifact(artifact_id, label, path=path, text=inline_text, meta=meta)
    if inline_text:
        return TextArtifact(artifact_id, label, path=path, text=inline_text, meta=meta)
    return RawDataArtifact(artifact_id, label, path=path, meta=meta)


def _normalize_plot(plot: PlotRecord | PlotResult, index: int) -> CurveArtifact:
    return CurveArtifact(
        artifact_id=f"plot:{index}",
        label=getattr(plot, "title", "").strip() or "Plot",
        x_label=getattr(plot, "x_label", "").strip(),
        y_label=getattr(plot, "y_label", "").strip(),
        csv_path=getattr(plot, "csv_path", "").strip(),
        png_path=getattr(plot, "png_path", "").strip(),
        meta=dict(getattr(plot, "meta", {}) or {}),
    )


def _display_entries_for_artifact(artifact: TypedArtifact) -> tuple[ArtifactDisplayEntry, ...]:
    if isinstance(artifact, CurveArtifact):
        entries: list[ArtifactDisplayEntry] = []
        if artifact.png_path:
            entries.append(
                ArtifactDisplayEntry(
                    entry_id=f"{artifact.artifact_id}:png",
                    artifact_id=artifact.artifact_id,
                    artifact_type=artifact.artifact_type,
                    list_label=f"{artifact.label} (PNG)",
                    label=artifact.label,
                    path=artifact.png_path,
                    preview_kind="image",
                    export_name=os.path.basename(artifact.png_path) or f"{artifact.label}.png",
                    meta=dict(artifact.meta),
                )
            )
        if artifact.csv_path:
            entries.append(
                ArtifactDisplayEntry(
                    entry_id=f"{artifact.artifact_id}:csv",
                    artifact_id=artifact.artifact_id,
                    artifact_type=artifact.artifact_type,
                    list_label=f"{artifact.label} (CSV)",
                    label=artifact.label,
                    path=artifact.csv_path,
                    preview_kind="text",
                    export_name=os.path.basename(artifact.csv_path) or f"{artifact.label}.csv",
                    meta=dict(artifact.meta),
                )
            )
        return tuple(entries)

    if isinstance(artifact, AnimationArtifact):
        return (_single_entry(artifact, path=artifact.path, preview_kind="media"),)
    if isinstance(artifact, ImageArtifact):
        return (_single_entry(artifact, path=artifact.path, preview_kind="image"),)
    if isinstance(artifact, TextArtifact):
        return (_single_entry(artifact, path=artifact.path, text=artifact.text, preview_kind="text"),)
    if isinstance(artifact, GeneratedScriptArtifact):
        return (_single_entry(artifact, path=artifact.path, text=artifact.text, preview_kind="text"),)
    if isinstance(artifact, TableArtifact):
        return (_single_entry(artifact, path=artifact.path, text=artifact.text, preview_kind="text"),)
    if isinstance(artifact, RawDataArtifact):
        return (_single_entry(artifact, path=artifact.path, preview_kind="text"),)
    if isinstance(artifact, ScalarMetricArtifact):
        text = artifact.value if not artifact.units else f"{artifact.value} {artifact.units}".strip()
        return (_single_entry(artifact, text=text, preview_kind="text"),)
    if isinstance(artifact, MetadataArtifact):
        return (
            _single_entry(
                artifact,
                text=json.dumps(artifact.payload, indent=2, sort_keys=True),
                preview_kind="text",
            ),
        )
    return ()


def _single_entry(
    artifact: TypedArtifact,
    *,
    path: str = "",
    text: str = "",
    preview_kind: str = "none",
) -> ArtifactDisplayEntry:
    legacy_kind = artifact.meta.get("legacy_kind", "").strip()
    list_label = f"{legacy_kind}: {artifact.label}" if legacy_kind else artifact.label
    export_name = os.path.basename(path) if path else _default_export_name(artifact)
    return ArtifactDisplayEntry(
        entry_id=artifact.artifact_id,
        artifact_id=artifact.artifact_id,
        artifact_type=artifact.artifact_type,
        list_label=list_label,
        label=artifact.label,
        path=path,
        text=text,
        preview_kind=preview_kind,  # type: ignore[arg-type]
        export_name=export_name,
        meta=dict(artifact.meta),
    )


def _default_export_name(artifact: TypedArtifact) -> str:
    stem = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in artifact.label) or artifact.artifact_id
    suffix = {
        "animation": ".mp4",
        "image": ".png",
        "text": ".txt",
        "generated_script": ".py",
        "table": ".csv",
        "metadata": ".json",
        "scalar_metric": ".txt",
        "curve": ".txt",
        "raw_data": ".dat",
    }.get(artifact.artifact_type, ".dat")
    if stem.lower().endswith(suffix):
        return stem
    return f"{stem}{suffix}"
