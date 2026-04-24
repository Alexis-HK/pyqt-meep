from __future__ import annotations

import cmath
from dataclasses import replace

from .base import PrimitiveField, SourceKindSpec

SOURCE_REGISTRY: dict[str, SourceKindSpec]
_TWO_PI = 6.283185307179586


def _prop_text(props: dict[str, str | bool], field_id: str, default: str) -> str:
    value = props.get(field_id, default)
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _prop_bool(props: dict[str, str | bool], field_id: str, default: bool = False) -> bool:
    from ..model import normalize_bool

    return normalize_bool(props.get(field_id, default), default)


def _continuous_source_time(item):
    from ..scene.types import SourceTimeSpec

    props = getattr(item, "props", {}) or {}
    return SourceTimeSpec(
        kind="continuous",
        frequency_expr=_prop_text(props, "fcen", "0.15"),
        bandwidth_expr="0",
    )


def _gaussian_source_time(item):
    from ..scene.types import SourceTimeSpec

    props = getattr(item, "props", {}) or {}
    return SourceTimeSpec(
        kind="gaussian",
        frequency_expr=_prop_text(props, "fcen", "0.15"),
        bandwidth_expr=_prop_text(props, "df", "0.1"),
    )


def _custom_source_time(item):
    from ..scene.types import SourceTimeSpec

    props = getattr(item, "props", {}) or {}
    return SourceTimeSpec(
        kind="custom",
        src_func_expr=_prop_text(props, "src_func", "0"),
        start_time_expr=_prop_text(props, "start_time", "-1e20"),
        end_time_expr=_prop_text(props, "end_time", "1e20"),
        is_integrated=_prop_bool(props, "is_integrated", False),
        center_frequency_expr=_prop_text(props, "center_frequency", "0"),
        fwidth_expr=_prop_text(props, "fwidth", "0"),
    )


def _chirped_pulse_source_time(item):
    from ..scene.types import SourceTimeSpec

    props = getattr(item, "props", {}) or {}
    v0_expr = _prop_text(props, "v0", "1.0")
    return SourceTimeSpec(
        kind="chirped_pulse",
        chirp_v0_expr=v0_expr,
        chirp_a_expr=_prop_text(props, "a", "0.2"),
        chirp_b_expr=_prop_text(props, "b", "-0.5"),
        chirp_t0_expr=_prop_text(props, "t0", "15"),
        center_frequency_expr=v0_expr,
    )


def _compile_continuous_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="continuous",
        component=getattr(item, "component", "Ez"),
        center_x_expr=_prop_text(props, "center_x", "0"),
        center_y_expr=_prop_text(props, "center_y", "0"),
        size_x_expr=_prop_text(props, "size_x", "0"),
        size_y_expr=_prop_text(props, "size_y", "0"),
        enabled=getattr(item, "enabled", True),
        source_time=_continuous_source_time(item),
    )


def _compile_gaussian_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="gaussian",
        component=getattr(item, "component", "Ez"),
        center_x_expr=_prop_text(props, "center_x", "0"),
        center_y_expr=_prop_text(props, "center_y", "0"),
        size_x_expr=_prop_text(props, "size_x", "0"),
        size_y_expr=_prop_text(props, "size_y", "0"),
        enabled=getattr(item, "enabled", True),
        source_time=_gaussian_source_time(item),
    )


def _compile_custom_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="custom",
        component=getattr(item, "component", "Ez"),
        center_x_expr=_prop_text(props, "center_x", "0"),
        center_y_expr=_prop_text(props, "center_y", "0"),
        size_x_expr=_prop_text(props, "size_x", "0"),
        size_y_expr=_prop_text(props, "size_y", "0"),
        enabled=getattr(item, "enabled", True),
        amplitude_expr=_prop_text(props, "amplitude", "1"),
        amp_func_expr=_prop_text(props, "amp_func", ""),
        source_time=_custom_source_time(item),
    )


def _compile_chirped_pulse_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="chirped_pulse",
        component=getattr(item, "component", "Ez"),
        center_x_expr=_prop_text(props, "center_x", "0"),
        center_y_expr=_prop_text(props, "center_y", "0"),
        size_x_expr=_prop_text(props, "size_x", "0"),
        size_y_expr=_prop_text(props, "size_y", "0"),
        enabled=getattr(item, "enabled", True),
        source_time=_chirped_pulse_source_time(item),
    )


