from __future__ import annotations

import os

from ...model import FIELD_COMPONENTS
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import (
    parameter_names,
    signatures_match,
    transmission_monitor_signature_from_meta,
    transmission_monitor_signature_from_state,
)


def selected_reuse_run_id(panel) -> str:
    return str(panel.reuse_reference.currentData() or "").strip()


def current_reuse_csv_name(panel) -> str:
    run_id = selected_reuse_run_id(panel)
    if run_id and run_id in panel._reuse_candidates:
        return panel._reuse_candidates[run_id].get("csv_name", "transmission_spectrum.csv")
    return "transmission_spectrum.csv"


def sync_animation_controls(panel) -> None:
    if selected_reuse_run_id(panel) and panel.animate_reference.isChecked():
        panel.animate_reference.blockSignals(True)
        panel.animate_reference.setChecked(False)
        panel.animate_reference.blockSignals(False)
    panel.animate_reference.setDisabled(bool(selected_reuse_run_id(panel)))
    enabled = panel.animate_reference.isChecked() or panel.animate_scattering.isChecked()
    panel.animation_box.setVisible(enabled)


def refresh_monitor_choices(panel) -> None:
    current_i = panel.incident_monitor.currentText()
    current_t = panel.transmission_monitor.currentText()
    current_r = panel.reflection_monitor.currentText()
    current_rr = panel.reference_reflection_monitor.currentText()
    cfg = panel.store.state.analysis.transmission_spectrum
    ref_names = [m.name for m in cfg.reference_state.flux_monitors if m.name]
    dev_names = [m.name for m in panel.store.state.flux_monitors if m.name]

    for combo, names, current, allow_blank in (
        (panel.incident_monitor, ref_names, current_i, False),
        (panel.transmission_monitor, dev_names, current_t, False),
        (panel.reflection_monitor, dev_names, current_r, True),
        (panel.reference_reflection_monitor, ref_names, current_rr, True),
    ):
        combo.blockSignals(True)
        combo.clear()
        if allow_blank:
            combo.addItem("")
        combo.addItems(names)
        idx = combo.findText(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.count() > 0 and not allow_blank:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    refresh_reuse_choices(panel)


def refresh_reuse_choices(panel) -> None:
    current_run_id = selected_reuse_run_id(panel)
    current_signature = transmission_monitor_signature_from_state(
        panel.store,
        panel.incident_monitor.currentText(),
        panel.transmission_monitor.currentText(),
    )

    candidates: dict[str, dict[str, str]] = {}
    panel.reuse_reference.blockSignals(True)
    panel.reuse_reference.clear()
    panel.reuse_reference.addItem("Run fresh reference (default)", "")
    for run in reversed(panel.store.state.results):
        if run.analysis_kind != "transmission_spectrum" or run.status != "completed":
            continue
        candidate_signature = transmission_monitor_signature_from_meta(run.meta)
        if not signatures_match(current_signature, candidate_signature):
            continue
        csv_path = ""
        for artifact in run.artifacts:
            if artifact.kind == "transmission_csv" and artifact.path and os.path.exists(artifact.path):
                csv_path = artifact.path
                break
        if not csv_path:
            continue
        incident = run.meta.get("incident_monitor", "?")
        transmission = run.meta.get("transmission_monitor", "?")
        stamp = run.created_at or run.run_id
        panel.reuse_reference.addItem(
            f"{stamp} | {run.run_id} | inc:{incident} tx:{transmission}",
            run.run_id,
        )
        candidates[run.run_id] = {"csv_path": csv_path, "csv_name": os.path.basename(csv_path)}

    if current_run_id in candidates:
        idx = panel.reuse_reference.findData(current_run_id)
        panel.reuse_reference.setCurrentIndex(idx if idx >= 0 else 0)
    else:
        panel.reuse_reference.setCurrentIndex(0)
    panel.reuse_reference.blockSignals(False)
    panel._reuse_candidates = candidates
    sync_animation_controls(panel)
    if panel._ready and selected_reuse_run_id(panel) != current_run_id:
        panel._auto_apply()


def validate_panel(panel) -> bool:
    allowed = parameter_names(panel.store)
    ok = True
    result = validate_numeric_expression(panel.until_after_sources.text().strip(), allowed)
    _set_invalid(panel.until_after_sources, not result.ok)
    if not result.ok:
        _log_error(panel.store, f"Until After Sources: {result.message}", panel)
        ok = False
    anim_enabled = panel.animate_reference.isChecked() or panel.animate_scattering.isChecked()
    if anim_enabled:
        for widget, label in (
            (panel.animation_interval, "Animation Interval"),
            (panel.animation_fps, "Animation FPS"),
        ):
            anim_result = validate_numeric_expression(widget.text().strip(), allowed)
            _set_invalid(widget, not anim_result.ok)
            if not anim_result.ok:
                _log_error(panel.store, f"{label}: {anim_result.message}", panel)
                ok = False
        if panel.animation_component.currentText() not in FIELD_COMPONENTS:
            _set_invalid(panel.animation_component, True)
            _log_error(panel.store, "Animation Component is invalid.", panel)
            ok = False
        else:
            _set_invalid(panel.animation_component, False)
    else:
        _set_invalid(panel.animation_interval, False)
        _set_invalid(panel.animation_fps, False)
        _set_invalid(panel.animation_component, False)

    tx_cfg = panel.store.state.analysis.transmission_spectrum
    reference_names = {m.name for m in tx_cfg.reference_state.flux_monitors if m.name}
    scattering_names = {m.name for m in panel.store.state.flux_monitors if m.name}
    incident = panel.incident_monitor.currentText().strip()
    transmitted = panel.transmission_monitor.currentText().strip()
    reflected = panel.reflection_monitor.currentText().strip()
    reference_reflected = panel.reference_reflection_monitor.currentText().strip()

    def check(combo, name, names, label):
        nonlocal ok
        if not name and label != "Reflection monitor" and label != "Reference reflection monitor":
            _set_invalid(combo, True)
            _log_error(panel.store, f"{label} is required.", panel)
            ok = False
        elif name and name not in names:
            _set_invalid(combo, True)
            _log_error(panel.store, f"{label} '{name}' is not available.", panel)
            ok = False
        else:
            _set_invalid(combo, False)

    check(panel.incident_monitor, incident, reference_names, "Incident monitor")
    check(panel.transmission_monitor, transmitted, scattering_names, "Transmission monitor")
    check(panel.reflection_monitor, reflected, scattering_names, "Reflection monitor")
    check(panel.reference_reflection_monitor, reference_reflected, reference_names, "Reference reflection monitor")

    reuse_run_id = selected_reuse_run_id(panel)
    if reuse_run_id and reuse_run_id not in panel._reuse_candidates:
        _set_invalid(panel.reuse_reference, True)
        _log_error(
            panel.store,
            f"Selected cached reference run '{reuse_run_id}' is unavailable or incompatible.",
            panel,
        )
        ok = False
    else:
        _set_invalid(panel.reuse_reference, False)
    return ok
