from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import Material
from ...store import ProjectStore
from ...validation import NameRegistry, validate_name, validate_numeric_expression
from ..common import _log_error, _mark_row_warning, _set_invalid
from ..dialogs import MaterialEditDialog
from ..scope import parameter_names


class MaterialsTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._invalid_items: set[str] = set()

        self.name_input = QtWidgets.QLineEdit()
        self.index_input = QtWidgets.QLineEdit()
        self.add_button = QtWidgets.QPushButton("Add")
        self.update_button = QtWidgets.QPushButton("Update")
        self.remove_button = QtWidgets.QPushButton("Remove")

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Index", self.index_input)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.add_button)
        btn_row.addWidget(self.update_button)
        btn_row.addWidget(self.remove_button)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Index"])
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
        self.table.itemSelectionChanged.connect(self._on_select)
        self.store.state_changed.connect(self.refresh)

        self.refresh()

    def _current_row(self) -> int:
        selection = self.table.selectionModel().selectedRows()
        if selection:
            return selection[0].row()
        return -1

    def _validate(self, name: str, index_expr: str, row: int) -> bool:
        registry = NameRegistry.from_state(self.store.state)
        exclude = None
        if 0 <= row < len(self.store.state.materials):
            exclude = self.store.state.materials[row].name
        name_result = validate_name(name, registry, exclude=exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return False

        expr_result = validate_numeric_expression(index_expr, parameter_names(self.store))
        _set_invalid(self.index_input, not expr_result.ok)
        if not expr_result.ok:
            _log_error(self.store, expr_result.message, self)
            return False

        return True

    def _on_add(self) -> None:
        name = self.name_input.text().strip()
        index_expr = self.index_input.text().strip()
        row = len(self.store.state.materials)
        if not self._validate(name, index_expr, row):
            return
        self.store.state.materials.append(Material(name=name, index_expr=index_expr))
        self.store.notify()

    def _on_update(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        item = self.store.state.materials[row]
        dialog = MaterialEditDialog(self.store, item, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.result:
            self.store.state.materials[row] = dialog.result
            self.store.notify()

    def _on_remove(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        self.store.state.materials.pop(row)
        self.store.notify()

    def _on_select(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        item = self.store.state.materials[row]
        self.name_input.setText(item.name)
        self.index_input.setText(item.index_expr)
        _set_invalid(self.name_input, False)
        _set_invalid(self.index_input, False)

    def refresh(self) -> None:
        self.table.setRowCount(0)
        invalid: dict[str, str] = {}
        allowed = parameter_names(self.store)
        for mat in self.store.state.materials:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(mat.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(mat.index_expr))
            result = validate_numeric_expression(mat.index_expr, allowed)
            if not result.ok:
                key = mat.name or f"row-{row}"
                message = f"Material '{mat.name}': {result.message}"
                invalid[key] = message
                _mark_row_warning(self.table, row, message)

        for key, message in invalid.items():
            if key not in self._invalid_items:
                self.store.log_message(message)
        self._invalid_items = set(invalid.keys())
