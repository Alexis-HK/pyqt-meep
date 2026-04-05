from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import GeometryItem
from ...primitives import GEOMETRY_REGISTRY, geometry_kind
from ...store import ProjectStore
from ...validation import validate_name, validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import active_scope, parameter_names


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
        mats = [mat.name for mat in store.state.materials]
        if item.material and item.material not in mats:
            mats.append(item.material)
        self.material_input.addItems(mats)
        if item.material:
            self.material_input.setCurrentText(item.material)
        self.center_x = QtWidgets.QLineEdit(item.props.get("center_x", ""))
        self.center_y = QtWidgets.QLineEdit(item.props.get("center_y", ""))
        self.size_x = QtWidgets.QLineEdit(item.props.get("size_x", ""))
        self.size_y = QtWidgets.QLineEdit(item.props.get("size_y", ""))
        self.radius = QtWidgets.QLineEdit(item.props.get("radius", ""))
        self._prop_widgets = {
            "center_x": self.center_x,
            "center_y": self.center_y,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "radius": self.radius,
        }

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Type", self.kind_input)
        form.addRow("Material", self.material_input)
        form.addRow("Center X", self.center_x)
        form.addRow("Center Y", self.center_y)
        form.addRow("Size X", self.size_x)
        form.addRow("Size Y", self.size_y)
        form.addRow("Radius", self.radius)

        self.save_button = QtWidgets.QPushButton("Save")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.save_button)
        btn_row.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_row)

        self.kind_input.currentTextChanged.connect(self._sync_kind_fields)
        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.reject)
        self._sync_kind_fields(self.kind_input.currentText())

    @property
    def result(self) -> GeometryItem | None:
        return self._result

    def _sync_kind_fields(self, kind: str) -> None:
        enabled = {field.field_id for field in geometry_kind(kind).fields}
        for field_id, widget in self._prop_widgets.items():
            widget.setEnabled(field_id in enabled)

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        kind = self.kind_input.currentText()
        material = self.material_input.currentText()
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

        for field in geometry_kind(kind).fields:
            widget = self._prop_widgets[field.field_id]
            result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{field.field_id}: {result.message}", self)
                return

        props = {
            field.field_id: self._prop_widgets[field.field_id].text().strip()
            for field in geometry_kind(kind).fields
        }
        self._result = GeometryItem(name=name, kind=kind, material=material, props=props)
        self.accept()
