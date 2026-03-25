from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import KPoint
from ...store import ProjectStore
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


class KPointEditDialog(QtWidgets.QDialog):
    def __init__(self, store: ProjectStore, kpoint: KPoint, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._result: KPoint | None = None
        self.setWindowTitle("Edit K-Point")

        self.kx_input = QtWidgets.QLineEdit(kpoint.kx)
        self.ky_input = QtWidgets.QLineEdit(kpoint.ky)

        form = QtWidgets.QFormLayout()
        form.addRow("Kx", self.kx_input)
        form.addRow("Ky", self.ky_input)

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
    def result(self) -> KPoint | None:
        return self._result

    def _on_save(self) -> None:
        for widget, label in ((self.kx_input, "Kx"), (self.ky_input, "Ky")):
            result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                return
        self._result = KPoint(kx=self.kx_input.text().strip(), ky=self.ky_input.text().strip())
        self.accept()
