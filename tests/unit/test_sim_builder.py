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


def test_build_sim_passes_eigenmode_source_kwargs(monkeypatch) -> None:
    eigenmode_calls: list[dict[str, object]] = []

    class _FakeSimulation:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _FakeMP:
        X = "X"
        Y = "Y"
        Ez = object()
        ALL_COMPONENTS = "ALL_COMPONENTS"
        AUTOMATIC = "AUTOMATIC"
        NO_DIRECTION = "NO_DIRECTION"
        NO_PARITY = 0
        EVEN_Y = 1
        ODD_Z = 8
        Simulation = _FakeSimulation

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return (x, y, z)

        @staticmethod
        def PML(thickness=0.0, direction=None):
            return ("PML", thickness, direction)

        @staticmethod
        def ContinuousSource(frequency=0.0):
            return ("ContinuousSource", frequency)

        @staticmethod
        def Volume(**kwargs):
            return ("Volume", kwargs)

        @staticmethod
        def EigenModeSource(**kwargs):
            eigenmode_calls.append(kwargs)
            return ("EigenModeSource", kwargs)

    monkeypatch.setattr(sim_builder, "import_meep", lambda: _FakeMP())
    monkeypatch.setattr(sim_builder, "component_map", lambda _mp: {"Ez": _FakeMP.Ez})

    sim_builder.build_sim(
        SimParams(
            sources=[
                SourceSpec(
                    kind="eigenmode",
                    center_x=1.0,
                    center_y=2.0,
                    width_x=0.0,
                    width_y=3.0,
                    component="ALL_COMPONENTS",
                    amplitude=2 + 1j,
                    amp_func=lambda x, y: x + y,
                    source_time=SourceTimeSpec(kind="continuous", frequency=0.2),
                    eig_lattice_size=(4.0, 5.0),
                    eig_lattice_center=(0.5, -0.5),
                    eig_vol_size=(0.0, 2.0),
                    eig_vol_center=(1.5, 0.0),
                    eig_direction="AUTOMATIC",
                    eig_band=2,
                    eig_kpoint=(0.1, 0.2, 0.3),
                    eig_match_freq=False,
                    eig_parity="EVEN_Y+ODD_Z",
                    eig_resolution=16,
                    eig_tolerance=1e-9,
                )
            ]
        ),
        lambda _msg: None,
    )

    assert eigenmode_calls
    kwargs = eigenmode_calls[0]
    assert kwargs["src"] == ("ContinuousSource", 0.2)
    assert kwargs["center"] == (1.0, 2.0, 0)
    assert kwargs["size"] == (0.0, 3.0, 0)
    assert kwargs["component"] == "ALL_COMPONENTS"
    assert kwargs["direction"] == "AUTOMATIC"
    assert kwargs["eig_band"] == 2
    assert kwargs["eig_kpoint"] == (0.1, 0.2, 0.3)
    assert kwargs["eig_match_freq"] is False
    assert kwargs["eig_parity"] == 9
    assert kwargs["eig_resolution"] == 16
    assert kwargs["eig_tolerance"] == 1e-9
    assert kwargs["amplitude"] == 2 + 1j
    assert kwargs["eig_lattice_size"] == (4.0, 5.0, 0)
    assert kwargs["eig_lattice_center"] == (0.5, -0.5, 0)
    assert kwargs["eig_vol"] == (
        "Volume",
        {"center": (1.5, 0.0, 0), "size": (0.0, 2.0, 0)},
    )
