from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

import meep_gui.analysis as analysis
import meep_gui.analysis.domain_artifacts as domain_artifacts_module
import meep_gui.analysis.transmission as transmission_module
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
    RunRecord,
    SourceItem,
    SymmetryItem,
    SweepConfig,
    SweepParameter,
    TransmissionDomainState,
    TransmissionSpectrumConfig,
)
from meep_gui.preview.domain_render import render_domain_preview_axes


def _no_cancel() -> bool:
    return False


def _log(_msg: str) -> None:
    return


def _patch_recipe_runner(monkeypatch, kind: str, runner) -> None:
    recipe = analysis.get_recipe(kind)
    monkeypatch.setattr(
        type(recipe),
        "run",
        lambda self, state, plan, log, cancel, *, deps: runner(state, log, cancel),
    )


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


def test_transmission_reuse_trusts_cached_reference_and_pairs_by_index(
    monkeypatch, tmp_path
) -> None:
    cached_csv = tmp_path / "cached.csv"
    cached_csv.write_text(
        "frequency,incident\n0.55,2.0\n0.65,4.0\n",
        encoding="utf-8",
    )

    export_calls: dict[str, object] = {}
    logs: list[str] = []
    run_calls: list[dict[str, object]] = []

    def _fake_export_transmission_outputs(**kwargs):
        export_calls.update(kwargs)
        return (
            ArtifactResult(kind="transmission_csv", label="out.csv", path=str(tmp_path / "out.csv")),
            PlotResult(
                title="Transmission Spectrum",
                x_label="Frequency",
                y_label="Normalized Response",
                csv_path=str(tmp_path / "out.csv"),
                png_path=str(tmp_path / "out.png"),
            ),
        )

    def _fake_build_flux_specs(run_state, _values):
        return [
            SimpleNamespace(
                name=item.name,
                fcen=float(item.fcen or 0.0),
                df=float(item.df or 0.0),
                nfreq=int(item.nfreq or 1),
            )
            for item in run_state.flux_monitors
        ]

    def _fake_run_sim(_params, _log, **kwargs):
        run_calls.append(kwargs)
        return SimpleNamespace(
            canceled=False,
            flux_results=[
                SimpleNamespace(
                    name="dev_tx",
                    freqs=[0.1, 0.2, 0.3],
                    values=[6.0, 12.0, 24.0],
                )
            ],
            flux_data={},
        )

    monkeypatch.setattr(transmission_module, "create_run_output_dir", lambda _prefix: str(tmp_path))
    monkeypatch.setattr(
        transmission_module,
        "export_transmission_outputs",
        _fake_export_transmission_outputs,
    )

    state = ProjectState(
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="ref_inc",
                transmission_monitor="dev_tx",
                until_after_sources="100",
                reuse_reference_run_id="cached_run",
                reference_state=TransmissionDomainState(
                    flux_monitors=[
                        FluxMonitorConfig(name="ref_inc", fcen="0.2", df="0.1", nfreq="50")
                    ]
                ),
            ),
        ),
        flux_monitors=[FluxMonitorConfig(name="dev_tx", fcen="0.4", df="0.3", nfreq="10")],
    )
    state.results.append(
        RunRecord(
            run_id="cached_run",
            analysis_kind="transmission_spectrum",
            status="completed",
            artifacts=[
                ArtifactResult(
                    kind="transmission_csv",
                    label="cached.csv",
                    path=str(cached_csv),
                )
            ],
            meta={
                "ref_incident_fcen": "9.9",
                "ref_incident_df": "8.8",
                "ref_incident_nfreq": "7",
                "dev_trans_fcen": "6.6",
                "dev_trans_df": "5.5",
                "dev_trans_nfreq": "4",
            },
        )
    )

    deps = SimpleNamespace(
        run_sim=_fake_run_sim,
        evaluate_parameters=lambda _params: ({}, []),
        _eval_required=lambda expr, _values, _name: float(expr),
        _build_flux_specs=_fake_build_flux_specs,
        _build_sim_params=lambda _state: object(),
        _run_canceled=lambda: RunResult(status="canceled"),
        _import_meep=lambda: None,
    )

    result = transmission_module.run_transmission_spectrum_impl(
        state,
        logs.append,
        _no_cancel,
        deps=deps,
    )

    assert result.status == "completed"
    assert result.meta["reference_mode"] == "reused"
    assert result.meta["reused_reference_run_id"] == "cached_run"
    assert len(run_calls) == 1
    assert export_calls["freqs"] == [0.1, 0.2]
    assert export_calls["incident"] == [2.0, 4.0]
    assert export_calls["transmitted"] == [6.0, 12.0]
    assert export_calls["trans_ratio"] == [3.0, 3.0]
    assert any("Skipping reference simulation." in message for message in logs)
    assert any("lengths differ" in message for message in logs)
    assert any("frequency grid differs" in message for message in logs)


