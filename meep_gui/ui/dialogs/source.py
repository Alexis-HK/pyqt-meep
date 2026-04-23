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
        self.component_input = QtWidgets.QComboBox()
        self.component_input.addItems(list(FIELD_COMPONENTS))
        self.component_input.setCurrentText(item.component)
        self.src_name = QtWidgets.QComboBox()
        self.center_x = QtWidgets.QLineEdit(item.props.get("center_x", ""))
        self.center_y = QtWidgets.QLineEdit(item.props.get("center_y", ""))
        self.size_x = QtWidgets.QLineEdit(item.props.get("size_x", ""))
        self.size_y = QtWidgets.QLineEdit(item.props.get("size_y", ""))
        self.fcen = QtWidgets.QLineEdit(item.props.get("fcen", ""))
        self.df = QtWidgets.QLineEdit(item.props.get("df", ""))
        self.beam_x0_x = QtWidgets.QLineEdit(item.props.get("beam_x0_x", ""))
        self.beam_x0_y = QtWidgets.QLineEdit(item.props.get("beam_x0_y", ""))
        self.beam_kdir_x = QtWidgets.QLineEdit(item.props.get("beam_kdir_x", ""))
        self.beam_kdir_y = QtWidgets.QLineEdit(item.props.get("beam_kdir_y", ""))
        self.beam_w0 = QtWidgets.QLineEdit(item.props.get("beam_w0", ""))
        self.beam_e0_x = QtWidgets.QLineEdit(item.props.get("beam_e0_x", ""))
        self.beam_e0_y = QtWidgets.QLineEdit(item.props.get("beam_e0_y", ""))
        self.beam_e0_z = QtWidgets.QLineEdit(item.props.get("beam_e0_z", ""))
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

        self.save_button = QtWidgets.QPushButton("Save")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.save_button)
        btn_row.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addLayout(btn_row)

        self.kind_input.currentTextChanged.connect(self._sync_kind_fields)
        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.reject)
        self._refresh_source_ref_choices(item.props.get("src", ""))
        self._sync_kind_fields(self.kind_input.currentText())

    @property
    def result(self) -> SourceItem | None:
        return self._result

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

    def _source_ref_names(self) -> list[str]:
        return [
            src.name
            for src in active_scope(self.store).sources
            if src.name and src.name != self._exclude and src.kind in {"continuous", "gaussian"}
        ]

    def _refresh_source_ref_choices(self, current: str = "") -> None:
        names = self._source_ref_names()
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
            widget = self._prop_widgets[field.field_id]
            if field.value_type == "source_ref":
                result = self._validate_source_ref(widget.currentText().strip())
            elif field.value_type == "complex":
                result = validate_complex_expression(widget.text().strip(), parameter_names(self.store))
            else:
                result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.field_id}: {result.message}", self)
                return

        props = {
            field.field_id: (
                self._prop_widgets[field.field_id].currentText().strip()
                if field.value_type == "source_ref"
                else self._prop_widgets[field.field_id].text().strip()
            )
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
