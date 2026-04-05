from __future__ import annotations

from .base import PrimitiveField, SourceKindSpec

SOURCE_REGISTRY: dict[str, SourceKindSpec]


def _compile_continuous_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="continuous",
        component=getattr(item, "component", "Ez"),
        center_x_expr=props.get("center_x", "0"),
        center_y_expr=props.get("center_y", "0"),
        size_x_expr=props.get("size_x", "0"),
        size_y_expr=props.get("size_y", "0"),
        frequency_expr=props.get("fcen", "0.15"),
        bandwidth_expr="0",
    )


def _compile_gaussian_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="gaussian",
        component=getattr(item, "component", "Ez"),
        center_x_expr=props.get("center_x", "0"),
        center_y_expr=props.get("center_y", "0"),
        size_x_expr=props.get("size_x", "0"),
        size_y_expr=props.get("size_y", "0"),
        frequency_expr=props.get("fcen", "0.15"),
        bandwidth_expr=props.get("df", "0.1"),
    )


def _continuous_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec

    return SourceSpec(
        kind="continuous",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        frequency=eval_required(src.frequency_expr, context, "fcen"),
        bandwidth=0.0,
        component=src.component,
    )


def _gaussian_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec

    return SourceSpec(
        kind="gaussian",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        frequency=eval_required(src.frequency_expr, context, "fcen"),
        bandwidth=eval_required(src.bandwidth_expr, context, "df"),
        component=src.component,
    )


def _emit_continuous_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    name = f"{var_name}_{idx}"
    return (
        f"{name} = mp.Source(mp.ContinuousSource(frequency={src.frequency_expr}), "
        f"component=mp.{src.component}, center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}), "
        f"size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0))",
        f"{var_name}.append({name})",
    )


def _emit_gaussian_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    name = f"{var_name}_{idx}"
    return (
        f"{name} = mp.Source(mp.GaussianSource(frequency={src.frequency_expr}, fwidth={src.bandwidth_expr}), "
        f"component=mp.{src.component}, center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}), "
        f"size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0))",
        f"{var_name}.append({name})",
    )


SOURCE_REGISTRY = {
    "continuous": SourceKindSpec(
        kind_id="continuous",
        display_name="Continuous",
        fields=(
            PrimitiveField("center_x", "Center X"),
            PrimitiveField("center_y", "Center Y"),
            PrimitiveField("size_x", "Size X"),
            PrimitiveField("size_y", "Size Y"),
            PrimitiveField("fcen", "Frequency"),
        ),
        compile_scene_source=_compile_continuous_source,
        to_runtime_source=_continuous_to_runtime_source,
        emit_script_source=_emit_continuous_script,
    ),
    "gaussian": SourceKindSpec(
        kind_id="gaussian",
        display_name="Gaussian",
        fields=(
            PrimitiveField("center_x", "Center X"),
            PrimitiveField("center_y", "Center Y"),
            PrimitiveField("size_x", "Size X"),
            PrimitiveField("size_y", "Size Y"),
            PrimitiveField("fcen", "Frequency"),
            PrimitiveField("df", "Bandwidth"),
        ),
        compile_scene_source=_compile_gaussian_source,
        to_runtime_source=_gaussian_to_runtime_source,
        emit_script_source=_emit_gaussian_script,
    ),
}


def source_kind(kind: str) -> SourceKindSpec:
    try:
        return SOURCE_REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported source kind: {kind}") from exc

