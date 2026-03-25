from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import FluxMonitorConfig
from ...store import ProjectStore
from ...validation import validate_name, validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import active_scope, parameter_names


class FluxMonitorEditDialog(QtWidgets.QDialog):
    def __init__(self, store: ProjectStore, monitor: FluxMonitorConfig, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._exclude = monitor.name
        self._result: FluxMonitorConfig | None = None
        self.setWindowTitle("Edit Flux Monitor")

        self.name_input = QtWidgets.QLineEdit(monitor.name)
        self.center_x = QtWidgets.QLineEdit(monitor.center_x)
        self.center_y = QtWidgets.QLineEdit(monitor.center_y)
        self.size_x = QtWidgets.QLineEdit(monitor.size_x)
        self.size_y = QtWidgets.QLineEdit(monitor.size_y)
        self.fcen = QtWidgets.QLineEdit(monitor.fcen)
        self.df = QtWidgets.QLineEdit(monitor.df)
        self.nfreq = QtWidgets.QLineEdit(monitor.nfreq)

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Center X", self.center_x)
        form.addRow("Center Y", self.center_y)
        form.addRow("Size X", self.size_x)
        form.addRow("Size Y", self.size_y)
        form.addRow("fcen", self.fcen)
        form.addRow("df", self.df)
        form.addRow("nfreq", self.nfreq)

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
    def result(self) -> FluxMonitorConfig | None:
        return self._result

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        scope = active_scope(self.store)
        registry = scope.name_registry()
        name_result = validate_name(name, registry, exclude=self._exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return

        other_names = {m.name for m in scope.flux_monitors if m.name != self._exclude}
        if name in other_names:
            _set_invalid(self.name_input, True)
            _log_error(self.store, f"Name '{name}' is already in use.", self)
            return

        for widget, label in (
            (self.center_x, "Center X"),
            (self.center_y, "Center Y"),
            (self.size_x, "Size X"),
            (self.size_y, "Size Y"),
            (self.fcen, "fcen"),
            (self.df, "df"),
            (self.nfreq, "nfreq"),
        ):
            result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                return

        self._result = FluxMonitorConfig(
            name=name,
            center_x=self.center_x.text().strip(),
            center_y=self.center_y.text().strip(),
            size_x=self.size_x.text().strip(),
            size_y=self.size_y.text().strip(),
            fcen=self.fcen.text().strip(),
            df=self.df.text().strip(),
            nfreq=self.nfreq.text().strip(),
        )
        self.accept()
