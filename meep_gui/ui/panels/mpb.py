from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import KPoint, MpbModeSolverConfig
from ...store import ProjectStore
from ..dialogs import KPointEditDialog
from .mpb_support import (
    build_kpoint,
    cfg_with_updates,
    load_config,
    replace_cfg,
    validate_kpoint_widgets,
    validate_panel,
)


class MpbPanel(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._ready = False

        self.lattice_x = QtWidgets.QLineEdit()
        self.lattice_y = QtWidgets.QLineEdit()
        self.basis1_x = QtWidgets.QLineEdit()
        self.basis1_y = QtWidgets.QLineEdit()
        self.basis2_x = QtWidgets.QLineEdit()
        self.basis2_y = QtWidgets.QLineEdit()
        self.num_bands = QtWidgets.QLineEdit()
        self.resolution = QtWidgets.QLineEdit()
        self.unit_cells = QtWidgets.QLineEdit()
        self.kpoint_interp = QtWidgets.QLineEdit()
        self.max_mode_images = QtWidgets.QLineEdit()
        self.run_tm = QtWidgets.QCheckBox("Run TM (Ez fields)")
        self.run_te = QtWidgets.QCheckBox("Run TE (Hz fields)")
        self.run_tm.setChecked(True)

        for widget in (
            self.lattice_x,
            self.lattice_y,
            self.basis1_x,
            self.basis1_y,
            self.basis2_x,
            self.basis2_y,
            self.num_bands,
            self.resolution,
            self.unit_cells,
            self.kpoint_interp,
            self.max_mode_images,
        ):
            widget.setMinimumHeight(24)

        form = QtWidgets.QFormLayout()
        form.addRow("Lattice X", self.lattice_x)
        form.addRow("Lattice Y", self.lattice_y)
        form.addRow("Basis1 X", self.basis1_x)
        form.addRow("Basis1 Y", self.basis1_y)
        form.addRow("Basis2 X", self.basis2_x)
        form.addRow("Basis2 Y", self.basis2_y)
        form.addRow("Num Bands", self.num_bands)
        form.addRow("Resolution", self.resolution)
        form.addRow("Unit Cells", self.unit_cells)
        form.addRow("K-Point Interp", self.kpoint_interp)
        form.addRow("Max Mode Images", self.max_mode_images)

        self.kx = QtWidgets.QLineEdit()
        self.ky = QtWidgets.QLineEdit()
        self.add_k = QtWidgets.QPushButton("Add")
        self.update_k = QtWidgets.QPushButton("Update")
        self.remove_k = QtWidgets.QPushButton("Remove")
        kform = QtWidgets.QFormLayout()
        kform.addRow("Kx", self.kx)
        kform.addRow("Ky", self.ky)
        kbtns = QtWidgets.QHBoxLayout()
        kbtns.addWidget(self.add_k)
        kbtns.addWidget(self.update_k)
        kbtns.addWidget(self.remove_k)

        self.k_table = QtWidgets.QTableWidget(0, 2)
        self.k_table.setHorizontalHeaderLabels(["Kx", "Ky"])
        self.k_table.horizontalHeader().setStretchLastSection(True)
        self.k_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.k_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.field_kx = QtWidgets.QLineEdit()
        self.field_ky = QtWidgets.QLineEdit()
        self.add_field_k = QtWidgets.QPushButton("Add")
        self.update_field_k = QtWidgets.QPushButton("Update")
        self.remove_field_k = QtWidgets.QPushButton("Remove")
        field_form = QtWidgets.QFormLayout()
        field_form.addRow("Kx", self.field_kx)
        field_form.addRow("Ky", self.field_ky)
        field_btns = QtWidgets.QHBoxLayout()
        field_btns.addWidget(self.add_field_k)
        field_btns.addWidget(self.update_field_k)
        field_btns.addWidget(self.remove_field_k)

        self.field_k_table = QtWidgets.QTableWidget(0, 2)
        self.field_k_table.setHorizontalHeaderLabels(["Kx", "Ky"])
        self.field_k_table.horizontalHeader().setStretchLastSection(True)
        self.field_k_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.field_k_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        left_col = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_col)
        left_layout.addLayout(form)
        left_layout.addWidget(QtWidgets.QLabel("Band K-Points"))
        left_layout.addLayout(kform)
        left_layout.addLayout(kbtns)
        left_layout.addWidget(self.k_table)
        left_layout.addStretch(1)

        right_col = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_col)
        pol_box = QtWidgets.QGroupBox("Polarizations")
        pol_layout = QtWidgets.QVBoxLayout(pol_box)
        pol_layout.addWidget(self.run_tm)
        pol_layout.addWidget(self.run_te)
        right_layout.addWidget(pol_box)
        right_layout.addWidget(QtWidgets.QLabel("Field K-Points"))
        right_layout.addLayout(field_form)
        right_layout.addLayout(field_btns)
        right_layout.addWidget(self.field_k_table)
        right_layout.addStretch(1)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(left_col, 1)
        layout.addWidget(right_col, 1)

        self.add_k.clicked.connect(self._on_add)
        self.update_k.clicked.connect(self._on_update)
        self.remove_k.clicked.connect(self._on_remove)
        self.k_table.itemSelectionChanged.connect(self._on_select)
        self.add_field_k.clicked.connect(self._on_field_add)
        self.update_field_k.clicked.connect(self._on_field_update)
        self.remove_field_k.clicked.connect(self._on_field_remove)
        self.field_k_table.itemSelectionChanged.connect(self._on_field_select)
        self.run_tm.toggled.connect(self._auto_apply)
        self.run_te.toggled.connect(self._auto_apply)
        for widget in (
            self.lattice_x,
            self.lattice_y,
            self.basis1_x,
            self.basis1_y,
            self.basis2_x,
            self.basis2_y,
            self.num_bands,
            self.resolution,
            self.unit_cells,
            self.kpoint_interp,
            self.max_mode_images,
            self.kx,
            self.ky,
            self.field_kx,
            self.field_ky,
        ):
            widget.editingFinished.connect(self._auto_apply)

    def _auto_apply(self) -> None:
        if not self._ready:
            return
        self.apply()

    def _current_row(self) -> int:
        selection = self.k_table.selectionModel().selectedRows()
        if selection:
            return selection[0].row()
        return -1

    def _current_field_row(self) -> int:
        selection = self.field_k_table.selectionModel().selectedRows()
        if selection:
            return selection[0].row()
        return -1

    def _item(self, text: str) -> QtWidgets.QTableWidgetItem:
        return QtWidgets.QTableWidgetItem(text)

    def _on_add(self) -> None:
        if not validate_kpoint_widgets(self, ((self.kx, "Kx"), (self.ky, "Ky"))):
            return
        kpoint = build_kpoint(self.kx, self.ky)
        cfg = cfg_with_updates(
            self,
            kpoints=list(self.store.state.analysis.mpb_modesolver.kpoints) + [kpoint]
        )
        replace_cfg(self, cfg)

    def _on_update(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        item = self.store.state.analysis.mpb_modesolver.kpoints[row]
        dialog = KPointEditDialog(self.store, item, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted or dialog.result is None:
            return
        kpoints = list(self.store.state.analysis.mpb_modesolver.kpoints)
        kpoints[row] = dialog.result
        replace_cfg(self, cfg_with_updates(self, kpoints=kpoints))

    def _on_remove(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        kpoints = list(self.store.state.analysis.mpb_modesolver.kpoints)
        kpoints.pop(row)
        replace_cfg(self, cfg_with_updates(self, kpoints=kpoints))

    def _on_select(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        kp = self.store.state.analysis.mpb_modesolver.kpoints[row]
        self.kx.setText(kp.kx)
        self.ky.setText(kp.ky)

    def _on_field_add(self) -> None:
        if not validate_kpoint_widgets(self, ((self.field_kx, "Field Kx"), (self.field_ky, "Field Ky"))):
            return
        kpoint = build_kpoint(self.field_kx, self.field_ky)
        cfg = cfg_with_updates(
            self,
            field_kpoints=list(self.store.state.analysis.mpb_modesolver.field_kpoints)
            + [kpoint]
        )
        replace_cfg(self, cfg)

    def _on_field_update(self) -> None:
        row = self._current_field_row()
        if row < 0:
            return
        item = self.store.state.analysis.mpb_modesolver.field_kpoints[row]
        dialog = KPointEditDialog(self.store, item, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted or dialog.result is None:
            return
        kpoints = list(self.store.state.analysis.mpb_modesolver.field_kpoints)
        kpoints[row] = dialog.result
        replace_cfg(self, cfg_with_updates(self, field_kpoints=kpoints))

    def _on_field_remove(self) -> None:
        row = self._current_field_row()
        if row < 0:
            return
        kpoints = list(self.store.state.analysis.mpb_modesolver.field_kpoints)
        kpoints.pop(row)
        replace_cfg(self, cfg_with_updates(self, field_kpoints=kpoints))

    def _on_field_select(self) -> None:
        row = self._current_field_row()
        if row < 0:
            return
        kp = self.store.state.analysis.mpb_modesolver.field_kpoints[row]
        self.field_kx.setText(kp.kx)
        self.field_ky.setText(kp.ky)

    def load_from_config(self, cfg: MpbModeSolverConfig) -> None:
        load_config(self, cfg)

    def validate(self) -> bool:
        return validate_panel(self)

    def apply(self) -> bool:
        if not self.validate():
            return False
        cfg = MpbModeSolverConfig(
            lattice_x=self.lattice_x.text().strip(),
            lattice_y=self.lattice_y.text().strip(),
            basis1_x=self.basis1_x.text().strip(),
            basis1_y=self.basis1_y.text().strip(),
            basis2_x=self.basis2_x.text().strip(),
            basis2_y=self.basis2_y.text().strip(),
            num_bands=self.num_bands.text().strip(),
            resolution=self.resolution.text().strip(),
            unit_cells=self.unit_cells.text().strip(),
            kpoint_interp=self.kpoint_interp.text().strip(),
            max_mode_images=self.max_mode_images.text().strip(),
            run_tm=self.run_tm.isChecked(),
            run_te=self.run_te.isChecked(),
            kpoints=list(self.store.state.analysis.mpb_modesolver.kpoints),
            field_kpoints=list(self.store.state.analysis.mpb_modesolver.field_kpoints),
        )
        replace_cfg(self, cfg)
        return True
