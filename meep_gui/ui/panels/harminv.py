from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import AnalysisConfig, FIELD_COMPONENTS, HarminvConfig
from ...store import ProjectStore
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


class HarminvPanel(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._ready = False

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
        form.addRow("Component", self.component)
        form.addRow("Point X", self.point_x)
        form.addRow("Point Y", self.point_y)
        form.addRow("fcen", self.fcen)
        form.addRow("df", self.df)
        form.addRow("Until After Sources", self.until_after_sources)
        form.addRow("Anim Interval", self.animation_interval)
        form.addRow("Anim FPS", self.animation_fps)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch(1)

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

    def _auto_apply(self) -> None:
        if not self._ready:
            return
        self.apply()

    def load_from_config(self, cfg: HarminvConfig) -> None:
        self._ready = False
        self.component.setCurrentText(cfg.component)
        self.point_x.setText(cfg.point_x)
        self.point_y.setText(cfg.point_y)
        self.fcen.setText(cfg.fcen)
        self.df.setText(cfg.df)
        self.until_after_sources.setText(cfg.until_after_sources)
        self.animation_interval.setText(cfg.animation_interval)
        self.animation_fps.setText(cfg.animation_fps)
        self._ready = True

    def validate(self) -> bool:
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
        return ok

    def apply(self) -> bool:
        if not self.validate():
            return False
        defaults = HarminvConfig()
        cfg = HarminvConfig(
            component=self.component.currentText(),
            point_x=self.point_x.text().strip(),
            point_y=self.point_y.text().strip(),
            fcen=self.fcen.text().strip(),
            df=self.df.text().strip(),
            until_after_sources=self.until_after_sources.text().strip(),
            animation_interval=self.animation_interval.text().strip(),
            animation_fps=self.animation_fps.text().strip(),
            output_dir=defaults.output_dir,
            output_name=defaults.output_name,
            harminv_log_path=defaults.harminv_log_path,
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
        return True
