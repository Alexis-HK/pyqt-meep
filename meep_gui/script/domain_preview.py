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
        "def _resolve_preview_monitor_regions(monitor_specs, parameter_values, *, rng=None):",
        "    regions = []",
        "    for center_x_expr, center_y_expr, size_x_expr, size_y_expr in monitor_specs:",
        "        try:",
        "            cx = _eval_numeric(center_x_expr, dict(parameter_values), rng=rng)",
        "            cy = _eval_numeric(center_y_expr, dict(parameter_values), rng=rng)",
        "            sx = _eval_numeric(size_x_expr, dict(parameter_values), rng=rng)",
        "            sy = _eval_numeric(size_y_expr, dict(parameter_values), rng=rng)",
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
        "    marker_exprs=None,",
        "    rng=None,",
        "):",
        "    from matplotlib.backends.backend_agg import FigureCanvasAgg",
        "    from matplotlib.figure import Figure",
        "    from matplotlib.patches import Rectangle",
        "    fig = Figure(figsize=(6, 5), dpi=120)",
        "    FigureCanvasAgg(fig)",
        "    ax = fig.add_subplot(111)",
        "    try:",
        "        sim.plot2D(ax=ax)",
        "        for cx, cy, sx, sy in _resolve_preview_monitor_regions(monitor_specs, parameter_values, rng=rng):",
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
        "        marker_items = []",
        "        if marker_exprs is not None:",
        "            marker_items.extend(marker_exprs)",
        "        elif marker_expr is not None:",
        "            marker_items.append(('', marker_expr[0], marker_expr[1]))",
        "        for marker_label, marker_x_expr, marker_y_expr in marker_items:",
        "            try:",
        "                hx = _eval_numeric(marker_x_expr, dict(parameter_values), rng=rng)",
        "                hy = _eval_numeric(marker_y_expr, dict(parameter_values), rng=rng)",
        "                ax.plot(hx, hy, marker='x', color='#006400', markersize=7, markeredgewidth=1.6)",
        "                if marker_label:",
        "                    ax.text(hx, hy, marker_label, color='#006400', fontsize=8, ha='left', va='bottom')",
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
    marker_exprs: tuple[tuple[str, str, str], ...] | None = None,
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
    if marker_exprs is None:
        marker_exprs_literal = "None"
    else:
        marker_exprs_literal = repr(tuple(marker_exprs))
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
        f"    marker_exprs={marker_exprs_literal},",
        "    rng=_rng,",
        ")",
    ):
        line(lines, text)
