from __future__ import annotations

from ...store import ProjectStore
from ..widgets.result_browser import ResultBrowserWidget
from .base import QuitOnCloseWindow


class OutputWindow(QuitOnCloseWindow):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.setWindowTitle("Meep GUI - Output")
        self.resize(980, 640)
        self.browser = ResultBrowserWidget(store, self)
        self.setCentralWidget(self.browser)
        self.run_list = self.browser.run_list
        self.run_status = self.browser.run_status
        self.artifact_list = self.browser.artifact_list
        self.export_artifact_button = self.browser.export_artifact_button
        self.export_all_button = self.browser.export_all_button
        self.remove_run_button = self.browser.remove_run_button
