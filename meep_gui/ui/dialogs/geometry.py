from __future__ import annotations

from PyQt5 import QtWidgets

from ...geometry_script import validate_geometry_script
from ...model import GeometryItem
from ...primitives import GEOMETRY_REGISTRY, geometry_kind
from ...store import ProjectStore
from ...validation import build_project_rng, evaluate_parameters, validate_name, validate_numeric_expression
from ..common import _log_error, _set_form_row_visible, _set_invalid
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
        self.kind_input.addItems(_editor_geometry_kinds())
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
        self.script_source = QtWidgets.QPlainTextEdit(str(item.props.get("source", "")))
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
        self.form.addRow("Script", self.script_source)
        self.form.addRow("", self.validate_script_button)
        self.form.addRow("Summary", self.script_summary)
        self.form.addRow("Errors", self.script_errors)

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
        self.validate_script_button.clicked.connect(self._on_validate_script)
        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.reject)
        self._sync_kind_fields(self.kind_input.currentText())

    @property
    def result(self) -> GeometryItem | None:
        return self._result

    def _sync_kind_fields(self, kind: str) -> None:
        visible_fields = {field.field_id for field in geometry_kind(kind).fields}
        scripted = kind == "scripted"
        _set_form_row_visible(self.form, self.material_input, not scripted)
        for field_id, widget in self._prop_widgets.items():
            _set_form_row_visible(self.form, widget, field_id in visible_fields)
        _set_form_row_visible(self.form, self.validate_script_button, scripted)
        _set_form_row_visible(self.form, self.script_summary, scripted)
        _set_form_row_visible(self.form, self.script_errors, scripted)

    def _field_value(self, field_id: str) -> str:
        widget = self._prop_widgets[field_id]
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText().strip()
        if isinstance(widget, QtWidgets.QPlainTextEdit):
            return widget.toPlainText()
        return widget.text().strip()

    def _validate_script_source(self, source: str):
        rng = build_project_rng(self.store.state.parameters, self.store.state.random_seed)
        values, results = evaluate_parameters(self.store.state.parameters, rng=rng)
        for result in results:
            if not result.ok:
                return None, f"Parameter '{result.name}': {result.message}"
        validation = validate_geometry_script(
            source,
            parameter_values=values,
            material_names=set(_material_names(self.store)),
            name_prefix=self.name_input.text().strip() or "scripted",
            rng=rng,
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

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        kind = self.kind_input.currentText()
        material = "" if kind == "scripted" else self.material_input.currentText().strip()
        registry = active_scope(self.store).name_registry()
        name_result = validate_name(name, registry, exclude=self._exclude)
        _set_invalid(self.name_input, not name_result.ok)
        if not name_result.ok:
            _log_error(self.store, name_result.message, self)
            return
        if kind == "scripted":
            source = self._field_value("source").strip()
            _set_invalid(self.script_source, not source)
            if not source:
                _log_error(self.store, "Script source is required.", self)
                return
            validation, error = self._validate_script_source(source)
            self._update_script_summary(validation)
            self.script_errors.setPlainText(error)
            if error:
                _set_invalid(self.script_source, True)
                _log_error(self.store, error, self)
                return
            _set_invalid(self.script_source, False)
            self._result = GeometryItem(
                name=name,
                kind=kind,
                material="",
                props={"source": source},
            )
            self.accept()
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
