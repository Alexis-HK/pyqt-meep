from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import AnalysisConfig, FIELD_COMPONENTS, HarminvConfig, HarminvMonitorConfig
from ...store import ProjectStore
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..dialogs import HarminvMonitorEditDialog
from ..scope import parameter_names


class HarminvPanel(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._ready = False
        self._pending_select_row = -1

        self.animation_component = QtWidgets.QComboBox()
        self.animation_component.addItems(list(FIELD_COMPONENTS))
        self.component = QtWidgets.QComboBox()
        self.component.addItems(list(FIELD_COMPONENTS))
        self.point_x = QtWidgets.QLineEdit()
        self.point_y = QtWidgets.QLineEdit()
        self.fcen = QtWidgets.QLineEdit()
        self.df = QtWidgets.QLineEdit()
        self.until_after_sources = QtWidgets.QLineEdit()
        self.animation_interval = QtWidgets.QLineEdit()
        self.animation_fps = QtWidgets.QLineEdit()

        form = QtWidgets.QFormLayout()
        form.addRow("Animation Component", self.animation_component)
        form.addRow("Monitor Component", self.component)
        form.addRow("Point X", self.point_x)
        form.addRow("Point Y", self.point_y)
        form.addRow("fcen", self.fcen)
        form.addRow("df", self.df)
        form.addRow("Until After Sources", self.until_after_sources)
        form.addRow("Anim Interval", self.animation_interval)
        form.addRow("Anim FPS", self.animation_fps)

        self.add_button = QtWidgets.QPushButton("Add")
        self.update_button = QtWidgets.QPushButton("Update")
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.update_button.setDisabled(True)
        self.remove_button.setDisabled(True)
        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.update_button)
        button_row.addWidget(self.remove_button)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Component", "Point", "fcen", "df"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addWidget(self.table)

        self.animation_component.currentTextChanged.connect(lambda _: self._auto_apply())
        self.component.currentTextChanged.connect(lambda _: self._auto_apply())
        for widget in (
            self.point_x,
            self.point_y,
            self.fcen,
            self.df,
            self.until_after_sources,
            self.animation_interval,
            self.animation_fps,
        ):
            widget.editingFinished.connect(self._auto_apply)
        self.add_button.clicked.connect(self._on_add)
        self.update_button.clicked.connect(self._on_update)
        self.remove_button.clicked.connect(self._on_remove)
        self.table.itemSelectionChanged.connect(self._on_select)

    def _auto_apply(self) -> None:
        if not self._ready:
            return
        self.apply(require_monitors=False)

    def _current_row(self) -> int:
        selection = self.table.selectionModel().selectedRows()
        if selection:
            return selection[0].row()
        return -1

    def _update_buttons(self) -> None:
        row = self._current_row()
        can_edit = 0 <= row < len(self.store.state.analysis.harminv.monitors)
        self.update_button.setDisabled(not can_edit)
        self.remove_button.setDisabled(not can_edit)

    def _draft_monitor(self) -> HarminvMonitorConfig:
        return HarminvMonitorConfig(
            component=self.component.currentText(),
            point_x=self.point_x.text().strip(),
            point_y=self.point_y.text().strip(),
            fcen=self.fcen.text().strip(),
            df=self.df.text().strip(),
        )

    def load_from_config(self, cfg: HarminvConfig) -> None:
        self._ready = False
        self.animation_component.setCurrentText(cfg.animation_component or cfg.component)
        self.component.setCurrentText(cfg.component)
        self.point_x.setText(cfg.point_x)
        self.point_y.setText(cfg.point_y)
        self.fcen.setText(cfg.fcen)
        self.df.setText(cfg.df)
        self.until_after_sources.setText(cfg.until_after_sources)
        self.animation_interval.setText(cfg.animation_interval)
        self.animation_fps.setText(cfg.animation_fps)

        selected_row = self._pending_select_row
        if selected_row < 0:
            selected_row = self._current_row()
        was_blocked = self.table.blockSignals(True)
        self.table.setRowCount(0)
        for idx, monitor in enumerate(cfg.monitors, start=1):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(f"h{idx}"))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(monitor.component))
            self.table.setItem(
                row,
                2,
                QtWidgets.QTableWidgetItem(f"({monitor.point_x}, {monitor.point_y})"),
            )
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(monitor.fcen))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(monitor.df))
        self._pending_select_row = -1
        if 0 <= selected_row < self.table.rowCount():
            self.table.setCurrentCell(selected_row, 0)
        self.table.blockSignals(was_blocked)
        self._ready = True
        self._update_buttons()

    def _validate_monitor(self, monitor: HarminvMonitorConfig, *, label: str) -> bool:
        allowed = parameter_names(self.store)
        if monitor.component not in FIELD_COMPONENTS:
            _log_error(self.store, f"{label} Component: unsupported component.", self)
            return False
        fields = [
            (monitor.point_x, "Point X"),
            (monitor.point_y, "Point Y"),
            (monitor.fcen, "fcen"),
            (monitor.df, "df"),
        ]
        ok = True
        for value, field_label in fields:
            result = validate_numeric_expression(value, allowed)
            if not result.ok:
                _log_error(self.store, f"{label} {field_label}: {result.message}", self)
                ok = False
        return ok

    def validate(self, *, require_monitors: bool = True) -> bool:
        allowed = parameter_names(self.store)
        fields = [
            (self.point_x, "Point X"),
            (self.point_y, "Point Y"),
            (self.fcen, "fcen"),
            (self.df, "df"),
            (self.until_after_sources, "Until After Sources"),
            (self.animation_interval, "Anim Interval"),
            (self.animation_fps, "Anim FPS"),
        ]
        ok = True
        for widget, label in fields:
            result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                ok = False
        if self.animation_component.currentText() not in FIELD_COMPONENTS:
            _log_error(self.store, "Animation Component: unsupported component.", self)
            ok = False
        for idx, monitor in enumerate(self.store.state.analysis.harminv.monitors, start=1):
            ok = self._validate_monitor(monitor, label=f"h{idx}") and ok
        if require_monitors and not self.store.state.analysis.harminv.monitors:
            _log_error(self.store, "Harminv requires at least one monitor.", self)
            ok = False
        return ok

    def _replace_config(self, monitors: list[HarminvMonitorConfig] | None = None) -> None:
        current = self.store.state.analysis.harminv
        cfg = HarminvConfig(
            component=self.component.currentText(),
            point_x=self.point_x.text().strip(),
            point_y=self.point_y.text().strip(),
            fcen=self.fcen.text().strip(),
            df=self.df.text().strip(),
            animation_component=self.animation_component.currentText(),
            until_after_sources=self.until_after_sources.text().strip(),
            animation_interval=self.animation_interval.text().strip(),
            animation_fps=self.animation_fps.text().strip(),
            output_dir=current.output_dir,
            output_name=current.output_name,
            harminv_log_path=current.harminv_log_path,
            monitors=list(current.monitors if monitors is None else monitors),
        )
        analysis = self.store.state.analysis
        self.store.state.analysis = AnalysisConfig(
            kind=analysis.kind,
            field_animation=analysis.field_animation,
            harminv=cfg,
            transmission_spectrum=analysis.transmission_spectrum,
            frequency_domain_solver=analysis.frequency_domain_solver,
            meep_k_points=analysis.meep_k_points,
            mpb_modesolver=analysis.mpb_modesolver,
        )
        self.store.notify()

    def apply(self, *, require_monitors: bool = True) -> bool:
        if not self.validate(require_monitors=require_monitors):
            return False
        self._replace_config()
        return True

    def _on_add(self) -> None:
        monitor = self._draft_monitor()
        if not self._validate_monitor(monitor, label="Monitor"):
            return
        monitors = list(self.store.state.analysis.harminv.monitors)
        monitors.append(monitor)
        self._pending_select_row = len(monitors) - 1
        self._replace_config(monitors)

    def _on_update(self) -> None:
        row = self._current_row()
        monitors = list(self.store.state.analysis.harminv.monitors)
        if row < 0 or row >= len(monitors):
            return
        dialog = HarminvMonitorEditDialog(self.store, monitors[row], self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.result:
            monitors[row] = dialog.result
            self._pending_select_row = row
            self._replace_config(monitors)

    def _on_remove(self) -> None:
        row = self._current_row()
        monitors = list(self.store.state.analysis.harminv.monitors)
        if row < 0 or row >= len(monitors):
            return
        monitors.pop(row)
        self._pending_select_row = min(row, len(monitors) - 1)
        self._replace_config(monitors)

    def _on_select(self) -> None:
        row = self._current_row()
        monitors = self.store.state.analysis.harminv.monitors
        if row < 0 or row >= len(monitors):
            self._update_buttons()
            return
        monitor = monitors[row]
        was_ready = self._ready
        self._ready = False
        self.component.setCurrentText(monitor.component)
        self.point_x.setText(monitor.point_x)
        self.point_y.setText(monitor.point_y)
        self.fcen.setText(monitor.fcen)
        self.df.setText(monitor.df)
        self._ready = was_ready
        self._update_buttons()
