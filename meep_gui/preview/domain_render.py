from __future__ import annotations

import copy
from dataclasses import dataclass

from ..model import ProjectState
from ..scene import compile_project_scene, scene_to_sim_params
from ..validation import evaluate_numeric_expression, evaluate_parameters

try:
    from ..sim import build_sim as _default_build_sim
except Exception:  # pragma: no cover - preview can still render placeholders
    _default_build_sim = None  # type: ignore[assignment]


@dataclass
class RenderIssue:
    message: str


def _symmetry_summary(domain) -> str:
    if not getattr(domain, "symmetry_enabled", False) or not getattr(domain, "symmetries", []):
        return "Symmetries: none"
    parts: list[str] = []
    for symmetry in domain.symmetries:
        kind = str(getattr(symmetry, "kind", "")).strip().lower()
        direction = str(getattr(symmetry, "direction", "")).strip().lower()
        phase = str(getattr(symmetry, "phase", getattr(symmetry, "phase_expr", ""))).strip()
        if kind == "mirror":
            prefix = "m"
        elif kind == "rotate2":
            prefix = "r2"
        elif kind == "rotate4":
            prefix = "r4"
        else:
            prefix = kind or "sym"
        parts.append(f"{prefix}{direction}({phase})")
    return "Symmetries: " + ", ".join(parts)


def _safe_import_meep_mpb():
    try:
        import meep as mp
    except Exception as exc:
        raise RuntimeError(f"Meep import failed: {exc}") from exc
    if not hasattr(mp, "Simulation"):
        source = getattr(mp, "__file__", "<unknown>")
        raise RuntimeError(
            "Imported module 'meep' is not the pymeep package. "
            f"Loaded from: {source}. "
            "If this points to a local meep.py file, rename it."
        )
    try:
        from meep import mpb
    except Exception as exc:
        raise RuntimeError(f"MPB import failed: {exc}") from exc
    return mp, mpb


def _state_for_meep_preview(
    state: ProjectState,
    *,
    preview_domain: str | None = None,
) -> ProjectState:
    preview_state = copy.deepcopy(state)
    if preview_state.analysis.kind != "transmission_spectrum":
        return preview_state

    mode = preview_domain or preview_state.analysis.transmission_spectrum.preview_domain
    if mode != "reference":
        return preview_state

    reference_cfg = preview_state.analysis.transmission_spectrum.reference_state
    preview_state.domain = copy.deepcopy(reference_cfg.domain)
    preview_state.geometries = copy.deepcopy(reference_cfg.geometries)
    preview_state.sources = copy.deepcopy(reference_cfg.sources)
    preview_state.flux_monitors = copy.deepcopy(reference_cfg.flux_monitors)
    return preview_state


def render_domain_preview_axes(
    ax,
    state: ProjectState,
    *,
    preview_domain: str | None = None,
    build_sim_impl=None,
) -> list[RenderIssue]:
    issues: list[RenderIssue] = []
    ax.clear()

    values, param_results = evaluate_parameters(state.parameters)
    for result in param_results:
        if not result.ok:
            issues.append(RenderIssue(f"Parameter '{result.name}': {result.message}"))

    if state.analysis.kind == "mpb_modesolver":
        _render_mpb_preview(ax, state, values, issues)
    else:
        _render_meep_preview(
            ax,
            state,
            values,
            issues,
            preview_domain=preview_domain,
            build_sim_impl=build_sim_impl,
        )
    return issues


def save_domain_preview_png(
    path: str,
    state: ProjectState,
    *,
    preview_domain: str | None = None,
    build_sim_impl=None,
) -> list[RenderIssue]:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(5, 4), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    issues = render_domain_preview_axes(
        ax,
        state,
        preview_domain=preview_domain,
        build_sim_impl=build_sim_impl,
    )
    fig.tight_layout()
    fig.savefig(path)
    return issues