def test_transmission_field_decay_stop_condition_uses_per_domain_settings(
    monkeypatch, tmp_path
) -> None:
    stop_calls: list[tuple[float, object, object, float]] = []
    run_calls: list[dict[str, object]] = []

    class _FakeMeep:
        Hz = object()
        Ez = object()

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return ("Vector3", x, y, z)

        @staticmethod
        def stop_when_fields_decayed(additional_time, component, point, decay_by):
            token = object()
            stop_calls.append((additional_time, component, point, decay_by))
            return token

    def _fake_export_transmission_outputs(**_kwargs):
        return (
            ArtifactResult(kind="transmission_csv", label="out.csv", path=str(tmp_path / "out.csv")),
            PlotResult(
                title="Transmission Spectrum",
                x_label="Frequency",
                y_label="Normalized Response",
                csv_path=str(tmp_path / "out.csv"),
                png_path=str(tmp_path / "out.png"),
            ),
        )

    def _fake_build_flux_specs(run_state, _values):
        return [
            SimpleNamespace(
                name=item.name,
                fcen=float(item.fcen or 0.0),
                df=float(item.df or 0.0),
                nfreq=int(item.nfreq or 1),
            )
            for item in run_state.flux_monitors
        ]

    def _fake_run_sim(_params, _log, **kwargs):
        run_calls.append(kwargs)
        if len(run_calls) == 1:
            flux_results = [
                SimpleNamespace(
                    name="ref_inc",
                    freqs=[0.1, 0.2],
                    values=[2.0, 4.0],
                )
            ]
        else:
            flux_results = [
                SimpleNamespace(
                    name="dev_tx",
                    freqs=[0.1, 0.2],
                    values=[1.0, 2.0],
                )
            ]
        return SimpleNamespace(canceled=False, flux_results=flux_results, flux_data={})

    monkeypatch.setattr(transmission_module, "create_run_output_dir", lambda _prefix: str(tmp_path))
    monkeypatch.setattr(
        transmission_module,
        "export_transmission_outputs",
        _fake_export_transmission_outputs,
    )
    monkeypatch.setattr(transmission_module, "create_domain_preview_artifacts", lambda *_args, **_kwargs: [])

    state = ProjectState(
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="ref_inc",
                transmission_monitor="dev_tx",
                stop_condition="field_decay",
                field_decay_component="Hz",
                reference_field_decay_additional_time="11",
                reference_field_decay_point_x="1.5",
                reference_field_decay_point_y="2.5",
                reference_field_decay_by="1e-4",
                scattering_field_decay_additional_time="22",
                scattering_field_decay_point_x="3.5",
                scattering_field_decay_point_y="4.5",
                scattering_field_decay_by="5e-4",
                reference_state=TransmissionDomainState(
                    flux_monitors=[FluxMonitorConfig(name="ref_inc", fcen="0.2", df="0.1", nfreq="50")]
                ),
            ),
        ),
        flux_monitors=[FluxMonitorConfig(name="dev_tx", fcen="0.2", df="0.1", nfreq="50")],
    )

    deps = SimpleNamespace(
        run_sim=_fake_run_sim,
        evaluate_parameters=lambda _params: ({}, []),
        _eval_required=lambda expr, _values, _name: float(expr),
        _build_flux_specs=_fake_build_flux_specs,
        _build_sim_params=lambda _state: object(),
        _run_canceled=lambda: RunResult(status="canceled"),
        _import_meep=lambda: _FakeMeep(),
    )

    result = transmission_module.run_transmission_spectrum_impl(
        state,
        lambda _msg: None,
        _no_cancel,
        deps=deps,
    )

    assert result.status == "completed"
    assert len(run_calls) == 2
    assert len(stop_calls) == 2
    assert stop_calls[0] == (11.0, _FakeMeep.Hz, ("Vector3", 1.5, 2.5, 0), 1e-4)
    assert stop_calls[1] == (22.0, _FakeMeep.Hz, ("Vector3", 3.5, 4.5, 0), 5e-4)
    assert run_calls[0]["until_after_sources"] is not run_calls[1]["until_after_sources"]


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


