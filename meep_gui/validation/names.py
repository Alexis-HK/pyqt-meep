from __future__ import annotations

from dataclasses import dataclass
import re

from .errors import ValidationResult

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class NameRegistry:
    parameters: set[str]
    materials: set[str]
    geometries: set[str]
    sources: set[str]

    @classmethod
    def from_state(cls, state: object) -> "NameRegistry":
        params = {getattr(item, "name", "") for item in getattr(state, "parameters", [])}
        mats = {getattr(item, "name", "") for item in getattr(state, "materials", [])}
        geos = {getattr(item, "name", "") for item in getattr(state, "geometries", [])}
        srcs = {getattr(item, "name", "") for item in getattr(state, "sources", [])}
        return cls(parameters=params, materials=mats, geometries=geos, sources=srcs)

    @property
    def all_names(self) -> set[str]:
        names: set[str] = set()
        names.update(self.parameters)
        names.update(self.materials)
        names.update(self.geometries)
        names.update(self.sources)
        return names

    def is_unique(self, name: str, exclude: str | None = None) -> bool:
        if exclude is not None and name == exclude:
            return True
        return name not in self.all_names


def validate_name(name: str, registry: NameRegistry, exclude: str | None = None) -> ValidationResult:
    if not name:
        return ValidationResult(False, "Name is required.")
    if not _NAME_RE.match(name):
        return ValidationResult(
            False,
            "Name must start with a letter or underscore and use only letters, digits, or underscores.",
        )
    if not registry.is_unique(name, exclude=exclude):
        return ValidationResult(False, f"Name '{name}' is already in use.")
    return ValidationResult(True, "")
