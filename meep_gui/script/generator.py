from __future__ import annotations

from ..analysis.preparation import (
    emit_validation_warnings,
    prepare_script_analysis,
    raise_for_validation_errors,
)
from ..analysis.types import LogFn, ScriptPlan
from ..model import ProjectState
from ..primitives import monitor_kind
from .analyses import emit_flux_exports
from .common import line
from .simulation import (
    emit_geometry,
    emit_materials,
    emit_sources,
    emit_symmetries,
)


def _emit_header(lines: list[str], plan: ScriptPlan) -> None:
    line(lines, "from math import sqrt, exp, sin, cos, tan, log, log10")
    line(lines, "import csv")
    line(lines, "import os")
    line(lines, "import meep as mp")
    if plan.backend == "mpb":
        line(lines, "from meep import mpb")
    line(lines)
    line(lines, "script_dir = os.path.dirname(os.path.abspath(__file__))")
    line(lines)


def _primary_scene(plan: ScriptPlan):
    if plan.transmission is not None:
        return plan.transmission.scattering.scene
    if plan.scene is not None:
        return plan.scene.scene
    raise ValueError("Script plan does not include a compiled scene.")


def _parameter_specs(scene) -> tuple[tuple[str, str], ...]:
    return tuple(
        (param.name, param.expr)
        for param in scene.parameters
        if getattr(param, "name", "") and getattr(param, "expr", "")
    )


def _indent_block(block: list[str], level: int = 1) -> list[str]:
    prefix = "    " * level
    return [f"{prefix}{text}" if text else "" for text in block]


def _default_output_dir_expr(kind: str) -> str:
    return {
        "field_animation": "script_dir",
        "harminv": "os.path.join(script_dir, 'harminv_outputs')",
        "transmission_spectrum": "os.path.join(script_dir, 'transmission_outputs')",
        "frequency_domain_solver": "os.path.join(script_dir, 'frequency_domain_outputs')",
        "meep_k_points": "os.path.join(script_dir, 'meep_k_points_outputs')",
        "mpb_modesolver": "os.path.join(script_dir, 'mpb_outputs')",
    }.get(kind, "script_dir")


def _emit_geometry_and_sources(lines: list[str], scene) -> None:
    line(lines, "# Geometry")
    if scene.objects:
        emit_geometry(lines, "geometry", scene.objects)
        line(lines)
    else:
        line(lines, "geometry = []")
        line(lines)

    line(lines, "# Sources")
    if scene.sources:
        emit_sources(lines, "sources", scene.sources)
        line(lines)
    else:
        line(lines, "sources = []")
        line(lines)


def _emit_fdtd_setup(
    lines: list[str],
    scene,
    *,
    enabled: bool,
    force_complex_fields: bool = False,
    include_flux_monitors: bool = True,
) -> None:
    if not enabled:
        return

    line(lines, "# Simulation")
    line(lines, "boundary_layers = []")
    pml = scene.domain.pml_width_expr
    if scene.domain.pml_mode in {"x", "both"}:
        line(lines, f"boundary_layers.append(mp.PML(thickness={pml}, direction=mp.X))")
    if scene.domain.pml_mode in {"y", "both"}:
        line(lines, f"boundary_layers.append(mp.PML(thickness={pml}, direction=mp.Y))")
    emit_symmetries(lines, "symmetries", scene.symmetries)
    force_complex_arg = ", force_complex_fields=True" if force_complex_fields else ""
    line(
        lines,
        "sim = mp.Simulation("
        f"cell_size=mp.Vector3({scene.domain.cell_x_expr}, {scene.domain.cell_y_expr}, 0), "
        "boundary_layers=boundary_layers, geometry=geometry, sources=sources, "
        "symmetries=symmetries, "
        f"resolution={scene.domain.resolution_expr}{force_complex_arg})",
    )
    line(lines)

    if include_flux_monitors and scene.monitors:
        line(lines, "# Flux monitors")
        line(lines, "flux_monitors = []")
        for mon in scene.monitors:
            line(
                lines,
                "flux_monitors.append(("
                f"'{mon.name}', "
                f"{monitor_kind(mon.kind).script_add_flux_expr('sim', mon)}"
                "))",
            )
        line(lines)


