from __future__ import annotations

from .base import MaterialKindSpec, PrimitiveField

MATERIAL_FIELDS = (
    PrimitiveField("index_expr", "Index"),
)


def _compile_constant_medium(item):
    from ..scene.types import MediumSpec

    return MediumSpec(
        name=getattr(item, "name", ""),
        kind="constant",
        constant_index_expr=getattr(item, "index_expr", ""),
    )


def _resolve_constant_index(medium, context, eval_required):
    return eval_required(medium.constant_index_expr, context, f"material '{medium.name}'")


def _emit_constant_medium(medium) -> tuple[str, ...]:
    if medium.name and medium.constant_index_expr:
        return (
            f"{medium.name} = mp.Medium(index={medium.constant_index_expr})",
            f"materials['{medium.name}'] = {medium.name}",
        )
    return ()


MATERIAL_REGISTRY: dict[str, MaterialKindSpec] = {
    "constant": MaterialKindSpec(
        kind_id="constant",
        display_name="Constant Dielectric",
        fields=MATERIAL_FIELDS,
        compile_scene_medium=_compile_constant_medium,
        resolve_index=_resolve_constant_index,
        emit_script_medium=_emit_constant_medium,
    )
}

DEFAULT_MATERIAL_KIND = "constant"


def material_kind(kind: str) -> MaterialKindSpec:
    try:
        return MATERIAL_REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported material kind: {kind}") from exc

