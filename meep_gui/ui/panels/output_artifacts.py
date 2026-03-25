from __future__ import annotations

from PyQt5 import QtWidgets


class OutputArtifactsPanel(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.artifact_list = QtWidgets.QListWidget()
        self.export_artifact_button = QtWidgets.QPushButton("Export Selected")
        self.export_all_button = QtWidgets.QPushButton("Export All")
        self.export_artifact_button.setDisabled(True)
        self.export_all_button.setDisabled(True)
        layout.addWidget(self.artifact_list)
        layout.addWidget(self.export_artifact_button)
        layout.addWidget(self.export_all_button)
