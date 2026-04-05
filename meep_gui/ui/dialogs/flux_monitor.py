from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import FluxMonitorConfig
from ...primitives import DEFAULT_MONITOR_KIND, monitor_kind
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
        self._monitor_spec = monitor_kind(DEFAULT_MONITOR_KIND)
        self._field_widgets = {
            "center_x": self.center_x,
            "center_y": self.center_y,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "fcen": self.fcen,
            "df": self.df,
            "nfreq": self.nfreq,
        }

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        for field in self._monitor_spec.fields:
            form.addRow(field.label, self._field_widgets[field.field_id])

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

        for field in self._monitor_spec.fields:
            widget = self._field_widgets[field.field_id]
            result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.label}: {result.message}", self)
                return

        props = {
            field.field_id: self._field_widgets[field.field_id].text().strip()
            for field in self._monitor_spec.fields
        }
        self._result = FluxMonitorConfig(name=name, **props)
        self.accept()
