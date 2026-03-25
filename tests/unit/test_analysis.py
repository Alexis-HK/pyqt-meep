from __future__ import annotations

from types import SimpleNamespace

import pytest

import meep_gui.analysis as analysis
from meep_gui.analysis import (
    ArtifactResult,
    PlotResult,
    RunResult,
    _build_sim_params,
    _save_image,
    run_by_kind,
    run_field_animation,
    run_sweep,
)
from meep_gui.model import (
    AnalysisConfig,
    Domain,
    KPoint,
    MeepKPointsConfig,
    MpbModeSolverConfig,
    Parameter,
    FluxMonitorConfig,
    ProjectState,
    SourceItem,
    SymmetryItem,
    SweepConfig,
    SweepParameter,
    TransmissionDomainState,
    TransmissionSpectrumConfig,
)


def _no_cancel() -> bool:
    return False


def _log(_msg: str) -> None:
    return


def test_run_by_kind_with_unknown_analysis_returns_failed() -> None:
    state = ProjectState(analysis=AnalysisConfig(kind="unknown"))

    result = run_by_kind(state, _log, _no_cancel)

    assert isinstance(result, RunResult)
    assert result.status == "failed"


def test_run_sweep_requires_parameters() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="field_animation"),
        sweep=SweepConfig(enabled=True, params=[]),
    )

    result = run_sweep(state, _log, _no_cancel)

    assert result.status == "failed"
    assert "without any sweep parameters" in result.message


def test_transmission_requires_monitors_before_running_meep() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="inc",
                transmission_monitor="tx",
                until_after_sources="100",
            ),
        ),
        flux_monitors=[FluxMonitorConfig(name="only_one")],
    )

    with pytest.raises(ValueError, match="At least one reference flux monitor is required"):
        run_by_kind(state, _log, _no_cancel)


def test_harminv_rejects_continuous_sources() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="harminv"),
        sources=[SourceItem(name="src", kind="continuous", component="Ez", props={"fcen": "0.15"})],
    )

    with pytest.raises(ValueError, match="Harminv requires Gaussian"):
        run_by_kind(state, _log, _no_cancel)


def test_transmission_rejects_continuous_sources_in_both_domains() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="inc",
                transmission_monitor="tx",
                reference_state=TransmissionDomainState(
                    sources=[
                        SourceItem(
                            name="ref_src",
                            kind="continuous",
                            component="Ez",
                            props={"fcen": "0.2"},
                        )
                    ]
                ),
            ),
        ),
        sources=[SourceItem(name="src", kind="continuous", component="Ez", props={"fcen": "0.15"})],
    )

    with pytest.raises(ValueError, match="Transmission spectrum requires Gaussian"):
        run_by_kind(state, _log, _no_cancel)


def test_frequency_domain_rejects_gaussian_sources() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        sources=[SourceItem(name="src", kind="gaussian", component="Ez", props={"fcen": "0.15"})],
    )

    with pytest.raises(ValueError, match="Frequency-domain solver supports only continuous sources"):
        run_by_kind(state, _log, _no_cancel)


def test_meep_k_points_rejects_missing_or_continuous_sources() -> None:
    empty_state = ProjectState(
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
            ),
        )
    )
    with pytest.raises(ValueError, match="requires at least one Gaussian"):
        run_by_kind(empty_state, _log, _no_cancel)

    continuous_state = ProjectState(
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
            ),
        ),
        sources=[
            SourceItem(name="src", kind="continuous", component="Ez", props={"fcen": "0.15"})
        ],
    )
    with pytest.raises(ValueError, match="Continuous sources are not supported"):
        run_by_kind(continuous_state, _log, _no_cancel)