def _compile_gaussian_beam_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="gaussian_beam",
        component=getattr(item, "component", "Ez"),
        center_x_expr=_prop_text(props, "center_x", "0"),
        center_y_expr=_prop_text(props, "center_y", "0"),
        size_x_expr=_prop_text(props, "size_x", "1"),
        size_y_expr=_prop_text(props, "size_y", "0"),
        enabled=getattr(item, "enabled", True),
        source_time_ref=_prop_text(props, "src", ""),
        beam_x0_x_expr=_prop_text(props, "beam_x0_x", "0"),
        beam_x0_y_expr=_prop_text(props, "beam_x0_y", "0"),
        beam_kdir_x_expr=_prop_text(props, "beam_kdir_x", "0"),
        beam_kdir_y_expr=_prop_text(props, "beam_kdir_y", "1"),
        beam_w0_expr=_prop_text(props, "beam_w0", "1"),
        beam_e0_x_expr=_prop_text(props, "beam_e0_x", "0"),
        beam_e0_y_expr=_prop_text(props, "beam_e0_y", "0"),
        beam_e0_z_expr=_prop_text(props, "beam_e0_z", "1"),
    )


def _source_time_to_runtime(source_time, context, eval_required, label: str):
    from ..specs.simulation import SourceTimeSpec
    from ..validation import compile_complex_expression

    if source_time.kind == "continuous":
        return SourceTimeSpec(
            kind="continuous",
            frequency=eval_required(source_time.frequency_expr, context, f"{label}.fcen"),
            bandwidth=0.0,
        )

    if source_time.kind == "gaussian":
        return SourceTimeSpec(
            kind="gaussian",
            frequency=eval_required(source_time.frequency_expr, context, f"{label}.fcen"),
            bandwidth=eval_required(source_time.bandwidth_expr, context, f"{label}.df"),
        )
    if source_time.kind == "chirped_pulse":
        v0 = eval_required(source_time.chirp_v0_expr, context, f"{label}.v0")
        a = eval_required(source_time.chirp_a_expr, context, f"{label}.a")
        b = eval_required(source_time.chirp_b_expr, context, f"{label}.b")
        t0 = eval_required(source_time.chirp_t0_expr, context, f"{label}.t0")

        def src_func(t: float) -> complex:
            delta = t - t0
            return cmath.exp(1j * _TWO_PI * v0 * delta) * cmath.exp(
                (-a + 1j * b) * delta * delta
            )

        return SourceTimeSpec(
            kind="chirped_pulse",
            frequency=v0,
            bandwidth=0.0,
            src_func=src_func,
            center_frequency=v0,
            chirp_v0=v0,
            chirp_a=a,
            chirp_b=b,
            chirp_t0=t0,
        )

    evaluator = compile_complex_expression(
        source_time.src_func_expr,
        context.parameter_values.keys(),
        extra_names=("t",),
    )
    parameter_values = dict(context.parameter_values)

    def src_func(t: float) -> complex:
        try:
            return evaluator(parameter_values, {"t": t})
        except ValueError as exc:
            raise ValueError(f"{label}.src_func: {exc}") from exc

    center_frequency = eval_required(
        source_time.center_frequency_expr,
        context,
        f"{label}.center_frequency",
    )
    fwidth = eval_required(source_time.fwidth_expr, context, f"{label}.fwidth")
    return SourceTimeSpec(
        kind="custom",
        frequency=center_frequency,
        bandwidth=fwidth,
        src_func=src_func,
        start_time=eval_required(source_time.start_time_expr, context, f"{label}.start_time"),
        end_time=eval_required(source_time.end_time_expr, context, f"{label}.end_time"),
        is_integrated=bool(source_time.is_integrated),
        center_frequency=center_frequency,
        fwidth=fwidth,
    )


def _continuous_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec

    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")
    return SourceSpec(
        kind="continuous",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        component=src.component,
        source_time=_source_time_to_runtime(src.source_time, context, eval_required, src.name or "src"),
    )


def _gaussian_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec

    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")
    return SourceSpec(
        kind="gaussian",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        component=src.component,
        source_time=_source_time_to_runtime(src.source_time, context, eval_required, src.name or "src"),
    )


def _chirped_pulse_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec

    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")
    return SourceSpec(
        kind="chirped_pulse",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        component=src.component,
        source_time=_source_time_to_runtime(src.source_time, context, eval_required, src.name or "src"),
    )


def _custom_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec
    from ..validation import compile_complex_expression, evaluate_complex_expression

    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")

    amplitude = evaluate_complex_expression(src.amplitude_expr, context.parameter_values)
    amp_func = None
    if src.amp_func_expr.strip():
        evaluator = compile_complex_expression(
            src.amp_func_expr,
            context.parameter_values.keys(),
            extra_names=("x", "y"),
        )
        parameter_values = dict(context.parameter_values)

        def amp_func(x: float, y: float) -> complex:
            try:
                return evaluator(parameter_values, {"x": x, "y": y})
            except ValueError as exc:
                raise ValueError(f"source '{src.name}' amp_func: {exc}") from exc

    return SourceSpec(
        kind="custom",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        component=src.component,
        amplitude=amplitude,
        amp_func=amp_func,
        source_time=_source_time_to_runtime(src.source_time, context, eval_required, src.name or "src"),
    )


