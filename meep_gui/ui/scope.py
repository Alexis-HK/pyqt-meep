from __future__ import annotations

from dataclasses import dataclass, replace

from ..model import Domain, FluxMonitorConfig, GeometryItem, SourceItem
from ..store import ProjectStore
from ..validation import NameRegistry, evaluate_numeric_expression, evaluate_parameters


@dataclass(frozen=True)
class ProjectScope:
    store: ProjectStore

    @property
    def is_reference(self) -> bool:
        analysis = self.store.state.analysis
        return (
            analysis.kind == "transmission_spectrum"
            and analysis.transmission_spectrum.preview_domain == "reference"
        )

    @property
    def domain(self) -> Domain:
        if self.is_reference:
            return self.store.state.analysis.transmission_spectrum.reference_state.domain
        return self.store.state.domain

    def set_domain(self, domain: Domain) -> None:
        if self.is_reference:
            self.store.state.analysis.transmission_spectrum.reference_state.domain = domain
            return
        self.store.state.domain = domain

    def replace_domain(self, **changes) -> None:
        self.set_domain(replace(self.domain, **changes))

    @property
    def geometries(self) -> list[GeometryItem]:
        if self.is_reference:
            return self.store.state.analysis.transmission_spectrum.reference_state.geometries
        return self.store.state.geometries

    @property
    def sources(self) -> list[SourceItem]:
        if self.is_reference:
            return self.store.state.analysis.transmission_spectrum.reference_state.sources
        return self.store.state.sources

    @property
    def flux_monitors(self) -> list[FluxMonitorConfig]:
        if self.is_reference:
            return self.store.state.analysis.transmission_spectrum.reference_state.flux_monitors
        return self.store.state.flux_monitors

    def name_registry(self) -> NameRegistry:
        if not self.is_reference:
            return NameRegistry.from_state(self.store.state)
        tx_reference = self.store.state.analysis.transmission_spectrum.reference_state
        return NameRegistry(
            parameters={getattr(item, "name", "") for item in self.store.state.parameters},
            materials={getattr(item, "name", "") for item in self.store.state.materials},
            geometries={getattr(item, "name", "") for item in tx_reference.geometries},
            sources={getattr(item, "name", "") for item in tx_reference.sources},
        )


def active_scope(store: ProjectStore) -> ProjectScope:
    return ProjectScope(store)


def parameter_names(store: ProjectStore) -> list[str]:
    return [param.name for param in store.state.parameters]


def transmission_monitor_signature_from_state(
    store: ProjectStore,
    incident_name: str,
    transmission_name: str,
) -> tuple[float, float, int, float, float, int] | None:
    incident_name = incident_name.strip()
    transmission_name = transmission_name.strip()
    if not incident_name or not transmission_name:
        return None

    tx_cfg = store.state.analysis.transmission_spectrum
    ref_monitor = next(
        (item for item in tx_cfg.reference_state.flux_monitors if item.name == incident_name),
        None,
    )
    dev_monitor = next(
        (item for item in store.state.flux_monitors if item.name == transmission_name),
        None,
    )
    if ref_monitor is None or dev_monitor is None:
        return None

    values, results = evaluate_parameters(store.state.parameters)
    for result in results:
        if not result.ok:
            return None

    try:
        ref_fcen = float(evaluate_numeric_expression(ref_monitor.fcen, values))
        ref_df = float(evaluate_numeric_expression(ref_monitor.df, values))
        ref_nfreq = max(1, int(evaluate_numeric_expression(ref_monitor.nfreq, values)))
        dev_fcen = float(evaluate_numeric_expression(dev_monitor.fcen, values))
        dev_df = float(evaluate_numeric_expression(dev_monitor.df, values))
        dev_nfreq = max(1, int(evaluate_numeric_expression(dev_monitor.nfreq, values)))
    except Exception:
        return None

    return (ref_fcen, ref_df, ref_nfreq, dev_fcen, dev_df, dev_nfreq)


def transmission_monitor_signature_from_meta(
    meta: dict[str, str],
) -> tuple[float, float, int, float, float, int] | None:
    try:
        return (
            float(str(meta.get("ref_incident_fcen", "")).strip()),
            float(str(meta.get("ref_incident_df", "")).strip()),
            int(str(meta.get("ref_incident_nfreq", "")).strip()),
            float(str(meta.get("dev_trans_fcen", "")).strip()),
            float(str(meta.get("dev_trans_df", "")).strip()),
            int(str(meta.get("dev_trans_nfreq", "")).strip()),
        )
    except Exception:
        return None


def signatures_match(
    current: tuple[float, float, int, float, float, int] | None,
    candidate: tuple[float, float, int, float, float, int] | None,
) -> bool:
    if current is None or candidate is None:
        return False
    tol = 1e-12
    return (
        abs(current[0] - candidate[0]) <= tol
        and abs(current[1] - candidate[1]) <= tol
        and int(current[2]) == int(candidate[2])
        and abs(current[3] - candidate[3]) <= tol
        and abs(current[4] - candidate[4]) <= tol
        and int(current[5]) == int(candidate[5])
    )