def test_save_image_accepts_complex_arrays(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("matplotlib")
    out = tmp_path / "complex.png"
    data = np.ones((8, 8), dtype=np.complex128) * (1 + 2j)

    _save_image(str(out), data, "complex")

    assert out.exists()
    assert out.stat().st_size > 0


def test_run_field_animation_wrapper_uses_patched_run_sim(monkeypatch) -> None:
    class _FakeAnimate:
        def to_mp4(self, _fps: int, path: str) -> None:
            with open(path, "wb") as handle:
                handle.write(b"mp4")

    class _FakeMeep:
        Ez = object()

        def Animate2D(self, **_kwargs):
            return _FakeAnimate()

        def at_every(self, interval, fn):
            return ("at_every", interval, fn)

    calls: list[dict[str, object]] = []

    def _fake_run_sim(params, log, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(canceled=False, flux_results=[], flux_data={})

    monkeypatch.setattr(analysis, "_import_meep", lambda: _FakeMeep())
    monkeypatch.setattr(analysis, "run_sim", _fake_run_sim)

    result = run_field_animation(ProjectState(), _log, _no_cancel)

    assert result.status == "completed"
    assert len(calls) == 1


def test_frequency_domain_run_uses_force_complex_fields_and_emits_png_and_csv(monkeypatch) -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("matplotlib")

    class _FakeMeep:
        Dielectric = "dielectric"
        Ez = "Ez"

        @staticmethod
        def Vector3(x=0, y=0, z=0):
            return (x, y, z)

    class _FakeSim:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def init_sim(self) -> None:
            self.calls.append("init_sim")

        def solve_cw(self, tol: float, max_iters: int, bicgstab_l: int) -> None:
            self.calls.append(("solve_cw", tol, max_iters, bicgstab_l))

        def get_array(self, **kwargs):
            self.calls.append(("get_array", kwargs))
            if kwargs.get("component") == _FakeMeep.Dielectric:
                return np.ones((8, 8))
            return np.ones((8, 8), dtype=np.complex128) * (1 + 2j)

        def plot2D(self, ax=None, **kwargs):
            self.calls.append(("plot2D", kwargs))
            ax.imshow(np.ones((4, 4)))

    sim = _FakeSim()
    build_calls: list[bool] = []
    logs: list[str] = []

    def _fake_build_sim(params, log, *, force_complex_fields: bool = False):
        build_calls.append(force_complex_fields)
        return sim

    monkeypatch.setattr(analysis, "_import_meep", lambda: _FakeMeep())
    monkeypatch.setattr(analysis, "build_sim", _fake_build_sim)

    result = run_by_kind(
        ProjectState(analysis=AnalysisConfig(kind="frequency_domain_solver")),
        logs.append,
        _no_cancel,
    )

    assert result.status == "completed"
    assert len(result.artifacts) == 2
    assert result.artifacts[0].kind == "frequency_domain_field_png"
    assert result.artifacts[1].kind == "frequency_domain_field_csv"
    assert result.artifacts[0].path
    assert result.artifacts[1].path
    assert result.plots == []
    assert build_calls == [True]
    assert logs[0].startswith("Warning: no sources are configured")
    assert sim.calls[0] == "init_sim"
    assert sim.calls[1] == ("solve_cw", 1e-08, 10000, 10)
    assert any(call[0] == "plot2D" for call in sim.calls if isinstance(call, tuple))
    assert result.artifacts[0].meta["component"] == "Ez"
    csv_data = np.loadtxt(result.artifacts[1].path, delimiter=",")
    assert csv_data.shape == (8, 8)
    assert np.allclose(csv_data, 1.0)


def test_sweep_uses_step_size_and_publishes_each_point(monkeypatch) -> None:
    calls: list[str] = []
    published: list[RunResult] = []

    def _fake_runner(state, log, cancel):
        calls.append(next(param.expr for param in state.parameters if param.name == "a"))
        return RunResult(
            status="completed",
            message="ok",
            artifacts=[ArtifactResult(kind="dummy", label="artifact.txt", path="")],
            plots=[
                PlotResult(
                    title="Flux: monitor1",
                    x_label="x",
                    y_label="y",
                    csv_path="/tmp/example.csv",
                    png_path="/tmp/example.png",
                )
            ],
        )

    monkeypatch.setattr(analysis, "run_frequency_domain_solver", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="1")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="3", steps="0.5")],
        ),
    )

    result = run_sweep(state, _log, _no_cancel, publish_result=published.append)

    assert calls == ["1", "1.5", "2", "2.5", "3"]
    assert result.status == "completed"
    assert result.artifacts == []
    assert result.plots == []
    assert result.meta["skip_store"] == "1"
    assert len(published) == 5
    assert published[0].meta["sweep_label"] == "a=1"
    assert published[-1].meta["sweep_label"] == "a=3"
    assert published[0].artifacts[0].label == "a=1 | artifact.txt"
    assert published[0].plots[0].title == "a=1 | Flux: monitor1"


def test_sweep_supports_descending_and_single_value(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_runner(state, log, cancel):
        calls.append(next(param.expr for param in state.parameters if param.name == "a"))
        return RunResult(status="completed", message="ok")

    monkeypatch.setattr(analysis, "run_frequency_domain_solver", _fake_runner)

    descending = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="3")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="3", stop="1", steps="-0.5")],
        ),
    )

    result = run_sweep(descending, _log, _no_cancel)

    assert result.status == "completed"
    assert calls == ["3", "2.5", "2", "1.5", "1"]

    calls.clear()
    single = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="2")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="2", stop="2", steps="0.5")],
        ),
    )

    result = run_sweep(single, _log, _no_cancel)

    assert result.status == "completed"
    assert calls == ["2"]


