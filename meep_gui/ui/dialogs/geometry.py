from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import GeometryItem
from ...primitives import GEOMETRY_REGISTRY, geometry_kind
from ...store import ProjectStore
from ...validation import validate_name, validate_numeric_expression
from ..common import _log_error, _set_form_row_visible, _set_invalid
from ..scope import active_scope, parameter_names


def _material_names(store: ProjectStore) -> list[str]:
    return [mat.name for mat in store.state.materials if mat.name]


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
    combo.addItems(choices)
    combo.setCurrentText(selected)


class GeometryEditDialog(QtWidgets.QDialog):
    def __init__(self, store: ProjectStore, item: GeometryItem, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._exclude = item.name
        self._result: GeometryItem | None = None
        self.setWindowTitle("Edit Geometry")

        self.name_input = QtWidgets.QLineEdit(item.name)
        self.kind_input = QtWidgets.QComboBox()
        self.kind_input.addItems(list(GEOMETRY_REGISTRY))
        self.kind_input.setCurrentText(item.kind)
        self.material_input = QtWidgets.QComboBox()
        mats = _material_names(store)
        _set_combo_items(self.material_input, mats, selected=item.material)
        self.inner_material = QtWidgets.QComboBox()
        _set_combo_items(
            self.inner_material,
            mats,
            selected=item.props.get("inner_material", ""),
            include_blank=True,
        )
        self.center_x = QtWidgets.QLineEdit(item.props.get("center_x", ""))
        self.center_y = QtWidgets.QLineEdit(item.props.get("center_y", ""))
        self.size_x = QtWidgets.QLineEdit(item.props.get("size_x", ""))
        self.size_y = QtWidgets.QLineEdit(item.props.get("size_y", ""))
        self.radius = QtWidgets.QLineEdit(item.props.get("radius", ""))
        self.width = QtWidgets.QLineEdit(item.props.get("width", ""))
        self._prop_widgets = {
            "inner_material": self.inner_material,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "radius": self.radius,
            "width": self.width,
        }

        self.form = QtWidgets.QFormLayout()
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
        self._sync_kind_fields(self.kind_input.currentText())

    @property
    def result(self) -> GeometryItem | None:
        return self._result

    def _sync_kind_fields(self, kind: str) -> None:
        visible_fields = {field.field_id for field in geometry_kind(kind).fields}
        for field_id, widget in self._prop_widgets.items():
            _set_form_row_visible(self.form, widget, field_id in visible_fields)

    def _field_value(self, field_id: str) -> str:
        widget = self._prop_widgets[field_id]
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText().strip()
        return widget.text().strip()

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        kind = self.kind_input.currentText()
        material = self.material_input.currentText().strip()
        registry = active_scope(self.store).name_registry()
        name_result = validate_name(name, registry, exclude=self._exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return
        if not material:
            _set_invalid(self.material_input, True)
            _log_error(self.store, "Material is required.", self)
            return
        _set_invalid(self.material_input, False)

        materials = set(_material_names(self.store))
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
                    return
                continue
            result = validate_numeric_expression(value, parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.field_id}: {result.message}", self)
                return

        props = {
            field.field_id: self._field_value(field.field_id)
            for field in geometry_kind(kind).fields
        }
        self._result = GeometryItem(name=name, kind=kind, material=material, props=props)
        self.accept()
