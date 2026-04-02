from __future__ import annotations

import codecs
import copy
import errno
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Callable

from PyQt5 import QtCore

from .analysis.types import RunResult
from .model import ProjectState, RUN_STATE_VALUES
from .run_protocol import (
    invoke_run_target,
    project_state_to_json,
    resolve_run_target,
    run_result_from_dict,
)

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

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
            result = invoke_run_target(
                self._func,
                self._state,
                self.log.emit,
                self._cancel_fn,
                publish_result=self.published.emit,
            )
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover - background thread
            self.error.emit(str(exc))


class _LinePipeReader(QtCore.QObject):
    line = QtCore.pyqtSignal(str)
    closed = QtCore.pyqtSignal()

    def __init__(self, fd: int, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._fd = fd
        self._buffer = ""
        self._closed = False
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

        if fcntl is not None:
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        self._notifier = QtCore.QSocketNotifier(fd, QtCore.QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._on_activated)

    def _on_activated(self, _fd: int) -> None:
        self._drain_available()

    def _drain_available(self) -> None:
        if self._closed:
            return
        while True:
            try:
                chunk = os.read(self._fd, 4096)
            except OSError as exc:
                if exc.errno in {errno.EAGAIN, errno.EWOULDBLOCK}:
                    return
                self.close()
                return
            if not chunk:
                tail = self._decoder.decode(b"", final=True)
                if tail:
                    self._append_text(tail)
                self.close()
                return
            self._append_text(self._decoder.decode(chunk))

    def _append_text(self, text: str) -> None:
        self._buffer += text.replace("\r", "")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.line.emit(line)

    def drain(self) -> None:
        self._drain_available()
        if self._closed:
            return
        if self._buffer:
            self.line.emit(self._buffer)
            self._buffer = ""

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._notifier.setEnabled(False)
        self._notifier.deleteLater()
        try:
            os.close(self._fd)
        except OSError:
            pass
        if self._buffer:
            self.line.emit(self._buffer)
            self._buffer = ""
        self.closed.emit()


class RunManager(QtCore.QObject):
    state_changed = QtCore.pyqtSignal(str)
    completed = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)
    log = QtCore.pyqtSignal(str)
    published = QtCore.pyqtSignal(object)
    terminal = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._state = "idle"
        self._cancel_requested = False
        self._thread: QtCore.QThread | None = None
        self._worker: _RunWorker | None = None
        self._analysis_kind = ""
        self._backend = ""
        self._process: subprocess.Popen[bytes] | None = None
        self._process_timer = QtCore.QTimer(self)
        self._process_timer.setInterval(100)
        self._process_timer.timeout.connect(self._poll_process)
        self._grace_timer = QtCore.QTimer(self)
        self._grace_timer.setSingleShot(True)
        self._grace_timer.setInterval(3000)
        self._grace_timer.timeout.connect(self._on_grace_timeout)
        self._term_timer = QtCore.QTimer(self)
        self._term_timer.setSingleShot(True)
        self._term_timer.setInterval(1000)
        self._term_timer.timeout.connect(self._on_term_timeout)
        self._event_reader: _LinePipeReader | None = None
        self._stdout_reader: _LinePipeReader | None = None
        self._stderr_reader: _LinePipeReader | None = None
        self._workspace_dir = ""
        self._cancel_path = ""
        self._published_count = 0
        self._final_result: RunResult | None = None
        self._error_message = ""
        self._force_stopped = False

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
        target = resolve_run_target(func)
        if (
            os.name == "posix"
            and fcntl is not None
            and target is not None
            and self._start_process_backend(target, snapshot)
        ):
            return True
        return self._start_thread_backend(func, snapshot)

    def cancel(self) -> bool:
        if not self.is_active():
            return False
        self._cancel_requested = True
        self._transition("cancelling")
        self.log.emit("Stop requested. Waiting for a safe stop point...")
        if self._backend == "process" and self._cancel_path:
            try:
                with open(self._cancel_path, "a", encoding="utf-8"):
                    pass
            except OSError as exc:
                self.log.emit(f"Warning: failed to create cancel sentinel: {exc}")
            if not self._grace_timer.isActive() and not self._force_stopped:
                self._grace_timer.start()
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
        self._backend = ""

    def _start_thread_backend(self, func: RunFn, state: ProjectState) -> bool:
        self._backend = "thread"
        self._thread = QtCore.QThread()
        self._worker = _RunWorker(func, state, self.cancel_requested)
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

    def _start_process_backend(
        self,
        target: tuple[str, str],
        state: ProjectState,
    ) -> bool:
        module_name, qualname = target
        workspace_dir = tempfile.mkdtemp(prefix="meep_gui_run_")
        cancel_path = os.path.join(workspace_dir, "cancel.flag")
        event_r, event_w = os.pipe()
        process: subprocess.Popen[bytes] | None = None
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            python_bin = os.path.dirname(sys.executable)
            existing_path = env.get("PATH", "").strip()
            if existing_path:
                env["PATH"] = python_bin + os.pathsep + existing_path
            else:
                env["PATH"] = python_bin
            existing_pythonpath = env.get("PYTHONPATH", "").strip()
            if existing_pythonpath:
                env["PYTHONPATH"] = package_root + os.pathsep + existing_pythonpath
            else:
                env["PYTHONPATH"] = package_root
            args = [
                sys.executable,
                "-m",
                "meep_gui.run_worker",
                "--module",
                module_name,
                "--qualname",
                qualname,
                "--event-fd",
                str(event_w),
                "--cancel-path",
                cancel_path,
                "--workspace",
                workspace_dir,
            ]
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(event_w,),
                cwd=os.getcwd(),
                env=env,
                start_new_session=True,
            )
            os.close(event_w)
            event_w = -1

            assert process.stdin is not None
            process.stdin.write(project_state_to_json(state).encode("utf-8"))
            process.stdin.close()

            assert process.stdout is not None
            assert process.stderr is not None
            self._backend = "process"
            self._process = process
            self._workspace_dir = workspace_dir
            self._cancel_path = cancel_path
            self._published_count = 0
            self._final_result = None
            self._error_message = ""
            self._force_stopped = False

            self._event_reader = _LinePipeReader(event_r, self)
            self._stdout_reader = _LinePipeReader(process.stdout.fileno(), self)
            self._stderr_reader = _LinePipeReader(process.stderr.fileno(), self)
            self._event_reader.line.connect(self._on_worker_event)
            self._stdout_reader.line.connect(self.terminal.emit)
            self._stderr_reader.line.connect(self.terminal.emit)
            self._transition("running")
            self._process_timer.start()
            return True
        except Exception as exc:
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
            if event_w >= 0:
                try:
                    os.close(event_w)
                except OSError:
                    pass
            try:
                os.close(event_r)
            except OSError:
                pass
            shutil.rmtree(workspace_dir, ignore_errors=True)
            self.log.emit(f"Failed to start worker process: {exc}")
            self._backend = ""
            self._analysis_kind = ""
            return False

    def _on_worker_event(self, line: str) -> None:
        text = line.strip()
        if not text:
            return
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            self.log.emit(f"Worker protocol error: {exc}")
            return

        event_type = str(payload.get("type", ""))
        if event_type == "log":
            self.log.emit(str(payload.get("message", "")))
            return
        if event_type == "published":
            raw = payload.get("result", {})
            if isinstance(raw, dict):
                self._published_count += 1
                self.published.emit(run_result_from_dict(raw))
            return
        if self._force_stopped:
            return
        if event_type == "result":
            raw = payload.get("result", {})
            if isinstance(raw, dict):
                self._final_result = run_result_from_dict(raw)
            self._stop_cancel_timers()
            return
        if event_type == "error":
            self._error_message = str(payload.get("message", "Worker failed."))
            self._stop_cancel_timers()

    def _poll_process(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            return
        self._process_timer.stop()
        self._stop_cancel_timers()
        self._drain_readers()
        self._finalize_process(self._process.returncode)

    def _on_grace_timeout(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._force_stopped = True
        self.log.emit("Graceful stop timed out. Terminating worker process...")
        self._signal_process_group(signal.SIGTERM)
        self._term_timer.start()

    def _on_term_timeout(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self.log.emit("Worker did not exit after SIGTERM. Killing it...")
        self._signal_process_group(signal.SIGKILL)

    def _signal_process_group(self, sig: signal.Signals) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        try:
            os.killpg(self._process.pid, sig)
        except ProcessLookupError:
            return
        except OSError as exc:
            self.log.emit(f"Warning: failed to send signal {int(sig)} to worker: {exc}")

    def _stop_cancel_timers(self) -> None:
        self._grace_timer.stop()
        self._term_timer.stop()

    def _drain_readers(self) -> None:
        for reader in (self._event_reader, self._stdout_reader, self._stderr_reader):
            if reader is not None:
                reader.drain()
                reader.close()
        self._event_reader = None
        self._stdout_reader = None
        self._stderr_reader = None

    def _finalize_process(self, returncode: int | None) -> None:
        forced = self._force_stopped
        published_count = self._published_count
        workspace_dir = self._workspace_dir
        process = self._process

        self._process = None
        self._backend = ""
        self._cancel_path = ""
        self._workspace_dir = ""
        self._published_count = 0

        if process is not None:
            for stream_name in ("stdin", "stdout", "stderr"):
                stream = getattr(process, stream_name, None)
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass

        if forced:
            result = RunResult(
                status="canceled",
                message="Run force-stopped after timeout.",
                meta={"skip_store": "1", "forced_kill": "1"},
            )
            self._transition("finished")
            self.completed.emit(result)
            self._transition("idle")
        elif self._final_result is not None:
            result = self._final_result
            self._transition("finished")
            self.completed.emit(result)
            self._transition("idle")
        elif self._error_message:
            message = self._error_message
            self._transition("failed")
            self.failed.emit(message)
            self._transition("idle")
        else:
            code = "unknown" if returncode is None else str(returncode)
            self._transition("failed")
            self.failed.emit(f"Worker exited without a result (code {code}).")
            self._transition("idle")

        self._final_result = None
        self._error_message = ""
        self._force_stopped = False
        self._analysis_kind = ""

        if forced and published_count == 0 and workspace_dir:
            shutil.rmtree(workspace_dir, ignore_errors=True)

    def _transition(self, state: str) -> None:
        if state not in RUN_STATE_VALUES:
            raise ValueError(f"Invalid run state: {state}")
        self._state = state
        self.state_changed.emit(state)