def test_sweep_rejects_zero_or_wrong_direction_step(monkeypatch) -> None:
    monkeypatch.setattr(
        analysis,
        "run_frequency_domain_solver",
        lambda state, log, cancel: RunResult(status="completed"),
    )

    zero_step = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="1")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="3", steps="0")],
        ),
    )
    with pytest.raises(ValueError, match="step size must be non-zero"):
        run_sweep(zero_step, _log, _no_cancel)

    wrong_direction = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="1")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="3", steps="-0.5")],
        ),
    )
    with pytest.raises(ValueError, match="must be positive when stop > start"):
        run_sweep(wrong_direction, _log, _no_cancel)


def test_multiple_sweep_rows_run_sequentially_not_cartesian(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def _fake_runner(state, log, cancel):
        params = {param.name: param.expr for param in state.parameters}
        calls.append((params["a"], params["b"]))
        return RunResult(status="completed", message="ok")

    monkeypatch.setattr(analysis, "run_frequency_domain_solver", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="0"), Parameter(name="b", expr="10")],
        sweep=SweepConfig(
            enabled=True,
            params=[
                SweepParameter(name="a", start="1", stop="3", steps="1"),
                SweepParameter(name="b", start="5", stop="7", steps="1"),
            ],
        ),
    )

    result = run_sweep(state, _log, _no_cancel)

    assert result.status == "completed"
    assert calls == [
        ("1", "10"),
        ("2", "10"),
        ("3", "10"),
        ("0", "5"),
        ("0", "6"),
        ("0", "7"),
    ]


def test_meep_k_points_emits_plot_and_csv(monkeypatch) -> None:
    pytest.importorskip("matplotlib")

    class _FakeVector3:
        def __init__(self, x=0.0, y=0.0, z=0.0) -> None:
            self.x = x
            self.y = y
            self.z = z

    class _FakeMP:
        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return _FakeVector3(x, y, z)

        @staticmethod
        def interpolate(count, points):
            assert count == 2
            return [
                _FakeVector3(points[0].x, points[0].y, 0),
                _FakeVector3(0.25, 0.0, 0),
                _FakeVector3(points[-1].x, points[-1].y, 0),
            ]

    class _FakeSim:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def run_k_points(self, run_time, points):
            self.calls.append((run_time, points))
            return [
                [0.2 + 0.01j, 0.3 - 0.02j],
                [0.25 + 0.0j],
                [],
            ]

    sim = _FakeSim()

    monkeypatch.setattr(analysis, "_import_meep", lambda: _FakeMP())
    monkeypatch.setattr(analysis, "build_sim", lambda params, log: sim)

    state = ProjectState(
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoint_interp="2",
                run_time="300",
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")],
            ),
        ),
        sources=[
            SourceItem(
                name="src",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.15", "df": "0.1"},
            )
        ],
    )

    result = run_by_kind(state, _log, _no_cancel)

    assert result.status == "completed"
    assert result.artifacts == []
    assert len(result.plots) == 1
    assert sim.calls and sim.calls[0][0] == 300.0
    assert len(sim.calls[0][1]) == 3
    assert result.plots[0].png_path
    assert result.plots[0].csv_path
    assert result.meta["primary_frequency"] == "0.2"
    csv_text = open(result.plots[0].csv_path, "r", encoding="utf-8").read()
    assert "k_index,kx,ky,mode,freq_real,freq_imag" in csv_text
    assert "0,0.0,0.0,1,0.2,0.01" in csv_text


def test_sweep_dispatches_meep_k_points(monkeypatch) -> None:
    calls: list[str] = []
    published: list[RunResult] = []

    def _fake_runner(state, log, cancel):
        calls.append(next(param.expr for param in state.parameters if param.name == "a"))
        return RunResult(status="completed", message="ok", meta={"primary_frequency": "0.25"})

    monkeypatch.setattr(analysis, "run_meep_k_points", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(kind="meep_k_points"),
        parameters=[Parameter(name="a", expr="1")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="2", steps="1")],
        ),
    )

    result = run_sweep(state, _log, _no_cancel, publish_result=published.append)

    assert result.status == "completed"
    assert calls == ["1", "2"]
    assert published[0].meta["primary_frequency"] == "0.25"
    assert published[0].meta["sweep_label"] == "a=1"