def _gaussian_beam_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec
    from ..validation import evaluate_complex_expression

    if src.source_time is None:
        raise ValueError(f"Gaussian beam source '{src.name}' is missing a SourceTime.")

    return SourceSpec(
        kind="gaussian_beam",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        component=src.component,
        source_time=_source_time_to_runtime(src.source_time, context, eval_required, src.name or "src"),
        beam_x0_x=eval_required(src.beam_x0_x_expr, context, "beam_x0_x"),
        beam_x0_y=eval_required(src.beam_x0_y_expr, context, "beam_x0_y"),
        beam_kdir_x=eval_required(src.beam_kdir_x_expr, context, "beam_kdir_x"),
        beam_kdir_y=eval_required(src.beam_kdir_y_expr, context, "beam_kdir_y"),
        beam_w0=eval_required(src.beam_w0_expr, context, "beam_w0"),
        beam_e0_x=evaluate_complex_expression(src.beam_e0_x_expr, context.parameter_values),
        beam_e0_y=evaluate_complex_expression(src.beam_e0_y_expr, context.parameter_values),
        beam_e0_z=evaluate_complex_expression(src.beam_e0_z_expr, context.parameter_values),
    )


def _maybe_append(var_name: str, item_name: str, enabled: bool) -> tuple[str, ...]:
    if enabled:
        return (f"{var_name}.append({item_name})",)
    return ()


def _source_time_script_parts(source_time, *, helper_prefix: str) -> tuple[tuple[str, ...], str]:
    if source_time.kind == "continuous":
        return (), f"mp.ContinuousSource(frequency={source_time.frequency_expr})"
    if source_time.kind == "gaussian":
        return (
            (),
            f"mp.GaussianSource(frequency={source_time.frequency_expr}, fwidth={source_time.bandwidth_expr})",
        )
    if source_time.kind == "chirped_pulse":
        helper_name = f"{helper_prefix}_src_func"
        lines = (
            f"def {helper_name}(t):",
            f"    delta = t - ({source_time.chirp_t0_expr})",
            "    return (",
            f"        cmath.exp(1j * {_TWO_PI} * ({source_time.chirp_v0_expr}) * delta)",
            f"        * cmath.exp((-({source_time.chirp_a_expr}) + 1j * ({source_time.chirp_b_expr})) * delta * delta)",
            "    )",
        )
        return (
            lines,
            "mp.CustomSource("
            f"src_func={helper_name}, "
            f"center_frequency={source_time.center_frequency_expr})",
        )

    helper_name = f"{helper_prefix}_src_func"
    lines = (
        f"def {helper_name}(t):",
        f"    return {source_time.src_func_expr}",
    )
    expr = (
        "mp.CustomSource("
        f"src_func={helper_name}, "
        f"start_time={source_time.start_time_expr}, "
        f"end_time={source_time.end_time_expr}, "
        f"is_integrated={bool(source_time.is_integrated)}, "
        f"center_frequency={source_time.center_frequency_expr}, "
        f"fwidth={source_time.fwidth_expr})"
    )
    return lines, expr


def _emit_continuous_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")
    name = f"{var_name}_{idx}"
    _, src_expr = _source_time_script_parts(src.source_time, helper_prefix=f"{name}_time")
    return (
        f"{name} = mp.Source({src_expr}, "
        f"component=mp.{src.component}, center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}), "
        f"size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0))",
        *_maybe_append(var_name, name, src.enabled),
    )


def _emit_gaussian_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")
    name = f"{var_name}_{idx}"
    _, src_expr = _source_time_script_parts(src.source_time, helper_prefix=f"{name}_time")
    return (
        f"{name} = mp.Source({src_expr}, "
        f"component=mp.{src.component}, center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}), "
        f"size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0))",
        *_maybe_append(var_name, name, src.enabled),
    )


def _emit_custom_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")

    name = f"{var_name}_{idx}"
    lines: list[str] = []
    helper_lines, src_expr = _source_time_script_parts(src.source_time, helper_prefix=f"{name}_time")
    lines.extend(helper_lines)
    if helper_lines:
        lines.append("")

    amp_func_name = ""
    if src.amp_func_expr.strip():
        amp_func_name = f"{name}_amp_func"
        lines.extend(
            (
                f"def {amp_func_name}(pos):",
                "    x = pos.x",
                "    y = pos.y",
                f"    return {src.amp_func_expr}",
                "",
            )
        )

    source_lines = [
        f"{name} = mp.Source(",
        f"    {src_expr},",
        f"    component=mp.{src.component},",
        f"    center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}),",
        f"    size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0),",
        f"    amplitude={src.amplitude_expr},",
    ]
    if amp_func_name:
        source_lines.append(f"    amp_func={amp_func_name},")
    source_lines.append(")")
    lines.extend(source_lines)
    lines.extend(_maybe_append(var_name, name, src.enabled))
    return tuple(lines)