def _render_meep_preview(
    ax,
    state: ProjectState,
    values: dict[str, float],
    issues: list[RenderIssue],
    *,
    preview_domain: str | None = None,
    build_sim_impl=None,
) -> None:
    sim_builder = _default_build_sim if build_sim_impl is None else build_sim_impl
    if sim_builder is None:
        issues.append(RenderIssue("Meep preview unavailable: simulation builders are not available."))
        ax.text(0.5, 0.5, "Meep preview unavailable", transform=ax.transAxes, ha="center", va="center")
        return

    preview_state = _state_for_meep_preview(state, preview_domain=preview_domain)
    try:
        compiled = compile_project_scene(preview_state)
        params = scene_to_sim_params(compiled.scene, compiled.context)
        params.symmetries = []
        sim = sim_builder(params, lambda _msg: None)
        sim.plot2D(ax=ax)
    except Exception as exc:
        issues.append(RenderIssue(f"Domain preview error: {exc}"))
        ax.text(0.5, 0.5, f"Preview error:\n{exc}", transform=ax.transAxes, ha="center", va="center")
        return

    from matplotlib.patches import Rectangle

    for monitor in compiled.scene.monitors:
        try:
            cx = evaluate_numeric_expression(
                monitor.center_x_expr,
                compiled.context.parameter_values,
            )
            cy = evaluate_numeric_expression(
                monitor.center_y_expr,
                compiled.context.parameter_values,
            )
            sx = evaluate_numeric_expression(
                monitor.size_x_expr,
                compiled.context.parameter_values,
            )
            sy = evaluate_numeric_expression(
                monitor.size_y_expr,
                compiled.context.parameter_values,
            )
        except ValueError as exc:
            issues.append(RenderIssue(f"Flux monitor '{monitor.name}': {exc}"))
            continue
        ax.add_patch(
            Rectangle(
                (cx - sx / 2, cy - sy / 2),
                sx,
                sy,
                fill=False,
                edgecolor="#f59e0b",
                linewidth=1.1,
                linestyle="--",
            )
        )

    if preview_state.analysis.kind == "harminv":
        cfg = preview_state.analysis.harminv
        try:
            hx = evaluate_numeric_expression(cfg.point_x, values)
            hy = evaluate_numeric_expression(cfg.point_y, values)
            ax.plot(hx, hy, marker="x", color="#006400", markersize=7, markeredgewidth=1.6)
        except ValueError as exc:
            issues.append(RenderIssue(f"Harminv monitor: {exc}"))

    if preview_state.analysis.kind == "transmission_spectrum":
        mode = preview_domain or state.analysis.transmission_spectrum.preview_domain
        cfg = preview_state.analysis.transmission_spectrum
        if cfg.stop_condition == "field_decay":
            prefix = "reference" if mode == "reference" else "scattering"
            try:
                tx = evaluate_numeric_expression(
                    getattr(cfg, f"{prefix}_field_decay_point_x"),
                    values,
                )
                ty = evaluate_numeric_expression(
                    getattr(cfg, f"{prefix}_field_decay_point_y"),
                    values,
                )
                ax.plot(tx, ty, marker="x", color="#006400", markersize=7, markeredgewidth=1.6)
            except ValueError as exc:
                issues.append(RenderIssue(f"Transmission stop probe: {exc}"))
        suffix = "reference" if mode == "reference" else "scattering"
        ax.set_title(f"Domain Preview ({suffix})")
    else:
        ax.set_title("Domain Preview")
    ax.text(
        0.02,
        0.98,
        _symmetry_summary(preview_state.domain),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=8.5,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.85, "pad": 3},
    )