def test_sweep_dispatches_harminv(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_runner(state, log, cancel):
        calls.append(next(param.expr for param in state.parameters if param.name == "a"))
        return RunResult(status="completed", message="ok")

    monkeypatch.setattr(analysis, "run_harminv", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(kind="harminv"),
        parameters=[Parameter(name="a", expr="1")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="2", steps="1")],
        ),
    )

    result = run_sweep(state, _log, _no_cancel)

    assert result.status == "completed"
    assert calls == ["1", "2"]


def test_sweep_dispatches_transmission_spectrum(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_runner(state, log, cancel):
        calls.append(next(param.expr for param in state.parameters if param.name == "a"))
        return RunResult(status="completed", message="ok")

    monkeypatch.setattr(analysis, "run_transmission_spectrum", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(kind="transmission_spectrum"),
        parameters=[Parameter(name="a", expr="1")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="2", steps="1")],
        ),
    )

    result = run_sweep(state, _log, _no_cancel)

    assert result.status == "completed"
    assert calls == ["1", "2"]


def test_sweep_stops_on_first_failed_point_and_publishes_failure(monkeypatch) -> None:
    calls: list[str] = []
    published: list[RunResult] = []

    def _fake_runner(state, log, cancel):
        value = next(param.expr for param in state.parameters if param.name == "a")
        calls.append(value)
        if value == "1.5":
            return RunResult(
                status="failed",
                message="boom",
                artifacts=[ArtifactResult(kind="dummy", label="artifact.txt", path="")],
            )
        return RunResult(status="completed", message="ok")

    monkeypatch.setattr(analysis, "run_frequency_domain_solver", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="1")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="2", steps="0.5")],
        ),
    )

    result = run_sweep(state, _log, _no_cancel, publish_result=published.append)

    assert calls == ["1", "1.5"]
    assert [item.status for item in published] == ["completed", "failed"]
    assert published[-1].artifacts[0].label == "a=1.5 | artifact.txt"
    assert result.status == "failed"
    assert result.message == "Sweep stopped after a=1.5 failed."
    assert result.meta["skip_store"] == "1"


def test_sweep_cancel_after_partial_completion(monkeypatch) -> None:
    calls: list[str] = []
    published: list[RunResult] = []
    cancel_state = {"requested": False}

    def _cancel() -> bool:
        return cancel_state["requested"]

    def _fake_runner(state, log, cancel):
        value = next(param.expr for param in state.parameters if param.name == "a")
        calls.append(value)
        if len(calls) == 2:
            cancel_state["requested"] = True
        return RunResult(status="completed", message="ok")

    monkeypatch.setattr(analysis, "run_frequency_domain_solver", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="1")],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="3", steps="0.5")],
        ),
    )

    result = run_sweep(state, _log, _cancel, publish_result=published.append)

    assert calls == ["1", "1.5"]
    assert [item.meta["sweep_label"] for item in published] == ["a=1", "a=1.5"]
    assert result.status == "canceled"
    assert result.message == "Sweep canceled after 2 completed points."


def test_mpb_skips_field_images_when_no_field_kpoints(monkeypatch) -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("matplotlib")

    class _FakeVector3:
        def __init__(self, x=0.0, y=0.0, z=0.0) -> None:
            self.x = x
            self.y = y
            self.z = z

    class _FakeLattice:
        def __init__(self, **_kwargs) -> None:
            return

    class _FakeModeSolver:
        init_count = 0

        def __init__(self, **kwargs) -> None:
            _FakeModeSolver.init_count += 1
            self.k_points = kwargs.get("k_points", [])
            self.all_freqs = np.asarray([[0.2, 0.3]])

        def run_tm(self, *_callbacks) -> None:
            return

        def init_params(self, *_args) -> None:
            return

        def get_epsilon(self):
            return np.ones((4, 4))

    class _FakeMPBData:
        def __init__(self, **_kwargs) -> None:
            return

        def convert(self, data):
            return np.asarray(data)

    class _FakeMPB:
        ModeSolver = _FakeModeSolver
        MPBData = _FakeMPBData

    class _FakeMP:
        NO_PARITY = object()

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return _FakeVector3(x, y, z)

        @staticmethod
        def Lattice(**kwargs):
            return _FakeLattice(**kwargs)

        @staticmethod
        def interpolate(_count, points):
            return points

    monkeypatch.setattr(analysis, "_import_mpb", lambda: (_FakeMP(), _FakeMPB()))

    state = ProjectState(
        analysis=AnalysisConfig(
            kind="mpb_modesolver",
            mpb_modesolver=MpbModeSolverConfig(
                run_tm=True,
                run_te=False,
                num_bands="2",
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")],
                field_kpoints=[],
            ),
        )
    )

    logs: list[str] = []
    result = run_by_kind(state, logs.append, _no_cancel)

    assert result.status == "completed"
    assert [item.kind for item in result.artifacts] == [
        "mpb_band_csv",
        "mpb_band_png",
        "mpb_epsilon_png",
    ]
    assert result.meta["field_kpoint_count"] == "0"
    assert result.meta["mode_images"] == "0"
    assert any("No field k-points configured" in message for message in logs)
    assert _FakeModeSolver.init_count == 1


