from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import GEOMETRY_KINDS, GeometryItem
from ...store import ProjectStore
from ...validation import validate_name, validate_numeric_expression
from ..common import _log_error, _mark_row_warning, _set_invalid
from ..dialogs import GeometryEditDialog
from ..scope import active_scope, parameter_names


class GeometryTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._invalid_items: set[str] = set()

        self.name_input = QtWidgets.QLineEdit()
        self.kind_input = QtWidgets.QComboBox()
        self.kind_input.addItems(list(GEOMETRY_KINDS))
        self.material_input = QtWidgets.QComboBox()
        self.center_x = QtWidgets.QLineEdit()
        self.center_y = QtWidgets.QLineEdit()
        self.size_x = QtWidgets.QLineEdit()
        self.size_y = QtWidgets.QLineEdit()
        self.radius = QtWidgets.QLineEdit()

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Type", self.kind_input)
        form.addRow("Material", self.material_input)
        form.addRow("Center X", self.center_x)
        form.addRow("Center Y", self.center_y)
        form.addRow("Size X", self.size_x)
        form.addRow("Size Y", self.size_y)
        form.addRow("Radius", self.radius)

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
        if kind == "circle":
            self.radius.setEnabled(True)
            self.size_x.setEnabled(False)
            self.size_y.setEnabled(False)
        else:
            self.radius.setEnabled(False)
            self.size_x.setEnabled(True)
            self.size_y.setEnabled(True)

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

        if not material:
            _set_invalid(self.material_input, True)
            _log_error(self.store, "Material is required.", self)
            return False
        _set_invalid(self.material_input, False)

        allowed = parameter_names(self.store)
        fields = {
            "center_x": self.center_x,
            "center_y": self.center_y,
        }
        if kind == "circle":
            fields["radius"] = self.radius
        else:
            fields["size_x"] = self.size_x
            fields["size_y"] = self.size_y

        ok = True
        for label, widget in fields.items():
            result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                ok = False
        return ok

    def _on_add(self) -> None:
        name = self.name_input.text().strip()
        kind = self.kind_input.currentText()
        material = self.material_input.currentText()
        geometries = active_scope(self.store).geometries
        row = len(geometries)
        if not self._validate(name, kind, material, row):
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
        self.center_x.setText(item.props.get("center_x", ""))
        self.center_y.setText(item.props.get("center_y", ""))
        self.size_x.setText(item.props.get("size_x", ""))
        self.size_y.setText(item.props.get("size_y", ""))
        self.radius.setText(item.props.get("radius", ""))
        self._sync_kind_fields(item.kind)
        _set_invalid(self.name_input, False)

    def refresh(self) -> None:
        self.material_input.clear()
        self.material_input.addItems([mat.name for mat in self.store.state.materials])

        self.table.setRowCount(0)
        invalid: dict[str, str] = {}
        allowed = parameter_names(self.store)
        for geo in active_scope(self.store).geometries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(geo.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(geo.kind))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(geo.material))
            fields: list[tuple[str, str]] = [
                ("center_x", geo.props.get("center_x", "")),
                ("center_y", geo.props.get("center_y", "")),
            ]
            if geo.kind == "circle":
                fields.append(("radius", geo.props.get("radius", "")))
            else:
                fields.append(("size_x", geo.props.get("size_x", "")))
                fields.append(("size_y", geo.props.get("size_y", "")))
            message = ""
            for label, value in fields:
                result = validate_numeric_expression(value, allowed)
                if not result.ok:
                    message = f"Geometry '{geo.name}': {label} {result.message}"
                    break
            if message:
                key = geo.name or f"row-{row}"
                invalid[key] = message
                _mark_row_warning(self.table, row, message)

        for key, message in invalid.items():
            if key not in self._invalid_items:
                self.store.log_message(message)
        self._invalid_items = set(invalid.keys())