def _emit_chirped_pulse_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")

    name = f"{var_name}_{idx}"
    lines: list[str] = []
    helper_lines, src_expr = _source_time_script_parts(src.source_time, helper_prefix=f"{name}_time")
    lines.extend(helper_lines)
    if helper_lines:
        lines.append("")
    lines.extend(
        (
            f"{name} = mp.Source({src_expr}, "
            f"component=mp.{src.component}, center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}), "
            f"size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0))",
        )
    )
    lines.extend(_maybe_append(var_name, name, src.enabled))
    return tuple(lines)


def _emit_gaussian_beam_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    if src.source_time is None:
        raise ValueError(f"Gaussian beam source '{src.name}' is missing a SourceTime.")

    name = f"{var_name}_{idx}"
    lines: list[str] = []
    helper_lines, src_expr = _source_time_script_parts(src.source_time, helper_prefix=f"{name}_time")
    lines.extend(helper_lines)
    if helper_lines:
        lines.append("")
    lines.extend(
        (
            f"{name} = mp.GaussianBeamSource(",
            f"    src={src_expr},",
            f"    center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}, 0),",
            f"    size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0),",
            f"    beam_x0=mp.Vector3({src.beam_x0_x_expr}, {src.beam_x0_y_expr}, 0),",
            f"    beam_kdir=mp.Vector3({src.beam_kdir_x_expr}, {src.beam_kdir_y_expr}, 0),",
            f"    beam_w0={src.beam_w0_expr},",
            f"    beam_E0=mp.Vector3({src.beam_e0_x_expr}, {src.beam_e0_y_expr}, {src.beam_e0_z_expr}),",
            ")",
        )
    )
    lines.extend(_maybe_append(var_name, name, src.enabled))
    return tuple(lines)


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
        if ref.kind not in {"continuous", "gaussian", "custom", "chirped_pulse"} or ref.source_time is None:
            raise ValueError(
                f"Gaussian beam source '{item.name}' can only reference continuous, Gaussian, custom, or chirped pulse sources."
            )
        resolved.append(replace(item, source_time=ref.source_time))
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
    "custom": SourceKindSpec(
        kind_id="custom",
        display_name="Custom",
        fields=(
            PrimitiveField("center_x", "Center X", "0", section="spatial"),
            PrimitiveField("center_y", "Center Y", "0", section="spatial"),
            PrimitiveField("size_x", "Size X", "0", section="spatial"),
            PrimitiveField("size_y", "Size Y", "0", section="spatial"),
            PrimitiveField("amplitude", "Amplitude", "1", value_type="complex", section="spatial"),
            PrimitiveField(
                "amp_func",
                "amp_func",
                "",
                value_type="complex",
                required=False,
                allowed_locals=("x", "y"),
                section="spatial",
            ),
            PrimitiveField(
                "src_func",
                "src_func",
                "0",
                value_type="complex",
                allowed_locals=("t",),
                section="temporal",
            ),
            PrimitiveField("start_time", "Start Time", "-1e20", section="temporal"),
            PrimitiveField("end_time", "End Time", "1e20", section="temporal"),
            PrimitiveField(
                "is_integrated",
                "Is Integrated",
                False,
                value_type="bool",
                section="temporal",
            ),
            PrimitiveField(
                "center_frequency",
                "Center Frequency",
                "0",
                section="temporal",
            ),
            PrimitiveField("fwidth", "Fwidth", "0", section="temporal"),
        ),
        compile_scene_source=_compile_custom_source,
        to_runtime_source=_custom_to_runtime_source,
        emit_script_source=_emit_custom_script,
    ),
    "chirped_pulse": SourceKindSpec(
        kind_id="chirped_pulse",
        display_name="Chirped Pulse",
        fields=(
            PrimitiveField("center_x", "Center X", "0", section="spatial"),
            PrimitiveField("center_y", "Center Y", "0", section="spatial"),
            PrimitiveField("size_x", "Size X", "0", section="spatial"),
            PrimitiveField("size_y", "Size Y", "0", section="spatial"),
            PrimitiveField("v0", "v0", "1.0", section="temporal"),
            PrimitiveField("a", "a", "0.2", section="temporal"),
            PrimitiveField("b", "b", "-0.5", section="temporal"),
            PrimitiveField("t0", "t0", "15", section="temporal"),
        ),
        compile_scene_source=_compile_chirped_pulse_source,
        to_runtime_source=_chirped_pulse_to_runtime_source,
        emit_script_source=_emit_chirped_pulse_script,
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
