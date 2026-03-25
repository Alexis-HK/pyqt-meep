from __future__ import annotations

import copy
from dataclasses import dataclass

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from ..model import ProjectState
from ..validation import evaluate_numeric_expression, evaluate_parameters

try:
    from ..sim import build_sim
    from ..specs import build_sim_params
except Exception:  # pragma: no cover - UI can still load
    build_sim_params = None  # type: ignore[assignment]
    build_sim = None  # type: ignore[assignment]


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
        phase = str(getattr(symmetry, "phase", "")).strip()
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


def _state_for_meep_preview(state: ProjectState) -> ProjectState:
    preview_state = copy.deepcopy(state)
    if (
        preview_state.analysis.kind == "transmission_spectrum"
        and preview_state.analysis.transmission_spectrum.preview_domain == "reference"
    ):
        reference_cfg = preview_state.analysis.transmission_spectrum.reference_state
        preview_state.domain = copy.deepcopy(reference_cfg.domain)
        preview_state.geometries = copy.deepcopy(reference_cfg.geometries)
        preview_state.sources = copy.deepcopy(reference_cfg.sources)
        preview_state.flux_monitors = copy.deepcopy(reference_cfg.flux_monitors)
    return preview_state


class DomainPreviewWidget(FigureCanvas):
    def __init__(self, parent=None) -> None:
        fig = Figure(figsize=(5, 4), dpi=100)
        self._ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)

    def update_from_state(self, state: ProjectState) -> list[RenderIssue]:
        issues: list[RenderIssue] = []
        ax = self._ax
        ax.clear()

        values, param_results = evaluate_parameters(state.parameters)
        for result in param_results:
            if not result.ok:
                issues.append(RenderIssue(f"Parameter '{result.name}': {result.message}"))

        if state.analysis.kind == "mpb_modesolver":
            self._render_mpb_preview(ax, state, values, issues)
        else:
            self._render_meep_preview(ax, state, values, issues)

        self.draw_idle()
        return issues

    def _render_meep_preview(
        self,
        ax,
        state: ProjectState,
        values: dict[str, float],
        issues: list[RenderIssue],
    ) -> None:
        if build_sim_params is None or build_sim is None:
            issues.append(RenderIssue("Meep preview unavailable: simulation builders are not available."))
            ax.text(0.5, 0.5, "Meep preview unavailable", transform=ax.transAxes, ha="center", va="center")
            return

        preview_state = _state_for_meep_preview(state)
        try:
            params = build_sim_params(preview_state)
            params.symmetries = []
            sim = build_sim(params, lambda _msg: None)
            sim.plot2D(ax=ax)
        except Exception as exc:
            issues.append(RenderIssue(f"Domain preview error: {exc}"))
            ax.text(0.5, 0.5, f"Preview error:\n{exc}", transform=ax.transAxes, ha="center", va="center")
            return

        # Overlay flux monitor regions so monitor placements remain visible.
        for monitor in preview_state.flux_monitors:
            try:
                cx = evaluate_numeric_expression(monitor.center_x, values)
                cy = evaluate_numeric_expression(monitor.center_y, values)
                sx = evaluate_numeric_expression(monitor.size_x, values)
                sy = evaluate_numeric_expression(monitor.size_y, values)
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
            mode = preview_state.analysis.transmission_spectrum.preview_domain
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
        self,
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
                0,
                0,
                "MPB preview unavailable",
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

        materials: dict[str, float] = {}
        for mat in state.materials:
            if not mat.name:
                continue
            try:
                idx = evaluate_numeric_expression(mat.index_expr, values)
            except ValueError as exc:
                issues.append(RenderIssue(f"Material '{mat.name}': {exc}"))
                continue
            materials[mat.name] = idx

        geometry = []
        for geo in state.geometries:
            if geo.material not in materials:
                issues.append(RenderIssue(f"Geometry '{geo.name}': unknown material '{geo.material}'"))
                continue
            mat = mp.Medium(index=materials[geo.material])
            try:
                if geo.kind == "block":
                    size_x = evaluate_numeric_expression(geo.props.get("size_x", "0"), values)
                    size_y = evaluate_numeric_expression(geo.props.get("size_y", "0"), values)
                    center_x = evaluate_numeric_expression(geo.props.get("center_x", "0"), values)
                    center_y = evaluate_numeric_expression(geo.props.get("center_y", "0"), values)
                    geometry.append(
                        mp.Block(
                            size=mp.Vector3(size_x, size_y, mp.inf),
                            center=mp.Vector3(center_x, center_y),
                            material=mat,
                        )
                    )
                elif geo.kind == "circle":
                    radius = evaluate_numeric_expression(geo.props.get("radius", "0"), values)
                    center_x = evaluate_numeric_expression(geo.props.get("center_x", "0"), values)
                    center_y = evaluate_numeric_expression(geo.props.get("center_y", "0"), values)
                    geometry.append(
                        mp.Cylinder(
                            radius=radius,
                            height=mp.inf,
                            center=mp.Vector3(center_x, center_y),
                            material=mat,
                        )
                    )
            except ValueError as exc:
                issues.append(RenderIssue(f"Geometry '{geo.name}': {exc}"))

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
