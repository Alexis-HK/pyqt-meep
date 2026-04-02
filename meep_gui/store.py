from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from PyQt5 import QtCore

from .model import PlotRecord, ProjectState, ResultArtifact, RunRecord
from .run_manager import RunManager

if TYPE_CHECKING:
    from .analysis import RunResult


class ProjectStore(QtCore.QObject):
    state_changed = QtCore.pyqtSignal()
    log = QtCore.pyqtSignal(str)
    terminal = QtCore.pyqtSignal(str)
    result_changed = QtCore.pyqtSignal()
    run_state_changed = QtCore.pyqtSignal(str)

    def __init__(self, state: ProjectState | None = None) -> None:
        super().__init__()
        self.state = state or ProjectState()
        self.run_manager = RunManager()
        self.run_state = self.run_manager.state
        self._last_log_message = ""
        self._log_history: list[str] = []
        self._terminal_history: list[str] = []

        self.run_manager.log.connect(self.log_message)
        self.run_manager.terminal.connect(self.terminal_message)
        self.run_manager.state_changed.connect(self._on_run_state_changed)

    def notify(self) -> None:
        self.state_changed.emit()

    def log_message(self, message: str, *, dedupe: bool = True) -> None:
        text = str(message).strip()
        if not text:
            return
        if dedupe and text == self._last_log_message:
            return
        self._last_log_message = text
        self._log_history.append(text)
        self.log.emit(text)

    @property
    def log_history(self) -> list[str]:
        return list(self._log_history)

    def terminal_message(self, message: str) -> None:
        text = str(message).replace("\r", "")
        if not text:
            return
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            self._terminal_history.append(line)
            self.terminal.emit(line)

    @property
    def terminal_history(self) -> list[str]:
        return list(self._terminal_history)

    def add_run_result(self, run_result: "RunResult", analysis_kind: str) -> RunRecord:
        created_at = datetime.now().isoformat(timespec="seconds")
        run_id = run_result.run_id or uuid4().hex[:12]

        artifacts = [
            ResultArtifact(
                kind=item.kind,
                label=item.label,
                path=item.path,
                meta={str(k): str(v) for k, v in item.meta.items()},
            )
            for item in run_result.artifacts
        ]
        plots = [
            PlotRecord(
                title=item.title,
                x_label=item.x_label,
                y_label=item.y_label,
                csv_path=item.csv_path,
                png_path=item.png_path,
                meta={str(k): str(v) for k, v in item.meta.items()},
            )
            for item in run_result.plots
        ]

        record = RunRecord(
            run_id=run_id,
            analysis_kind=analysis_kind,
            status=run_result.status,
            created_at=created_at,
            message=run_result.message,
            artifacts=artifacts,
            plots=plots,
            meta={str(k): str(v) for k, v in run_result.meta.items()},
        )
        self.state.results.append(record)
        self.result_changed.emit()
        self.state_changed.emit()
        return record

    def remove_run_result(self, index: int) -> bool:
        if index < 0 or index >= len(self.state.results):
            return False
        self.state.results.pop(index)
        self.result_changed.emit()
        self.state_changed.emit()
        return True

    def _on_run_state_changed(self, state: str) -> None:
        self.run_state = state
        self.run_state_changed.emit(state)
