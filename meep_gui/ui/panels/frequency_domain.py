from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import AnalysisConfig, FIELD_COMPONENTS, FrequencyDomainSolverConfig
from ...store import ProjectStore
from ...validation import (
    evaluate_numeric_expression,
    evaluate_parameters,
    validate_numeric_expression,
)
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


class FrequencyDomainPanel(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store
        self._ready = False

        self.component = QtWidgets.QComboBox()
        self.component.addItems(list(FIELD_COMPONENTS))
        self.tolerance = QtWidgets.QLineEdit()
        self.max_iters = QtWidgets.QLineEdit()
        self.bicgstab_l = QtWidgets.QLineEdit()

        form = QtWidgets.QFormLayout()
        form.addRow("Component", self.component)
        form.addRow("Tolerance", self.tolerance)
        form.addRow("Max Iters", self.max_iters)
        form.addRow("L", self.bicgstab_l)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch(1)

        self.component.currentTextChanged.connect(lambda _: self._auto_apply())
        for widget in (self.tolerance, self.max_iters, self.bicgstab_l):
            widget.editingFinished.connect(self._auto_apply)

    def _auto_apply(self) -> None:
        if not self._ready:
            return
        self.apply()

    def load_from_config(self, cfg: FrequencyDomainSolverConfig) -> None:
        self._ready = False
        self.component.setCurrentText(cfg.component)
        self.tolerance.setText(cfg.tolerance)
        self.max_iters.setText(cfg.max_iters)
        self.bicgstab_l.setText(cfg.bicgstab_l)
        self._ready = True

    def validate(self) -> bool:
        allowed = parameter_names(self.store)
        fields = [
            (self.tolerance, "Tolerance"),
            (self.max_iters, "Max Iters"),
            (self.bicgstab_l, "L"),
        ]
        ok = True
        for widget, label in fields:
            result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not result.ok)
            if not result.ok:
                _log_error(self.store, f"{label}: {result.message}", self)
                ok = False
        if not ok:
            return False

        values, results = evaluate_parameters(self.store.state.parameters)
        for result in results:
            if not result.ok:
                _log_error(self.store, f"Parameter '{result.name}': {result.message}", self)
                return False

        tolerance_value = evaluate_numeric_expression(self.tolerance.text().strip(), values)
        tolerance_ok = tolerance_value > 0
        _set_invalid(self.tolerance, not tolerance_ok)
        if not tolerance_ok:
            _log_error(self.store, "Tolerance must be > 0.", self)
            return False

        for widget, label in (
            (self.max_iters, "Max Iters"),
            (self.bicgstab_l, "L"),
        ):
            value = evaluate_numeric_expression(widget.text().strip(), values)
            is_integer = abs(value - round(value)) <= 1e-9 and round(value) > 0
            _set_invalid(widget, not is_integer)
            if not is_integer:
                _log_error(self.store, f"{label} must be a positive integer.", self)
                return False

        return True

    def apply(self) -> bool:
        if not self.validate():
            return False
        defaults = FrequencyDomainSolverConfig()
        cfg = FrequencyDomainSolverConfig(
            component=self.component.currentText(),
            tolerance=self.tolerance.text().strip(),
            max_iters=self.max_iters.text().strip(),
            bicgstab_l=self.bicgstab_l.text().strip(),
            output_dir=defaults.output_dir,
            output_name=defaults.output_name,
        )
        analysis = self.store.state.analysis
        self.store.state.analysis = AnalysisConfig(
            kind=analysis.kind,
            field_animation=analysis.field_animation,
            harminv=analysis.harminv,
            transmission_spectrum=analysis.transmission_spectrum,
            frequency_domain_solver=cfg,
            meep_k_points=analysis.meep_k_points,
            mpb_modesolver=analysis.mpb_modesolver,
        )
        self.store.notify()
        return True
