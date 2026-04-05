from __future__ import annotations

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .domain_render import RenderIssue, render_domain_preview_axes

try:
    from ..sim import build_sim
except Exception:  # pragma: no cover - UI can still load
    build_sim = None  # type: ignore[assignment]


class DomainPreviewWidget(FigureCanvas):
    def __init__(self, parent=None) -> None:
        fig = Figure(figsize=(5, 4), dpi=100)
        self._ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)

    def export_png(self, path: str) -> None:
        self.draw()
        self.figure.savefig(path)

    def update_from_state(self, state) -> list[RenderIssue]:
        issues = render_domain_preview_axes(self._ax, state, build_sim_impl=build_sim)
        self.draw_idle()
        return issues
