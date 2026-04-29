from __future__ import annotations

from dataclasses import replace

from PyQt5 import QtWidgets

from ...model import PML_MODES, SymmetryItem
from ...store import ProjectStore
from ...validation import evaluate_random_seed_expression, validate_numeric_expression
from ..common import (
    _log_error,
    _refresh_scroll_area,
    _scroll_area_for,
    _set_form_row_visible,
    _set_invalid,
)
from ..dialogs import SymmetryEditDialog
from ..scope import active_scope, parameter_names


class DomainTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store

        self.cell_x = QtWidgets.QLineEdit()
        self.cell_y = QtWidgets.QLineEdit()
        self.resolution = QtWidgets.QLineEdit()
        self.pml_width = QtWidgets.QLineEdit()
        self.random_seed = QtWidgets.QLineEdit()
        self.pml_mode = QtWidgets.QComboBox()
        self.pml_mode.addItems(list(PML_MODES))
        self.periodic_enabled = QtWidgets.QCheckBox("Periodic Boundary (use k_point)")
        self.k_point_x = QtWidgets.QLineEdit()
        self.k_point_y = QtWidgets.QLineEdit()
        self.k_point_z = QtWidgets.QLineEdit()
        self.k_point_widget = QtWidgets.QWidget()
        k_point_layout = QtWidgets.QHBoxLayout(self.k_point_widget)
        k_point_layout.setContentsMargins(0, 0, 0, 0)
        for label, widget in (
            ("Kx", self.k_point_x),
            ("Ky", self.k_point_y),
            ("Kz", self.k_point_z),
        ):
            k_point_layout.addWidget(QtWidgets.QLabel(label))
            k_point_layout.addWidget(widget)
        self.cylindrical_enabled = QtWidgets.QCheckBox("Cylindrical Coordinates")
        self.cylindrical_m = QtWidgets.QLineEdit()
        self.symmetry_enabled = QtWidgets.QCheckBox("Enable Symmetries")
        self.add_symmetry = QtWidgets.QPushButton("Add")
        self.update_symmetry = QtWidgets.QPushButton("Update")
        self.remove_symmetry = QtWidgets.QPushButton("Remove")
        self.symmetry_table = QtWidgets.QTableWidget(0, 4)
        self.symmetry_table.setHorizontalHeaderLabels(["Name", "Type", "Direction", "Phase"])
        self.symmetry_table.horizontalHeader().setStretchLastSection(True)
        self.symmetry_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.symmetry_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.domain_form_container = QtWidgets.QWidget()
        self.domain_form = QtWidgets.QFormLayout(self.domain_form_container)
        self.domain_form.addRow("Cell X", self.cell_x)
        self.domain_form.addRow("Cell Y", self.cell_y)
        self.domain_form.addRow("Resolution", self.resolution)
        self.domain_form.addRow("PML Width", self.pml_width)
        self.domain_form.addRow("Random Seed", self.random_seed)
        self.domain_form.addRow("PML Mode", self.pml_mode)
        self.domain_form.addRow(self.periodic_enabled)
        self.domain_form.addRow("k_point", self.k_point_widget)
        self.domain_form.addRow(self.cylindrical_enabled)
        self.domain_form.addRow("m", self.cylindrical_m)
        self.domain_form_scroll = _scroll_area_for(self.domain_form_container)

        symmetry_buttons = QtWidgets.QHBoxLayout()
        symmetry_buttons.addWidget(self.add_symmetry)
        symmetry_buttons.addWidget(self.update_symmetry)
        symmetry_buttons.addWidget(self.remove_symmetry)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.domain_form_scroll, stretch=1)
        layout.addWidget(self.symmetry_enabled)
        layout.addLayout(symmetry_buttons)
        layout.addWidget(self.symmetry_table)

        for widget in (
            self.cell_x,
            self.cell_y,
            self.resolution,
            self.pml_width,
            self.random_seed,
            self.k_point_x,
            self.k_point_y,
            self.k_point_z,
            self.cylindrical_m,
        ):
            widget.editingFinished.connect(self._on_apply)
        self.pml_mode.currentTextChanged.connect(lambda _: self._on_apply())
        self.periodic_enabled.toggled.connect(self._on_periodic_toggle)
        self.cylindrical_enabled.toggled.connect(self._on_cylindrical_toggle)
        self.symmetry_enabled.toggled.connect(self._on_symmetry_toggle)
        self.add_symmetry.clicked.connect(self._on_add_symmetry)
        self.update_symmetry.clicked.connect(self._on_update_symmetry)
        self.remove_symmetry.clicked.connect(self._on_remove_symmetry)
        self.symmetry_table.itemSelectionChanged.connect(self._sync_symmetry_controls)
        self.store.state_changed.connect(self.refresh)
        self.refresh()

    def _current_symmetry_row(self) -> int:
        selection = self.symmetry_table.selectionModel().selectedRows()
        if selection:
            return selection[0].row()
        return -1

    def _active_symmetries(self) -> list[SymmetryItem]:
        return list(active_scope(self.store).domain.symmetries)

    def _validate(self) -> bool:
        allowed = parameter_names(self.store)
        fields = [
            (self.cell_x, "Cell X"),
            (self.cell_y, "Cell Y"),
            (self.resolution, "Resolution"),
            (self.pml_width, "PML Width"),
        ]
        if self.periodic_enabled.isChecked():
            fields.extend(
                [
                    (self.k_point_x, "Kx"),
                    (self.k_point_y, "Ky"),
                    (self.k_point_z, "Kz"),
                ]
            )
        if self.cylindrical_enabled.isChecked():
            fields.append((self.cylindrical_m, "m"))
        ok = True
        for widget, label in fields:
            result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                ok = False
        seed = self.random_seed.text().strip()
        if seed:
            try:
                evaluate_random_seed_expression(seed, self.store.state.parameters)
                _set_invalid(self.random_seed, False)
            except ValueError as exc:
                _set_invalid(self.random_seed, True)
                _log_error(self.store, f"Random Seed: {exc}", self)
                ok = False
        else:
            _set_invalid(self.random_seed, False)
        return ok

    def _on_apply(self) -> None:
        if not self._validate():
            return
        active_scope(self.store).replace_domain(
            cell_x=self.cell_x.text().strip(),
            cell_y=self.cell_y.text().strip(),
            resolution=self.resolution.text().strip(),
            pml_width=self.pml_width.text().strip(),
            pml_mode=self.pml_mode.currentText(),
            periodic_enabled=self.periodic_enabled.isChecked(),
            k_point_x=self.k_point_x.text().strip(),
            k_point_y=self.k_point_y.text().strip(),
            k_point_z=self.k_point_z.text().strip(),
            cylindrical_enabled=self.cylindrical_enabled.isChecked(),
            cylindrical_m=self.cylindrical_m.text().strip(),
        )
        self.store.state.random_seed = self.random_seed.text().strip()
        self.store.notify()

    def _sync_periodic_controls(self) -> None:
        self.k_point_widget.setVisible(self.periodic_enabled.isChecked())
        _refresh_scroll_area(self.domain_form_scroll)

    def _on_periodic_toggle(self, _checked: bool) -> None:
        self._sync_periodic_controls()
        self._on_apply()

    def _sync_cylindrical_controls(self) -> None:
        enabled = self.cylindrical_enabled.isChecked()
        _set_form_row_visible(self.domain_form, self.cylindrical_m, enabled)
        if not enabled:
            _set_invalid(self.cylindrical_m, False)
        _refresh_scroll_area(self.domain_form_scroll)

    def _on_cylindrical_toggle(self, _checked: bool) -> None:
        self._sync_cylindrical_controls()
        self._on_apply()

    def _sync_symmetry_controls(self) -> None:
        enabled = self.symmetry_enabled.isChecked()
        self.symmetry_table.setEnabled(enabled)
        self.add_symmetry.setEnabled(enabled)
        has_selection = enabled and self._current_symmetry_row() >= 0
        self.update_symmetry.setEnabled(has_selection)
        self.remove_symmetry.setEnabled(has_selection)

    def _apply_symmetry_state(
        self,
        *,
        enabled: bool | None = None,
        symmetries: list[SymmetryItem] | None = None,
    ) -> None:
        scope = active_scope(self.store)
        domain = scope.domain
        scope.set_domain(
            replace(
                domain,
                symmetry_enabled=domain.symmetry_enabled if enabled is None else enabled,
                symmetries=domain.symmetries if symmetries is None else list(symmetries),
            )
        )
        self.store.notify()

    def _on_symmetry_toggle(self, checked: bool) -> None:
        self._apply_symmetry_state(enabled=checked)

    def _on_add_symmetry(self) -> None:
        existing = {item.name for item in self._active_symmetries() if item.name}
        dialog = SymmetryEditDialog(
            self.store,
            SymmetryItem(name="", kind="mirror", direction="x", phase="1"),
            existing,
            self,
        )
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.result is not None:
            symmetries = self._active_symmetries()
            symmetries.append(dialog.result)
            self._apply_symmetry_state(symmetries=symmetries)

    def _on_update_symmetry(self) -> None:
        row = self._current_symmetry_row()
        symmetries = self._active_symmetries()
        if row < 0 or row >= len(symmetries):
            return
        existing = {item.name for item in symmetries if item.name}
        dialog = SymmetryEditDialog(self.store, symmetries[row], existing, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.result is not None:
            symmetries[row] = dialog.result
            self._apply_symmetry_state(symmetries=symmetries)

    def _on_remove_symmetry(self) -> None:
        row = self._current_symmetry_row()
        symmetries = self._active_symmetries()
        if row < 0 or row >= len(symmetries):
            return
        symmetries.pop(row)
        self._apply_symmetry_state(symmetries=symmetries)

    def refresh(self) -> None:
        domain = active_scope(self.store).domain
        self.cell_x.setText(domain.cell_x)
        self.cell_y.setText(domain.cell_y)
        self.resolution.setText(domain.resolution)
        self.pml_width.setText(domain.pml_width)
        self.random_seed.setText(self.store.state.random_seed)
        self.k_point_x.setText(domain.k_point_x)
        self.k_point_y.setText(domain.k_point_y)
        self.k_point_z.setText(domain.k_point_z)
        self.cylindrical_m.setText(domain.cylindrical_m)
        idx = self.pml_mode.findText(domain.pml_mode)
        if idx >= 0:
            self.pml_mode.setCurrentIndex(idx)
        self.periodic_enabled.blockSignals(True)
        self.periodic_enabled.setChecked(domain.periodic_enabled)
        self.periodic_enabled.blockSignals(False)
        self._sync_periodic_controls()
        self.cylindrical_enabled.blockSignals(True)
        self.cylindrical_enabled.setChecked(domain.cylindrical_enabled)
        self.cylindrical_enabled.blockSignals(False)
        self._sync_cylindrical_controls()
        self.symmetry_enabled.blockSignals(True)
        self.symmetry_enabled.setChecked(domain.symmetry_enabled)
        self.symmetry_enabled.blockSignals(False)
        selected_name = ""
        row = self._current_symmetry_row()
        if 0 <= row < self.symmetry_table.rowCount():
            item = self.symmetry_table.item(row, 0)
            selected_name = item.text() if item is not None else ""
        self.symmetry_table.setRowCount(0)
        selected_row = -1
        for symmetry in domain.symmetries:
            row = self.symmetry_table.rowCount()
            self.symmetry_table.insertRow(row)
            self.symmetry_table.setItem(row, 0, QtWidgets.QTableWidgetItem(symmetry.name))
            self.symmetry_table.setItem(row, 1, QtWidgets.QTableWidgetItem(symmetry.kind))
            self.symmetry_table.setItem(row, 2, QtWidgets.QTableWidgetItem(symmetry.direction))
            self.symmetry_table.setItem(row, 3, QtWidgets.QTableWidgetItem(symmetry.phase))
            if symmetry.name == selected_name:
                selected_row = row
        if selected_row >= 0:
            self.symmetry_table.setCurrentCell(selected_row, 0)
        self._sync_symmetry_controls()
