from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import FIELD_COMPONENTS, SourceItem, normalize_bool
from ...primitives import SOURCE_REGISTRY, source_kind
from ...store import ProjectStore
from ...validation import (
    ValidationResult,
    evaluate_numeric_expression,
    validate_complex_expression,
    validate_name,
    validate_numeric_expression,
)
from ..common import _log_error, _mark_row_warning, _set_form_row_visible, _set_invalid
from ..dialogs import SourceEditDialog
from ..scope import active_scope, parameter_names

_CUSTOM_MANUAL_TEMPORAL_FIELDS = {
    "src_func",
    "start_time",
    "end_time",
    "is_integrated",
    "center_frequency",
    "fwidth",
}


def _source_field_choices(kind: str, field_id: str) -> tuple[str, ...]:
    for field in source_kind(kind).fields:
        if field.field_id == field_id:
            return field.choices
    return ()


def _source_ref_allows_blank(kind: str) -> bool:
    for field in source_kind(kind).fields:
        if field.field_id == "src":
            return not field.required
    return False


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
        self.spatial_header = QtWidgets.QLabel("Spatial component")
        self.temporal_header = QtWidgets.QLabel("Temporal component")
        for header in (self.spatial_header, self.temporal_header):
            header.setStyleSheet("font-weight: 600;")
        self.component_input = QtWidgets.QComboBox()
        self.component_input.addItems(list(FIELD_COMPONENTS))
        self.src_name = QtWidgets.QComboBox()
        self.center_x = QtWidgets.QLineEdit()
        self.center_y = QtWidgets.QLineEdit()
        self.size_x = QtWidgets.QLineEdit()
        self.size_y = QtWidgets.QLineEdit()
        self.fcen = QtWidgets.QLineEdit()
        self.df = QtWidgets.QLineEdit()
        self.amplitude = QtWidgets.QLineEdit()
        self.amp_func = QtWidgets.QLineEdit()
        self.src_func = QtWidgets.QLineEdit()
        self.start_time = QtWidgets.QLineEdit()
        self.end_time = QtWidgets.QLineEdit()
        self.is_integrated = QtWidgets.QCheckBox()
        self.center_frequency = QtWidgets.QLineEdit()
        self.fwidth = QtWidgets.QLineEdit()
        self.v0 = QtWidgets.QLineEdit()
        self.a = QtWidgets.QLineEdit()
        self.b = QtWidgets.QLineEdit()
        self.t0 = QtWidgets.QLineEdit()
        self.beam_x0_x = QtWidgets.QLineEdit()
        self.beam_x0_y = QtWidgets.QLineEdit()
        self.beam_kdir_x = QtWidgets.QLineEdit()
        self.beam_kdir_y = QtWidgets.QLineEdit()
        self.beam_w0 = QtWidgets.QLineEdit()
        self.beam_e0_x = QtWidgets.QLineEdit()
        self.beam_e0_y = QtWidgets.QLineEdit()
        self.beam_e0_z = QtWidgets.QLineEdit()
        self.eig_component = QtWidgets.QComboBox()
        self.eig_component.addItems(_source_field_choices("eigenmode", "eig_component"))
        self.eig_direction = QtWidgets.QComboBox()
        self.eig_direction.addItems(_source_field_choices("eigenmode", "eig_direction"))
        self.eig_band = QtWidgets.QLineEdit()
        self.eig_kpoint_x = QtWidgets.QLineEdit()
        self.eig_kpoint_y = QtWidgets.QLineEdit()
        self.eig_kpoint_z = QtWidgets.QLineEdit()
        self.eig_match_freq = QtWidgets.QCheckBox()
        self.eig_match_freq.setChecked(True)
        self.eig_parity = QtWidgets.QComboBox()
        self.eig_parity.addItems(_source_field_choices("eigenmode", "eig_parity"))
        self.eig_resolution = QtWidgets.QLineEdit()
        self.eig_tolerance = QtWidgets.QLineEdit()
        self.eig_lattice_size_x = QtWidgets.QLineEdit()
        self.eig_lattice_size_y = QtWidgets.QLineEdit()
        self.eig_lattice_center_x = QtWidgets.QLineEdit()
        self.eig_lattice_center_y = QtWidgets.QLineEdit()
        self.eig_vol_size_x = QtWidgets.QLineEdit()
        self.eig_vol_size_y = QtWidgets.QLineEdit()
        self.eig_vol_center_x = QtWidgets.QLineEdit()
        self.eig_vol_center_y = QtWidgets.QLineEdit()
        self._prop_widgets = {
            "src": self.src_name,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "fcen": self.fcen,
            "df": self.df,
            "amplitude": self.amplitude,
            "amp_func": self.amp_func,
            "src_func": self.src_func,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_integrated": self.is_integrated,
            "center_frequency": self.center_frequency,
            "fwidth": self.fwidth,
            "v0": self.v0,
            "a": self.a,
            "b": self.b,
            "t0": self.t0,
            "beam_x0_x": self.beam_x0_x,
            "beam_x0_y": self.beam_x0_y,
            "beam_kdir_x": self.beam_kdir_x,
            "beam_kdir_y": self.beam_kdir_y,
            "beam_w0": self.beam_w0,
            "beam_e0_x": self.beam_e0_x,
            "beam_e0_y": self.beam_e0_y,
            "beam_e0_z": self.beam_e0_z,
            "eig_component": self.eig_component,
            "eig_direction": self.eig_direction,
            "eig_band": self.eig_band,
            "eig_kpoint_x": self.eig_kpoint_x,
            "eig_kpoint_y": self.eig_kpoint_y,
            "eig_kpoint_z": self.eig_kpoint_z,
            "eig_match_freq": self.eig_match_freq,
            "eig_parity": self.eig_parity,
            "eig_resolution": self.eig_resolution,
            "eig_tolerance": self.eig_tolerance,
            "eig_lattice_size_x": self.eig_lattice_size_x,
            "eig_lattice_size_y": self.eig_lattice_size_y,
            "eig_lattice_center_x": self.eig_lattice_center_x,
            "eig_lattice_center_y": self.eig_lattice_center_y,
            "eig_vol_size_x": self.eig_vol_size_x,
            "eig_vol_size_y": self.eig_vol_size_y,
            "eig_vol_center_x": self.eig_vol_center_x,
            "eig_vol_center_y": self.eig_vol_center_y,
        }

        self.form = QtWidgets.QFormLayout()
        self.form.addRow("Name", self.name_input)
        self.form.addRow("ON", self.enabled_input)
        self.form.addRow("Type", self.kind_input)
        self.form.addRow(self.spatial_header)
        self.form.addRow("Component", self.component_input)
        self.form.addRow("SourceTime", self.src_name)
        self.form.addRow("Center X", self.center_x)
        self.form.addRow("Center Y", self.center_y)
        self.form.addRow("Size X", self.size_x)
        self.form.addRow("Size Y", self.size_y)
        self.form.addRow("Frequency", self.fcen)
        self.form.addRow("Bandwidth", self.df)
        self.form.addRow("Amplitude", self.amplitude)
        self.form.addRow("amp_func", self.amp_func)
        self.form.addRow(self.temporal_header)
        self.form.addRow("v0", self.v0)
        self.form.addRow("a", self.a)
        self.form.addRow("b", self.b)
        self.form.addRow("t0", self.t0)
        self.form.addRow("src_func", self.src_func)
        self.form.addRow("Start Time", self.start_time)
        self.form.addRow("End Time", self.end_time)
        self.form.addRow("Is Integrated", self.is_integrated)
        self.form.addRow("Center Frequency", self.center_frequency)
        self.form.addRow("Fwidth", self.fwidth)
        self.form.addRow("Focus X", self.beam_x0_x)
        self.form.addRow("Focus Y", self.beam_x0_y)
        self.form.addRow("Direction X", self.beam_kdir_x)
        self.form.addRow("Direction Y", self.beam_kdir_y)
        self.form.addRow("Waist Radius", self.beam_w0)
        self.form.addRow("E0 X", self.beam_e0_x)
        self.form.addRow("E0 Y", self.beam_e0_y)
        self.form.addRow("E0 Z", self.beam_e0_z)
        self.form.addRow("Eigen Component", self.eig_component)
        self.form.addRow("Eigen Direction", self.eig_direction)
        self.form.addRow("eig_band", self.eig_band)
        self.form.addRow("eig_kpoint X", self.eig_kpoint_x)
        self.form.addRow("eig_kpoint Y", self.eig_kpoint_y)
        self.form.addRow("eig_kpoint Z", self.eig_kpoint_z)
        self.form.addRow("eig_match_freq", self.eig_match_freq)
        self.form.addRow("eig_parity", self.eig_parity)
        self.form.addRow("eig_resolution", self.eig_resolution)
        self.form.addRow("eig_tolerance", self.eig_tolerance)
        self.form.addRow("eig_lattice Size X", self.eig_lattice_size_x)
        self.form.addRow("eig_lattice Size Y", self.eig_lattice_size_y)
        self.form.addRow("eig_lattice Center X", self.eig_lattice_center_x)
        self.form.addRow("eig_lattice Center Y", self.eig_lattice_center_y)
        self.form.addRow("eig_vol Size X", self.eig_vol_size_x)
        self.form.addRow("eig_vol Size Y", self.eig_vol_size_y)
        self.form.addRow("eig_vol Center X", self.eig_vol_center_x)
        self.form.addRow("eig_vol Center Y", self.eig_vol_center_y)

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
        self.src_name.currentTextChanged.connect(
            lambda _text: self._sync_kind_fields(self.kind_input.currentText())
        )
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

    def _field_value(self, field_id: str) -> str | bool:
        widget = self._prop_widgets[field_id]
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText().strip()
        if isinstance(widget, QtWidgets.QCheckBox):
            return widget.isChecked()
        return widget.text().strip()

    def _set_field_value(self, field_id: str, value: str | bool) -> None:
        widget = self._prop_widgets[field_id]
        if isinstance(widget, QtWidgets.QComboBox):
            widget.setCurrentText(str(value).strip())
        elif isinstance(widget, QtWidgets.QCheckBox):
            widget.setChecked(normalize_bool(value, False))
        else:
            widget.setText("" if value is None else str(value))

    def _sync_kind_fields(self, kind: str) -> None:
        self._refresh_source_ref_choices(
            str(self._field_value("src")),
            allow_blank=_source_ref_allows_blank(kind),
        )
        fields = source_kind(kind).fields
        visible_fields = {field.field_id for field in fields}
        custom_uses_ref = kind == "custom" and bool(str(self._field_value("src")).strip())
        for field in fields:
            widget = self._prop_widgets[field.field_id]
            if (
                isinstance(widget, QtWidgets.QLineEdit)
                and field.default != ""
                and not widget.text().strip()
            ):
                widget.setText(str(field.default))
        for field_id, widget in self._prop_widgets.items():
            visible = field_id in visible_fields
            if custom_uses_ref and field_id in _CUSTOM_MANUAL_TEMPORAL_FIELDS:
                visible = False
            _set_form_row_visible(self.form, widget, visible)
        _set_form_row_visible(
            self.form,
            self.component_input,
            kind not in {"gaussian_beam", "eigenmode"},
        )
        spatial_visible = kind == "custom" and any(field.section == "spatial" for field in fields)
        temporal_visible = kind == "custom" and any(field.section == "temporal" for field in fields)
        self.spatial_header.setVisible(spatial_visible)
        self.temporal_header.setVisible(temporal_visible)

    def _source_ref_names(self, exclude: str = "") -> list[str]:
        return [
            src.name
            for src in active_scope(self.store).sources
            if src.name
            and src.name != exclude
            and src.kind in {"continuous", "gaussian", "custom", "chirped_pulse"}
        ]

    def _refresh_source_ref_choices(
        self,
        current: str = "",
        exclude: str = "",
        *,
        allow_blank: bool = False,
    ) -> None:
        names = self._source_ref_names(exclude=exclude)
        self.src_name.blockSignals(True)
        self.src_name.clear()
        if allow_blank:
            self.src_name.addItem("")
        self.src_name.addItems(names)
        if current and current in names:
            self.src_name.setCurrentText(current)
        elif allow_blank:
            self.src_name.setCurrentText("")
        self.src_name.blockSignals(False)

    def _validate_source_ref(self, value: str, *, exclude: str = "") -> ValidationResult:
        if not value:
            return ValidationResult(False, "SourceTime source is required.")
        if value not in self._source_ref_names(exclude=exclude):
            return ValidationResult(False, f"Unknown SourceTime source: {value}")
        return ValidationResult(True, "")

    def _validate_field(self, field, value: str | bool, *, exclude: str = "") -> ValidationResult:
        allowed = parameter_names(self.store)
        if field.value_type == "enum":
            text = str(value).strip()
            if field.choices and text not in field.choices:
                return ValidationResult(False, f"Expected one of: {', '.join(field.choices)}")
            return ValidationResult(True, "")
        if field.value_type == "bool":
            return ValidationResult(True, "")
        if value == "" and not field.required:
            return ValidationResult(True, "")
        if field.value_type == "source_ref":
            return self._validate_source_ref(str(value).strip(), exclude=exclude)
        if field.value_type == "complex":
            return validate_complex_expression(
                str(value).strip(),
                allowed,
                extra_names=field.allowed_locals,
            )
        if field.value_type == "int":
            return self._validate_int_expression(str(value).strip(), allowed)
        return validate_numeric_expression(
            str(value).strip(),
            allowed,
            extra_names=field.allowed_locals,
        )

    def _validate_int_expression(self, value: str, allowed) -> ValidationResult:
        result = validate_numeric_expression(value, allowed)
        if not result.ok:
            return result
        try:
            evaluated = evaluate_numeric_expression(value, {})
        except ValueError:
            return result
        if abs(evaluated - round(evaluated)) > 1e-9:
            return ValidationResult(False, "Expression must evaluate to an integer.")
        return result

    def _validate_optional_region(self, prefix: str) -> bool:
        size_x = str(self._field_value(f"{prefix}_size_x")).strip()
        size_y = str(self._field_value(f"{prefix}_size_y")).strip()
        if bool(size_x) == bool(size_y):
            return True
        self.store.log_message(f"{prefix}: both size_x and size_y are required.")
        _set_invalid(self._prop_widgets[f"{prefix}_size_x"], not size_x)
        _set_invalid(self._prop_widgets[f"{prefix}_size_y"], not size_y)
        return False

    def _validate(self, name: str, kind: str, row: int) -> bool:
        scope = active_scope(self.store)
        registry = scope.name_registry()
        sources = scope.sources
        exclude = ""
        if 0 <= row < len(sources):
            exclude = sources[row].name
        name_result = validate_name(name, registry, exclude=exclude or None)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return False

        ok = True
        for field in source_kind(kind).fields:
            value = self._field_value(field.field_id)
            result = self._validate_field(field, value, exclude=exclude)
            _set_invalid(self._prop_widgets[field.field_id], not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.field_id}: {result.message}", self)
                ok = False
        if kind == "eigenmode":
            ok = self._validate_optional_region("eig_lattice") and ok
            ok = self._validate_optional_region("eig_vol") and ok
        return ok

    def _build_props(self, kind: str) -> dict[str, str | bool]:
        return {
            field.field_id: self._field_value(field.field_id)
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
        self._refresh_source_ref_choices(
            str(item.props.get("src", "")),
            exclude=item.name,
            allow_blank=_source_ref_allows_blank(item.kind),
        )
        for field_id in self._prop_widgets:
            self._set_field_value(field_id, item.props.get(field_id, ""))
        self._sync_kind_fields(item.kind)
        _set_invalid(self.name_input, False)

    def refresh(self) -> None:
        self.table.setRowCount(0)
        invalid: dict[str, str] = {}
        for src in active_scope(self.store).sources:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem("ON" if src.enabled else "OFF"))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(src.name))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(src.kind))
            self.table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem(
                    "" if src.kind in {"gaussian_beam", "eigenmode"} else src.component
                ),
            )
            message = ""
            for field in source_kind(src.kind).fields:
                value = src.props.get(field.field_id, "")
                result = self._validate_field(field, value, exclude=src.name)
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
