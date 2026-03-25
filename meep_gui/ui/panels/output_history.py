from __future__ import annotations

from PyQt5 import QtWidgets


class OutputHistoryPanel(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.run_list = QtWidgets.QListWidget()
        self.run_list.setMinimumWidth(280)
        self.run_status = QtWidgets.QLabel("No run selected")
        self.remove_run_button = QtWidgets.QPushButton("Remove Selected Run")
        self.remove_run_button.setDisabled(True)
        layout.addWidget(self.run_list)
        layout.addWidget(self.run_status)
        layout.addWidget(self.remove_run_button)
