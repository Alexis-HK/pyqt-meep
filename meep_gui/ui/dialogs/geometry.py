from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import GEOMETRY_KINDS, GeometryItem
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
        self.kind_input.addItems(list(GEOMETRY_KINDS))
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
        circle = kind == "circle"
        self.radius.setEnabled(circle)
        self.size_x.setEnabled(not circle)
        self.size_y.setEnabled(not circle)

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

        fields = {"center_x": self.center_x, "center_y": self.center_y}
        if kind == "circle":
            fields["radius"] = self.radius
        else:
            fields["size_x"] = self.size_x
            fields["size_y"] = self.size_y
        for label, widget in fields.items():
            result = validate_numeric_expression(widget.text().strip(), parameter_names(self.store))
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                return

        props = {
            "center_x": self.center_x.text().strip(),
            "center_y": self.center_y.text().strip(),
        }
        if kind == "circle":
            props["radius"] = self.radius.text().strip()
        else:
            props["size_x"] = self.size_x.text().strip()
            props["size_y"] = self.size_y.text().strip()
        self._result = GeometryItem(name=name, kind=kind, material=material, props=props)
        self.accept()