def _emit_runtime_helpers(
    lines: list[str],
    scene,
    *,
    include_sweep_helpers: bool,
) -> None:
    params = _parameter_specs(scene)

    for text in (
        "def _eval_numeric(expr, scope):",
        "    env = dict(globals())",
        "    env.update(scope)",
        "    return eval(str(expr), {'__builtins__': {}}, env)",
        "",
        "def _build_parameter_values(overrides=None):",
        "    parameter_overrides = dict(overrides or {})",
        "    parameter_values = {}",
    ):
        line(lines, text)
    for name, expr in params:
        for text in (
            f"    if {name!r} in parameter_overrides:",
            f"        parameter_values[{name!r}] = _eval_numeric(str(parameter_overrides[{name!r}]), parameter_values)",
            "    else:",
            f"        parameter_values[{name!r}] = _eval_numeric({expr!r}, parameter_values)",
        ):
            line(lines, text)
    line(lines, "    return parameter_values")
    line(lines)

    if not include_sweep_helpers:
        return

    for text in (
        "def _safe_dir_name(text):",
        "    value = str(text).strip()",
        "    for source, target in {",
        "        '|': '-',",
        "        ':': '-',",
        "        '/': '_',",
        "        '\\\\': '_',",
        "        '<': '_',",
        "        '>': '_',",
        "        '\"': '_',",
        "        '?': '_',",
        "        '*': '_',",
        "    }.items():",
        "        value = value.replace(source, target)",
        "    value = ' '.join(value.split()).rstrip(' .')",
        "    return value or 'run'",
        "",
        "def _unique_dir(path):",
        "    candidate = path",
        "    idx = 2",
        "    while os.path.exists(candidate):",
        "        candidate = f'{path}_{idx}'",
        "        idx += 1",
        "    return candidate",
        "",
        "def _format_sweep_value(value):",
        "    return f'{value:.12g}'",
        "",
        "def _sweep_label(name, value):",
        "    return f'{name}={_format_sweep_value(value)}'",
        "",
        "def _expand_sweep_values(name, start_expr, stop_expr, step_expr, base_values):",
        "    available = set(base_values)",
        "    if name not in available:",
        "        raise ValueError(f\"Sweep parameter '{name}' is not defined in Parameters.\")",
        "    start = _eval_numeric(start_expr, dict(base_values))",
        "    stop = _eval_numeric(stop_expr, dict(base_values))",
        "    step_size = _eval_numeric(step_expr, dict(base_values))",
        "    eps = 1e-12 * max(1.0, abs(start), abs(stop), abs(step_size))",
        "    if abs(start - stop) <= eps:",
        "        return [float(stop)]",
        "    if abs(step_size) <= eps:",
        "        raise ValueError(f'sweep.{name}.steps: step size must be non-zero.')",
        "    if stop > start and step_size <= 0:",
        "        raise ValueError(",
        "            f'sweep.{name}.steps: step size must be positive when stop > start.'",
        "        )",
        "    if stop < start and step_size >= 0:",
        "        raise ValueError(",
        "            f'sweep.{name}.steps: step size must be negative when stop < start.'",
        "        )",
        "    values = []",
        "    current = start",
        "    while True:",
        "        if step_size > 0 and current > stop + eps:",
        "            break",
        "        if step_size < 0 and current < stop - eps:",
        "            break",
        "        if abs(current - stop) <= eps:",
        "            values.append(float(stop))",
        "        else:",
        "            values.append(float(current))",
        "        current += step_size",
        "    if not values:",
        "        raise ValueError(f\"Sweep parameter '{name}' produced no sweep points.\")",
        "    return values",
        "",
    ):
        line(lines, text)


def _build_analysis_body(
    state: ProjectState,
    prepared,
    scene,
) -> list[str]:
    params = _parameter_specs(scene)
    body: list[str] = []

    line(body, "os.makedirs(out_dir, exist_ok=True)")
    if params:
        line(body, "# Parameters")
    line(body, "parameter_values = _build_parameter_values(overrides)")
    for name, _expr in params:
        line(body, f"{name} = parameter_values[{name!r}]")
    if params:
        line(body)

    emit_materials(body, scene)
    _emit_geometry_and_sources(body, scene)
    _emit_fdtd_setup(
        body,
        scene,
        enabled=prepared.recipe.uses_fdtd_script_setup(prepared.plan),
        force_complex_fields=prepared.recipe.script_force_complex_fields(prepared.plan),
        include_flux_monitors=prepared.recipe.script_include_flux_monitors(prepared.plan),
    )
    prepared.recipe.emit_script(state, prepared.plan, body)

    if scene.monitors and prepared.recipe.script_include_flux_exports(prepared.plan):
        emit_flux_exports(body)
    return body


