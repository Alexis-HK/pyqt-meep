from __future__ import annotations

import os

from .common import line
from .domain_preview import emit_domain_preview_call
from .simulation import (
    emit_boundary_layers,
    emit_flux_handles,
    emit_geometry,
    emit_sources,
    emit_symmetries,
)


def emit_transmission(lines: list[str], state, scattering_scene, reference_scene) -> None:
    cfg = state.analysis.transmission_spectrum
    output_prefix = cfg.output_prefix.strip() or "transmission"
    ref_marker_expr = None
    dev_marker_expr = None
    if cfg.stop_condition == "field_decay":
        ref_marker_expr = (
            cfg.reference_field_decay_point_x,
            cfg.reference_field_decay_point_y,
        )
        dev_marker_expr = (
            cfg.scattering_field_decay_point_x,
            cfg.scattering_field_decay_point_y,
        )
    reuse_csv_name = os.path.basename(
        (cfg.reuse_reference_csv_name or "transmission_spectrum.csv").strip()
    ) or "transmission_spectrum.csv"
    line(lines, "# Transmission spectrum (two runs)")
    line(lines, f"reference_incident_csv = '{reuse_csv_name}'")
    line(lines, f"incident_monitor_name = '{cfg.incident_monitor}'")
    line(lines, f"trans_monitor_name = '{cfg.transmission_monitor}'")
    line(lines, f"refl_monitor_name = '{cfg.reflection_monitor}'")
    line(lines, f"ref_refl_monitor_name = '{cfg.reference_reflection_monitor}'")
    line(lines, f"animate_ref = {cfg.animate_reference}")
    line(lines, f"animate_dev = {cfg.animate_scattering}")
    if cfg.animate_reference or cfg.animate_scattering:
        line(lines, f"anim_component = mp.{cfg.animation_component}")
        line(lines, f"anim_interval = {cfg.animation_interval}")
        line(lines, f"anim_fps = int({cfg.animation_fps})")
    else:
        line(lines, "anim_component = mp.Ez")
        line(lines, "anim_interval = 1")
        line(lines, "anim_fps = 20")
    line(lines)

    for text in (
        "def _load_cached_incident(path):",
        "    if not os.path.exists(path):",
        "        return None, None",
        "    try:",
        "        with open(path, 'r', encoding='utf-8', newline='') as f:",
        "            reader = csv.DictReader(f)",
        "            fieldnames = set(reader.fieldnames or [])",
        "            if 'frequency' not in fieldnames or 'incident' not in fieldnames:",
        "                print(f\"Warning: cached reference CSV '{path}' is missing required columns; running fresh reference.\")",
        "                return None, None",
        "            freqs = []",
        "            incident = []",
        "            for row in reader:",
        "                freqs.append(float(str(row.get('frequency', '')).strip()))",
        "                incident.append(float(str(row.get('incident', '')).strip()))",
        "            if not freqs or len(freqs) != len(incident):",
        "                print(f\"Warning: cached reference CSV '{path}' has invalid data; running fresh reference.\")",
        "                return None, None",
        "            return freqs, incident",
        "    except Exception as exc:",
        "        print(f\"Warning: could not read cached reference CSV '{path}': {exc}; running fresh reference.\")",
        "        return None, None",
        "",
        "reference_incident_path = os.path.join(out_dir, reference_incident_csv)",
        "cached_ref_freqs, cached_incident_ref = _load_cached_incident(reference_incident_path)",
        "use_cached_reference = cached_ref_freqs is not None and cached_incident_ref is not None",
        "",
        "def _transmission_stop_condition(domain_name):",
    ):
        line(lines, text)
    if cfg.stop_condition == "field_decay":
        for text in (
            "    if domain_name == 'reference':",
            "        return mp.stop_when_fields_decayed(",
            f"            {cfg.reference_field_decay_additional_time},",
            f"            mp.{cfg.field_decay_component},",
            f"            mp.Vector3({cfg.reference_field_decay_point_x}, {cfg.reference_field_decay_point_y}, 0),",
            f"            {cfg.reference_field_decay_by},",
            "        )",
            "    return mp.stop_when_fields_decayed(",
            f"        {cfg.scattering_field_decay_additional_time},",
            f"        mp.{cfg.field_decay_component},",
            f"        mp.Vector3({cfg.scattering_field_decay_point_x}, {cfg.scattering_field_decay_point_y}, 0),",
            f"        {cfg.scattering_field_decay_by},",
            "    )",
            "",
            "# Reference-domain setup",
        ):
            line(lines, text)
    else:
        for text in (
            f"    return {cfg.until_after_sources}",
            "",
            "# Reference-domain setup",
        ):
            line(lines, text)

    emit_geometry(lines, "ref_geometry", reference_scene.objects)
    line(lines)
    emit_sources(lines, "ref_sources", reference_scene.sources)
    line(lines)
    emit_boundary_layers(lines, "ref_boundary_layers", reference_scene.domain)
    line(lines)
    emit_symmetries(lines, "ref_symmetries", reference_scene.symmetries)
    line(lines)
    for text in (
        "sim_ref = mp.Simulation(",
        f"    cell_size=mp.Vector3({reference_scene.domain.cell_x_expr}, {reference_scene.domain.cell_y_expr}, 0),",
        "    boundary_layers=ref_boundary_layers,",
        "    geometry=ref_geometry,",
        "    sources=ref_sources,",
        "    symmetries=ref_symmetries,",
        f"    resolution={reference_scene.domain.resolution_expr},",
        ")",
    ):
        line(lines, text)
    emit_flux_handles(lines, "ref_flux_handles", "sim_ref", reference_scene.monitors)
    for text in (
        "if incident_monitor_name not in ref_flux_handles:",
        "    raise ValueError(f\"Incident monitor '{incident_monitor_name}' not found in reference monitors.\")",
        "if ref_refl_monitor_name and ref_refl_monitor_name not in ref_flux_handles:",
        "    raise ValueError(f\"Reference reflection monitor '{ref_refl_monitor_name}' not found in reference monitors.\")",
        "",
        "ref_anim = None",
        "ref_freqs = None",
        "incident_ref = None",
        "minus_flux_data = None",
        "if use_cached_reference:",
        "    print(f\"Reusing reference incident data from {reference_incident_path}; skipping reference simulation.\")",
        "    ref_freqs = cached_ref_freqs",
        "    incident_ref = cached_incident_ref",
        "    if animate_ref:",
        "        print('Warning: reference animation disabled while reusing cached incident data.')",
        "    if refl_monitor_name:",
        "        print('Warning: reflection monitor selected while reusing cached incident data; running without minus-flux subtraction.')",
        "else:",
        "    ref_anim = mp.Animate2D(fields=anim_component, realtime=False) if animate_ref else None",
        "    ref_step_funcs = []",
        "    if ref_anim is not None:",
        "        ref_step_funcs.append(mp.at_every(anim_interval, ref_anim))",
        "    sim_ref.run(*ref_step_funcs, until_after_sources=_transmission_stop_condition('reference'))",
        "    ref_freqs = list(mp.get_flux_freqs(ref_flux_handles[incident_monitor_name]))",
        "    incident_ref = list(mp.get_fluxes(ref_flux_handles[incident_monitor_name]))",
        "    if refl_monitor_name and ref_refl_monitor_name:",
        "        minus_flux_data = sim_ref.get_flux_data(ref_flux_handles[ref_refl_monitor_name])",
        "    elif refl_monitor_name:",
        "        print('Warning: reflection monitor selected without reference reflection monitor; running without minus-flux subtraction.')",
    ):
        line(lines, text)
    emit_domain_preview_call(
        lines,
        prefix="ref",
        sim_var="sim_ref",
        output_name="domain_preview_reference.png",
        title="Domain Preview (reference)",
        domain=reference_scene.domain,
        monitors=reference_scene.monitors,
        marker_expr=ref_marker_expr,
    )
    line(lines)
    line(lines, "# Scattering-domain setup")

    emit_boundary_layers(lines, "dev_boundary_layers", scattering_scene.domain)
    line(lines)
    emit_symmetries(lines, "dev_symmetries", scattering_scene.symmetries)
    line(lines)
    for text in (
        "sim_dev = mp.Simulation(",
        f"    cell_size=mp.Vector3({scattering_scene.domain.cell_x_expr}, {scattering_scene.domain.cell_y_expr}, 0),",
        "    boundary_layers=dev_boundary_layers,",
        "    geometry=geometry,",
        "    sources=sources,",
        "    symmetries=dev_symmetries,",
        f"    resolution={scattering_scene.domain.resolution_expr},",
        ")",
    ):
        line(lines, text)
    emit_flux_handles(lines, "dev_flux_handles", "sim_dev", scattering_scene.monitors)
    for text in (
        "if trans_monitor_name not in dev_flux_handles:",
        "    raise ValueError(f\"Transmission monitor '{trans_monitor_name}' not found in scattering monitors.\")",
        "if refl_monitor_name and refl_monitor_name not in dev_flux_handles:",
        "    raise ValueError(f\"Reflection monitor '{refl_monitor_name}' not found in scattering monitors.\")",
        "if refl_monitor_name and minus_flux_data is not None:",
        "    sim_dev.load_minus_flux_data(dev_flux_handles[refl_monitor_name], minus_flux_data)",
    ):
        line(lines, text)
    emit_domain_preview_call(
        lines,
        prefix="dev",
        sim_var="sim_dev",
        output_name="domain_preview_scattering.png",
        title="Domain Preview (scattering)",
        domain=scattering_scene.domain,
        monitors=scattering_scene.monitors,
        marker_expr=dev_marker_expr,
    )
    for text in (
        "dev_anim = mp.Animate2D(fields=anim_component, realtime=False) if animate_dev else None",
        "dev_step_funcs = []",
        "if dev_anim is not None:",
        "    dev_step_funcs.append(mp.at_every(anim_interval, dev_anim))",
        "sim_dev.run(*dev_step_funcs, until_after_sources=_transmission_stop_condition('scattering'))",
        "freqs = [float(x) for x in mp.get_flux_freqs(dev_flux_handles[trans_monitor_name])]",
        "trans_dev = [float(x) for x in mp.get_fluxes(dev_flux_handles[trans_monitor_name])]",
        "if ref_freqs is None or incident_ref is None:",
        "    raise ValueError('Reference incident data is unavailable.')",
        "if len(freqs) != len(ref_freqs):",
        "    raise ValueError('Cached reference frequency grid length does not match scattering frequencies. Remove cache CSV or rerun fresh reference.')",
        "for idx, (f_dev, f_ref) in enumerate(zip(freqs, ref_freqs)):",
        "    if abs(float(f_dev) - float(f_ref)) > 1e-12:",
        "        raise ValueError(f'Cached reference frequency mismatch at index {idx}. Remove cache CSV or rerun fresh reference.')",
        "if len(trans_dev) != len(incident_ref):",
        "    raise ValueError('Cached incident data length does not match scattering transmission data.')",
        "T = [t / i if abs(i) > 1e-18 else float('nan') for t, i in zip(trans_dev, incident_ref)]",
        "R = None",
        "refl_dev = None",
        "if refl_monitor_name:",
        "    refl_dev = [float(x) for x in mp.get_fluxes(dev_flux_handles[refl_monitor_name])]",
        "    R = [(-r) / i if abs(i) > 1e-18 else float('nan') for r, i in zip(refl_dev, incident_ref)]",
        "",
        f"safe_prefix = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in \"{output_prefix}\") or 'transmission'",
        "if (not use_cached_reference) and ref_anim is not None:",
        "    ref_anim.to_mp4(anim_fps, os.path.join(out_dir, f\"{safe_prefix}_reference.mp4\"))",
        "if dev_anim is not None:",
        "    dev_anim.to_mp4(anim_fps, os.path.join(out_dir, f\"{safe_prefix}_scattering.mp4\"))",
        "",
        "import matplotlib.pyplot as plt",
        f"prefix = \"{output_prefix}\"",
        "csv_path = os.path.join(out_dir, f\"{prefix}_spectrum.csv\")",
        "with open(csv_path, 'w', newline='', encoding='utf-8') as f:",
        "    writer = csv.writer(f)",
        "    if R is None:",
        "        writer.writerow(['frequency', 'incident', 'transmitted', 'T'])",
        "        for fr, iv, tv, tr in zip(freqs, incident_ref, trans_dev, T):",
        "            writer.writerow([fr, iv, tv, tr])",
        "    else:",
        "        writer.writerow(['frequency', 'incident', 'transmitted', 'T', 'reflected', 'R', 'T_plus_R'])",
        "        for fr, iv, tv, tr, rv_raw, rv in zip(freqs, incident_ref, trans_dev, T, refl_dev, R):",
        "            writer.writerow([fr, iv, tv, tr, rv_raw, rv, tr + rv])",
        "plt.figure(figsize=(6, 4), dpi=120)",
        "plt.plot(freqs, T, label='T')",
        "if R is not None:",
        "    plt.plot(freqs, R, label='R')",
        "    plt.plot(freqs, [tv + rv for tv, rv in zip(T, R)], '--', label='T+R')",
        "plt.xlabel('Frequency')",
        "plt.ylabel('Normalized response')",
        "plt.grid(True, linestyle=':', linewidth=0.5)",
        "plt.legend(loc='best')",
        "plt.tight_layout()",
        "plt.savefig(os.path.join(out_dir, f\"{prefix}_spectrum.png\"))",
        "plt.close()",
    ):
        line(lines, text)
