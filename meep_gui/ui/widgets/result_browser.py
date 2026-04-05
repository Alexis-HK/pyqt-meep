from __future__ import annotations

import os
import re
import shutil

from PyQt5 import QtCore, QtWidgets

from ...model import RunRecord
from ...results import ArtifactDisplayEntry, display_entries_from_run_record
from ...store import ProjectStore
from ..common import format_run_list_label
from ..panels.output_artifacts import OutputArtifactsPanel
from ..panels.output_history import OutputHistoryPanel
from .result_preview import ResultPreviewWidget


class ResultBrowserWidget(QtWidgets.QWidget):
    def __init__(self, store: ProjectStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._current_run: RunRecord | None = None
        self._display_artifacts: list[ArtifactDisplayEntry] = []

        self.history = OutputHistoryPanel(self)
        self.artifacts = OutputArtifactsPanel(self)
        self.run_list = self.history.run_list
        self.export_all_runs_button = self.history.export_all_runs_button
        self.remove_run_button = self.history.remove_run_button
        self.artifact_list = self.artifacts.artifact_list
        self.export_artifact_button = self.artifacts.export_artifact_button
        self.export_all_button = self.artifacts.export_all_button

        self.preview = ResultPreviewWidget(self)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.history)
        layout.addWidget(self.artifacts)
        layout.addWidget(self.preview, stretch=1)

        self.run_list.currentRowChanged.connect(self._on_run_selected)
        self.artifact_list.currentRowChanged.connect(self._on_artifact_selected)
        self.export_artifact_button.clicked.connect(self._export_selected_artifact)
        self.export_all_button.clicked.connect(self._export_all_artifacts)
        self.export_all_runs_button.clicked.connect(self._export_all_runs)
        self.remove_run_button.clicked.connect(self._remove_selected_run)

        store.result_changed.connect(self.refresh)
        store.state_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        run_id = None
        current_item = self.run_list.currentItem()
        if current_item is not None:
            run_id = current_item.data(QtCore.Qt.UserRole)

        self.run_list.clear()
        for run in self._store.state.results:
            item = QtWidgets.QListWidgetItem(self._run_list_label(run))
            item.setData(QtCore.Qt.UserRole, run.run_id)
            self.run_list.addItem(item)

        self.export_all_runs_button.setDisabled(not self._completed_runs())
        if self.run_list.count() == 0:
            self.artifact_list.clear()
            self._display_artifacts = []
            self._current_run = None
            self.remove_run_button.setDisabled(True)
            self.export_artifact_button.setDisabled(True)
            self.export_all_button.setDisabled(True)
            self.preview.clear_preview()
            return

        if self._store.run_manager.is_active():
            latest = self._store.state.results[-1]
            if latest.meta.get("sweep_label"):
                self.run_list.setCurrentRow(self.run_list.count() - 1)
                return

        if run_id:
            for i in range(self.run_list.count()):
                if self.run_list.item(i).data(QtCore.Qt.UserRole) == run_id:
                    self.run_list.setCurrentRow(i)
                    return
        self.run_list.setCurrentRow(self.run_list.count() - 1)

    def _selected_run(self) -> RunRecord | None:
        row = self.run_list.currentRow()
        if row < 0 or row >= len(self._store.state.results):
            return None
        return self._store.state.results[row]

    def _selected_artifact(self):
        row = self.artifact_list.currentRow()
        if row < 0 or row >= len(self._display_artifacts):
            return None
        return self._display_artifacts[row]

    def _completed_runs(self) -> list[RunRecord]:
        return [run for run in self._store.state.results if run.status == "completed"]

    def _is_exportable_artifact(self, artifact: ArtifactDisplayEntry) -> bool:
        return bool((artifact.path and os.path.exists(artifact.path)) or artifact.text)

    def _exportable_artifacts(self) -> list[ArtifactDisplayEntry]:
        return [item for item in self._display_artifacts if self._is_exportable_artifact(item)]

    def _sanitize_name(self, value: str, default: str, *, allow_dot: bool = False) -> str:
        allowed = "-_." if allow_dot else "-_"
        sanitized = "".join(ch if ch.isalnum() or ch in allowed else "_" for ch in value.strip())
        return sanitized or default

    def _run_list_label(self, run: RunRecord) -> str:
        return format_run_list_label(run)

    def _sanitize_run_list_dir_name(self, label: str) -> str:
        text = label.strip()
        replacements = {
            "|": "-",
            ":": "-",
            "/": "_",
            "\\": "_",
            "<": "_",
            ">": "_",
            '"': "_",
            "?": "_",
            "*": "_",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        text = re.sub(r"[\x00-\x1f]", "_", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = text.rstrip(" .")
        return text or "run"

    def _unique_path(self, path: str) -> str:
        stem, ext = os.path.splitext(path)
        candidate = path
        idx = 2
        while os.path.exists(candidate):
            candidate = f"{stem}_{idx}{ext}"
            idx += 1
        return candidate

    def _run_export_dir_name(self, run: RunRecord) -> str:
        safe_kind = self._sanitize_name(run.analysis_kind, "analysis")
        safe_run = self._sanitize_name(run.run_id, "run")
        return f"{safe_kind}_{safe_run}"

    def _artifact_export_filename(self, artifact: ArtifactDisplayEntry) -> str:
        label = artifact.export_name.strip() or artifact.label.strip() or "artifact"
        safe_label = self._sanitize_name(label, "artifact.txt", allow_dot=True)
        if "." not in safe_label:
            safe_label += ".txt"
        return safe_label

    def _export_artifact_to_dir(self, artifact: ArtifactDisplayEntry, out_dir: str) -> None:
        if artifact.path and os.path.exists(artifact.path):
            out_path = self._unique_path(os.path.join(out_dir, os.path.basename(artifact.path)))
            shutil.copyfile(artifact.path, out_path)
            return
        if artifact.text:
            out_path = self._unique_path(
                os.path.join(out_dir, self._artifact_export_filename(artifact))
            )
            with open(out_path, "w", encoding="utf-8") as handle:
                handle.write(artifact.text + "\n")
            return
        raise RuntimeError("Artifact source is missing.")

    def _export_artifacts_to_dir(
        self,
        artifacts: list[ArtifactDisplayEntry],
        out_dir: str,
    ) -> tuple[int, int]:
        exported = 0
        skipped = 0
        for artifact in artifacts:
            if not self._is_exportable_artifact(artifact):
                skipped += 1
                continue
            try:
                self._export_artifact_to_dir(artifact, out_dir)
                exported += 1
            except Exception:
                skipped += 1
        return exported, skipped

    def _on_run_selected(self, _row: int) -> None:
        run = self._selected_run()
        self._current_run = run
        self.artifact_list.clear()
        self._display_artifacts = []
        self.export_artifact_button.setDisabled(True)
        self.export_all_button.setDisabled(True)
        if run is None:
            self.remove_run_button.setDisabled(True)
            self.preview.clear_preview()
            return

        self.remove_run_button.setDisabled(False)
        self._display_artifacts = list(display_entries_from_run_record(run))
        for idx, artifact in enumerate(self._display_artifacts):
            text = artifact.list_label
            if artifact.path and not os.path.exists(artifact.path):
                text += " [missing]"
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, idx)
            self.artifact_list.addItem(item)

        if not self._display_artifacts:
            self.preview.show_text("No artifacts in this run.")

        if self.artifact_list.count() > 0:
            self.artifact_list.setCurrentRow(0)
        self.export_all_button.setDisabled(len(self._exportable_artifacts()) <= 1)

    def _on_artifact_selected(self, _row: int) -> None:
        artifact = self._selected_artifact()
        if artifact is None:
            self.export_artifact_button.setDisabled(True)
            self.preview.clear_preview()
            return
        self.export_artifact_button.setDisabled(False)
        self.preview.show_artifact(artifact)

    def _export_selected_artifact(self) -> None:
        artifact = self._selected_artifact()
        if artifact is None:
            return
        path = artifact.path
        text = artifact.text
        default_name = artifact.export_name or (os.path.basename(path) if path else "artifact.txt")
        out_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Artifact", default_name)
        if not out_path:
            return
        try:
            if path and os.path.exists(path):
                shutil.copyfile(path, out_path)
            elif text:
                with open(out_path, "w", encoding="utf-8") as handle:
                    handle.write(text + "\n")
            else:
                raise RuntimeError("Artifact source is missing.")
            self._store.log_message(f"Exported artifact to {out_path}")
        except Exception as exc:
            self._store.log_message(f"Artifact export failed: {exc}")

    def _export_all_artifacts(self) -> None:
        run = self._current_run
        if run is None:
            return
        exportable = self._exportable_artifacts()
        if len(exportable) <= 1:
            self._store.log_message("Export All is only available when multiple artifacts exist.")
            return
        parent_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if not parent_dir:
            return

        run_dir_name = self._sanitize_run_list_dir_name(self._run_list_label(run))
        out_dir = self._unique_path(os.path.join(parent_dir, run_dir_name))
        os.makedirs(out_dir, exist_ok=True)
        copied, skipped = self._export_artifacts_to_dir(self._display_artifacts, out_dir)

        if skipped:
            self._store.log_message(
                f"Exported {copied} artifacts to {out_dir}; {skipped} were skipped or missing."
            )
        else:
            self._store.log_message(f"Exported {copied} artifacts to {out_dir}")

    def _export_all_runs(self) -> None:
        completed_runs = self._completed_runs()
        if not completed_runs:
            self._store.log_message(
                "Export All Runs is only available when at least one completed run exists."
            )
            return

        parent_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if not parent_dir:
            return

        bundle_dir = self._unique_path(os.path.join(parent_dir, "all_runs"))
        os.makedirs(bundle_dir, exist_ok=True)

        total_exported = 0
        total_skipped = 0
        for run in completed_runs:
            run_dir_name = self._sanitize_run_list_dir_name(self._run_list_label(run))
            run_dir = self._unique_path(os.path.join(bundle_dir, run_dir_name))
            os.makedirs(run_dir, exist_ok=True)
            artifacts = list(display_entries_from_run_record(run))
            exported, skipped = self._export_artifacts_to_dir(artifacts, run_dir)
            total_exported += exported
            total_skipped += skipped

        message = (
            f"Exported {len(completed_runs)} completed runs ({total_exported} artifacts) "
            f"to {bundle_dir}"
        )
        if total_skipped:
            message += f"; {total_skipped} artifacts were skipped or missing."
        self._store.log_message(message)

    def _remove_selected_run(self) -> None:
        row = self.run_list.currentRow()
        if row >= 0 and self._store.remove_run_result(row):
            self._store.log_message("Removed selected analysis result.")
