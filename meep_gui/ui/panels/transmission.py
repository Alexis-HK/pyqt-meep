from __future__ import annotations

import copy

from PyQt5 import QtWidgets

from ...model import AnalysisConfig, FIELD_COMPONENTS, TransmissionSpectrumConfig
from ...store import ProjectStore
from .transmission_support import (
    current_reuse_csv_name,
    refresh_monitor_choices,
    refresh_reuse_choices,
    selected_reuse_run_id,
    sync_animation_controls,
    validate_panel,
)


class TransmissionSpectrumPanel(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._ready = False
        self._reuse_candidates: dict[str, dict[str, str]] = {}

        self.incident_monitor = QtWidgets.QComboBox()
        self.transmission_monitor = QtWidgets.QComboBox()
        self.reflection_monitor = QtWidgets.QComboBox()
        self.reference_reflection_monitor = QtWidgets.QComboBox()
        self.reuse_reference = QtWidgets.QComboBox()
        self.reflection_monitor.addItem("")
        self.reference_reflection_monitor.addItem("")
        self.until_after_sources = QtWidgets.QLineEdit()
        self.animate_reference = QtWidgets.QCheckBox("Reference")
        self.animate_scattering = QtWidgets.QCheckBox("Scattering")
        self.animation_component = QtWidgets.QComboBox()
        self.animation_component.addItems(list(FIELD_COMPONENTS))
        self.animation_interval = QtWidgets.QLineEdit()
        self.animation_fps = QtWidgets.QLineEdit()
        self.preview_domain = QtWidgets.QComboBox()
        self.preview_domain.addItems(["scattering", "reference"])

        form = QtWidgets.QFormLayout()
        form.addRow("Incident Monitor", self.incident_monitor)
        form.addRow("Transmission Monitor", self.transmission_monitor)
        form.addRow("Reference Reflection (optional)", self.reference_reflection_monitor)
        form.addRow("Reflection Monitor (optional)", self.reflection_monitor)
        form.addRow("Reuse Reference Data (optional)", self.reuse_reference)
        form.addRow("Until After Sources", self.until_after_sources)
        animate_row = QtWidgets.QHBoxLayout()
        animate_row.addWidget(self.animate_reference)
        animate_row.addWidget(self.animate_scattering)
        animate_row.addStretch(1)
        form.addRow("Animations", animate_row)
        form.addRow("Domain Preview", self.preview_domain)

        self.animation_box = QtWidgets.QGroupBox("Animation Settings")
        anim_form = QtWidgets.QFormLayout(self.animation_box)
        anim_form.addRow("Component", self.animation_component)
        anim_form.addRow("Interval", self.animation_interval)
        anim_form.addRow("FPS", self.animation_fps)
        self.animation_box.setVisible(False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.animation_box)
        layout.addStretch(1)

        self.incident_monitor.currentTextChanged.connect(lambda _: self._auto_apply())
        self.transmission_monitor.currentTextChanged.connect(lambda _: self._auto_apply())
        self.reflection_monitor.currentTextChanged.connect(lambda _: self._auto_apply())
        self.reference_reflection_monitor.currentTextChanged.connect(lambda _: self._auto_apply())
        self.reuse_reference.currentIndexChanged.connect(self._on_reuse_selection_changed)
        self.animate_reference.toggled.connect(self._on_animation_toggle)
        self.animate_scattering.toggled.connect(self._on_animation_toggle)
        self.animation_component.currentTextChanged.connect(lambda _: self._auto_apply())
        self.preview_domain.currentTextChanged.connect(self._on_preview_domain_changed)
        for widget in (self.until_after_sources, self.animation_interval, self.animation_fps):
            widget.editingFinished.connect(self._auto_apply)
        self.store.state_changed.connect(self._refresh_monitor_choices)
        self.store.result_changed.connect(self._refresh_reuse_choices)

        self._refresh_reuse_choices()

    def _auto_apply(self) -> None:
        if not self._ready:
            return
        self.apply()

    def _on_animation_toggle(self, _checked: bool) -> None:
        sync_animation_controls(self)
        self._auto_apply()

    def _sync_animation_controls(self) -> None:
        sync_animation_controls(self)

    def _refresh_monitor_choices(self) -> None:
        refresh_monitor_choices(self)

    def _refresh_reuse_choices(self) -> None:
        refresh_reuse_choices(self)

    def _on_reuse_selection_changed(self, _index: int) -> None:
        if selected_reuse_run_id(self) and self.animate_reference.isChecked():
            self.animate_reference.blockSignals(True)
            self.animate_reference.setChecked(False)
            self.animate_reference.blockSignals(False)
        sync_animation_controls(self)
        self._auto_apply()

    def _on_preview_domain_changed(self, value: str) -> None:
        if not self._ready:
            return
        analysis = self.store.state.analysis
        current_cfg = analysis.transmission_spectrum
        if value == current_cfg.preview_domain:
            return

        reference_state = current_cfg.reference_state
        if (
            value == "reference"
            and not reference_state.flux_monitors
            and self.store.state.flux_monitors
        ):
            reference_state.flux_monitors = copy.deepcopy(self.store.state.flux_monitors)
            self.store.log_message(
                "Reference monitors initialized from scattering monitors."
            )

        cfg = TransmissionSpectrumConfig(
            incident_monitor=current_cfg.incident_monitor,
            transmission_monitor=current_cfg.transmission_monitor,
            reflection_monitor=current_cfg.reflection_monitor,
            reference_reflection_monitor=current_cfg.reference_reflection_monitor,
            until_after_sources=current_cfg.until_after_sources,
            animate_reference=current_cfg.animate_reference,
            animate_scattering=current_cfg.animate_scattering,
            animation_component=current_cfg.animation_component,
            animation_interval=current_cfg.animation_interval,
            animation_fps=current_cfg.animation_fps,
            output_dir=current_cfg.output_dir,
            output_prefix=current_cfg.output_prefix,
            reuse_reference_run_id=current_cfg.reuse_reference_run_id,
            reuse_reference_csv_name=current_cfg.reuse_reference_csv_name,
            preview_domain=value,
            reference_state=reference_state,
        )
        self.store.state.analysis = AnalysisConfig(
            kind=analysis.kind,
            field_animation=analysis.field_animation,
            harminv=analysis.harminv,
            transmission_spectrum=cfg,
            frequency_domain_solver=analysis.frequency_domain_solver,
            meep_k_points=analysis.meep_k_points,
            mpb_modesolver=analysis.mpb_modesolver,
        )
        self.store.notify()

    def load_from_config(self, cfg: TransmissionSpectrumConfig) -> None:
        self._ready = False
        refresh_monitor_choices(self)
        self.incident_monitor.setCurrentText(cfg.incident_monitor)
        self.transmission_monitor.setCurrentText(cfg.transmission_monitor)
        self.reflection_monitor.setCurrentText(cfg.reflection_monitor)
        self.reference_reflection_monitor.setCurrentText(cfg.reference_reflection_monitor)
        refresh_reuse_choices(self)
        reuse_index = self.reuse_reference.findData(cfg.reuse_reference_run_id)
        self.reuse_reference.setCurrentIndex(reuse_index if reuse_index >= 0 else 0)
        self.until_after_sources.setText(cfg.until_after_sources)
        self.animate_reference.setChecked(cfg.animate_reference)
        self.animate_scattering.setChecked(cfg.animate_scattering)
        self.animation_component.setCurrentText(cfg.animation_component)
        self.animation_interval.setText(cfg.animation_interval)
        self.animation_fps.setText(cfg.animation_fps)
        sync_animation_controls(self)
        idx = self.preview_domain.findText(cfg.preview_domain)
        if idx >= 0:
            self.preview_domain.setCurrentIndex(idx)
        self._ready = True

    def validate(self) -> bool:
        return validate_panel(self)

    def apply(self) -> bool:
        if not self.validate():
            return False
        current_cfg = self.store.state.analysis.transmission_spectrum
        cfg = TransmissionSpectrumConfig(
            incident_monitor=self.incident_monitor.currentText().strip(),
            transmission_monitor=self.transmission_monitor.currentText().strip(),
            reflection_monitor=self.reflection_monitor.currentText().strip(),
            reference_reflection_monitor=self.reference_reflection_monitor.currentText().strip(),
            until_after_sources=self.until_after_sources.text().strip(),
            animate_reference=self.animate_reference.isChecked(),
            animate_scattering=self.animate_scattering.isChecked(),
            animation_component=self.animation_component.currentText(),
            animation_interval=self.animation_interval.text().strip(),
            animation_fps=self.animation_fps.text().strip(),
            output_dir=current_cfg.output_dir,
            output_prefix=current_cfg.output_prefix,
            reuse_reference_run_id=selected_reuse_run_id(self),
            reuse_reference_csv_name=current_reuse_csv_name(self),
            preview_domain=self.preview_domain.currentText(),
            reference_state=current_cfg.reference_state,
        )
        analysis = self.store.state.analysis
        self.store.state.analysis = AnalysisConfig(
            kind=analysis.kind,
            field_animation=analysis.field_animation,
            harminv=analysis.harminv,
            transmission_spectrum=cfg,
            frequency_domain_solver=analysis.frequency_domain_solver,
            meep_k_points=analysis.meep_k_points,
            mpb_modesolver=analysis.mpb_modesolver,
        )
        self.store.notify()
        return True
