from __future__ import annotations

import copy
import os

from ..model import ProjectState
from .domain_artifacts import create_domain_preview_artifacts
from .transmission_support import (
    align_reused_incident_data,
    artifact_path_by_kind,
    build_transmission_reference_state,
    export_transmission_outputs,
    find_flux_spec_by_name,
    find_run_record_by_id,
    flux_by_name,
    load_incident_data_from_transmission_csv,
    safe_ratio,
)
from .types import ArtifactResult, CancelFn, LogFn, PlotResult, RunResult
from .workspace import create_run_output_dir


def _build_field_decay_stop_condition(
    cfg,
    values: dict[str, float],
    deps,
    domain_name: str,
):
    mp = deps._import_meep()
    component = getattr(mp, cfg.field_decay_component, getattr(mp, "Ez", None))
    if component is None:
        raise ValueError("Meep field components are unavailable. Check your Meep installation.")
    prefix = "reference" if domain_name == "reference" else "scattering"
    additional_time = deps._eval_required(
        getattr(cfg, f"{prefix}_field_decay_additional_time"),
        values,
        f"{prefix}_field_decay_additional_time",
    )
    point_x = deps._eval_required(
        getattr(cfg, f"{prefix}_field_decay_point_x"),
        values,
        f"{prefix}_field_decay_point_x",
    )
    point_y = deps._eval_required(
        getattr(cfg, f"{prefix}_field_decay_point_y"),
        values,
        f"{prefix}_field_decay_point_y",
    )
    decay_by = deps._eval_required(
        getattr(cfg, f"{prefix}_field_decay_by"),
        values,
        f"{prefix}_field_decay_by",
    )
    return mp.stop_when_fields_decayed(
        additional_time,
        component,
        mp.Vector3(point_x, point_y, 0),
        decay_by,
    )


def _build_transmission_stop_condition(
    cfg,
    values: dict[str, float],
    deps,
    domain_name: str,
):
    if cfg.stop_condition == "field_decay":
        return _build_field_decay_stop_condition(cfg, values, deps, domain_name)
    return deps._eval_required(cfg.until_after_sources, values, "until_after_sources")


