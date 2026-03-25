from __future__ import annotations

from PyQt5 import QtGui, QtWidgets

from ..store import ProjectStore

_INVALID_STYLE = "background-color: #f6c7c7;"
_WARN_COLOR = "#f6c7c7"


def _set_invalid(widget: QtWidgets.QWidget, invalid: bool) -> None:
    widget.setStyleSheet(_INVALID_STYLE if invalid else "")


def _log_error(store: ProjectStore, message: str, parent: QtWidgets.QWidget) -> None:
    store.log_message(message)
    QtWidgets.QMessageBox.warning(parent, "Invalid input", message)


def _mark_row_warning(table: QtWidgets.QTableWidget, row: int, message: str) -> None:
    color = QtGui.QColor(_WARN_COLOR)
    for col in range(table.columnCount()):
        item = table.item(row, col)
        if item is not None:
            item.setBackground(color)
            item.setToolTip(message)
