from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import Material
from ...store import ProjectStore
from ...validation import NameRegistry, validate_name, validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


class MaterialEditDialog(QtWidgets.QDialog):
    def __init__(self, store: ProjectStore, material: Material, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._exclude = material.name
        self._result: Material | None = None
        self.setWindowTitle("Edit Material")

        self.name_input = QtWidgets.QLineEdit(material.name)
        self.index_input = QtWidgets.QLineEdit(material.index_expr)

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Index", self.index_input)

        self.save_button = QtWidgets.QPushButton("Save")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.save_button)
        btn_row.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_row)

        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.reject)

    @property
    def result(self) -> Material | None:
        return self._result

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        index_expr = self.index_input.text().strip()
        registry = NameRegistry.from_state(self.store.state)
        name_result = validate_name(name, registry, exclude=self._exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return

        expr_result = validate_numeric_expression(index_expr, parameter_names(self.store))
        _set_invalid(self.index_input, not expr_result.ok)
        if not expr_result.ok:
            _log_error(self.store, expr_result.message, self)
            return

        self._result = Material(name=name, index_expr=index_expr)
        self.accept()