def _emit_run_function(lines: list[str], body: list[str]) -> None:
    line(lines, "def run_analysis(out_dir, overrides=None):")
    for text in _indent_block(body):
        line(lines, text)
    line(lines)


def _emit_non_sweep_main(lines: list[str], kind: str) -> None:
    line(lines, "if __name__ == '__main__':")
    line(lines, f"    out_dir = {_default_output_dir_expr(kind)}")
    line(lines, "    run_analysis(out_dir)")


def _emit_sweep_main(lines: list[str], state: ProjectState) -> None:
    line(lines, "if __name__ == '__main__':")
    line(lines, f"    analysis_kind = {state.analysis.kind!r}")
    line(lines, "    base_parameter_values = _build_parameter_values()")
    line(lines, "    sweep_specs = [")
    for item in state.sweep.params:
        line(
            lines,
            "        "
            f"({item.name!r}, {item.start!r}, {item.stop!r}, {item.steps!r}),",
        )
    line(lines, "    ]")
    line(lines, "    if not sweep_specs:")
    line(lines, "        raise ValueError('Sweep is enabled without any sweep parameters.')")
    line(
        lines,
        "    sweep_root = _unique_dir(os.path.join(script_dir, f\"{analysis_kind}_sweeps\"))",
    )
    line(lines, "    os.makedirs(sweep_root, exist_ok=True)")
    line(lines, "    expanded_sweeps = []")
    line(lines, "    seen_sweep_names = set()")
    line(lines, "    queue_total = 0")
    line(lines, "    for name, start_expr, stop_expr, step_expr in sweep_specs:")
    line(lines, "        if name in seen_sweep_names:")
    line(lines, "            raise ValueError(f\"Sweep parameter '{name}' is already configured.\")")
    line(lines, "        seen_sweep_names.add(name)")
    line(
        lines,
        "        values = _expand_sweep_values(name, start_expr, stop_expr, step_expr, base_parameter_values)",
    )
    line(lines, "        expanded_sweeps.append((name, values))")
    line(lines, "        queue_total += len(values)")
    line(lines, "    if queue_total == 0:")
    line(lines, "        raise ValueError('Sweep produced no points.')")
    line(lines, "    queue_index = 1")
    line(lines, "    completed = 0")
    line(lines, "    for name, values in expanded_sweeps:")
    line(
        lines,
        "        row_dir = _unique_dir(os.path.join(sweep_root, _safe_dir_name(f\"{analysis_kind}_{name}\")))",
    )
    line(lines, "        os.makedirs(row_dir, exist_ok=True)")
    line(lines, "        point_total = len(values)")
    line(lines, "        for point_index, value in enumerate(values, start=1):")
    line(lines, "            label = _sweep_label(name, value)")
    line(
        lines,
        "            print(f\"Sweep {queue_index}/{queue_total}: {label} ({point_index}/{point_total} for {name})\")",
    )
    line(lines, "            run_dir = _unique_dir(os.path.join(row_dir, _safe_dir_name(label)))")
    line(lines, "            try:")
    line(lines, "                run_analysis(run_dir, overrides={name: value})")
    line(lines, "            except Exception:")
    line(lines, "                print(f\"Sweep stopped after {label} failed.\")")
    line(lines, "                raise")
    line(lines, "            completed += 1")
    line(lines, "            queue_index += 1")
    line(lines, "    print(f\"Sweep completed. {completed} runs saved under {sweep_root}\")")


def generate_script(state: ProjectState, log: LogFn | None = None) -> str:
    prepared = prepare_script_analysis(state)
    if log is not None:
        emit_validation_warnings(prepared.validation, log)
    raise_for_validation_errors(prepared.validation)

    scene = _primary_scene(prepared.plan)
    sweep_enabled = state.sweep.enabled

    lines: list[str] = []
    _emit_header(lines, prepared.plan)
    _emit_runtime_helpers(lines, scene, include_sweep_helpers=sweep_enabled)
    _emit_run_function(lines, _build_analysis_body(state, prepared, scene))
    line(lines, f"# Analysis type: {prepared.recipe.display_name}")
    if sweep_enabled:
        _emit_sweep_main(lines, state)
    else:
        _emit_non_sweep_main(lines, state.analysis.kind)
    return "\n".join(lines)
