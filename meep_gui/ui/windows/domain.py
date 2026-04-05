from __future__ import annotations

from PyQt5 import QtWidgets

from ...store import ProjectStore
from ..common import _log_error
from .base import QuitOnCloseWindow


class DomainWindow(QuitOnCloseWindow):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.setWindowTitle("Meep GUI - Domain")
        self.resize(700, 600)
        self._store = store

        from ...preview import DomainPreviewWidget

        self.preview = DomainPreviewWidget(self)
        self.export_preview_button = QtWidgets.QPushButton("Export Preview")

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.export_preview_button)

        container = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(container)
        layout.addLayout(button_row)
        layout.addWidget(self.preview, stretch=1)
        self.setCentralWidget(container)

        self.export_preview_button.clicked.connect(self._export_preview)
        store.state_changed.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        issues = self.preview.update_from_state(self._store.state)
        for issue in issues:
            self._store.log_message(issue.message)

    def _default_export_filename(self) -> str:
        analysis = self._store.state.analysis
        if analysis.kind == "mpb_modesolver":
            return "mpb_unit_cell.png"
        if analysis.kind == "transmission_spectrum":
            mode = analysis.transmission_spectrum.preview_domain
            if mode == "reference":
                return "domain_preview_reference.png"
            if mode == "scattering":
                return "domain_preview_scattering.png"
        return "domain_preview.png"

    def _export_preview(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Preview",
            self._default_export_filename(),
            "PNG Files (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            self.preview.export_png(path)
            self._store.log_message(f"Exported preview to {path}")
        except Exception as exc:
            _log_error(self._store, f"Export error: {exc}", self)
