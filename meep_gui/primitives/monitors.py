from __future__ import annotations

from .base import MonitorKindSpec, PrimitiveField


def _compile_flux_monitor(item):
    from ..scene.types import MonitorSpec

    return MonitorSpec(
        name=getattr(item, "name", ""),
        kind="flux",
        center_x_expr=getattr(item, "center_x", "0"),
        center_y_expr=getattr(item, "center_y", "0"),
        size_x_expr=getattr(item, "size_x", "0"),
        size_y_expr=getattr(item, "size_y", "0"),
        fcen_expr=getattr(item, "fcen", "0.15"),
        df_expr=getattr(item, "df", "0.1"),
        nfreq_expr=getattr(item, "nfreq", "50"),
    )


def _flux_to_spec(item, context, eval_required):
    from ..specs.analysis import FluxMonitorSpec

    size_x = eval_required(item.size_x_expr, context, f"{item.name}.size_x")
    size_y = eval_required(item.size_y_expr, context, f"{item.name}.size_y")
    if abs(size_x) > 1e-12 and abs(size_y) > 1e-12:
        raise ValueError(
            f"Flux monitor '{item.name}' must be a line in 2D. "
            "Set one of size_x or size_y to 0."
        )
    if abs(size_x) <= 1e-12 and abs(size_y) <= 1e-12:
        raise ValueError(
            f"Flux monitor '{item.name}' has zero area and undefined normal direction. "
            "Set exactly one of size_x or size_y to a non-zero value."
        )
    return FluxMonitorSpec(
        name=item.name,
        center_x=eval_required(item.center_x_expr, context, f"{item.name}.center_x"),
        center_y=eval_required(item.center_y_expr, context, f"{item.name}.center_y"),
        size_x=size_x,
        size_y=size_y,
        fcen=eval_required(item.fcen_expr, context, f"{item.name}.fcen"),
        df=eval_required(item.df_expr, context, f"{item.name}.df"),
        nfreq=max(1, int(eval_required(item.nfreq_expr, context, f"{item.name}.nfreq"))),
    )


def _script_add_flux_expr(sim_var: str, mon) -> str:
    return (
        f"{sim_var}.add_flux({mon.fcen_expr}, {mon.df_expr}, int({mon.nfreq_expr}), "
        f"mp.FluxRegion(center=mp.Vector3({mon.center_x_expr}, {mon.center_y_expr}, 0), "
        f"size=mp.Vector3({mon.size_x_expr}, {mon.size_y_expr}, 0)))"
    )


MONITOR_REGISTRY: dict[str, MonitorKindSpec] = {
    "flux": MonitorKindSpec(
        kind_id="flux",
        display_name="Flux Monitor",
        fields=(
            PrimitiveField("center_x", "Center X"),
            PrimitiveField("center_y", "Center Y"),
            PrimitiveField("size_x", "Size X"),
            PrimitiveField("size_y", "Size Y"),
            PrimitiveField("fcen", "fcen"),
            PrimitiveField("df", "df"),
            PrimitiveField("nfreq", "nfreq"),
        ),
        compile_scene_monitor=_compile_flux_monitor,
        to_flux_spec=_flux_to_spec,
        script_add_flux_expr=_script_add_flux_expr,
    )
}

DEFAULT_MONITOR_KIND = "flux"


def monitor_kind(kind: str) -> MonitorKindSpec:
    try:
        return MONITOR_REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported monitor kind: {kind}") from exc

