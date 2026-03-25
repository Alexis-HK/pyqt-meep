from __future__ import annotations

import pytest

pytest.importorskip("PyQt5")
pytest.importorskip("pytestqt")

from meep_gui.store import ProjectStore
from meep_gui.ui.windows import DomainWindow, LogWindow, OutputWindow, WorkflowWindow


def test_full_application_windows_instantiate_offscreen(qtbot) -> None:
    store = ProjectStore()
    workflow = WorkflowWindow(store)
    output = OutputWindow(store)
    log = LogWindow(store)
    domain = DomainWindow(store)

    for window in (workflow, output, log, domain):
        qtbot.addWidget(window)
        window.show()

    assert workflow.centralWidget().count() == 9
    assert output.run_list.count() == 0
    assert domain.preview is not None