def test_transmission_preview_marks_active_field_decay_probe() -> None:
    pytest.importorskip("matplotlib")
    from matplotlib.figure import Figure

    class _FakeSim:
        def plot2D(self, ax) -> None:
            ax.set_xlim(-5, 5)
            ax.set_ylim(-5, 5)

    state = ProjectState(
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                stop_condition="field_decay",
                preview_domain="reference",
                reference_field_decay_point_x="1.25",
                reference_field_decay_point_y="-0.5",
                scattering_field_decay_point_x="-2.5",
                scattering_field_decay_point_y="3.0",
            ),
        ),
    )

    fig = Figure()
    ax = fig.add_subplot(111)

    issues = render_domain_preview_axes(
        ax,
        state,
        preview_domain="reference",
        build_sim_impl=lambda _params, _log: _FakeSim(),
    )

    assert not issues
    assert len(ax.lines) == 1
    assert list(ax.lines[0].get_xdata()) == [1.25]
    assert list(ax.lines[0].get_ydata()) == [-0.5]

    issues = render_domain_preview_axes(
        ax,
        state,
        preview_domain="scattering",
        build_sim_impl=lambda _params, _log: _FakeSim(),
    )

    assert not issues
    assert len(ax.lines) == 1
    assert list(ax.lines[0].get_xdata()) == [-2.5]
    assert list(ax.lines[0].get_ydata()) == [3.0]


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
    assert any(item.kind == "domain_preview_png" for item in result.artifacts)


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
    assert len(result.artifacts) == 3
    assert result.artifacts[0].kind == "frequency_domain_field_png"
    assert result.artifacts[1].kind == "frequency_domain_field_csv"
    assert result.artifacts[2].kind == "domain_preview_png"
    assert result.artifacts[0].path
    assert result.artifacts[1].path
    assert result.artifacts[2].path
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

    _patch_recipe_runner(monkeypatch, "frequency_domain_solver", _fake_runner)

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

    _patch_recipe_runner(monkeypatch, "frequency_domain_solver", _fake_runner)

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
    _patch_recipe_runner(
        monkeypatch,
        "frequency_domain_solver",
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

    _patch_recipe_runner(monkeypatch, "frequency_domain_solver", _fake_runner)

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
    assert [item.kind for item in result.artifacts] == ["domain_preview_png"]
    assert len(result.plots) == 1
    assert sim.calls and sim.calls[0][0] == 300.0
    assert len(sim.calls[0][1]) == 3
    assert result.plots[0].png_path
    assert result.plots[0].csv_path
    assert result.meta["primary_frequency"] == "0.2"
    csv_text = open(result.plots[0].csv_path, "r", encoding="utf-8").read()
    assert "k_index,kx,ky,mode,freq_real,freq_imag" in csv_text
    assert "0,0.0,0.0,1,0.2,0.01" in csv_text


def test_create_domain_preview_artifacts_writes_single_preview_for_fdtd(tmp_path) -> None:
    pytest.importorskip("matplotlib")

    class _FakeSim:
        def plot2D(self, ax=None):
            ax.imshow([[1, 1], [1, 1]])

    logs: list[str] = []
    artifacts = domain_artifacts_module.create_domain_preview_artifacts(
        ProjectState(analysis=AnalysisConfig(kind="field_animation")),
        str(tmp_path),
        logs.append,
        build_sim_impl=lambda _params, _log: _FakeSim(),
    )

    assert [item.label for item in artifacts] == ["domain_preview.png"]
    assert artifacts[0].kind == "domain_preview_png"
    assert artifacts[0].path.endswith("domain_preview.png")
    assert artifacts[0].meta["export_name"] == "domain_preview.png"
    assert artifacts[0].path and os.path.exists(artifacts[0].path)
    assert logs == []


def test_create_domain_preview_artifacts_writes_reference_and_scattering_for_transmission(
    tmp_path,
) -> None:
    pytest.importorskip("matplotlib")

    class _FakeSim:
        def plot2D(self, ax=None):
            ax.imshow([[1, 1], [1, 1]])

    state = ProjectState(
        sources=[
            SourceItem(
                name="dev_src",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
            )
        ],
        flux_monitors=[FluxMonitorConfig(name="dev_tx")],
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="ref_inc",
                transmission_monitor="dev_tx",
                reference_state=TransmissionDomainState(
                    sources=[
                        SourceItem(
                            name="ref_src",
                            kind="gaussian",
                            component="Ez",
                            props={"fcen": "0.2", "df": "0.1"},
                        )
                    ],
                    flux_monitors=[FluxMonitorConfig(name="ref_inc")],
                ),
            ),
        )
    )

    artifacts = domain_artifacts_module.create_domain_preview_artifacts(
        state,
        str(tmp_path),
        _log,
        build_sim_impl=lambda _params, _log: _FakeSim(),
    )

    assert [item.label for item in artifacts] == [
        "domain_preview_reference.png",
        "domain_preview_scattering.png",
    ]
    assert all(item.kind == "domain_preview_png" for item in artifacts)
    assert all(item.path and os.path.exists(item.path) for item in artifacts)


def test_sweep_dispatches_meep_k_points(monkeypatch) -> None:
    calls: list[str] = []
    published: list[RunResult] = []

    def _fake_runner(state, log, cancel):
        calls.append(next(param.expr for param in state.parameters if param.name == "a"))
        return RunResult(status="completed", message="ok", meta={"primary_frequency": "0.25"})

    _patch_recipe_runner(monkeypatch, "meep_k_points", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
            ),
        ),
        parameters=[Parameter(name="a", expr="1")],
        sources=[
            SourceItem(
                name="src",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.15", "df": "0.1"},
            )
        ],
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

    _patch_recipe_runner(monkeypatch, "harminv", _fake_runner)

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

    _patch_recipe_runner(monkeypatch, "transmission_spectrum", _fake_runner)

    state = ProjectState(
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="inc",
                transmission_monitor="tx",
            ),
        ),
        parameters=[Parameter(name="a", expr="1")],
        sources=[
            SourceItem(
                name="src",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.15", "df": "0.1"},
            )
        ],
        flux_monitors=[FluxMonitorConfig(name="tx")],
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

    _patch_recipe_runner(monkeypatch, "frequency_domain_solver", _fake_runner)

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

    _patch_recipe_runner(monkeypatch, "frequency_domain_solver", _fake_runner)

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