def _render_mpb_preview(
    ax,
    state: ProjectState,
    values: dict[str, float],
    issues: list[RenderIssue],
) -> None:
    if state.domain.symmetry_enabled and state.domain.symmetries:
        msg = "Domain symmetries are FDTD-only and ignored in MPB preview."
        issues.append(RenderIssue(msg))
    try:
        mp, mpb = _safe_import_meep_mpb()
    except Exception as exc:
        issues.append(RenderIssue(f"MPB preview import failed: {exc}"))
        ax.text(
            0.5,
            0.5,
            "MPB preview unavailable",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            color="#555555",
        )
        return

    cfg = state.analysis.mpb_modesolver
    try:
        lattice_x = evaluate_numeric_expression(cfg.lattice_x, values)
        lattice_y = evaluate_numeric_expression(cfg.lattice_y, values)
        basis1_x = evaluate_numeric_expression(cfg.basis1_x, values)
        basis1_y = evaluate_numeric_expression(cfg.basis1_y, values)
        basis2_x = evaluate_numeric_expression(cfg.basis2_x, values)
        basis2_y = evaluate_numeric_expression(cfg.basis2_y, values)
        num_bands = int(evaluate_numeric_expression(cfg.num_bands, values))
        resolution = int(evaluate_numeric_expression(cfg.resolution, values))
        unit_cells = int(evaluate_numeric_expression(cfg.unit_cells, values))
    except ValueError as exc:
        issues.append(RenderIssue(f"MPB preview: {exc}"))
        ax.text(0.5, 0.5, str(exc), transform=ax.transAxes, ha="center", va="center")
        return

    try:
        compiled = compile_project_scene(state)
        params = scene_to_sim_params(compiled.scene, compiled.context)
    except Exception as exc:
        issues.append(RenderIssue(f"MPB preview scene: {exc}"))
        ax.text(0.5, 0.5, str(exc), transform=ax.transAxes, ha="center", va="center")
        return

    geometry = []
    for shape in params.shapes:
        material = mp.Medium(epsilon=shape.eps)
        if shape.kind == "rect":
            geometry.append(
                mp.Block(
                    size=mp.Vector3(shape.size_x, shape.size_y, mp.inf),
                    center=mp.Vector3(shape.center_x, shape.center_y),
                    material=material,
                )
            )
        elif shape.kind == "circle":
            geometry.append(
                mp.Cylinder(
                    radius=shape.radius,
                    height=mp.inf,
                    center=mp.Vector3(shape.center_x, shape.center_y),
                    material=material,
                )
            )

    k_points = []
    if cfg.kpoints:
        for kp in cfg.kpoints:
            try:
                kx = evaluate_numeric_expression(kp.kx, values)
                ky = evaluate_numeric_expression(kp.ky, values)
            except ValueError as exc:
                issues.append(RenderIssue(f"K-point: {exc}"))
                continue
            k_points.append(mp.Vector3(kx, ky, 0))
    if not k_points:
        k_points = [mp.Vector3(0, 0, 0)]

    lattice = mp.Lattice(
        size=mp.Vector3(lattice_x, lattice_y, 0),
        basis1=mp.Vector3(basis1_x, basis1_y, 0),
        basis2=mp.Vector3(basis2_x, basis2_y, 0),
    )
    try:
        ms = mpb.ModeSolver(
            geometry_lattice=lattice,
            geometry=geometry,
            k_points=k_points,
            resolution=resolution,
            num_bands=num_bands,
        )
        ms.init_params(mp.NO_PARITY, True)
        md = mpb.MPBData(rectify=True, periods=unit_cells, resolution=resolution)
        eps = ms.get_epsilon()
        converted_eps = md.convert(eps)
        ax.imshow(
            converted_eps.T,
            interpolation="spline36",
            cmap="binary",
        )
        ax.set_title("MPB Unit Cell")
        ax.axis("off")
        if state.domain.symmetry_enabled and state.domain.symmetries:
            ax.text(
                0.02,
                0.98,
                "FDTD-only symmetries ignored",
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=8.5,
                bbox={"facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.85, "pad": 3},
            )
    except Exception as exc:
        issues.append(RenderIssue(f"MPB preview error: {exc}"))
        ax.text(0.5, 0.5, f"MPB preview error:\n{exc}", transform=ax.transAxes, ha="center", va="center")
