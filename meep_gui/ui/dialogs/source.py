from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import FIELD_COMPONENTS, SourceItem, normalize_bool
from ...primitives import SOURCE_REGISTRY, source_kind
from ...store import ProjectStore
from ...validation import (
    ValidationResult,
    validate_complex_expression,
    validate_name,
    validate_numeric_expression,
)
from ..common import _log_error, _set_form_row_visible, _set_invalid
from ..scope import active_scope, parameter_names


class SourceEditDialog(QtWidgets.QDialog):
    def __init__(self, store: ProjectStore, item: SourceItem, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._exclude = item.name
        self._result: SourceItem | None = None
        self.setWindowTitle("Edit Source")

        self.name_input = QtWidgets.QLineEdit(item.name)
        self.enabled_input = QtWidgets.QCheckBox()
        self.enabled_input.setChecked(item.enabled)
        self.kind_input = QtWidgets.QComboBox()
        self.kind_input.addItems(list(SOURCE_REGISTRY))
        self.kind_input.setCurrentText(item.kind)
        self.spatial_header = QtWidgets.QLabel("Spatial component")
        self.temporal_header = QtWidgets.QLabel("Temporal component")
        for header in (self.spatial_header, self.temporal_header):
            header.setStyleSheet("font-weight: 600;")
        self.component_input = QtWidgets.QComboBox()
        self.component_input.addItems(list(FIELD_COMPONENTS))
        self.component_input.setCurrentText(item.component)
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

        self.save_button = QtWidgets.QPushButton("Save")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.save_button)
        btn_row.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addLayout(btn_row)

        for field_id in self._prop_widgets:
            self._set_field_value(field_id, item.props.get(field_id, ""))

        self.kind_input.currentTextChanged.connect(self._sync_kind_fields)
        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.reject)
        self._refresh_source_ref_choices(self.src_name.currentText())
        self._sync_kind_fields(self.kind_input.currentText())

    @property
    def result(self) -> SourceItem | None:
        return self._result

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
        self._refresh_source_ref_choices(str(self._field_value("src")), exclude=self._exclude)
        fields = source_kind(kind).fields
        visible_fields = {field.field_id for field in fields}
        for field in fields:
            widget = self._prop_widgets[field.field_id]
            if (
                isinstance(widget, QtWidgets.QLineEdit)
                and field.default != ""
                and not widget.text().strip()
            ):
                widget.setText(str(field.default))
        for field_id, widget in self._prop_widgets.items():
            _set_form_row_visible(self.form, widget, field_id in visible_fields)
        _set_form_row_visible(self.form, self.component_input, kind != "gaussian_beam")
        spatial_visible = kind == "custom" and any(field.section == "spatial" for field in fields)
        temporal_visible = kind == "custom" and any(field.section == "temporal" for field in fields)
        self.spatial_header.setVisible(spatial_visible)
        self.temporal_header.setVisible(temporal_visible)

    def _source_ref_names(self) -> list[str]:
        return [
            src.name
            for src in active_scope(self.store).sources
            if src.name
            and src.name != self._exclude
            and src.kind in {"continuous", "gaussian", "custom", "chirped_pulse"}
        ]

    def _refresh_source_ref_choices(self, current: str = "", exclude: str = "") -> None:
        names = [
            name
            for name in self._source_ref_names()
            if not exclude or name != exclude
        ]
        self.src_name.blockSignals(True)
        self.src_name.clear()
        self.src_name.addItems(names)
        if current and current in names:
            self.src_name.setCurrentText(current)
        self.src_name.blockSignals(False)

    def _validate_source_ref(self, value: str) -> ValidationResult:
        if not value:
            return ValidationResult(False, "SourceTime source is required.")
        if value not in self._source_ref_names():
            return ValidationResult(False, f"Unknown SourceTime source: {value}")
        return ValidationResult(True, "")

    def _validate_field(self, field, value: str | bool) -> ValidationResult:
        allowed = parameter_names(self.store)
        if field.value_type == "bool":
            return ValidationResult(True, "")
        if value == "" and not field.required:
            return ValidationResult(True, "")
        if field.value_type == "source_ref":
            return self._validate_source_ref(str(value).strip())
        if field.value_type == "complex":
            return validate_complex_expression(
                str(value).strip(),
                allowed,
                extra_names=field.allowed_locals,
            )
        return validate_numeric_expression(
            str(value).strip(),
            allowed,
            extra_names=field.allowed_locals,
        )

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        kind = self.kind_input.currentText()
        registry = active_scope(self.store).name_registry()
        name_result = validate_name(name, registry, exclude=self._exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return

        for field in source_kind(kind).fields:
            value = self._field_value(field.field_id)
            result = self._validate_field(field, value)
            _set_invalid(self._prop_widgets[field.field_id], not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.field_id}: {result.message}", self)
                return

        props = {
            field.field_id: self._field_value(field.field_id)
            for field in source_kind(kind).fields
        }
        self._result = SourceItem(
            name=name,
            kind=kind,
            component=self.component_input.currentText(),
            props=props,
            enabled=self.enabled_input.isChecked(),
        )
        self.accept()
