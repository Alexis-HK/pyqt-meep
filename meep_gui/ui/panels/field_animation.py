from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import AnalysisConfig, FIELD_COMPONENTS, FieldAnimationConfig
from ...store import ProjectStore
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


class FieldAnimationPanel(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._ready = False

        self.component = QtWidgets.QComboBox()
        self.component.addItems(list(FIELD_COMPONENTS))
        self.duration = QtWidgets.QLineEdit()
        self.interval = QtWidgets.QLineEdit()
        self.fps = QtWidgets.QLineEdit()

        form = QtWidgets.QFormLayout()
        form.addRow("Component", self.component)
        form.addRow("Duration", self.duration)
        form.addRow("Interval", self.interval)
        form.addRow("FPS", self.fps)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch(1)

        self.component.currentTextChanged.connect(lambda _: self._auto_apply())
        for widget in (self.duration, self.interval, self.fps):
            widget.editingFinished.connect(self._auto_apply)

    def _auto_apply(self) -> None:
        if not self._ready:
            return
        self.apply()

    def load_from_config(self, cfg: FieldAnimationConfig) -> None:
        self._ready = False
        self.component.setCurrentText(cfg.component)
        self.duration.setText(cfg.duration)
        self.interval.setText(cfg.interval)
        self.fps.setText(cfg.fps)
        self._ready = True

    def validate(self) -> bool:
        allowed = parameter_names(self.store)
        fields = [
            (self.duration, "Duration"),
            (self.interval, "Interval"),
            (self.fps, "FPS"),
        ]
        ok = True
        for widget, label in fields:
            result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                ok = False
        return ok

    def apply(self) -> bool:
        if not self.validate():
            return False
        defaults = FieldAnimationConfig()
        cfg = FieldAnimationConfig(
            component=self.component.currentText(),
            duration=self.duration.text().strip(),
            interval=self.interval.text().strip(),
            fps=self.fps.text().strip(),
            output_dir=defaults.output_dir,
            output_name=defaults.output_name,
        )
        analysis = self.store.state.analysis
        self.store.state.analysis = AnalysisConfig(
            kind=analysis.kind,
            field_animation=cfg,
            harminv=analysis.harminv,
            transmission_spectrum=analysis.transmission_spectrum,
            frequency_domain_solver=analysis.frequency_domain_solver,
            meep_k_points=analysis.meep_k_points,
            mpb_modesolver=analysis.mpb_modesolver,
        )
        self.store.notify()
        return True
