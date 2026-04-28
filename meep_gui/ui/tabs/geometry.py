from __future__ import annotations

from PyQt5 import QtWidgets

from ...geometry_script import validate_geometry_script
from ...model import GeometryItem
from ...primitives import GEOMETRY_REGISTRY, geometry_kind
from ...store import ProjectStore
from ...validation import evaluate_parameters, validate_name, validate_numeric_expression
from ..common import (
    _log_error,
    _mark_row_warning,
    _refresh_scroll_area,
    _scroll_area_for,
    _set_form_row_visible,
    _set_invalid,
)
from ..dialogs import GeometryEditDialog
from ..scope import active_scope, parameter_names


def _material_names(store: ProjectStore) -> list[str]:
    return [mat.name for mat in store.state.materials if mat.name]


def _editor_geometry_kinds() -> list[str]:
    return [kind for kind, spec in GEOMETRY_REGISTRY.items() if spec.editor_visible]


def _set_combo_items(
    combo: QtWidgets.QComboBox,
    items: list[str],
    *,
    selected: str = "",
    include_blank: bool = False,
) -> None:
    choices = list(items)
    if include_blank:
        choices.insert(0, "")
    if selected and selected not in choices:
        choices.append(selected)
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(choices)
    combo.setCurrentText(selected)
    combo.blockSignals(False)


class GeometryTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._invalid_items: set[str] = set()

        self.name_input = QtWidgets.QLineEdit()
        self.kind_input = QtWidgets.QComboBox()
        self.kind_input.addItems(_editor_geometry_kinds())
        self.material_input = QtWidgets.QComboBox()
        self.inner_material = QtWidgets.QComboBox()
        self.center_x = QtWidgets.QLineEdit()
        self.center_y = QtWidgets.QLineEdit()
        self.size_x = QtWidgets.QLineEdit()
        self.size_y = QtWidgets.QLineEdit()
        self.radius = QtWidgets.QLineEdit()
        self.width = QtWidgets.QLineEdit()
        self.script_source = QtWidgets.QPlainTextEdit()
        self.script_source.setPlaceholderText("emit(rect(center=(0, 0), size=(1, 1)), material=materials[\"silicon\"])")
        self.script_source.setMinimumHeight(160)
        self.validate_script_button = QtWidgets.QPushButton("Validate / Generate")
        self.script_summary = QtWidgets.QLabel("")
        self.script_summary.setWordWrap(True)
        self.script_errors = QtWidgets.QPlainTextEdit()
        self.script_errors.setReadOnly(True)
        self.script_errors.setMaximumHeight(90)
        self._prop_widgets = {
            "inner_material": self.inner_material,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "radius": self.radius,
            "width": self.width,
            "source": self.script_source,
        }

        self.form_container = QtWidgets.QWidget()
        self.form = QtWidgets.QFormLayout(self.form_container)
        self.form.addRow("Name", self.name_input)
        self.form.addRow("Type", self.kind_input)
        self.form.addRow("Material", self.material_input)
        self.form.addRow("Inner Material", self.inner_material)
        self.form.addRow("Center X", self.center_x)
        self.form.addRow("Center Y", self.center_y)
        self.form.addRow("Size X", self.size_x)
        self.form.addRow("Size Y", self.size_y)
        self.form.addRow("Radius", self.radius)
        self.form.addRow("Width", self.width)
        self.form.addRow("Script", self.script_source)
        self.form.addRow("", self.validate_script_button)
        self.form.addRow("Summary", self.script_summary)
        self.form.addRow("Errors", self.script_errors)
        self.form_scroll = _scroll_area_for(self.form_container)

        self.add_button = QtWidgets.QPushButton("Add")
        self.update_button = QtWidgets.QPushButton("Update")
        self.remove_button = QtWidgets.QPushButton("Remove")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.add_button)
        btn_row.addWidget(self.update_button)
        btn_row.addWidget(self.remove_button)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Material"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.form_scroll, stretch=1)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.kind_input.currentTextChanged.connect(self._sync_kind_fields)
        self.validate_script_button.clicked.connect(self._on_validate_script)
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
        visible_fields = {field.field_id for field in geometry_kind(kind).fields}
        scripted = kind == "scripted"
        _set_form_row_visible(self.form, self.material_input, not scripted)
        for field_id, widget in self._prop_widgets.items():
            _set_form_row_visible(self.form, widget, field_id in visible_fields)
        _set_form_row_visible(self.form, self.validate_script_button, scripted)
        _set_form_row_visible(self.form, self.script_summary, scripted)
        _set_form_row_visible(self.form, self.script_errors, scripted)
        _refresh_scroll_area(self.form_scroll)

    def _field_value(self, field_id: str) -> str:
        widget = self._prop_widgets[field_id]
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText().strip()
        if isinstance(widget, QtWidgets.QPlainTextEdit):
            return widget.toPlainText()
        return widget.text().strip()

    def _set_field_value(self, field_id: str, value: str) -> None:
        widget = self._prop_widgets[field_id]
        if isinstance(widget, QtWidgets.QComboBox):
            if value and widget.findText(value) < 0:
                widget.addItem(value)
            widget.setCurrentText(value)
        elif isinstance(widget, QtWidgets.QPlainTextEdit):
            widget.setPlainText(value)
        else:
            widget.setText(value)

    def _validate_script_source(self, source: str):
        values, results = evaluate_parameters(self.store.state.parameters)
        for result in results:
            if not result.ok:
                return None, f"Parameter '{result.name}': {result.message}"
        validation = validate_geometry_script(
            source,
            parameter_values=values,
            material_names=set(_material_names(self.store)),
            name_prefix=self.name_input.text().strip() or "scripted",
        )
        if not validation.ok:
            return validation, validation.errors[0] if validation.errors else "Invalid geometry script."
        return validation, ""

    def _update_script_summary(self, validation) -> None:
        if validation is None:
            self.script_summary.setText("")
            return
        deps = []
        if validation.referenced_parameters:
            deps.append("params: " + ", ".join(validation.referenced_parameters))
        if validation.referenced_materials:
            deps.append("materials: " + ", ".join(validation.referenced_materials))
        dep_text = "; ".join(deps) if deps else "no dependencies"
        self.script_summary.setText(
            f"{validation.emitted_count} generated polygons, "
            f"{validation.vertex_count} vertices; {dep_text}"
        )

    def _on_validate_script(self) -> bool:
        validation, error = self._validate_script_source(self.script_source.toPlainText())
        self._update_script_summary(validation)
        self.script_errors.setPlainText(error)
        if error:
            self.store.log_message(error)
            return False
        return True

    def _validate(self, name: str, kind: str, material: str, row: int) -> bool:
        scope = active_scope(self.store)
        registry = scope.name_registry()
        geometries = scope.geometries
        exclude = None
        if 0 <= row < len(geometries):
            exclude = geometries[row].name
        name_result = validate_name(name, registry, exclude=exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return False

        if kind == "scripted":
            source = self._field_value("source").strip()
            _set_invalid(self.script_source, not source)
            if not source:
                _log_error(self.store, "Script source is required.", self)
                return False
            validation, error = self._validate_script_source(source)
            self._update_script_summary(validation)
            self.script_errors.setPlainText(error)
            if error:
                _set_invalid(self.script_source, True)
                _log_error(self.store, error, self)
                return False
            _set_invalid(self.script_source, False)
            _set_invalid(self.material_input, False)
            return True

        if not material:
            _set_invalid(self.material_input, True)
            _log_error(self.store, "Material is required.", self)
            return False
        _set_invalid(self.material_input, False)

        allowed = parameter_names(self.store)
        materials = set(_material_names(self.store))
        ok = True
        for field in geometry_kind(kind).fields:
            widget = self._prop_widgets[field.field_id]
            value = self._field_value(field.field_id)
            if field.value_type == "material":
                valid = bool(value) and value in materials
                _set_invalid(widget, not valid)
                if not valid:
                    message = (
                        f"{field.label} is required."
                        if not value
                        else f"Unknown {field.label.lower()} '{value}'."
                    )
                    _log_error(self.store, message, self)
                    ok = False
                continue
            result = validate_numeric_expression(value, allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.field_id}: {result.message}", self)
                ok = False
        return ok

    def _build_props(self, kind: str) -> dict[str, str]:
        return {
            field.field_id: self._field_value(field.field_id)
            for field in geometry_kind(kind).fields
        }

    def _on_add(self) -> None:
        name = self.name_input.text().strip()
        kind = self.kind_input.currentText()
        material = "" if kind == "scripted" else self.material_input.currentText().strip()
        geometries = active_scope(self.store).geometries
        row = len(geometries)
        if not self._validate(name, kind, material, row):
            return
        props = self._build_props(kind)
        geometries.append(GeometryItem(name=name, kind=kind, material=material, props=props))
        self.store.notify()

    def _on_update(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        geometries = active_scope(self.store).geometries
        if row >= len(geometries):
            return
        item = geometries[row]
        dialog = GeometryEditDialog(self.store, item, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.result:
            geometries[row] = dialog.result
            self.store.notify()

    def _on_remove(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        geometries = active_scope(self.store).geometries
        if row >= len(geometries):
            return
        geometries.pop(row)
        self.store.notify()

    def _on_select(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        geometries = active_scope(self.store).geometries
        if row >= len(geometries):
            return
        item = geometries[row]
        self.name_input.setText(item.name)
        self.kind_input.setCurrentText(item.kind)
        self.material_input.setCurrentText(item.material)
        for field_id, widget in self._prop_widgets.items():
            self._set_field_value(field_id, item.props.get(field_id, ""))
        self._sync_kind_fields(item.kind)
        _set_invalid(self.name_input, False)

    def refresh(self) -> None:
        material_items = _material_names(self.store)
        _set_combo_items(
            self.material_input,
            material_items,
            selected=self.material_input.currentText().strip(),
        )
        _set_combo_items(
            self.inner_material,
            material_items,
            selected=self.inner_material.currentText().strip(),
            include_blank=True,
        )

        self.table.setRowCount(0)
        invalid: dict[str, str] = {}
        allowed = parameter_names(self.store)
        materials = set(material_items)
        for geo in active_scope(self.store).geometries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(geo.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(geo.kind))
            self.table.setItem(
                row,
                2,
                QtWidgets.QTableWidgetItem("generated" if geo.kind == "scripted" else geo.material),
            )
            message = ""
            if geo.kind == "scripted":
                validation, error = self._validate_script_source(str(geo.props.get("source", "")))
                if error:
                    message = f"Geometry '{geo.name}': {error}"
            else:
                for field in geometry_kind(geo.kind).fields:
                    value = geo.props.get(field.field_id, "")
                    if field.value_type == "material":
                        if not value:
                            message = f"Geometry '{geo.name}': {field.label} is required."
                            break
                        if value not in materials:
                            message = f"Geometry '{geo.name}': unknown {field.label.lower()} '{value}'."
                            break
                        continue
                    result = validate_numeric_expression(value, allowed)
                    if not result.ok:
                        message = f"Geometry '{geo.name}': {field.field_id} {result.message}"
                        break
            if message:
                key = geo.name or f"row-{row}"
                invalid[key] = message
                _mark_row_warning(self.table, row, message)

        for key, message in invalid.items():
            if key not in self._invalid_items:
                self.store.log_message(message)
        self._invalid_items = set(invalid.keys())
