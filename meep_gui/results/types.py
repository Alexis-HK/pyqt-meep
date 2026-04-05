from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ArtifactType = Literal[
    "scalar_metric",
    "curve",
    "table",
    "image",
    "animation",
    "text",
    "generated_script",
    "raw_data",
    "metadata",
]
PreviewKind = Literal["none", "media", "image", "text"]


@dataclass(frozen=True)
class TypedArtifact:
    artifact_id: str
    artifact_type: ArtifactType
    label: str
    meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScalarMetricArtifact(TypedArtifact):
    value: str = ""
    units: str = ""

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        value: str = "",
        units: str = "",
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "scalar_metric")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "units", units)


@dataclass(frozen=True)
class CurveArtifact(TypedArtifact):
    x_label: str = ""
    y_label: str = ""
    csv_path: str = ""
    png_path: str = ""

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        x_label: str = "",
        y_label: str = "",
        csv_path: str = "",
        png_path: str = "",
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "curve")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "x_label", x_label)
        object.__setattr__(self, "y_label", y_label)
        object.__setattr__(self, "csv_path", csv_path)
        object.__setattr__(self, "png_path", png_path)


@dataclass(frozen=True)
class TableArtifact(TypedArtifact):
    path: str = ""
    text: str = ""

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        path: str = "",
        text: str = "",
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "table")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "text", text)


@dataclass(frozen=True)
class ImageArtifact(TypedArtifact):
    path: str = ""

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        path: str = "",
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "image")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "path", path)


@dataclass(frozen=True)
class AnimationArtifact(TypedArtifact):
    path: str = ""

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        path: str = "",
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "animation")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "path", path)


@dataclass(frozen=True)
class TextArtifact(TypedArtifact):
    path: str = ""
    text: str = ""

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        path: str = "",
        text: str = "",
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "text")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "text", text)


@dataclass(frozen=True)
class GeneratedScriptArtifact(TypedArtifact):
    path: str = ""
    text: str = ""

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        path: str = "",
        text: str = "",
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "generated_script")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "text", text)


@dataclass(frozen=True)
class RawDataArtifact(TypedArtifact):
    path: str = ""

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        path: str = "",
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "raw_data")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "path", path)


@dataclass(frozen=True)
class MetadataArtifact(TypedArtifact):
    payload: dict[str, str] = field(default_factory=dict)

    def __init__(
        self,
        artifact_id: str,
        label: str,
        *,
        payload: dict[str, str] | None = None,
        meta: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_type", "metadata")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "meta", dict(meta or {}))
        object.__setattr__(self, "payload", dict(payload or {}))


@dataclass(frozen=True)
class ArtifactDisplayEntry:
    entry_id: str
    artifact_id: str
    artifact_type: ArtifactType
    list_label: str
    label: str
    path: str = ""
    text: str = ""
    preview_kind: PreviewKind = "none"
    export_name: str = ""
    meta: dict[str, str] = field(default_factory=dict)

