from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import Parameter
from ...store import ProjectStore
from ...validation import (
    NameRegistry,
    parse_parameter_import_text,
    validate_name,
    validate_numeric_expression,
)
from ..common import _log_error, _set_invalid
from ..dialogs import ParameterEditDialog
from ..scope import parameter_names


class ParametersTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store

        self.name_input = QtWidgets.QLineEdit()
        self.expr_input = QtWidgets.QLineEdit()
        self.add_button = QtWidgets.QPushButton("Add")
        self.update_button = QtWidgets.QPushButton("Update")
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.import_button = QtWidgets.QPushButton("Import")

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Expression", self.expr_input)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.add_button)
        btn_row.addWidget(self.update_button)
        btn_row.addWidget(self.remove_button)
        btn_row.addWidget(self.import_button)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Expression"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.add_button.clicked.connect(self._on_add)
        self.update_button.clicked.connect(self._on_update)
        self.remove_button.clicked.connect(self._on_remove)
        self.import_button.clicked.connect(self._on_import)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.store.state_changed.connect(self.refresh)

        self.refresh()

    def _current_row(self) -> int:
        selection = self.table.selectionModel().selectedRows()
        if selection:
            return selection[0].row()
        return -1

    def _validate(self, name: str, expr: str, row: int) -> bool:
        registry = NameRegistry.from_state(self.store.state)
        exclude = None
        if 0 <= row < len(self.store.state.parameters):
            exclude = self.store.state.parameters[row].name
        name_result = validate_name(name, registry, exclude=exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return False

        allowed = set(parameter_names(self.store))
        if row >= 0:
            allowed = {n for i, n in enumerate(parameter_names(self.store)) if i < row}
        expr_result = validate_numeric_expression(expr, allowed)
        _set_invalid(self.expr_input, not expr_result.ok)
        if not expr_result.ok:
            _log_error(self.store, expr_result.message, self)
            return False

        return True

    def _on_add(self) -> None:
        name = self.name_input.text().strip()
        expr = self.expr_input.text().strip()
        row = len(self.store.state.parameters)
        if not self._validate(name, expr, row):
            return
        self.store.state.parameters.append(Parameter(name=name, expr=expr))
        self.store.notify()

    def _on_update(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        item = self.store.state.parameters[row]
        dialog = ParameterEditDialog(self.store, item, row, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.result:
            self.store.state.parameters[row] = dialog.result
            self.store.notify()

    def _on_remove(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        self.store.state.parameters.pop(row)
        self.store.notify()

    def _on_import(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Parameters",
            "",
            "Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as exc:
            _log_error(self.store, f"Parameter import failed: {exc}", self)
            return

        existing = NameRegistry.from_state(self.store.state)
        registry = NameRegistry(
            parameters=set(),
            materials=set(existing.materials),
            geometries=set(existing.geometries),
            sources=set(existing.sources),
        )
        try:
            imported = parse_parameter_import_text(text, registry)
        except ValueError as exc:
            _log_error(self.store, f"Parameter import failed: {exc}", self)
            return

        self.store.state.parameters = [Parameter(name=name, expr=expr) for name, expr in imported]
        self.store.notify()
        self.store.log_message(f"Imported {len(imported)} parameters from {path}")

    def _on_select(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        param = self.store.state.parameters[row]
        self.name_input.setText(param.name)
        self.expr_input.setText(param.expr)
        _set_invalid(self.name_input, False)
        _set_invalid(self.expr_input, False)

    def refresh(self) -> None:
        self.table.setRowCount(0)
        for param in self.store.state.parameters:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(param.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(param.expr))
