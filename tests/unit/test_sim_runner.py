from __future__ import annotations

import meep_gui.sim.runner as runner
from meep_gui.specs.simulation import SimParams


def test_run_sim_omits_periodic_time_logs_and_preserves_step_funcs(monkeypatch) -> None:
    step_marker = object()
    logs: list[str] = []

    class _FakeSim:
        def __init__(self) -> None:
            self.run_args: tuple[object, ...] = ()
            self.run_kwargs: dict[str, object] = {}

        def run(self, *callbacks, **kwargs) -> None:
            self.run_args = callbacks
            self.run_kwargs = kwargs

    sim = _FakeSim()
    at_every_calls: list[int] = []

    class _FakeMP:
        Simulation = object
        Ez = object()

        @staticmethod
        def at_every(interval, fn):
            at_every_calls.append(interval)
            return ("at_every", interval, fn)

    monkeypatch.setattr(runner, "import_meep", lambda: _FakeMP())
    monkeypatch.setattr(runner, "component_map", lambda _mp: {"Ez": _FakeMP.Ez})
    monkeypatch.setattr(runner, "build_sim", lambda _params, _log: sim)

    result = runner.run_sim(
        SimParams(),
        logs.append,
        until_time=25,
        step_funcs=[step_marker],
    )

    assert result.canceled is False
    assert logs == ["Running simulation...", "Done."]
    assert all(not message.startswith("t = ") for message in logs)
    assert sim.run_args == (step_marker,)
    assert sim.run_kwargs == {"until": 25}
    assert at_every_calls == []


def test_run_sim_still_checks_stop_flag_without_time_logs(monkeypatch) -> None:
    logs: list[str] = []

    class _FakeSim:
        def __init__(self) -> None:
            self.aborted = False

        def run(self, *callbacks, **kwargs) -> None:
            assert kwargs == {"until": 50}
            for callback in callbacks:
                if callable(callback):
                    callback(self)

        def abort(self) -> None:
            self.aborted = True

    sim = _FakeSim()
    at_every_calls: list[int] = []

    class _FakeMP:
        Simulation = object
        Ez = object()

        @staticmethod
        def at_every(interval, fn):
            at_every_calls.append(interval)

            def _wrapped(sim_inst):
                fn(sim_inst)

            return _wrapped

    monkeypatch.setattr(runner, "import_meep", lambda: _FakeMP())
    monkeypatch.setattr(runner, "component_map", lambda _mp: {"Ez": _FakeMP.Ez})
    monkeypatch.setattr(runner, "build_sim", lambda _params, _log: sim)

    result = runner.run_sim(
        SimParams(),
        logs.append,
        until_time=50,
        stop_flag=lambda: True,
    )

    assert result.canceled is True
    assert sim.aborted is True
    assert at_every_calls == [10]
    assert logs == [
        "Running simulation...",
        "Stop requested. Finishing early...",
        "Done.",
    ]
    assert all(not message.startswith("t = ") for message in logs)
