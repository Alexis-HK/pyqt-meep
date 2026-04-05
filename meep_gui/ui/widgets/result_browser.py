from __future__ import annotations

import os

from PyQt5 import QtCore, QtWidgets

from ...model import RunRecord
from ...results import ArtifactDisplayEntry, display_entries_from_run_record
from ...store import ProjectStore
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
        self.run_status = self.history.run_status
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
            prefix = run.meta.get("sweep_label", "").strip()
            label = f"{run.analysis_kind} [{run.status}] {run.created_at or run.run_id}"
            if prefix:
                label = f"{prefix} | {label}"
            if run.status == "canceled":
                label += " (canceled)"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, run.run_id)
            self.run_list.addItem(item)

        if self.run_list.count() == 0:
            self.run_status.setText("No runs yet")
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

    def _is_exportable_artifact(self, artifact: ArtifactDisplayEntry) -> bool:
        return bool((artifact.path and os.path.exists(artifact.path)) or artifact.text)

    def _exportable_artifacts(self) -> list[ArtifactDisplayEntry]:
        return [item for item in self._display_artifacts if self._is_exportable_artifact(item)]

    def _on_run_selected(self, _row: int) -> None:
        run = self._selected_run()
        self._current_run = run
        self.artifact_list.clear()
        self._display_artifacts = []
        self.export_artifact_button.setDisabled(True)
        self.export_all_button.setDisabled(True)
        if run is None:
            self.run_status.setText("No run selected")
            self.remove_run_button.setDisabled(True)
            self.preview.clear_preview()
            return

        self.remove_run_button.setDisabled(False)
        self.run_status.setText(f"Status: {run.status} | {run.message or 'No message'}")
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
                import shutil

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

        safe_kind = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run.analysis_kind) or "analysis"
        safe_run = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run.run_id) or "run"
        base_dir = os.path.join(parent_dir, f"{safe_kind}_{safe_run}")
        out_dir = base_dir
        suffix = 2
        while os.path.exists(out_dir):
            out_dir = f"{base_dir}_{suffix}"
            suffix += 1
        os.makedirs(out_dir, exist_ok=True)

        def unique_dest(path: str) -> str:
            stem, ext = os.path.splitext(path)
            candidate = path
            idx = 2
            while os.path.exists(candidate):
                candidate = f"{stem}_{idx}{ext}"
                idx += 1
            return candidate

        copied = 0
        failed = 0
        for artifact in exportable:
            try:
                src = artifact.path
                text = artifact.text
                label = artifact.export_name.strip() or artifact.label.strip() or "artifact"
                if src and os.path.exists(src):
                    import shutil

                    shutil.copyfile(src, unique_dest(os.path.join(out_dir, os.path.basename(src))))
                    copied += 1
                elif text:
                    safe_label = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in label)
                    safe_label = safe_label or "artifact.txt"
                    if "." not in safe_label:
                        safe_label += ".txt"
                    with open(unique_dest(os.path.join(out_dir, safe_label)), "w", encoding="utf-8") as handle:
                        handle.write(text + "\n")
                    copied += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        if failed:
            self._store.log_message(f"Exported {copied} artifacts to {out_dir}; {failed} could not be exported.")
        else:
            self._store.log_message(f"Exported {copied} artifacts to {out_dir}")

    def _remove_selected_run(self) -> None:
        row = self.run_list.currentRow()
        if row >= 0 and self._store.remove_run_result(row):
            self._store.log_message("Removed selected analysis result.")
