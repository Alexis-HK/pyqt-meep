from __future__ import annotations

import time

import pytest

pytest.importorskip("PyQt5")

from meep_gui.model import AnalysisConfig, ProjectState
from meep_gui.run_manager import RunManager


def test_run_manager_prevents_double_start(qtbot) -> None:
    manager = RunManager()

    def _worker(state, log, cancel):
        time.sleep(0.05)
        return "ok"

    assert manager.start(_worker, ProjectState())
    assert not manager.start(lambda state, log, cancel: "no", ProjectState())
    qtbot.waitUntil(lambda: manager.state == "idle", timeout=3000)


def test_run_manager_cancel_flow(qtbot) -> None:
    manager = RunManager()

    def _worker(state, log, cancel):
        t0 = time.time()
        while time.time() - t0 < 0.8:
            if cancel():
                return "canceled"
            time.sleep(0.01)
        return "done"

    states: list[str] = []
    manager.state_changed.connect(states.append)

    assert manager.start(_worker, ProjectState())
    qtbot.wait(60)
    assert manager.cancel()
    qtbot.waitUntil(lambda: manager.state == "idle", timeout=3000)

    assert "running" in states
    assert "cancelling" in states
    assert manager.state == "idle"


def test_run_manager_forwards_published_results_and_tracks_analysis_kind(qtbot) -> None:
    manager = RunManager()
    published: list[str] = []

    def _worker(state, log, cancel, publish_result=None):
        assert publish_result is not None
        publish_result("first")
        time.sleep(0.05)
        publish_result("second")
        return "done"

    state = ProjectState(analysis=AnalysisConfig(kind="harminv"))
    manager.published.connect(published.append)

    assert manager.start(_worker, state)
    assert manager.analysis_kind == "harminv"
    qtbot.waitUntil(lambda: published == ["first", "second"], timeout=3000)
    qtbot.waitUntil(lambda: manager.state == "idle", timeout=3000)
    assert manager.analysis_kind == ""


def test_run_manager_clears_analysis_kind_after_thread_error(qtbot) -> None:
    manager = RunManager()

    def _worker(state, log, cancel):
        raise RuntimeError("boom")

    state = ProjectState(analysis=AnalysisConfig(kind="frequency_domain_solver"))
    failures: list[str] = []
    manager.failed.connect(failures.append)

    assert manager.start(_worker, state)
    assert manager.analysis_kind == "frequency_domain_solver"
    qtbot.waitUntil(lambda: failures == ["boom"], timeout=3000)
    qtbot.waitUntil(lambda: manager.state == "idle", timeout=3000)
    assert manager.analysis_kind == ""
