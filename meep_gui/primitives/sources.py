from __future__ import annotations

from dataclasses import replace

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
        enabled=getattr(item, "enabled", True),
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
        enabled=getattr(item, "enabled", True),
    )


def _compile_gaussian_beam_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="gaussian_beam",
        component=getattr(item, "component", "Ez"),
        center_x_expr=props.get("center_x", "0"),
        center_y_expr=props.get("center_y", "0"),
        size_x_expr=props.get("size_x", "1"),
        size_y_expr=props.get("size_y", "0"),
        frequency_expr="0.15",
        bandwidth_expr="0",
        enabled=getattr(item, "enabled", True),
        source_time_ref=props.get("src", ""),
        beam_x0_x_expr=props.get("beam_x0_x", "0"),
        beam_x0_y_expr=props.get("beam_x0_y", "0"),
        beam_kdir_x_expr=props.get("beam_kdir_x", "0"),
        beam_kdir_y_expr=props.get("beam_kdir_y", "1"),
        beam_w0_expr=props.get("beam_w0", "1"),
        beam_e0_x_expr=props.get("beam_e0_x", "0"),
        beam_e0_y_expr=props.get("beam_e0_y", "0"),
        beam_e0_z_expr=props.get("beam_e0_z", "1"),
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


def _gaussian_beam_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec
    from ..validation import evaluate_complex_expression

    def eval_complex(expr: str, label: str) -> complex:
        try:
            return evaluate_complex_expression(expr, context.parameter_values)
        except ValueError as exc:
            raise ValueError(f"{label}: {exc}") from exc

    bandwidth = 0.0
    if src.source_time_kind == "gaussian":
        bandwidth = eval_required(src.bandwidth_expr, context, "df")
    elif src.source_time_kind != "continuous":
        raise ValueError(
            f"Gaussian beam source '{src.name}' references an unsupported SourceTime."
        )

    return SourceSpec(
        kind="gaussian_beam",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        frequency=eval_required(src.frequency_expr, context, "fcen"),
        bandwidth=bandwidth,
        component=src.component,
        source_time_kind=src.source_time_kind,
        beam_x0_x=eval_required(src.beam_x0_x_expr, context, "beam_x0_x"),
        beam_x0_y=eval_required(src.beam_x0_y_expr, context, "beam_x0_y"),
        beam_kdir_x=eval_required(src.beam_kdir_x_expr, context, "beam_kdir_x"),
        beam_kdir_y=eval_required(src.beam_kdir_y_expr, context, "beam_kdir_y"),
        beam_w0=eval_required(src.beam_w0_expr, context, "beam_w0"),
        beam_e0_x=eval_complex(src.beam_e0_x_expr, "beam_E0.x"),
        beam_e0_y=eval_complex(src.beam_e0_y_expr, "beam_E0.y"),
        beam_e0_z=eval_complex(src.beam_e0_z_expr, "beam_E0.z"),
    )


def _maybe_append(var_name: str, item_name: str, enabled: bool) -> tuple[str, ...]:
    if enabled:
        return (f"{var_name}.append({item_name})",)
    return ()


def _emit_continuous_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    name = f"{var_name}_{idx}"
    return (
        f"{name} = mp.Source(mp.ContinuousSource(frequency={src.frequency_expr}), "
        f"component=mp.{src.component}, center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}), "
        f"size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0))",
        *_maybe_append(var_name, name, src.enabled),
    )


def _emit_gaussian_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    name = f"{var_name}_{idx}"
    return (
        f"{name} = mp.Source(mp.GaussianSource(frequency={src.frequency_expr}, fwidth={src.bandwidth_expr}), "
        f"component=mp.{src.component}, center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}), "
        f"size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0))",
        *_maybe_append(var_name, name, src.enabled),
    )


def _source_time_expr(src) -> str:
    if src.source_time_kind == "continuous":
        return f"mp.ContinuousSource(frequency={src.frequency_expr})"
    if src.source_time_kind == "gaussian":
        return f"mp.GaussianSource(frequency={src.frequency_expr}, fwidth={src.bandwidth_expr})"
    raise ValueError(f"Gaussian beam source '{src.name}' references an unsupported SourceTime.")


def _emit_gaussian_beam_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    name = f"{var_name}_{idx}"
    return (
        f"{name} = mp.GaussianBeamSource(",
        f"    src={_source_time_expr(src)},",
        f"    center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}, 0),",
        f"    size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0),",
        f"    beam_x0=mp.Vector3({src.beam_x0_x_expr}, {src.beam_x0_y_expr}, 0),",
        f"    beam_kdir=mp.Vector3({src.beam_kdir_x_expr}, {src.beam_kdir_y_expr}, 0),",
        f"    beam_w0={src.beam_w0_expr},",
        f"    beam_E0=mp.Vector3({src.beam_e0_x_expr}, {src.beam_e0_y_expr}, {src.beam_e0_z_expr}),",
        ")",
        *_maybe_append(var_name, name, src.enabled),
    )


def resolve_source_time_references(sources):
    by_name = {item.name: item for item in sources if item.name}
    resolved = []
    for item in sources:
        if item.kind != "gaussian_beam":
            resolved.append(item)
            continue
        ref_name = item.source_time_ref.strip()
        if not ref_name:
            raise ValueError(f"Gaussian beam source '{item.name}' requires a SourceTime source.")
        ref = by_name.get(ref_name)
        if ref is None:
            raise ValueError(
                f"Gaussian beam source '{item.name}' references unknown SourceTime '{ref_name}'."
            )
        if ref.kind not in {"continuous", "gaussian"}:
            raise ValueError(
                f"Gaussian beam source '{item.name}' can only reference continuous or Gaussian sources."
            )
        resolved.append(
            replace(
                item,
                source_time_kind=ref.kind,
                frequency_expr=ref.frequency_expr,
                bandwidth_expr=ref.bandwidth_expr,
            )
        )
    return tuple(resolved)


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
    "gaussian_beam": SourceKindSpec(
        kind_id="gaussian_beam",
        display_name="Gaussian Beam",
        fields=(
            PrimitiveField("src", "SourceTime", value_type="source_ref"),
            PrimitiveField("center_x", "Center X", "0"),
            PrimitiveField("center_y", "Center Y", "0"),
            PrimitiveField("size_x", "Size X", "1"),
            PrimitiveField("size_y", "Size Y", "0"),
            PrimitiveField("beam_x0_x", "Focus X", "0"),
            PrimitiveField("beam_x0_y", "Focus Y", "0"),
            PrimitiveField("beam_kdir_x", "Direction X", "0"),
            PrimitiveField("beam_kdir_y", "Direction Y", "1"),
            PrimitiveField("beam_w0", "Waist Radius", "1"),
            PrimitiveField("beam_e0_x", "E0 X", "0", value_type="complex"),
            PrimitiveField("beam_e0_y", "E0 Y", "0", value_type="complex"),
            PrimitiveField("beam_e0_z", "E0 Z", "1", value_type="complex"),
        ),
        compile_scene_source=_compile_gaussian_beam_source,
        to_runtime_source=_gaussian_beam_to_runtime_source,
        emit_script_source=_emit_gaussian_beam_script,
    ),
}


def source_kind(kind: str) -> SourceKindSpec:
    try:
        return SOURCE_REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported source kind: {kind}") from exc
