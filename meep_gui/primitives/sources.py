from __future__ import annotations

import cmath
from dataclasses import replace

from .base import PrimitiveField, SourceKindSpec

SOURCE_REGISTRY: dict[str, SourceKindSpec]
_TWO_PI = 6.283185307179586
SOURCE_TIME_PROVIDER_KINDS = {"continuous", "gaussian", "custom", "chirped_pulse"}
SOURCE_TIME_REF_KINDS = {"custom", "gaussian_beam", "eigenmode"}
SOURCE_COMPONENT_CHOICES = ("ALL_COMPONENTS", "Ex", "Ey", "Ez", "Hx", "Hy", "Hz")
EIGENMODE_DIRECTION_CHOICES = ("AUTOMATIC", "NO_DIRECTION", "X", "Y", "Z")
EIGENMODE_PARITY_CHOICES = (
    "NO_PARITY",
    "EVEN_Y",
    "ODD_Y",
    "EVEN_Z",
    "ODD_Z",
    "EVEN_Y+EVEN_Z",
    "EVEN_Y+ODD_Z",
    "ODD_Y+EVEN_Z",
    "ODD_Y+ODD_Z",
)


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
        source_time_ref=_prop_text(props, "src", ""),
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


def _compile_eigenmode_source(item):
    from ..scene.types import SourceSpec

    props = getattr(item, "props", {}) or {}
    return SourceSpec(
        name=getattr(item, "name", ""),
        kind="eigenmode",
        component=_prop_text(props, "eig_component", "ALL_COMPONENTS"),
        center_x_expr=_prop_text(props, "center_x", "0"),
        center_y_expr=_prop_text(props, "center_y", "0"),
        size_x_expr=_prop_text(props, "size_x", "0"),
        size_y_expr=_prop_text(props, "size_y", "1"),
        enabled=getattr(item, "enabled", True),
        source_time_ref=_prop_text(props, "src", ""),
        amplitude_expr=_prop_text(props, "amplitude", "1"),
        amp_func_expr=_prop_text(props, "amp_func", ""),
        eig_lattice_size_x_expr=_prop_text(props, "eig_lattice_size_x", ""),
        eig_lattice_size_y_expr=_prop_text(props, "eig_lattice_size_y", ""),
        eig_lattice_center_x_expr=_prop_text(props, "eig_lattice_center_x", "0"),
        eig_lattice_center_y_expr=_prop_text(props, "eig_lattice_center_y", "0"),
        eig_vol_size_x_expr=_prop_text(props, "eig_vol_size_x", ""),
        eig_vol_size_y_expr=_prop_text(props, "eig_vol_size_y", ""),
        eig_vol_center_x_expr=_prop_text(props, "eig_vol_center_x", "0"),
        eig_vol_center_y_expr=_prop_text(props, "eig_vol_center_y", "0"),
        eig_direction=_prop_text(props, "eig_direction", "AUTOMATIC"),
        eig_band_expr=_prop_text(props, "eig_band", "1"),
        eig_kpoint_x_expr=_prop_text(props, "eig_kpoint_x", "0"),
        eig_kpoint_y_expr=_prop_text(props, "eig_kpoint_y", "0"),
        eig_kpoint_z_expr=_prop_text(props, "eig_kpoint_z", "0"),
        eig_match_freq=_prop_bool(props, "eig_match_freq", True),
        eig_parity=_prop_text(props, "eig_parity", "NO_PARITY"),
        eig_resolution_expr=_prop_text(props, "eig_resolution", "0"),
        eig_tolerance_expr=_prop_text(props, "eig_tolerance", "1e-12"),
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
            return evaluator(parameter_values, {"t": t}, rng=context.rng)
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


def _eval_required_int(expr: str, context, eval_required, label: str) -> int:
    value = eval_required(expr, context, label)
    rounded = round(value)
    if abs(value - rounded) > 1e-9:
        raise ValueError(f"{label}: must evaluate to an integer.")
    return int(rounded)


def _optional_region_to_runtime(
    *,
    size_x_expr: str,
    size_y_expr: str,
    center_x_expr: str,
    center_y_expr: str,
    context,
    eval_required,
    label: str,
) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    size_x_text = size_x_expr.strip()
    size_y_text = size_y_expr.strip()
    if not size_x_text and not size_y_text:
        return None, None
    if not size_x_text or not size_y_text:
        raise ValueError(f"{label}: both size_x and size_y are required.")
    center_x_text = center_x_expr.strip() or "0"
    center_y_text = center_y_expr.strip() or "0"
    return (
        (
            eval_required(size_x_text, context, f"{label}.size_x"),
            eval_required(size_y_text, context, f"{label}.size_y"),
        ),
        (
            eval_required(center_x_text, context, f"{label}.center_x"),
            eval_required(center_y_text, context, f"{label}.center_y"),
        ),
    )


def _runtime_amp_func(src, context):
    from ..validation import compile_complex_expression

    if not src.amp_func_expr.strip():
        return None
    evaluator = compile_complex_expression(
        src.amp_func_expr,
        context.parameter_values.keys(),
        extra_names=("x", "y"),
    )
    parameter_values = dict(context.parameter_values)

    def amp_func(x: float, y: float) -> complex:
        try:
            return evaluator(parameter_values, {"x": x, "y": y}, rng=context.rng)
        except ValueError as exc:
            raise ValueError(f"source '{src.name}' amp_func: {exc}") from exc

    return amp_func


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
    from ..validation import evaluate_complex_expression

    if src.source_time is None:
        raise ValueError(f"Source '{src.name}': missing source time.")

    amplitude = evaluate_complex_expression(src.amplitude_expr, context.parameter_values, rng=context.rng)
    return SourceSpec(
        kind="custom",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        component=src.component,
        amplitude=amplitude,
        amp_func=_runtime_amp_func(src, context),
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
        beam_e0_x=evaluate_complex_expression(src.beam_e0_x_expr, context.parameter_values, rng=context.rng),
        beam_e0_y=evaluate_complex_expression(src.beam_e0_y_expr, context.parameter_values, rng=context.rng),
        beam_e0_z=evaluate_complex_expression(src.beam_e0_z_expr, context.parameter_values, rng=context.rng),
    )


def _eigenmode_to_runtime_source(src, context, eval_required):
    from ..specs.simulation import SourceSpec
    from ..validation import evaluate_complex_expression

    if src.source_time is None:
        raise ValueError(f"Eigenmode source '{src.name}' is missing a SourceTime.")

    eig_lattice_size, eig_lattice_center = _optional_region_to_runtime(
        size_x_expr=src.eig_lattice_size_x_expr,
        size_y_expr=src.eig_lattice_size_y_expr,
        center_x_expr=src.eig_lattice_center_x_expr,
        center_y_expr=src.eig_lattice_center_y_expr,
        context=context,
        eval_required=eval_required,
        label="eig_lattice",
    )
    eig_vol_size, eig_vol_center = _optional_region_to_runtime(
        size_x_expr=src.eig_vol_size_x_expr,
        size_y_expr=src.eig_vol_size_y_expr,
        center_x_expr=src.eig_vol_center_x_expr,
        center_y_expr=src.eig_vol_center_y_expr,
        context=context,
        eval_required=eval_required,
        label="eig_vol",
    )
    return SourceSpec(
        kind="eigenmode",
        center_x=eval_required(src.center_x_expr, context, "center_x"),
        center_y=eval_required(src.center_y_expr, context, "center_y"),
        width_x=eval_required(src.size_x_expr, context, "size_x"),
        width_y=eval_required(src.size_y_expr, context, "size_y"),
        component=src.component,
        amplitude=evaluate_complex_expression(src.amplitude_expr, context.parameter_values, rng=context.rng),
        amp_func=_runtime_amp_func(src, context),
        source_time=_source_time_to_runtime(src.source_time, context, eval_required, src.name or "src"),
        eig_lattice_size=eig_lattice_size,
        eig_lattice_center=eig_lattice_center,
        eig_vol_size=eig_vol_size,
        eig_vol_center=eig_vol_center,
        eig_direction=src.eig_direction,
        eig_band=_eval_required_int(src.eig_band_expr, context, eval_required, "eig_band"),
        eig_kpoint=(
            eval_required(src.eig_kpoint_x_expr, context, "eig_kpoint_x"),
            eval_required(src.eig_kpoint_y_expr, context, "eig_kpoint_y"),
            eval_required(src.eig_kpoint_z_expr, context, "eig_kpoint_z"),
        ),
        eig_match_freq=bool(src.eig_match_freq),
        eig_parity=src.eig_parity,
        eig_resolution=_eval_required_int(
            src.eig_resolution_expr,
            context,
            eval_required,
            "eig_resolution",
        ),
        eig_tolerance=eval_required(src.eig_tolerance_expr, context, "eig_tolerance"),
    )


def _maybe_append(var_name: str, item_name: str, enabled: bool) -> tuple[str, ...]:
    if enabled:
        return (f"{var_name}.append({item_name})",)
    return ()


def _mp_constant_expr(value: str) -> str:
    parts = [part.strip() for part in str(value).split("+") if part.strip()]
    if not parts:
        return "mp.NO_PARITY"
    return " + ".join(f"mp.{part}" for part in parts)


def _has_optional_region(size_x_expr: str, size_y_expr: str, *, label: str) -> bool:
    size_x = size_x_expr.strip()
    size_y = size_y_expr.strip()
    if not size_x and not size_y:
        return False
    if not size_x or not size_y:
        raise ValueError(f"{label}: both size_x and size_y are required.")
    return True


def _optional_center_expr(expr: str) -> str:
    return expr.strip() or "0"


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


def _emit_eigenmode_script(var_name: str, idx: int, src) -> tuple[str, ...]:
    if src.source_time is None:
        raise ValueError(f"Eigenmode source '{src.name}' is missing a SourceTime.")

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
        f"{name} = mp.EigenModeSource(",
        f"    src={src_expr},",
        f"    center=mp.Vector3({src.center_x_expr}, {src.center_y_expr}, 0),",
        f"    size=mp.Vector3({src.size_x_expr}, {src.size_y_expr}, 0),",
        f"    component={_mp_constant_expr(src.component)},",
        f"    direction={_mp_constant_expr(src.eig_direction)},",
        f"    eig_band=int({src.eig_band_expr}),",
        f"    eig_kpoint=mp.Vector3({src.eig_kpoint_x_expr}, {src.eig_kpoint_y_expr}, {src.eig_kpoint_z_expr}),",
        f"    eig_match_freq={bool(src.eig_match_freq)},",
        f"    eig_parity={_mp_constant_expr(src.eig_parity)},",
        f"    eig_resolution=int({src.eig_resolution_expr}),",
        f"    eig_tolerance={src.eig_tolerance_expr},",
        f"    amplitude={src.amplitude_expr},",
    ]
    if _has_optional_region(
        src.eig_lattice_size_x_expr,
        src.eig_lattice_size_y_expr,
        label="eig_lattice",
    ):
        source_lines.extend(
            (
                "    eig_lattice_size="
                f"mp.Vector3({src.eig_lattice_size_x_expr}, {src.eig_lattice_size_y_expr}, 0),",
                "    eig_lattice_center="
                f"mp.Vector3({_optional_center_expr(src.eig_lattice_center_x_expr)}, "
                f"{_optional_center_expr(src.eig_lattice_center_y_expr)}, 0),",
            )
        )
    if _has_optional_region(
        src.eig_vol_size_x_expr,
        src.eig_vol_size_y_expr,
        label="eig_vol",
    ):
        source_lines.append(
            "    eig_vol=mp.Volume("
            f"center=mp.Vector3({_optional_center_expr(src.eig_vol_center_x_expr)}, "
            f"{_optional_center_expr(src.eig_vol_center_y_expr)}, 0), "
            f"size=mp.Vector3({src.eig_vol_size_x_expr}, {src.eig_vol_size_y_expr}, 0)),"
        )
    if amp_func_name:
        source_lines.append(f"    amp_func={amp_func_name},")
    source_lines.append(")")
    lines.extend(source_lines)
    lines.extend(_maybe_append(var_name, name, src.enabled))
    return tuple(lines)


