from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import FIELD_COMPONENTS, SourceItem
from ...primitives import SOURCE_REGISTRY, source_kind
from ...store import ProjectStore
from ...validation import (
    ValidationResult,
    validate_complex_expression,
    validate_name,
    validate_numeric_expression,
)
from ..common import _log_error, _mark_row_warning, _set_form_row_visible, _set_invalid
from ..dialogs import SourceEditDialog
from ..scope import active_scope, parameter_names


class SourcesTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._invalid_items: set[str] = set()

        self.name_input = QtWidgets.QLineEdit()
        self.enabled_input = QtWidgets.QCheckBox()
        self.enabled_input.setChecked(True)
        self.kind_input = QtWidgets.QComboBox()
        self.kind_input.addItems(list(SOURCE_REGISTRY))
        self.component_input = QtWidgets.QComboBox()
        self.component_input.addItems(list(FIELD_COMPONENTS))
        self.src_name = QtWidgets.QComboBox()
        self.center_x = QtWidgets.QLineEdit()
        self.center_y = QtWidgets.QLineEdit()
        self.size_x = QtWidgets.QLineEdit()
        self.size_y = QtWidgets.QLineEdit()
        self.fcen = QtWidgets.QLineEdit()
        self.df = QtWidgets.QLineEdit()
        self.beam_x0_x = QtWidgets.QLineEdit()
        self.beam_x0_y = QtWidgets.QLineEdit()
        self.beam_kdir_x = QtWidgets.QLineEdit()
        self.beam_kdir_y = QtWidgets.QLineEdit()
        self.beam_w0 = QtWidgets.QLineEdit()
        self.beam_e0_x = QtWidgets.QLineEdit()
        self.beam_e0_y = QtWidgets.QLineEdit()
        self.beam_e0_z = QtWidgets.QLineEdit()
        self._prop_widgets = {
            "src": self.src_name,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "fcen": self.fcen,
            "df": self.df,
            "beam_x0_x": self.beam_x0_x,
            "beam_x0_y": self.beam_x0_y,
            "beam_kdir_x": self.beam_kdir_x,
            "beam_kdir_y": self.beam_kdir_y,
            "beam_w0": self.beam_w0,
            "beam_e0_x": self.beam_e0_x,
            "beam_e0_y": self.beam_e0_y,
            "beam_e0_z": self.beam_e0_z,
        }

        self.form = QtWidgets.QFormLayout()
        self.form.addRow("Name", self.name_input)
        self.form.addRow("ON", self.enabled_input)
        self.form.addRow("Type", self.kind_input)
        self.form.addRow("Component", self.component_input)
        self.form.addRow("SourceTime", self.src_name)
        self.form.addRow("Center X", self.center_x)
        self.form.addRow("Center Y", self.center_y)
        self.form.addRow("Size X", self.size_x)
        self.form.addRow("Size Y", self.size_y)
        self.form.addRow("Frequency", self.fcen)
        self.form.addRow("Bandwidth", self.df)
        self.form.addRow("Focus X", self.beam_x0_x)
        self.form.addRow("Focus Y", self.beam_x0_y)
        self.form.addRow("Direction X", self.beam_kdir_x)
        self.form.addRow("Direction Y", self.beam_kdir_y)
        self.form.addRow("Waist Radius", self.beam_w0)
        self.form.addRow("E0 X", self.beam_e0_x)
        self.form.addRow("E0 Y", self.beam_e0_y)
        self.form.addRow("E0 Z", self.beam_e0_z)

        self.add_button = QtWidgets.QPushButton("Add")
        self.update_button = QtWidgets.QPushButton("Update")
        self.remove_button = QtWidgets.QPushButton("Remove")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.add_button)
        btn_row.addWidget(self.update_button)
        btn_row.addWidget(self.remove_button)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ON", "Name", "Type", "Component"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.form)
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
        self._refresh_source_ref_choices(self.src_name.currentText())
        fields = source_kind(kind).fields
        for field in fields:
            widget = self._prop_widgets[field.field_id]
            if (
                field.default
                and isinstance(widget, QtWidgets.QLineEdit)
                and not widget.text().strip()
            ):
                widget.setText(field.default)
        visible_fields = {field.field_id for field in fields}
        for field_id, widget in self._prop_widgets.items():
            _set_form_row_visible(self.form, widget, field_id in visible_fields)
        _set_form_row_visible(self.form, self.component_input, kind != "gaussian_beam")

    def _source_ref_names(self, exclude: str = "") -> list[str]:
        return [
            src.name
            for src in active_scope(self.store).sources
            if src.name and src.name != exclude and src.kind in {"continuous", "gaussian"}
        ]

    def _refresh_source_ref_choices(self, current: str = "", exclude: str = "") -> None:
        names = self._source_ref_names(exclude=exclude)
        self.src_name.blockSignals(True)
        self.src_name.clear()
        self.src_name.addItems(names)
        if current and current in names:
            self.src_name.setCurrentText(current)
        self.src_name.blockSignals(False)

    def _validate_source_ref(self, value: str, *, exclude: str = "") -> ValidationResult:
        if not value:
            return ValidationResult(False, "SourceTime source is required.")
        if value not in self._source_ref_names(exclude=exclude):
            return ValidationResult(False, f"Unknown SourceTime source: {value}")
        return ValidationResult(True, "")

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
            if field.value_type == "source_ref":
                result = self._validate_source_ref(widget.currentText().strip())
            elif field.value_type == "complex":
                result = validate_complex_expression(widget.text().strip(), allowed)
            else:
                result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.field_id}: {result.message}", self)
                ok = False
        return ok

    def _build_props(self, kind: str) -> dict[str, str]:
        return {
            field.field_id: (
                self._prop_widgets[field.field_id].currentText().strip()
                if field.value_type == "source_ref"
                else self._prop_widgets[field.field_id].text().strip()
            )
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
                enabled=self.enabled_input.isChecked(),
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
        self.enabled_input.setChecked(item.enabled)
        self.kind_input.setCurrentText(item.kind)
        self.component_input.setCurrentText(item.component)
        self._refresh_source_ref_choices(item.props.get("src", ""), exclude=item.name)
        for field_id, widget in self._prop_widgets.items():
            if isinstance(widget, QtWidgets.QComboBox):
                widget.setCurrentText(item.props.get(field_id, ""))
            else:
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
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem("ON" if src.enabled else "OFF"))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(src.name))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(src.kind))
            self.table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem("" if src.kind == "gaussian_beam" else src.component),
            )
            message = ""
            for field in source_kind(src.kind).fields:
                value = src.props.get(field.field_id, "")
                if field.value_type == "source_ref":
                    result = self._validate_source_ref(value, exclude=src.name)
                elif field.value_type == "complex":
                    result = validate_complex_expression(value, allowed)
                else:
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
