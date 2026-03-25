from __future__ import annotations

from dataclasses import asdict

from ..model import ProjectState


def dump_state_dict(state: ProjectState) -> dict:
    transmission_data = asdict(state.analysis.transmission_spectrum)
    transmission_data.pop("reuse_reference_run_id", None)
    transmission_data.pop("reuse_reference_csv_name", None)
    return {
        "parameters": [asdict(p) for p in state.parameters],
        "materials": [asdict(m) for m in state.materials],
        "geometries": [asdict(g) for g in state.geometries],
        "sources": [asdict(s) for s in state.sources],
        "domain": asdict(state.domain),
        "flux_monitors": [asdict(m) for m in state.flux_monitors],
        "analysis": {
            "kind": state.analysis.kind,
            "field_animation": asdict(state.analysis.field_animation),
            "harminv": asdict(state.analysis.harminv),
            "transmission_spectrum": transmission_data,
            "frequency_domain_solver": asdict(state.analysis.frequency_domain_solver),
            "meep_k_points": {
                **asdict(state.analysis.meep_k_points),
                "kpoints": [asdict(k) for k in state.analysis.meep_k_points.kpoints],
            },
            "mpb_modesolver": {
                **asdict(state.analysis.mpb_modesolver),
                "kpoints": [asdict(k) for k in state.analysis.mpb_modesolver.kpoints],
            },
        },
        "sweep": {
            "enabled": state.sweep.enabled,
            "params": [asdict(p) for p in state.sweep.params],
        },
    }
