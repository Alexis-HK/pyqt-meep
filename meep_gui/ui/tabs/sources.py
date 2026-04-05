from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import FIELD_COMPONENTS, SourceItem
from ...primitives import SOURCE_REGISTRY, source_kind
from ...store import ProjectStore
from ...validation import validate_name, validate_numeric_expression
from ..common import _log_error, _mark_row_warning, _set_invalid
from ..dialogs import SourceEditDialog
from ..scope import active_scope, parameter_names


class SourcesTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._invalid_items: set[str] = set()

        self.name_input = QtWidgets.QLineEdit()
        self.kind_input = QtWidgets.QComboBox()
        self.kind_input.addItems(list(SOURCE_REGISTRY))
        self.component_input = QtWidgets.QComboBox()
        self.component_input.addItems(list(FIELD_COMPONENTS))
        self.center_x = QtWidgets.QLineEdit()
        self.center_y = QtWidgets.QLineEdit()
        self.size_x = QtWidgets.QLineEdit()
        self.size_y = QtWidgets.QLineEdit()
        self.fcen = QtWidgets.QLineEdit()
        self.df = QtWidgets.QLineEdit()
        self._prop_widgets = {
            "center_x": self.center_x,
            "center_y": self.center_y,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "fcen": self.fcen,
            "df": self.df,
        }

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Type", self.kind_input)
        form.addRow("Component", self.component_input)
        form.addRow("Center X", self.center_x)
        form.addRow("Center Y", self.center_y)
        form.addRow("Size X", self.size_x)
        form.addRow("Size Y", self.size_y)
        form.addRow("Frequency", self.fcen)
        form.addRow("Bandwidth", self.df)

        self.add_button = QtWidgets.QPushButton("Add")
        self.update_button = QtWidgets.QPushButton("Update")
        self.remove_button = QtWidgets.QPushButton("Remove")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.add_button)
        btn_row.addWidget(self.update_button)
        btn_row.addWidget(self.remove_button)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Component"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.kind_input.currentTextChanged.connect(self._sync_kind_fields)
        self.add_button.clicked.connect(self._on_add)
        self.update_button.clicked.connect(self._on_update)
        self.remove_button.clicked.connect(self._on_remove)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.store.state_changed.connect(self.refresh)

        self.refresh()
        self._sync_kind_fields(self.kind_input.currentText())

    def _current_row(self) -> int:
        selection = self.table.selectionModel().selectedRows()
        if selection:
            return selection[0].row()
        return -1

    def _sync_kind_fields(self, kind: str) -> None:
        enabled = {field.field_id for field in source_kind(kind).fields}
        for field_id, widget in self._prop_widgets.items():
            widget.setEnabled(field_id in enabled)

    def _validate(self, name: str, kind: str, row: int) -> bool:
        scope = active_scope(self.store)
        registry = scope.name_registry()
        sources = scope.sources
        exclude = None
        if 0 <= row < len(sources):
            exclude = sources[row].name
        name_result = validate_name(name, registry, exclude=exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return False

        allowed = parameter_names(self.store)
        ok = True
        for field in source_kind(kind).fields:
            widget = self._prop_widgets[field.field_id]
            result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.field_id}: {result.message}", self)
                ok = False
        return ok

    def _build_props(self, kind: str) -> dict[str, str]:
        return {
            field.field_id: self._prop_widgets[field.field_id].text().strip()
            for field in source_kind(kind).fields
        }

    def _on_add(self) -> None:
        name = self.name_input.text().strip()
        kind = self.kind_input.currentText()
        sources = active_scope(self.store).sources
        row = len(sources)
        if not self._validate(name, kind, row):
            return
        props = self._build_props(kind)
        sources.append(
            SourceItem(
                name=name,
                kind=kind,
                component=self.component_input.currentText(),
                props=props,
            )
        )
        self.store.notify()

    def _on_update(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        sources = active_scope(self.store).sources
        if row >= len(sources):
            return
        item = sources[row]
        dialog = SourceEditDialog(self.store, item, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.result:
            sources[row] = dialog.result
            self.store.notify()

    def _on_remove(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        sources = active_scope(self.store).sources
        if row >= len(sources):
            return
        sources.pop(row)
        self.store.notify()

    def _on_select(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        sources = active_scope(self.store).sources
        if row >= len(sources):
            return
        item = sources[row]
        self.name_input.setText(item.name)
        self.kind_input.setCurrentText(item.kind)
        self.component_input.setCurrentText(item.component)
        for field_id, widget in self._prop_widgets.items():
            widget.setText(item.props.get(field_id, ""))
        self._sync_kind_fields(item.kind)
        _set_invalid(self.name_input, False)

    def refresh(self) -> None:
        self.table.setRowCount(0)
        invalid: dict[str, str] = {}
        allowed = parameter_names(self.store)
        for src in active_scope(self.store).sources:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(src.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(src.kind))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(src.component))
            message = ""
            for field in source_kind(src.kind).fields:
                value = src.props.get(field.field_id, "")
                result = validate_numeric_expression(value, allowed)
                if not result.ok:
                    message = f"Source '{src.name}': {field.field_id} {result.message}"
                    break
            if message:
                key = src.name or f"row-{row}"
                invalid[key] = message
                _mark_row_warning(self.table, row, message)

        for key, message in invalid.items():
            if key not in self._invalid_items:
                self.store.log_message(message)
        self._invalid_items = set(invalid.keys())
