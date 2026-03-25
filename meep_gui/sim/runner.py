from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..specs.simulation import FluxMonitorResult, FluxMonitorSpec, HarminvSpec, SimParams
from .builder import build_sim
from .imports import component_map, import_meep

LogFn = Callable[[str], None]


@dataclass
class SimRunResult:
    canceled: bool = False
    flux_results: list[FluxMonitorResult] = field(default_factory=list)
    flux_data: dict[str, object] = field(default_factory=dict)


def run_sim(
    params: SimParams,
    log: LogFn,
    until_time: float | None = None,
    until_after_sources: float | None = None,
    stop_flag: Callable[[], bool] | None = None,
    step_funcs: list[object] | None = None,
    harminv_spec: HarminvSpec | None = None,
    harminv_cb: Callable[[object], None] | None = None,
    flux_monitors: list[FluxMonitorSpec] | None = None,
    capture_flux_data: bool = False,
    minus_flux_data: dict[str, object] | None = None,
) -> SimRunResult:
    mp = import_meep()
    sim = build_sim(params, log)
    components = component_map(mp)
    canceled = False

    def log_step(sim_inst):
        nonlocal canceled
        t = sim_inst.meep_time()
        log(f"t = {t:.2f}")
        if stop_flag and stop_flag():
            canceled = True
            log("Stop requested. Finishing early...")
            if hasattr(sim_inst, "abort"):
                sim_inst.abort()

    callbacks = [mp.at_every(10, log_step)]
    if step_funcs:
        callbacks.extend(step_funcs)

    harminv_obj = None
    if harminv_spec is not None:
        comp = components.get(harminv_spec.component, mp.Ez)
        harminv_obj = mp.Harminv(
            comp,
            mp.Vector3(harminv_spec.center_x, harminv_spec.center_y),
            harminv_spec.frequency,
            harminv_spec.bandwidth,
        )
        callbacks.append(mp.after_sources(harminv_obj))

    flux_handles: list[tuple[FluxMonitorSpec, object]] = []
    if flux_monitors:
        for monitor in flux_monitors:
            region = mp.FluxRegion(
                center=mp.Vector3(monitor.center_x, monitor.center_y, 0),
                size=mp.Vector3(monitor.size_x, monitor.size_y, 0),
            )
            handle = sim.add_flux(monitor.fcen, monitor.df, monitor.nfreq, region)
            if minus_flux_data and monitor.name in minus_flux_data:
                try:
                    sim.load_minus_flux_data(handle, minus_flux_data[monitor.name])
                except Exception:
                    log(f"Warning: failed to preload minus flux data for monitor '{monitor.name}'.")
            flux_handles.append((monitor, handle))

    log("Running simulation...")
    if until_after_sources is not None:
        sim.run(*callbacks, until_after_sources=until_after_sources)
    elif until_time is not None:
        sim.run(*callbacks, until=until_time)
    else:
        raise ValueError("until_time or until_after_sources must be provided.")
    log("Done.")

    if harminv_obj is not None and harminv_cb is not None:
        harminv_cb(harminv_obj)

    flux_results: list[FluxMonitorResult] = []
    flux_data_out: dict[str, object] = {}
    for monitor, handle in flux_handles:
        freqs = [float(x) for x in mp.get_flux_freqs(handle)]
        values = [float(x) for x in mp.get_fluxes(handle)]
        flux_results.append(FluxMonitorResult(name=monitor.name, freqs=freqs, values=values))
        if capture_flux_data:
            try:
                flux_data_out[monitor.name] = sim.get_flux_data(handle)
            except Exception:
                log(f"Warning: failed to capture flux data for monitor '{monitor.name}'.")

    return SimRunResult(canceled=canceled, flux_results=flux_results, flux_data=flux_data_out)
