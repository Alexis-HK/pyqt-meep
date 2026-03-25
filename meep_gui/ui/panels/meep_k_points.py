from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import AnalysisConfig, KPoint, MeepKPointsConfig
from ...store import ProjectStore
from ...validation import evaluate_numeric_expression, evaluate_parameters, validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..dialogs import KPointEditDialog
from ..scope import parameter_names
from .mpb_support import build_kpoint, validate_kpoint_widgets


class MeepKPointsPanel(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._ready = False

        self.kpoint_interp = QtWidgets.QLineEdit()
        self.run_time = QtWidgets.QLineEdit()

        form = QtWidgets.QFormLayout()
        form.addRow("K Intercept", self.kpoint_interp)
        form.addRow("Run Time", self.run_time)

        self.kx = QtWidgets.QLineEdit()
        self.ky = QtWidgets.QLineEdit()
        point_form = QtWidgets.QFormLayout()
        point_form.addRow("Kx", self.kx)
        point_form.addRow("Ky", self.ky)

        self.add_k = QtWidgets.QPushButton("Add")
        self.update_k = QtWidgets.QPushButton("Update")
        self.remove_k = QtWidgets.QPushButton("Remove")
        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(self.add_k)
        button_row.addWidget(self.update_k)
        button_row.addWidget(self.remove_k)

        self.k_table = QtWidgets.QTableWidget(0, 2)
        self.k_table.setHorizontalHeaderLabels(["Kx", "Ky"])
        self.k_table.horizontalHeader().setStretchLastSection(True)
        self.k_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.k_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel("Input K-Points"))
        layout.addLayout(point_form)
        layout.addLayout(button_row)
        layout.addWidget(self.k_table)
        layout.addStretch(1)

        self.add_k.clicked.connect(self._on_add)
        self.update_k.clicked.connect(self._on_update)
        self.remove_k.clicked.connect(self._on_remove)
        self.k_table.itemSelectionChanged.connect(self._on_select)
        self.kpoint_interp.editingFinished.connect(self._auto_apply)
        self.run_time.editingFinished.connect(self._auto_apply)

    def _auto_apply(self) -> None:
        if not self._ready:
            return
        self.apply()

    def _item(self, text: str) -> QtWidgets.QTableWidgetItem:
        return QtWidgets.QTableWidgetItem(text)

    def _current_row(self) -> int:
        selection = self.k_table.selectionModel().selectedRows()
        if selection:
            return selection[0].row()
        return -1

    def _replace_cfg(self, cfg: MeepKPointsConfig) -> None:
        analysis = self.store.state.analysis
        self.store.state.analysis = AnalysisConfig(
            kind=analysis.kind,
            field_animation=analysis.field_animation,
            harminv=analysis.harminv,
            transmission_spectrum=analysis.transmission_spectrum,
            frequency_domain_solver=analysis.frequency_domain_solver,
            meep_k_points=cfg,
            mpb_modesolver=analysis.mpb_modesolver,
        )
        self.store.notify()

    def _cfg(self, *, kpoints: list[KPoint] | None = None) -> MeepKPointsConfig:
        current = self.store.state.analysis.meep_k_points
        return MeepKPointsConfig(
            kpoint_interp=self.kpoint_interp.text().strip(),
            run_time=self.run_time.text().strip(),
            kpoints=list(current.kpoints if kpoints is None else kpoints),
            output_dir=current.output_dir,
            output_prefix=current.output_prefix,
        )

    def _on_add(self) -> None:
        if not validate_kpoint_widgets(self, ((self.kx, "Kx"), (self.ky, "Ky"))):
            return
        kpoints = list(self.store.state.analysis.meep_k_points.kpoints)
        kpoints.append(build_kpoint(self.kx, self.ky))
        self._replace_cfg(self._cfg(kpoints=kpoints))

    def _on_update(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        item = self.store.state.analysis.meep_k_points.kpoints[row]
        dialog = KPointEditDialog(self.store, item, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted or dialog.result is None:
            return
        kpoints = list(self.store.state.analysis.meep_k_points.kpoints)
        kpoints[row] = dialog.result
        self._replace_cfg(self._cfg(kpoints=kpoints))

    def _on_remove(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        kpoints = list(self.store.state.analysis.meep_k_points.kpoints)
        kpoints.pop(row)
        self._replace_cfg(self._cfg(kpoints=kpoints))

    def _on_select(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        kp = self.store.state.analysis.meep_k_points.kpoints[row]
        self.kx.setText(kp.kx)
        self.ky.setText(kp.ky)

    def load_from_config(self, cfg: MeepKPointsConfig) -> None:
        self._ready = False
        self.kpoint_interp.setText(cfg.kpoint_interp)
        self.run_time.setText(cfg.run_time)
        self.k_table.setRowCount(0)
        for kp in cfg.kpoints:
            row = self.k_table.rowCount()
            self.k_table.insertRow(row)
            self.k_table.setItem(row, 0, self._item(kp.kx))
            self.k_table.setItem(row, 1, self._item(kp.ky))
        self._ready = True

    def validate(self) -> bool:
        allowed = parameter_names(self.store)
        ok = True
        for widget, label in ((self.kpoint_interp, "K Intercept"), (self.run_time, "Run Time")):
            result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                ok = False
        if not ok:
            return False

        if len(self.store.state.analysis.meep_k_points.kpoints) < 2:
            _log_error(self.store, "Meep k points requires at least two input k-points.", self)
            return False

        values, results = evaluate_parameters(self.store.state.parameters)
        for result in results:
            if not result.ok:
                _log_error(self.store, f"Parameter '{result.name}': {result.message}", self)
                return False

        interp_value = evaluate_numeric_expression(self.kpoint_interp.text().strip(), values)
        is_nonnegative_int = abs(interp_value - round(interp_value)) <= 1e-9 and round(interp_value) >= 0
        _set_invalid(self.kpoint_interp, not is_nonnegative_int)
        if not is_nonnegative_int:
            _log_error(self.store, "K Intercept must be a non-negative integer.", self)
            return False

        run_time_value = evaluate_numeric_expression(self.run_time.text().strip(), values)
        _set_invalid(self.run_time, run_time_value <= 0)
        if run_time_value <= 0:
            _log_error(self.store, "Run Time must be > 0.", self)
            return False
        return True

    def apply(self) -> bool:
        if not self.validate():
            return False
        self._replace_cfg(self._cfg())
        return True
