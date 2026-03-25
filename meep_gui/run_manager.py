from __future__ import annotations

import copy
import inspect
from typing import Callable

from PyQt5 import QtCore

from .model import ProjectState, RUN_STATE_VALUES

LogFn = Callable[[str], None]
CancelFn = Callable[[], bool]
RunFn = Callable[[ProjectState, LogFn, CancelFn], object]


class _RunWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)
    log = QtCore.pyqtSignal(str)
    published = QtCore.pyqtSignal(object)

    def __init__(self, func: RunFn, state: ProjectState, cancel_fn: CancelFn) -> None:
        super().__init__()
        self._func = func
        self._state = state
        self._cancel_fn = cancel_fn

    def run(self) -> None:
        try:
            try:
                signature = inspect.signature(self._func)
            except (TypeError, ValueError):
                signature = None

            supports_publish = False
            if signature is not None:
                supports_publish = "publish_result" in signature.parameters or any(
                    param.kind == inspect.Parameter.VAR_KEYWORD
                    for param in signature.parameters.values()
                )

            if supports_publish:
                result = self._func(
                    self._state,
                    self.log.emit,
                    self._cancel_fn,
                    publish_result=self.published.emit,
                )
            else:
                result = self._func(self._state, self.log.emit, self._cancel_fn)
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover - background thread
            self.error.emit(str(exc))


class RunManager(QtCore.QObject):
    state_changed = QtCore.pyqtSignal(str)
    completed = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)
    log = QtCore.pyqtSignal(str)
    published = QtCore.pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self._state = "idle"
        self._cancel_requested = False
        self._thread: QtCore.QThread | None = None
        self._worker: _RunWorker | None = None
        self._analysis_kind = ""

    @property
    def state(self) -> str:
        return self._state

    @property
    def analysis_kind(self) -> str:
        return self._analysis_kind

    def is_active(self) -> bool:
        return self._state in {"running", "cancelling"}

    def start(self, func: RunFn, state: ProjectState) -> bool:
        if self.is_active():
            self.log.emit("A run is already active.")
            return False

        snapshot = copy.deepcopy(state)
        self._cancel_requested = False
        self._analysis_kind = snapshot.analysis.kind
        self._thread = QtCore.QThread()
        self._worker = _RunWorker(func, snapshot, self.cancel_requested)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self.log)
        self._worker.published.connect(self.published.emit)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)

        self._transition("running")
        self._thread.start()
        return True

    def cancel(self) -> bool:
        if not self.is_active():
            return False
        self._cancel_requested = True
        self._transition("cancelling")
        self.log.emit("Stop requested. Waiting for a safe stop point...")
        return True

    def cancel_requested(self) -> bool:
        return self._cancel_requested

    def _on_finished(self, result: object) -> None:
        self._transition("finished")
        self.completed.emit(result)
        self._transition("idle")

    def _on_error(self, message: str) -> None:
        self._transition("failed")
        self.failed.emit(message)
        self._transition("idle")

    def _on_thread_finished(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self._analysis_kind = ""

    def _transition(self, state: str) -> None:
        if state not in RUN_STATE_VALUES:
            raise ValueError(f"Invalid run state: {state}")
        self._state = state
        self.state_changed.emit(state)
