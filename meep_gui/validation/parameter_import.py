from __future__ import annotations

from .expressions import validate_numeric_expression
from .names import NameRegistry, validate_name


def parse_parameter_import_text(text: str, registry: NameRegistry) -> list[tuple[str, str]]:
    lines = text.splitlines()
    if not lines:
        raise ValueError("Import file is empty.")

    imported: list[tuple[str, str]] = []
    imported_names: list[str] = []
    base_registry = NameRegistry(
        parameters=set(),
        materials=set(registry.materials),
        geometries=set(registry.geometries),
        sources=set(registry.sources),
    )

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            raise ValueError(f"Line {line_no}: blank lines are not allowed.")

        if "=" not in line:
            raise ValueError(f"Line {line_no}: expected 'name = expression'.")
        name_raw, expr_raw = line.split("=", 1)
        name = name_raw.strip()
        expr = expr_raw.strip()
        if not name or not expr:
            raise ValueError(f"Line {line_no}: expected 'name = expression'.")

        line_registry = NameRegistry(
            parameters=set(imported_names),
            materials=set(base_registry.materials),
            geometries=set(base_registry.geometries),
            sources=set(base_registry.sources),
        )
        name_result = validate_name(name, line_registry)
        if not name_result.ok:
            raise ValueError(f"Line {line_no}: {name_result.message}")

        expr_result = validate_numeric_expression(expr, imported_names)
        if not expr_result.ok:
            raise ValueError(f"Line {line_no}: {expr_result.message}")

        imported.append((name, expr))
        imported_names.append(name)

    return imported
