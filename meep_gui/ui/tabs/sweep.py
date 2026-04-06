from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import SweepConfig, SweepParameter
from ...store import ProjectStore
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..dialogs import SweepEditDialog
from ..scope import parameter_names


class SweepTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._pending_select_name: str | None = None

        self.enabled = QtWidgets.QCheckBox("Enable sweep")

        settings_form = QtWidgets.QFormLayout()
        settings_form.addRow("", self.enabled)

        self.param_name = QtWidgets.QComboBox()
        self.param_name.setEditable(False)
        self.start = QtWidgets.QLineEdit()
        self.stop = QtWidgets.QLineEdit()
        self.steps = QtWidgets.QLineEdit()
        param_form = QtWidgets.QFormLayout()
        param_form.addRow("Parameter", self.param_name)
        param_form.addRow("Start", self.start)
        param_form.addRow("Stop", self.stop)
        param_form.addRow("Step Size", self.steps)

        self.add_button = QtWidgets.QPushButton("Add")
        self.update_button = QtWidgets.QPushButton("Update")
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.update_button.setDisabled(True)
        self.remove_button.setDisabled(True)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.add_button)
        btn_row.addWidget(self.update_button)
        btn_row.addWidget(self.remove_button)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Parameter", "Start", "Stop", "Step Size"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(settings_form)
        layout.addWidget(QtWidgets.QLabel("Sweep Parameters"))
        layout.addLayout(param_form)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)
        layout.addStretch(1)

        self.enabled.toggled.connect(self._apply_enabled)
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

    def _refresh_param_names(self) -> None:
        current = self.param_name.currentText()
        self.param_name.blockSignals(True)
        self.param_name.clear()
        self.param_name.addItems([p.name for p in self.store.state.parameters if p.name])
        idx = self.param_name.findText(current)
        if idx >= 0:
            self.param_name.setCurrentIndex(idx)
        elif self.param_name.count() > 0:
            self.param_name.setCurrentIndex(0)
        self.param_name.blockSignals(False)

    def _update_buttons(self) -> None:
        enabled = self.enabled.isChecked()
        self.table.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        row = self._current_row()
        can_edit = enabled and 0 <= row < len(self.store.state.sweep.params)
        self.update_button.setEnabled(can_edit)
        self.remove_button.setEnabled(can_edit)

    def _validate_param(self, row: int) -> bool:
        name = self.param_name.currentText().strip()
        if not name:
            _set_invalid(self.param_name, True)
            _log_error(self.store, "Sweep parameter name is required.", self)
            return False
        if name not in parameter_names(self.store):
            _set_invalid(self.param_name, True)
            _log_error(self.store, f"Sweep parameter '{name}' is not defined in Parameters.", self)
            return False
        duplicate = [p.name for i, p in enumerate(self.store.state.sweep.params) if i != row]
        if name in duplicate:
            _set_invalid(self.param_name, True)
            _log_error(self.store, f"Sweep parameter '{name}' is already configured.", self)
            return False
        _set_invalid(self.param_name, False)

        ok = True
        for widget, label in ((self.start, "Start"), (self.stop, "Stop"), (self.steps, "Steps")):
            result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                ok = False
        return ok

    def _apply_enabled(self) -> None:
        sweep = self.store.state.sweep
        self.store.state.sweep = SweepConfig(
            enabled=self.enabled.isChecked(),
            params=list(sweep.params),
        )
        self._update_buttons()
        self.store.notify()

    def _build_param(self) -> SweepParameter:
        return SweepParameter(
            name=self.param_name.currentText().strip(),
            start=self.start.text().strip(),
            stop=self.stop.text().strip(),
            steps=self.steps.text().strip(),
        )

    def _replace_params(self, params: list[SweepParameter]) -> None:
        sweep = self.store.state.sweep
        self.store.state.sweep = SweepConfig(
            enabled=sweep.enabled,
            params=params,
        )
        self.store.notify()

    def _on_add(self) -> None:
        row = len(self.store.state.sweep.params)
        if not self._validate_param(row):
            return
        param = self._build_param()
        params = list(self.store.state.sweep.params) + [param]
        self._pending_select_name = param.name
        self._replace_params(params)

    def _on_update(self) -> None:
        row = self._current_row()
        if row < 0 or row >= len(self.store.state.sweep.params):
            return
        item = self.store.state.sweep.params[row]
        dialog = SweepEditDialog(self.store, item, row, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted or dialog.result is None:
            return
        param = dialog.result
        params = list(self.store.state.sweep.params)
        params[row] = param
        self._pending_select_name = param.name
        self._replace_params(params)

    def _on_remove(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        params = list(self.store.state.sweep.params)
        params.pop(row)
        if row < len(params):
            self._pending_select_name = params[row].name
        elif params:
            self._pending_select_name = params[-1].name
        else:
            self._pending_select_name = None
        self._replace_params(params)

    def _on_select(self) -> None:
        row = self._current_row()
        if row < 0 or row >= len(self.store.state.sweep.params):
            self._update_buttons()
            return
        param = self.store.state.sweep.params[row]
        idx = self.param_name.findText(param.name)
        if idx >= 0:
            self.param_name.setCurrentIndex(idx)
        self.start.setText(param.start)
        self.stop.setText(param.stop)
        self.steps.setText(param.steps)
        self._update_buttons()

    def refresh(self) -> None:
        sweep = self.store.state.sweep
        selected_name = self._pending_select_name
        if selected_name is None:
            row = self._current_row()
            if 0 <= row < len(sweep.params):
                selected_name = sweep.params[row].name

        self._refresh_param_names()
        self.enabled.blockSignals(True)
        self.enabled.setChecked(sweep.enabled)
        self.enabled.blockSignals(False)

        self.table.setRowCount(0)
        for item in sweep.params:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(item.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(item.start))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(item.stop))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(item.steps))

        self._pending_select_name = None
        if selected_name:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and item.text() == selected_name:
                    self.table.setCurrentCell(row, 0)
                    break
        self._update_buttons()
