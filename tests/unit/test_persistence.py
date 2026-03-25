from __future__ import annotations

import json
from pathlib import Path

from meep_gui.persistence import state_from_dict, state_to_dict

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_project_dict_roundtrip_fixture() -> None:
    raw = _load_fixture("project_roundtrip.json")

    state = state_from_dict(raw)
    dumped = state_to_dict(state)

    assert dumped == raw
    assert state.analysis.transmission_spectrum.reuse_reference_run_id == ""
    assert state.analysis.transmission_spectrum.reuse_reference_csv_name == "transmission_spectrum.csv"
    assert state.results == []


def test_legacy_animation_data_fixture_is_ignored() -> None:
    state = state_from_dict(_load_fixture("legacy_animation_data.json"))

    assert state.results == []


def test_absent_new_sections_fixture_keeps_defaults() -> None:
    state = state_from_dict(_load_fixture("minimal_analysis.json"))

    assert state.flux_monitors == []
    assert state.results == []
    assert state.sweep.enabled is False
    assert state.analysis.transmission_spectrum.output_prefix == "transmission"
    assert state.analysis.transmission_spectrum.reference_reflection_monitor == ""
    assert state.analysis.transmission_spectrum.animate_reference is False
    assert state.analysis.transmission_spectrum.animate_scattering is False
    assert state.analysis.transmission_spectrum.animation_component == "Ez"
    assert state.analysis.transmission_spectrum.animation_interval == "1"
    assert state.analysis.transmission_spectrum.animation_fps == "20"
    assert state.analysis.transmission_spectrum.reference_state.geometries == []
    assert state.analysis.transmission_spectrum.reference_state.sources == []
    assert state.analysis.transmission_spectrum.reference_state.flux_monitors == []
    assert state.domain.symmetry_enabled is False
    assert state.domain.symmetries == []
    assert state.analysis.frequency_domain_solver.component == "Ez"
    assert state.analysis.frequency_domain_solver.tolerance == "1e-8"
    assert state.analysis.frequency_domain_solver.max_iters == "10000"
    assert state.analysis.frequency_domain_solver.bicgstab_l == "10"
    assert state.analysis.meep_k_points.kpoint_interp == "19"
    assert state.analysis.meep_k_points.run_time == "300"
    assert state.analysis.meep_k_points.kpoints == []
    assert state.analysis.meep_k_points.output_prefix == "meep_k_points"
    assert state.analysis.mpb_modesolver.run_tm is True
    assert state.analysis.mpb_modesolver.run_te is False
    assert state.analysis.mpb_modesolver.field_kpoints == []


def test_invalid_symmetry_fixture_normalizes_to_safe_defaults() -> None:
    state = state_from_dict(_load_fixture("invalid_symmetry.json"))

    assert state.domain.symmetry_enabled is True
    assert state.domain.symmetries[0].kind == "mirror"
    assert state.domain.symmetries[0].direction == "x"


def test_legacy_sweep_limit_fields_are_ignored_on_load() -> None:
    raw = _load_fixture("minimal_analysis.json")
    raw["sweep"] = {
        "enabled": True,
        "max_points": "40",
        "allow_large": True,
        "params": [{"name": "a", "start": "1", "stop": "3", "steps": "0.5"}],
    }

    state = state_from_dict(raw)
    dumped = state_to_dict(state)

    assert state.sweep.enabled is True
    assert len(state.sweep.params) == 1
    assert "max_points" not in dumped["sweep"]
    assert "allow_large" not in dumped["sweep"]


def test_legacy_mpb_force_all_modes_is_ignored_on_load() -> None:
    raw = _load_fixture("minimal_analysis.json")
    raw.setdefault("analysis", {})
    raw["analysis"]["mpb_modesolver"] = {"force_all_modes": True}

    state = state_from_dict(raw)
    dumped = state_to_dict(state)

    assert not hasattr(state.analysis.mpb_modesolver, "force_all_modes")
    assert "force_all_modes" not in dumped["analysis"]["mpb_modesolver"]