def test_mpb_caps_field_images_at_max_mode_images(monkeypatch) -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("matplotlib")

    class _FakeVector3:
        def __init__(self, x=0.0, y=0.0, z=0.0) -> None:
            self.x = x
            self.y = y
            self.z = z

    class _FakeLattice:
        def __init__(self, **_kwargs) -> None:
            return

    class _FakeModeSolver:
        run_tm_calls = 0

        def __init__(self, **kwargs) -> None:
            self.k_points = kwargs.get("k_points", [])
            self.all_freqs = np.asarray([[0.2, 0.3, 0.4]])

        def run_tm(self, *_callbacks) -> None:
            _FakeModeSolver.run_tm_calls += 1

        def init_params(self, *_args) -> None:
            return

        def get_epsilon(self):
            return np.ones((4, 4))

        def get_efield(self, band, bloch_phase=True):
            return np.ones((4, 4, 1), dtype=np.complex128) * band

    class _FakeMPBData:
        def __init__(self, **_kwargs) -> None:
            return

        def convert(self, data):
            return np.asarray(data)

    class _FakeMPB:
        ModeSolver = _FakeModeSolver
        MPBData = _FakeMPBData

    class _FakeMP:
        NO_PARITY = object()

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return _FakeVector3(x, y, z)

        @staticmethod
        def Lattice(**kwargs):
            return _FakeLattice(**kwargs)

        @staticmethod
        def interpolate(_count, points):
            return points

    monkeypatch.setattr(analysis, "_import_mpb", lambda: (_FakeMP(), _FakeMPB()))

    state = ProjectState(
        analysis=AnalysisConfig(
            kind="mpb_modesolver",
            mpb_modesolver=MpbModeSolverConfig(
                run_tm=True,
                run_te=False,
                num_bands="3",
                max_mode_images="2",
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")],
                field_kpoints=[KPoint(kx="0.2", ky="0.1")],
            ),
        )
    )

    logs: list[str] = []
    result = run_by_kind(state, logs.append, _no_cancel)

    mode_artifacts = [item for item in result.artifacts if item.kind == "mpb_mode_png"]
    assert result.status == "completed"
    assert len(mode_artifacts) == 2
    assert result.meta["mode_images"] == "2"
    assert any("Mode image generation capped at 2 of 3." in message for message in logs)


def test_flux_monitor_requires_line_region_in_2d() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="field_animation"),
        flux_monitors=[
            FluxMonitorConfig(
                name="square",
                center_x="0",
                center_y="0",
                size_x="1",
                size_y="1",
                fcen="0.15",
                df="0.1",
                nfreq="20",
            )
        ],
    )

    with pytest.raises(ValueError, match="must be a line in 2D"):
        run_by_kind(state, _log, _no_cancel)


def test_build_sim_params_includes_domain_symmetries() -> None:
    state = ProjectState(
        domain=Domain(
            symmetry_enabled=True,
            symmetries=[
                SymmetryItem(name="mx", kind="mirror", direction="x", phase="-1"),
                SymmetryItem(name="r4y", kind="rotate4", direction="y", phase="1j"),
            ],
        ),
    )

    params = _build_sim_params(state)

    assert len(params.symmetries) == 2
    assert params.symmetries[0].kind == "mirror"
    assert params.symmetries[0].direction == "x"
    assert params.symmetries[0].phase == complex(-1, 0)
    assert params.symmetries[1].phase == complex(0, 1)


def test_build_sim_params_rejects_non_literal_symmetry_phase() -> None:
    state = ProjectState(
        domain=Domain(
            symmetry_enabled=True,
            symmetries=[SymmetryItem(name="mx", kind="mirror", direction="x", phase="a*1j")],
        ),
    )

    with pytest.raises(ValueError, match="symmetry 'mx' phase"):
        _build_sim_params(state)
