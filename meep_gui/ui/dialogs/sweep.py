from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import SweepParameter
from ...store import ProjectStore
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


class SweepEditDialog(QtWidgets.QDialog):
    def __init__(
        self,
        store: ProjectStore,
        item: SweepParameter,
        row: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self._row = row
        self._exclude = item.name
        self._result: SweepParameter | None = None
        self.setWindowTitle("Edit Sweep Parameter")

        self.param_name = QtWidgets.QComboBox()
        self.param_name.addItems([param.name for param in self.store.state.parameters if param.name])
        self.param_name.setCurrentText(item.name)
        self.start = QtWidgets.QLineEdit(item.start)
        self.stop = QtWidgets.QLineEdit(item.stop)
        self.steps = QtWidgets.QLineEdit(item.steps)

        form = QtWidgets.QFormLayout()
        form.addRow("Parameter", self.param_name)
        form.addRow("Start", self.start)
        form.addRow("Stop", self.stop)
        form.addRow("Step Size", self.steps)

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
    def result(self) -> SweepParameter | None:
        return self._result

    def _on_save(self) -> None:
        name = self.param_name.currentText().strip()
        if not name:
            _set_invalid(self.param_name, True)
            _log_error(self.store, "Sweep parameter name is required.", self)
            return
        if name not in parameter_names(self.store):
            _set_invalid(self.param_name, True)
            _log_error(self.store, f"Sweep parameter '{name}' is not defined in Parameters.", self)
            return

        duplicate = [
            param.name
            for idx, param in enumerate(self.store.state.sweep.params)
            if idx != self._row and param.name != self._exclude
        ]
        if name in duplicate:
            _set_invalid(self.param_name, True)
            _log_error(self.store, f"Sweep parameter '{name}' is already configured.", self)
            return
        _set_invalid(self.param_name, False)

        ok = True
        for widget, label in ((self.start, "Start"), (self.stop, "Stop"), (self.steps, "Steps")):
            result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                ok = False
        if not ok:
            return

        self._result = SweepParameter(
            name=name,
            start=self.start.text().strip(),
            stop=self.stop.text().strip(),
            steps=self.steps.text().strip(),
        )
        self.accept()
