from __future__ import annotations

from PyQt5 import QtWidgets

from ...analysis import RunResult, run_by_kind as default_run_by_kind
from ...model import AnalysisConfig
from ...store import ProjectStore
from ..common import _log_error
from ..panels import (
    FieldAnimationPanel,
    FrequencyDomainPanel,
    HarminvPanel,
    MeepKPointsPanel,
    MpbPanel,
    TransmissionSpectrumPanel,
)
from ..scope import analysis_source_issue


class AnalysisTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store

        self.kind = QtWidgets.QComboBox()
        self.kind.addItems(
            [
                "field_animation",
                "harminv",
                "transmission_spectrum",
                "frequency_domain_solver",
                "mpb_modesolver",
                "meep_k_points",
            ]
        )
        self.kind_label = QtWidgets.QLabel("Analysis Type")

        self.field_panel = FieldAnimationPanel(store)
        self.harminv_panel = HarminvPanel(store)
        self.transmission_panel = TransmissionSpectrumPanel(store)
        self.frequency_domain_panel = FrequencyDomainPanel(store)
        self.mpb_panel = MpbPanel(store)
        self.meep_k_points_panel = MeepKPointsPanel(store)
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.field_panel)
        self.stack.addWidget(self.harminv_panel)
        self.stack.addWidget(self.transmission_panel)
        self.stack.addWidget(self.frequency_domain_panel)
        self.stack.addWidget(self.mpb_panel)
        self.stack.addWidget(self.meep_k_points_panel)

        self.run_button = QtWidgets.QPushButton("Run")
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.setDisabled(True)
        self.run_state = QtWidgets.QLabel("State: idle")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.run_button)
        btn_row.addWidget(self.stop_button)
        btn_row.addWidget(self.run_state)
        btn_row.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.kind_label)
        layout.addWidget(self.kind)
        layout.addWidget(self.stack)
        layout.addLayout(btn_row)
        layout.addStretch(1)

        self.kind.currentTextChanged.connect(self._on_kind_changed)
        self.run_button.clicked.connect(self._on_run)
        self.stop_button.clicked.connect(self._on_stop)
        self.store.state_changed.connect(self.refresh)
        self.store.run_state_changed.connect(self._on_run_state_changed)
        self.store.run_manager.published.connect(self._on_run_published)
        self.store.run_manager.completed.connect(self._on_run_finished)
        self.store.run_manager.failed.connect(self._on_run_error)
        self.refresh()

    def _apply_active_panel(self) -> bool:
        kind = self.kind.currentText()
        if kind == "field_animation":
            return self.field_panel.apply()
        if kind == "harminv":
            return self.harminv_panel.apply()
        if kind == "transmission_spectrum":
            return self.transmission_panel.apply()
        if kind == "frequency_domain_solver":
            return self.frequency_domain_panel.apply()
        if kind == "mpb_modesolver":
            return self.mpb_panel.apply()
        if kind == "meep_k_points":
            return self.meep_k_points_panel.apply()
        return False

    def _on_kind_changed(self, text: str) -> None:
        analysis = self.store.state.analysis
        self.store.state.analysis = AnalysisConfig(
            kind=text,
            field_animation=analysis.field_animation,
            harminv=analysis.harminv,
            transmission_spectrum=analysis.transmission_spectrum,
            frequency_domain_solver=analysis.frequency_domain_solver,
            meep_k_points=analysis.meep_k_points,
            mpb_modesolver=analysis.mpb_modesolver,
        )
        self.store.notify()

    def _on_run(self) -> None:
        if not self._apply_active_panel():
            return
        kind = self.kind.currentText()
        message = analysis_source_issue(self.store, kind)
        if message:
            self.store.log_message(message, dedupe=False)
            QtWidgets.QMessageBox.warning(self, "Unsupported source type", message)
            return
        started = self.store.run_manager.start(default_run_by_kind, self.store.state)
        if not started:
            self.store.log_message("Simulation already running.")

    def _on_stop(self) -> None:
        if not self.store.run_manager.cancel():
            self.store.log_message("No active run.")

    def _on_run_state_changed(self, state: str) -> None:
        self.run_state.setText(f"State: {state}")
        running = state in {"running", "cancelling"}
        self.run_button.setDisabled(running)
        self.stop_button.setDisabled(not running)

    def _analysis_kind_for_active_run(self) -> str:
        return self.store.run_manager.analysis_kind or self.store.state.analysis.kind

    def _record_run_result(self, result: RunResult, *, show_error: bool) -> None:
        skip_store = result.meta.get("skip_store") == "1"
        force_killed = result.meta.get("forced_kill") == "1"
        if not skip_store:
            self.store.add_run_result(result, self._analysis_kind_for_active_run())
        if result.message:
            self.store.log_message(result.message, dedupe=False)
        if show_error and not skip_store and not force_killed and result.status == "failed":
            _log_error(self.store, result.message or "Run failed.", self)

    def _on_run_published(self, result: object) -> None:
        if not isinstance(result, RunResult):
            return
        self._record_run_result(result, show_error=False)

    def _on_run_finished(self, result: object) -> None:
        if not isinstance(result, RunResult):
            return
        self._record_run_result(result, show_error=result.meta.get("skip_store") != "1")

    def _on_run_error(self, message: str) -> None:
        failed = RunResult(status="failed", message=message)
        self.store.add_run_result(failed, self._analysis_kind_for_active_run())
        _log_error(self.store, message, self)

    def refresh(self) -> None:
        idx = self.kind.findText(self.store.state.analysis.kind)
        if idx >= 0:
            self.kind.blockSignals(True)
            self.kind.setCurrentIndex(idx)
            self.kind.blockSignals(False)
            self.stack.setCurrentIndex(idx)
        self.field_panel.load_from_config(self.store.state.analysis.field_animation)
        self.harminv_panel.load_from_config(self.store.state.analysis.harminv)
        self.transmission_panel.load_from_config(
            self.store.state.analysis.transmission_spectrum
        )
        self.frequency_domain_panel.load_from_config(
            self.store.state.analysis.frequency_domain_solver
        )
        self.mpb_panel.load_from_config(self.store.state.analysis.mpb_modesolver)
        self.meep_k_points_panel.load_from_config(self.store.state.analysis.meep_k_points)
