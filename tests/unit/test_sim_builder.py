from __future__ import annotations

import meep_gui.sim.builder as sim_builder
from meep_gui.specs.simulation import SimParams


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
