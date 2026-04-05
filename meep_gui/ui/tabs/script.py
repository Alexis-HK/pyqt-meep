from __future__ import annotations

import os

from PyQt5 import QtWidgets

from ...persistence import state_from_dict, state_to_dict
from ...script import generate_script
from ...store import ProjectStore
from ..common import _log_error


class ScriptTab(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.store = store

        self.file_name = QtWidgets.QLineEdit()
        self.dir_path = QtWidgets.QLineEdit()
        self.dir_path.setReadOnly(True)
        self.browse_button = QtWidgets.QPushButton("Browse")
        self.export_button = QtWidgets.QPushButton("Export")
        self.import_yaml_button = QtWidgets.QPushButton("Import YAML")
        self.export_yaml_button = QtWidgets.QPushButton("Export YAML")
        self.script_box = QtWidgets.QTextEdit()
        self.script_box.setReadOnly(True)
        self.file_name.setText("meep_script.py")
        self.script_box.setPlainText("Generating script...")

        form = QtWidgets.QFormLayout()
        form.addRow("File Name", self.file_name)
        dir_row = QtWidgets.QHBoxLayout()
        dir_row.addWidget(self.dir_path)
        dir_row.addWidget(self.browse_button)
        form.addRow("Directory", dir_row)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.export_button)
        btn_row.addWidget(self.import_yaml_button)
        btn_row.addWidget(self.export_yaml_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addWidget(self.script_box)

        self.browse_button.clicked.connect(self._browse)
        self.export_button.clicked.connect(self._export_script)
        self.import_yaml_button.clicked.connect(self._import_yaml)
        self.export_yaml_button.clicked.connect(self._export_yaml)
        self.store.state_changed.connect(self._refresh_script)
        self._refresh_script()

    def _browse(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.dir_path.setText(path)

    def _refresh_script(self) -> None:
        try:
            code = generate_script(self.store.state, log=self.store.log_message)
        except Exception as exc:
            code = f"# Error generating script: {exc}\\n"
        self.script_box.setPlainText(code)

    def _export_script(self) -> None:
        filename = self.file_name.text().strip() or "meep_script.py"
        directory = self.dir_path.text().strip() or os.getcwd()
        os.makedirs(directory, exist_ok=True)
        out_path = os.path.join(directory, filename)
        try:
            code = generate_script(self.store.state, log=self.store.log_message)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(code)
            self.store.log_message(f"Script exported to {out_path}")
        except Exception as exc:
            _log_error(self.store, f"Export error: {exc}", self)

    def _import_yaml(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import YAML", "", "YAML Files (*.yml *.yaml)"
        )
        if not path:
            return
        try:
            import yaml  # type: ignore
        except Exception as exc:
            _log_error(self.store, f"YAML import failed: {exc}", self)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            self.store.state = state_from_dict(raw)
            self.store.notify()
            self.store.log_message(f"Imported YAML from {path}")
        except Exception as exc:
            _log_error(self.store, f"Import error: {exc}", self)

    def _export_yaml(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export YAML", "project.yaml", "YAML Files (*.yml *.yaml)"
        )
        if not path:
            return
        try:
            import yaml  # type: ignore
        except Exception as exc:
            _log_error(self.store, f"YAML export failed: {exc}", self)
            return
        try:
            data = state_to_dict(self.store.state)
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, sort_keys=False)
            self.store.log_message(f"Exported YAML to {path}")
        except Exception as exc:
            _log_error(self.store, f"Export error: {exc}", self)
