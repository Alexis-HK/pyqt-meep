from __future__ import annotations

from PyQt5 import QtWidgets

from ...model import SYMMETRY_DIRECTIONS, SYMMETRY_KINDS, SymmetryItem
from ...store import ProjectStore
from ...validation import NameRegistry, validate_complex_literal, validate_name
from ..common import _log_error, _set_invalid


class SymmetryEditDialog(QtWidgets.QDialog):
    def __init__(
        self,
        store: ProjectStore,
        symmetry: SymmetryItem,
        existing_names: set[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self._exclude = symmetry.name
        self._existing_names = set(existing_names)
        self._result: SymmetryItem | None = None
        self.setWindowTitle("Edit Symmetry")

        self.name_input = QtWidgets.QLineEdit(symmetry.name)
        self.kind_input = QtWidgets.QComboBox()
        self.kind_input.addItems(list(SYMMETRY_KINDS))
        self.kind_input.setCurrentText(symmetry.kind)
        self.direction_input = QtWidgets.QComboBox()
        self.direction_input.addItems(list(SYMMETRY_DIRECTIONS))
        self.direction_input.setCurrentText(symmetry.direction)
        self.phase_input = QtWidgets.QLineEdit(symmetry.phase)

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Type", self.kind_input)
        form.addRow("Direction", self.direction_input)
        form.addRow("Phase", self.phase_input)

        self.save_button = QtWidgets.QPushButton("Save")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.save_button)
        btn_row.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_row)

        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.reject)

    @property
    def result(self) -> SymmetryItem | None:
        return self._result

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        syntax_result = validate_name(name, NameRegistry(set(), set(), set(), set()))
        _set_invalid(self.name_input, not syntax_result.ok)
        if not syntax_result.ok:
            _log_error(self.store, syntax_result.message, self)
            return
        if name in self._existing_names and name != self._exclude:
            _set_invalid(self.name_input, True)
            _log_error(self.store, f"Name '{name}' is already in use.", self)
            return

        phase = self.phase_input.text().strip()
        phase_result = validate_complex_literal(phase)
        _set_invalid(self.phase_input, not phase_result.ok)
        if not phase_result.ok:
            _log_error(self.store, f"Phase: {phase_result.message}", self)
            return

        self._result = SymmetryItem(
            name=name,
            kind=self.kind_input.currentText(),
            direction=self.direction_input.currentText(),
            phase=phase,
        )
        self.accept()
