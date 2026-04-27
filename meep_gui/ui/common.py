from __future__ import annotations

from PyQt5 import QtCore, QtGui, QtWidgets

from ..model import RunRecord
from ..store import ProjectStore

_INVALID_STYLE = "background-color: #f6c7c7;"
_WARN_COLOR = "#f6c7c7"


def _set_invalid(widget: QtWidgets.QWidget, invalid: bool) -> None:
    widget.setStyleSheet(_INVALID_STYLE if invalid else "")


def _log_error(store: ProjectStore, message: str, parent: QtWidgets.QWidget) -> None:
    store.log_message(message)
    QtWidgets.QMessageBox.warning(parent, "Invalid input", message)


def _set_form_row_visible(
    form: QtWidgets.QFormLayout,
    field: QtWidgets.QWidget,
    visible: bool,
) -> None:
    label = form.labelForField(field)
    if label is not None:
        label.setVisible(visible)
    field.setVisible(visible)


def _scroll_area_for(content: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    layout = content.layout()
    if layout is not None:
        layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
    content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    scroll_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    scroll_area.setWidget(content)
    return scroll_area


def _refresh_scroll_area(scroll_area: QtWidgets.QScrollArea) -> None:
    content = scroll_area.widget()
    if content is not None:
        content.updateGeometry()
        content.adjustSize()
    scroll_area.updateGeometry()
    scroll_area.viewport().update()


def format_run_list_label(run: RunRecord) -> str:
    prefix = run.meta.get("sweep_label", "").strip()
    label = f"{run.analysis_kind} [{run.status}] {run.created_at or run.run_id}"
    if prefix:
        label = f"{prefix} | {label}"
    if run.status == "canceled":
        label += " (canceled)"
    return label


def _mark_row_warning(table: QtWidgets.QTableWidget, row: int, message: str) -> None:
    color = QtGui.QColor(_WARN_COLOR)
    for col in range(table.columnCount()):
        item = table.item(row, col)
        if item is not None:
            item.setBackground(color)
            item.setToolTip(message)
