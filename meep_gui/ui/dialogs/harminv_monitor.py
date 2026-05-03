from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import FIELD_COMPONENTS, HarminvMonitorConfig
from ...store import ProjectStore
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


class HarminvMonitorEditDialog(QtWidgets.QDialog):
    def __init__(self, store: ProjectStore, monitor: HarminvMonitorConfig, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._result: HarminvMonitorConfig | None = None
        self.setWindowTitle("Edit Harminv Monitor")

        self.component = QtWidgets.QComboBox()
        self.component.addItems(list(FIELD_COMPONENTS))
        self.component.setCurrentText(monitor.component)
        self.point_x = QtWidgets.QLineEdit(monitor.point_x)
        self.point_y = QtWidgets.QLineEdit(monitor.point_y)
        self.fcen = QtWidgets.QLineEdit(monitor.fcen)
        self.df = QtWidgets.QLineEdit(monitor.df)

        form = QtWidgets.QFormLayout()
        form.addRow("Component", self.component)
        form.addRow("Point X", self.point_x)
        form.addRow("Point Y", self.point_y)
        form.addRow("fcen", self.fcen)
        form.addRow("df", self.df)

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
    def result(self) -> HarminvMonitorConfig | None:
        return self._result

    def _on_save(self) -> None:
        component = self.component.currentText()
        if component not in FIELD_COMPONENTS:
            _set_invalid(self.component, True)
            _log_error(self.store, "Component: unsupported component.", self)
            return
        _set_invalid(self.component, False)

        fields = [
            (self.point_x, "Point X"),
            (self.point_y, "Point Y"),
            (self.fcen, "fcen"),
            (self.df, "df"),
        ]
        allowed = parameter_names(self.store)
        for widget, label in fields:
            result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                return

        self._result = HarminvMonitorConfig(
            component=component,
            point_x=self.point_x.text().strip(),
            point_y=self.point_y.text().strip(),
            fcen=self.fcen.text().strip(),
            df=self.df.text().strip(),
        )
        self.accept()
