from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import Parameter
from ...store import ProjectStore
from ...validation import NameRegistry, validate_name, validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


class ParameterEditDialog(QtWidgets.QDialog):
    def __init__(self, store: ProjectStore, param: Parameter, index: int, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._exclude = param.name
        self._index = index
        self._result: Parameter | None = None
        self.setWindowTitle("Edit Parameter")

        self.name_input = QtWidgets.QLineEdit(param.name)
        self.expr_input = QtWidgets.QLineEdit(param.expr)

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Expression", self.expr_input)

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
    def result(self) -> Parameter | None:
        return self._result

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        expr = self.expr_input.text().strip()
        registry = NameRegistry.from_state(self.store.state)
        name_result = validate_name(name, registry, exclude=self._exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return

        allowed = {n for i, n in enumerate(parameter_names(self.store)) if i < self._index}
        expr_result = validate_numeric_expression(expr, allowed)
        _set_invalid(self.expr_input, not expr_result.ok)
        if not expr_result.ok:
            _log_error(self.store, expr_result.message, self)
            return

        self._result = Parameter(name=name, expr=expr)
        self.accept()
