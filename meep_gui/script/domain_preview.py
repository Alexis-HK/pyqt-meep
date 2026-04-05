from __future__ import annotations

from .common import line


def emit_domain_preview_helpers(lines: list[str]) -> None:
    for text in (
        "def _preview_symmetry_summary(symmetry_specs):",
        "    if not symmetry_specs:",
        "        return 'Symmetries: none'",
        "    parts = []",
        "    for kind, direction, phase_expr in symmetry_specs:",
        "        kind = str(kind).strip().lower()",
        "        direction = str(direction).strip().lower()",
        "        phase = str(phase_expr).strip()",
        "        if kind == 'mirror':",
        "            prefix = 'm'",
        "        elif kind == 'rotate2':",
        "            prefix = 'r2'",
        "        elif kind == 'rotate4':",
        "            prefix = 'r4'",
        "        else:",
        "            prefix = kind or 'sym'",
        "        parts.append(f'{prefix}{direction}({phase})')",
        "    return 'Symmetries: ' + ', '.join(parts)",
        "",
        "def _resolve_preview_monitor_regions(monitor_specs, parameter_values):",
        "    regions = []",
        "    for center_x_expr, center_y_expr, size_x_expr, size_y_expr in monitor_specs:",
        "        try:",
        "            cx = _eval_numeric(center_x_expr, dict(parameter_values))",
        "            cy = _eval_numeric(center_y_expr, dict(parameter_values))",
        "            sx = _eval_numeric(size_x_expr, dict(parameter_values))",
        "            sy = _eval_numeric(size_y_expr, dict(parameter_values))",
        "        except Exception:",
        "            continue",
        "        regions.append((cx, cy, sx, sy))",
        "    return regions",
        "",
        "def _save_domain_preview_png(",
        "    path,",
        "    sim,",
        "    parameter_values,",
        "    monitor_specs,",
        "    symmetry_specs,",
        "    *,",
        "    title='Domain Preview',",
        "    marker_expr=None,",
        "):",
        "    from matplotlib.backends.backend_agg import FigureCanvasAgg",
        "    from matplotlib.figure import Figure",
        "    from matplotlib.patches import Rectangle",
        "    fig = Figure(figsize=(6, 5), dpi=120)",
        "    FigureCanvasAgg(fig)",
        "    ax = fig.add_subplot(111)",
        "    try:",
        "        sim.plot2D(ax=ax)",
        "        for cx, cy, sx, sy in _resolve_preview_monitor_regions(monitor_specs, parameter_values):",
        "            ax.add_patch(",
        "                Rectangle(",
        "                    (cx - sx / 2, cy - sy / 2),",
        "                    sx,",
        "                    sy,",
        "                    fill=False,",
        "                    edgecolor='#f59e0b',",
        "                    linewidth=1.1,",
        "                    linestyle='--',",
        "                )",
        "            )",
        "        if marker_expr is not None:",
        "            try:",
        "                hx = _eval_numeric(marker_expr[0], dict(parameter_values))",
        "                hy = _eval_numeric(marker_expr[1], dict(parameter_values))",
        "                ax.plot(hx, hy, marker='x', color='#006400', markersize=7, markeredgewidth=1.6)",
        "            except Exception:",
        "                pass",
        "        ax.set_title(title)",
        "        ax.text(",
        "            0.02,",
        "            0.98,",
        "            _preview_symmetry_summary(symmetry_specs),",
        "            transform=ax.transAxes,",
        "            va='top',",
        "            ha='left',",
        "            fontsize=8.5,",
        "            bbox={'facecolor': 'white', 'edgecolor': '#cccccc', 'alpha': 0.85, 'pad': 3},",
        "        )",
        "    except Exception as exc:",
        "        ax.clear()",
        "        ax.text(0.5, 0.5, f'Preview error:\\n{exc}', transform=ax.transAxes, ha='center', va='center')",
        "    fig.tight_layout()",
        "    fig.savefig(path)",
        "",
    ):
        line(lines, text)


def emit_domain_preview_call(
    lines: list[str],
    *,
    prefix: str,
    sim_var: str,
    output_name: str,
    title: str,
    domain,
    monitors,
    marker_expr: tuple[str, str] | None = None,
) -> None:
    line(lines, f"{prefix}_monitor_specs = [")
    for monitor in monitors:
        line(
            lines,
            "    "
            f"({monitor.center_x_expr!r}, {monitor.center_y_expr!r}, "
            f"{monitor.size_x_expr!r}, {monitor.size_y_expr!r}),",
        )
    line(lines, "]")
    line(lines, f"{prefix}_symmetry_specs = [")
    if getattr(domain, "symmetry_enabled", False):
        for symmetry in getattr(domain, "symmetries", []):
            line(
                lines,
                "    "
                f"({symmetry.kind!r}, {symmetry.direction!r}, {symmetry.phase_expr!r}),",
            )
    line(lines, "]")
    marker_literal = (
        f"({marker_expr[0]!r}, {marker_expr[1]!r})" if marker_expr is not None else "None"
    )
    for text in (
        f"{prefix}_domain_preview_out = os.path.join(out_dir, {output_name!r})",
        "_save_domain_preview_png(",
        f"    {prefix}_domain_preview_out,",
        f"    {sim_var},",
        "    parameter_values,",
        f"    {prefix}_monitor_specs,",
        f"    {prefix}_symmetry_specs,",
        f"    title={title!r},",
        f"    marker_expr={marker_literal},",
        ")",
    ):
        line(lines, text)
