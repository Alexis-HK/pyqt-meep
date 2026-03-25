from __future__ import annotations

import os
import sys

from PyQt5 import QtWidgets

if __package__ in (None, ""):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from meep_gui.store import ProjectStore
    from meep_gui.ui import DomainWindow, LogWindow, OutputWindow, WorkflowWindow
else:
    from .store import ProjectStore
    from .ui import DomainWindow, LogWindow, OutputWindow, WorkflowWindow


class _StreamTee:
    def __init__(self, stream, sink) -> None:
        self._stream = stream
        self._sink = sink
        self._buffer = ""

    def write(self, data) -> int:
        text = str(data)
        if not text:
            return 0
        self._stream.write(text)
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._sink(line)
        return len(text)

    def flush(self) -> None:
        if self._buffer:
            self._sink(self._buffer)
            self._buffer = ""
        if hasattr(self._stream, "flush"):
            self._stream.flush()

    def fileno(self) -> int:
        return self._stream.fileno()

    @property
    def encoding(self) -> str:
        return getattr(self._stream, "encoding", "utf-8")

    def isatty(self) -> bool:
        fn = getattr(self._stream, "isatty", None)
        if callable(fn):
            return bool(fn())
        return False


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    store = ProjectStore()

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout_tee = _StreamTee(original_stdout, store.terminal_message)
    stderr_tee = _StreamTee(original_stderr, store.terminal_message)
    sys.stdout = stdout_tee
    sys.stderr = stderr_tee

    try:
        workflow = WorkflowWindow(store)
        output = OutputWindow(store)
        log = LogWindow(store)
        domain = DomainWindow(store)

        workflow.show()
        output.show()
        log.show()
        domain.show()

        return app.exec()
    finally:
        stdout_tee.flush()
        stderr_tee.flush()
        sys.stdout = original_stdout
        sys.stderr = original_stderr


if __name__ == "__main__":
    raise SystemExit(main())
