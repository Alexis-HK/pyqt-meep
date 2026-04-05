from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import FluxMonitorConfig
from ...primitives import DEFAULT_MONITOR_KIND, monitor_kind
from ...store import ProjectStore
from ...validation import validate_name, validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..dialogs import FluxMonitorEditDialog
from ..scope import active_scope, parameter_names


class FluxMonitorsTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._pending_select_name: str | None = None

        self.name_input = QtWidgets.QLineEdit()
        self.center_x = QtWidgets.QLineEdit()
        self.center_y = QtWidgets.QLineEdit()
        self.size_x = QtWidgets.QLineEdit()
        self.size_y = QtWidgets.QLineEdit()
        self.fcen = QtWidgets.QLineEdit()
        self.df = QtWidgets.QLineEdit()
        self.nfreq = QtWidgets.QLineEdit()
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
        self.table.setHorizontalHeaderLabels(["Name", "Center", "Size", "Spectrum"])
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

    def _resolve_row_for_edit(self) -> int:
        monitors = active_scope(self.store).flux_monitors
        row = self._current_row()
        if 0 <= row < len(monitors):
            return row
        name = self.name_input.text().strip()
        if not name:
            return -1
        for idx, monitor in enumerate(monitors):
            if monitor.name == name:
                return idx
        return -1

    def _update_buttons(self) -> None:
        can_edit = self._resolve_row_for_edit() >= 0
        self.update_button.setDisabled(not can_edit)
        self.remove_button.setDisabled(not can_edit)

    def _validate(self, row: int) -> bool:
        name = self.name_input.text().strip()
        scope = active_scope(self.store)
        monitors = scope.flux_monitors
        registry = scope.name_registry()
        exclude = None
        if 0 <= row < len(monitors):
            exclude = monitors[row].name
        name_result = validate_name(name, registry, exclude=exclude)
        if name_result.ok:
            other_names = [m.name for i, m in enumerate(monitors) if i != row]
            if name in other_names:
                _set_invalid(self.name_input, True)
                _log_error(self.store, f"Name '{name}' is already in use.", self)
                return False
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return False

        ok = True
        for field in self._monitor_spec.fields:
            widget = self._field_widgets[field.field_id]
            result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.label}: {result.message}", self)
                ok = False
        return ok

    def _build_monitor(self) -> FluxMonitorConfig:
        props = {
            field.field_id: self._field_widgets[field.field_id].text().strip()
            for field in self._monitor_spec.fields
        }
        return FluxMonitorConfig(name=self.name_input.text().strip(), **props)

    def _on_add(self) -> None:
        monitors = active_scope(self.store).flux_monitors
        row = len(monitors)
        if not self._validate(row):
            return
        monitor = self._build_monitor()
        monitors.append(monitor)
        self._pending_select_name = monitor.name
        self.store.notify()

    def _on_update(self) -> None:
        monitors = active_scope(self.store).flux_monitors
        row = self._resolve_row_for_edit()
        if row < 0 or row >= len(monitors):
            return
        item = monitors[row]
        dialog = FluxMonitorEditDialog(self.store, item, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.result:
            monitors[row] = dialog.result
            self._pending_select_name = dialog.result.name
            self.store.notify()

    def _on_remove(self) -> None:
        monitors = active_scope(self.store).flux_monitors
        row = self._resolve_row_for_edit()
        if row < 0:
            return
        monitors.pop(row)
        if row < len(monitors):
            self._pending_select_name = monitors[row].name
        elif monitors:
            self._pending_select_name = monitors[-1].name
        else:
            self._pending_select_name = None
        self.store.notify()

    def _on_select(self) -> None:
        row = self._current_row()
        if row < 0:
            self._update_buttons()
            return
        monitors = active_scope(self.store).flux_monitors
        if row >= len(monitors):
            self._update_buttons()
            return
        monitor = monitors[row]
        self.name_input.setText(monitor.name)
        self.center_x.setText(monitor.center_x)
        self.center_y.setText(monitor.center_y)
        self.size_x.setText(monitor.size_x)
        self.size_y.setText(monitor.size_y)
        self.fcen.setText(monitor.fcen)
        self.df.setText(monitor.df)
        self.nfreq.setText(monitor.nfreq)
        self._update_buttons()

    def refresh(self) -> None:
        monitors = active_scope(self.store).flux_monitors
        selected_name = self._pending_select_name
        if selected_name is None:
            row = self._current_row()
            if 0 <= row < len(monitors):
                selected_name = monitors[row].name

        self.table.setRowCount(0)
        for monitor in monitors:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(monitor.name))
            self.table.setItem(
                row, 1, QtWidgets.QTableWidgetItem(f"({monitor.center_x}, {monitor.center_y})")
            )
            self.table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(f"({monitor.size_x}, {monitor.size_y})")
            )
            self.table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem(f"fcen={monitor.fcen}, df={monitor.df}, nfreq={monitor.nfreq}"),
            )

        self._pending_select_name = None
        if selected_name:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and item.text() == selected_name:
                    self.table.setCurrentCell(row, 0)
                    break
        self._update_buttons()