def resolve_source_time_references(sources):
    by_name = {item.name: item for item in sources if item.name}
    resolving: set[str] = set()

    def _source_label(item) -> str:
        return {
            "custom": "Custom",
            "gaussian_beam": "Gaussian beam",
            "eigenmode": "Eigenmode",
        }.get(item.kind, "Source")

    def _resolve_source_time(item):
        ref_name = item.source_time_ref.strip()
        if item.kind in SOURCE_TIME_REF_KINDS and ref_name:
            if item.name in resolving:
                raise ValueError(f"{_source_label(item)} source '{item.name}' has a SourceTime cycle.")
            ref = by_name.get(ref_name)
            if ref is None:
                raise ValueError(
                    f"{_source_label(item)} source '{item.name}' references unknown SourceTime '{ref_name}'."
                )
            if ref.kind not in SOURCE_TIME_PROVIDER_KINDS or ref.source_time is None:
                raise ValueError(
                    f"{_source_label(item)} source '{item.name}' can only reference "
                    "continuous, Gaussian, custom, or chirped pulse sources."
                )
            resolving.add(item.name)
            try:
                return _resolve_source_time(ref)
            finally:
                resolving.discard(item.name)
        if item.kind in {"gaussian_beam", "eigenmode"}:
            raise ValueError(
                f"{_source_label(item)} source '{item.name}' requires a SourceTime source."
            )
        if item.source_time is None:
            raise ValueError(f"Source '{item.name}': missing source time.")
        return item.source_time

    resolved = []
    for item in sources:
        ref_name = item.source_time_ref.strip()
        if item.kind not in SOURCE_TIME_REF_KINDS or not ref_name:
            if item.kind in {"gaussian_beam", "eigenmode"}:
                _resolve_source_time(item)
            resolved.append(item)
            continue
        resolved.append(replace(item, source_time=_resolve_source_time(item)))
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
            PrimitiveField(
                "src",
                "SourceTime",
                "",
                value_type="source_ref",
                required=False,
                section="temporal",
            ),
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
    "eigenmode": SourceKindSpec(
        kind_id="eigenmode",
        display_name="Eigenmode",
        fields=(
            PrimitiveField("src", "SourceTime", value_type="source_ref"),
            PrimitiveField("center_x", "Center X", "0"),
            PrimitiveField("center_y", "Center Y", "0"),
            PrimitiveField("size_x", "Size X", "0"),
            PrimitiveField("size_y", "Size Y", "1"),
            PrimitiveField(
                "eig_component",
                "Component",
                "ALL_COMPONENTS",
                value_type="enum",
                choices=SOURCE_COMPONENT_CHOICES,
            ),
            PrimitiveField(
                "eig_direction",
                "Direction",
                "AUTOMATIC",
                value_type="enum",
                choices=EIGENMODE_DIRECTION_CHOICES,
            ),
            PrimitiveField("eig_band", "eig_band", "1", value_type="int"),
            PrimitiveField("eig_kpoint_x", "eig_kpoint X", "0"),
            PrimitiveField("eig_kpoint_y", "eig_kpoint Y", "0"),
            PrimitiveField("eig_kpoint_z", "eig_kpoint Z", "0"),
            PrimitiveField("eig_match_freq", "eig_match_freq", True, value_type="bool"),
            PrimitiveField(
                "eig_parity",
                "eig_parity",
                "NO_PARITY",
                value_type="enum",
                choices=EIGENMODE_PARITY_CHOICES,
            ),
            PrimitiveField("eig_resolution", "eig_resolution", "0", value_type="int"),
            PrimitiveField("eig_tolerance", "eig_tolerance", "1e-12"),
            PrimitiveField("eig_lattice_size_x", "eig_lattice Size X", "", required=False),
            PrimitiveField("eig_lattice_size_y", "eig_lattice Size Y", "", required=False),
            PrimitiveField("eig_lattice_center_x", "eig_lattice Center X", "0", required=False),
            PrimitiveField("eig_lattice_center_y", "eig_lattice Center Y", "0", required=False),
            PrimitiveField("eig_vol_size_x", "eig_vol Size X", "", required=False),
            PrimitiveField("eig_vol_size_y", "eig_vol Size Y", "", required=False),
            PrimitiveField("eig_vol_center_x", "eig_vol Center X", "0", required=False),
            PrimitiveField("eig_vol_center_y", "eig_vol Center Y", "0", required=False),
            PrimitiveField("amplitude", "Amplitude", "1", value_type="complex"),
            PrimitiveField(
                "amp_func",
                "amp_func",
                "",
                value_type="complex",
                required=False,
                allowed_locals=("x", "y"),
            ),
        ),
        compile_scene_source=_compile_eigenmode_source,
        to_runtime_source=_eigenmode_to_runtime_source,
        emit_script_source=_emit_eigenmode_script,
    ),
}


def source_kind(kind: str) -> SourceKindSpec:
    try:
        return SOURCE_REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported source kind: {kind}") from exc