def run_transmission_spectrum_impl(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    *,
    deps,
) -> RunResult:
    if deps.run_sim is None:
        raise RuntimeError("Meep runner is not available")

    state = copy.deepcopy(state)
    cfg = state.analysis.transmission_spectrum
    reference_state = build_transmission_reference_state(state)

    values, results = deps.evaluate_parameters(state.parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")

    output_prefix = cfg.output_prefix.strip() or "transmission"
    output_dir_cfg = cfg.output_dir.strip()
    reuse_reference_run_id = cfg.reuse_reference_run_id.strip()
    reuse_requested = bool(reuse_reference_run_id)
    animate_reference = bool(cfg.animate_reference)
    animate_scattering = bool(cfg.animate_scattering)
    if reuse_requested and animate_reference:
        log(
            "Warning: reference animation is disabled when reusing cached reference data."
        )
        animate_reference = False

    mp = None
    ref_animate = None
    dev_animate = None
    ref_step_funcs = None
    dev_step_funcs = None
    animation_fps = 0
    if animate_reference or animate_scattering:
        mp = deps._import_meep()
        anim_comp = getattr(mp, cfg.animation_component, getattr(mp, "Ez", None))
        if anim_comp is None:
            raise ValueError("Meep field components are unavailable. Check your Meep installation.")
        animation_interval = deps._eval_required(cfg.animation_interval, values, "animation_interval")
        animation_fps = int(deps._eval_required(cfg.animation_fps, values, "animation_fps"))
        if animation_interval <= 0:
            raise ValueError("animation_interval must be > 0.")
        if animation_fps <= 0:
            raise ValueError("animation_fps must be > 0.")
        if animate_reference:
            ref_animate = mp.Animate2D(fields=anim_comp, realtime=False)
            ref_step_funcs = [mp.at_every(animation_interval, ref_animate)]
        if animate_scattering:
            dev_animate = mp.Animate2D(fields=anim_comp, realtime=False)
            dev_step_funcs = [mp.at_every(animation_interval, dev_animate)]

    ref_flux_specs = deps._build_flux_specs(reference_state, values)
    if not ref_flux_specs:
        raise ValueError("At least one reference flux monitor is required for transmission analysis.")
    dev_flux_specs = deps._build_flux_specs(state, values)
    if not dev_flux_specs:
        raise ValueError("At least one scattering flux monitor is required for transmission analysis.")

    incident_name = cfg.incident_monitor.strip()
    transmission_name = cfg.transmission_monitor.strip()
    reflection_name = cfg.reflection_monitor.strip()
    reference_reflection_name = cfg.reference_reflection_monitor.strip()
    ref_available_names = {item.name for item in ref_flux_specs}
    dev_available_names = {item.name for item in dev_flux_specs}
    if not incident_name:
        raise ValueError("Incident monitor is required.")
    if not transmission_name:
        raise ValueError("Transmission monitor is required.")
    if incident_name not in ref_available_names:
        raise ValueError(f"Incident monitor '{incident_name}' was not found in reference monitors.")
    if transmission_name not in dev_available_names:
        raise ValueError(
            f"Transmission monitor '{transmission_name}' was not found in scattering monitors."
        )
    if reflection_name and reflection_name not in dev_available_names:
        raise ValueError(f"Reflection monitor '{reflection_name}' was not found in scattering monitors.")
    if reference_reflection_name and reference_reflection_name not in ref_available_names:
        raise ValueError(
            f"Reference reflection monitor '{reference_reflection_name}' was not found in reference monitors."
        )

    incident_spec = find_flux_spec_by_name(ref_flux_specs, incident_name)
    transmission_spec = find_flux_spec_by_name(dev_flux_specs, transmission_name)
    if incident_spec is None:
        raise RuntimeError(f"Incident monitor '{incident_name}' is unavailable.")
    if transmission_spec is None:
        raise RuntimeError(f"Transmission monitor '{transmission_name}' is unavailable.")

    if cancel_requested():
        return deps._run_canceled()

    params_device = deps._build_sim_params(state)

    minus_flux_data = None
    incident_freqs: list[float] = []
    incident_vals: list[float] = []
    reference_mode = "fresh"
    reused_reference_run_id = ""

    if reuse_requested:
        selected_run = find_run_record_by_id(state, reuse_reference_run_id)
        if selected_run is None:
            raise ValueError(
                f"Selected cached reference run '{reuse_reference_run_id}' was not found. "
                "Clear reuse selection or rerun reference."
            )
        if selected_run.analysis_kind != "transmission_spectrum":
            raise ValueError(
                f"Selected cached run '{reuse_reference_run_id}' is not a transmission spectrum run."
            )
        csv_path = artifact_path_by_kind(selected_run, "transmission_csv")
        if not csv_path:
            raise ValueError(
                f"Selected cached run '{reuse_reference_run_id}' does not include transmission CSV data."
            )
        incident_freqs, incident_vals = load_incident_data_from_transmission_csv(csv_path)
        reference_mode = "reused"
        reused_reference_run_id = selected_run.run_id
        log(
            f"Reusing reference incident data from run '{selected_run.run_id}' ({csv_path}). "
            "Skipping reference simulation."
        )
        if reflection_name:
            log(
                "Warning: reflection monitor selected while reusing cached incident data; "
                "minus-flux subtraction is unavailable."
            )
    else:
        params_reference = deps._build_sim_params(reference_state)
        log("Running transmission reference simulation...")
        ref_result = deps.run_sim(
            params_reference,
            log,
            until_after_sources=_build_transmission_stop_condition(
                cfg,
                values,
                deps,
                "reference",
            ),
            step_funcs=ref_step_funcs,
            stop_flag=cancel_requested,
            flux_monitors=ref_flux_specs,
            capture_flux_data=bool(reference_reflection_name and reflection_name),
        )
        if ref_result.canceled or cancel_requested():
            return deps._run_canceled()

        ref_flux = flux_by_name(ref_result.flux_results)
        if incident_name not in ref_flux:
            raise RuntimeError(f"Reference run did not produce monitor '{incident_name}'.")

        incident = ref_flux[incident_name]
        n_incident = min(len(incident.freqs), len(incident.values))
        if n_incident == 0:
            raise RuntimeError("Reference incident monitor returned empty spectral data.")
        incident_freqs = incident.freqs[:n_incident]
        incident_vals = incident.values[:n_incident]

        if reflection_name:
            if reference_reflection_name:
                minus_flux_data = {}
                if reference_reflection_name in ref_result.flux_data:
                    minus_flux_data[reflection_name] = ref_result.flux_data[reference_reflection_name]
                else:
                    log(
                        "Warning: reference reflection monitor flux-data was unavailable; "
                        "R will be computed without subtracting incident field."
                    )
            else:
                log(
                    "Warning: reflection monitor selected without a reference reflection monitor; "
                    "R will be computed without subtracting incident field."
                )

    log("Running transmission scattering simulation...")
    dev_result = deps.run_sim(
        params_device,
        log,
        until_after_sources=_build_transmission_stop_condition(
            cfg,
            values,
            deps,
            "scattering",
        ),
        step_funcs=dev_step_funcs,
        stop_flag=cancel_requested,
        flux_monitors=dev_flux_specs,
        minus_flux_data=minus_flux_data,
    )
    if dev_result.canceled or cancel_requested():
        return deps._run_canceled()

    dev_flux = flux_by_name(dev_result.flux_results)
    if transmission_name not in dev_flux:
        raise RuntimeError(f"Device run did not produce monitor '{transmission_name}'.")

    transmitted = dev_flux[transmission_name]
    trans_freqs = transmitted.freqs
    trans_values = transmitted.values
    n_trans = min(len(trans_freqs), len(trans_values))
    if n_trans == 0:
        raise RuntimeError("Transmission monitor returned empty spectral data.")
    trans_freqs = trans_freqs[:n_trans]
    trans_values = trans_values[:n_trans]

    if reference_mode == "reused":
        freqs, incident_vals, trans_vals, reuse_warnings = align_reused_incident_data(
            incident_freqs,
            incident_vals,
            trans_freqs,
            trans_values,
        )
        for message in reuse_warnings:
            log(message)
    else:
        n = min(
            len(incident_freqs),
            len(incident_vals),
            len(trans_values),
            len(trans_freqs),
        )
        if n == 0:
            raise RuntimeError("Transmission monitors returned empty spectral data.")
        freqs = incident_freqs[:n]
        incident_vals = incident_vals[:n]
        trans_vals = trans_values[:n]
    t_ratio = [safe_ratio(trans_vals[i], incident_vals[i]) for i in range(len(freqs))]

    refl_vals: list[float] | None = None
    r_ratio: list[float] | None = None
    if reflection_name and reflection_name in dev_flux:
        reflected = dev_flux[reflection_name]
        m = min(len(freqs), len(reflected.values), len(reflected.freqs), len(incident_vals), len(trans_vals))
        freqs = freqs[:m]
        incident_vals = incident_vals[:m]
        trans_vals = trans_vals[:m]
        t_ratio = t_ratio[:m]
        refl_vals = reflected.values[:m]
        r_ratio = [safe_ratio(-refl_vals[i], incident_vals[i]) for i in range(m)]

    out_dir = create_run_output_dir("meep_gui_transmission_")
    safe_prefix = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in output_prefix) or "transmission"
    artifact, plot = export_transmission_outputs(
        output_dir=out_dir,
        output_prefix=output_prefix,
        freqs=freqs,
        incident=incident_vals,
        transmitted=trans_vals,
        reflection=refl_vals,
        trans_ratio=t_ratio,
        refl_ratio=r_ratio,
    )
    artifacts: list[ArtifactResult] = [artifact]
    if ref_animate is not None:
        ref_name = f"{safe_prefix}_reference.mp4"
        ref_path = os.path.join(out_dir, ref_name)
        ref_animate.to_mp4(animation_fps, ref_path)
        artifacts.append(
            ArtifactResult(
                kind="animation_mp4",
                label=ref_name,
                path=ref_path,
                meta={"domain": "reference"},
            )
        )
    if dev_animate is not None:
        dev_name = f"{safe_prefix}_scattering.mp4"
        dev_path = os.path.join(out_dir, dev_name)
        dev_animate.to_mp4(animation_fps, dev_path)
        artifacts.append(
            ArtifactResult(
                kind="animation_mp4",
                label=dev_name,
                path=dev_path,
                meta={"domain": "scattering"},
            )
        )
    artifacts.extend(
        create_domain_preview_artifacts(
            state,
            out_dir,
            log,
            export_dir=output_dir_cfg,
            build_sim_impl=getattr(deps, "build_sim", None),
        )
    )

    if output_dir_cfg:
        for item in artifacts:
            item.meta["export_dir"] = output_dir_cfg
            item.meta["export_name"] = os.path.basename(item.path)
        plot.meta["export_dir"] = output_dir_cfg

    message = "Transmission spectrum completed."
    if any(abs(v) < 1e-18 for v in incident_vals):
        message += " Some incident values were near zero; ratios may include NaN."

    return RunResult(
        status="completed",
        message=message,
        artifacts=artifacts,
        plots=[plot],
        meta={
            "incident_monitor": incident_name,
            "transmission_monitor": transmission_name,
            "reflection_monitor": reflection_name,
            "reference_reflection_monitor": reference_reflection_name,
            "ref_incident_fcen": f"{incident_spec.fcen:.17g}",
            "ref_incident_df": f"{incident_spec.df:.17g}",
            "ref_incident_nfreq": str(int(incident_spec.nfreq)),
            "dev_trans_fcen": f"{transmission_spec.fcen:.17g}",
            "dev_trans_df": f"{transmission_spec.df:.17g}",
            "dev_trans_nfreq": str(int(transmission_spec.nfreq)),
            "reference_mode": reference_mode,
            "reused_reference_run_id": reused_reference_run_id,
            "point_count": str(len(freqs)),
        },
    )
