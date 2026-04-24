from __future__ import annotations

import meep_gui.sim.builder as sim_builder
from meep_gui.specs.simulation import SimParams, SourceSpec, SourceTimeSpec


def test_build_sim_omits_k_point_when_unset(monkeypatch) -> None:
    simulation_kwargs: list[dict[str, object]] = []

    class _FakeSimulation:
        def __init__(self, **kwargs) -> None:
            simulation_kwargs.append(kwargs)

    class _FakeMP:
        X = "X"
        Y = "Y"
        Ez = object()
        Simulation = _FakeSimulation

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return (x, y, z)

        @staticmethod
        def PML(thickness=0.0, direction=None):
            return ("PML", thickness, direction)

    monkeypatch.setattr(sim_builder, "import_meep", lambda: _FakeMP())
    monkeypatch.setattr(sim_builder, "component_map", lambda _mp: {"Ez": _FakeMP.Ez})

    sim_builder.build_sim(SimParams(k_point=None), lambda _msg: None)

    assert simulation_kwargs
    assert "k_point" not in simulation_kwargs[0]


def test_build_sim_passes_k_point_when_periodic_enabled(monkeypatch) -> None:
    simulation_kwargs: list[dict[str, object]] = []

    class _FakeSimulation:
        def __init__(self, **kwargs) -> None:
            simulation_kwargs.append(kwargs)

    class _FakeMP:
        X = "X"
        Y = "Y"
        Ez = object()
        Simulation = _FakeSimulation

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return (x, y, z)

        @staticmethod
        def PML(thickness=0.0, direction=None):
            return ("PML", thickness, direction)

    monkeypatch.setattr(sim_builder, "import_meep", lambda: _FakeMP())
    monkeypatch.setattr(sim_builder, "component_map", lambda _mp: {"Ez": _FakeMP.Ez})

    sim_builder.build_sim(SimParams(k_point=(0.1, 0.2, 0.3)), lambda _msg: None)

    assert simulation_kwargs
    assert simulation_kwargs[0]["k_point"] == (0.1, 0.2, 0.3)


def test_build_sim_passes_cylindrical_kwargs_only_when_enabled(monkeypatch) -> None:
    simulation_kwargs: list[dict[str, object]] = []

    class _FakeSimulation:
        def __init__(self, **kwargs) -> None:
            simulation_kwargs.append(kwargs)

    class _FakeMP:
        X = "X"
        Y = "Y"
        Ez = object()
        CYLINDRICAL = "CYLINDRICAL"
        Simulation = _FakeSimulation

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return (x, y, z)

        @staticmethod
        def PML(thickness=0.0, direction=None):
            return ("PML", thickness, direction)

    monkeypatch.setattr(sim_builder, "import_meep", lambda: _FakeMP())
    monkeypatch.setattr(sim_builder, "component_map", lambda _mp: {"Ez": _FakeMP.Ez})

    sim_builder.build_sim(SimParams(cylindrical_enabled=False, cylindrical_m=3), lambda _msg: None)
    sim_builder.build_sim(SimParams(cylindrical_enabled=True, cylindrical_m=3), lambda _msg: None)

    assert "dimensions" not in simulation_kwargs[0]
    assert "m" not in simulation_kwargs[0]
    assert simulation_kwargs[1]["dimensions"] == "CYLINDRICAL"
    assert simulation_kwargs[1]["m"] == 3


def test_build_sim_passes_center_frequency_for_chirped_beam_source_time(monkeypatch) -> None:
    custom_source_calls: list[dict[str, object]] = []
    gaussian_beam_calls: list[dict[str, object]] = []

    class _FakeSimulation:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _FakeMP:
        X = "X"
        Y = "Y"
        Ez = object()
        Simulation = _FakeSimulation

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return (x, y, z)

        @staticmethod
        def PML(thickness=0.0, direction=None):
            return ("PML", thickness, direction)

        @staticmethod
        def CustomSource(**kwargs):
            custom_source_calls.append(kwargs)
            return ("CustomSource", kwargs)

        @staticmethod
        def GaussianBeamSource(**kwargs):
            gaussian_beam_calls.append(kwargs)
            return ("GaussianBeamSource", kwargs)

    monkeypatch.setattr(sim_builder, "import_meep", lambda: _FakeMP())
    monkeypatch.setattr(sim_builder, "component_map", lambda _mp: {"Ez": _FakeMP.Ez})

    sim_builder.build_sim(
        SimParams(
            sources=[
                SourceSpec(
                    kind="gaussian_beam",
                    center_x=0.0,
                    center_y=0.0,
                    width_x=0.0,
                    width_y=1.0,
                    source_time=SourceTimeSpec(
                        kind="chirped_pulse",
                        src_func=lambda _t: 0j,
                        center_frequency=0.8,
                    ),
                )
            ]
        ),
        lambda _msg: None,
    )

    assert custom_source_calls == [
        {
            "src_func": custom_source_calls[0]["src_func"],
            "center_frequency": 0.8,
        }
    ]
    assert gaussian_beam_calls
