from __future__ import annotations

from PyQt5 import QtWidgets

from ...store import ProjectStore
from .base import QuitOnCloseWindow


class LogWindow(QuitOnCloseWindow):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.setWindowTitle("Meep GUI - Log")
        self.resize(700, 300)

        tabs = QtWidgets.QTabWidget()
        self.app_log = QtWidgets.QTextEdit()
        self.app_log.setReadOnly(True)
        self.terminal_log = QtWidgets.QTextEdit()
        self.terminal_log.setReadOnly(True)
        tabs.addTab(self.app_log, "App Log")
        tabs.addTab(self.terminal_log, "Terminal")
        self.setCentralWidget(tabs)

        store.log.connect(self._append_log)
        store.terminal.connect(self._append_terminal)

        for line in store.log_history:
            self._append_log(line)
        for line in store.terminal_history:
            self._append_terminal(line)

    def _append_log(self, message: str) -> None:
        self.app_log.append(message)

    def _append_terminal(self, message: str) -> None:
        self.terminal_log.append(message)
