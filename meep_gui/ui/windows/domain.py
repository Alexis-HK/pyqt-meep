from __future__ import annotations

from PyQt5 import QtWidgets

from ...store import ProjectStore
from .base import QuitOnCloseWindow


class DomainWindow(QuitOnCloseWindow):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.setWindowTitle("Meep GUI - Domain")
        self.resize(700, 600)
        self._store = store

        from ...preview import DomainPreviewWidget

        self.preview = DomainPreviewWidget(self)
        self.setCentralWidget(self.preview)
        store.state_changed.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        issues = self.preview.update_from_state(self._store.state)
        for issue in issues:
            self._store.log_message(issue.message)
