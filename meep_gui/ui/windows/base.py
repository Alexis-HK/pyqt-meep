from __future__ import annotations

from PyQt5 import QtCore, QtWidgets


class QuitOnCloseWindow(QtWidgets.QMainWindow):
    def closeEvent(self, event: QtCore.QEvent) -> None:  # type: ignore[override]
        QtWidgets.QApplication.instance().quit()
        event.accept()
