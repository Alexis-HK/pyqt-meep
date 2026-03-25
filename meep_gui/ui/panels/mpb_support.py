from __future__ import annotations

from ...model import AnalysisConfig, KPoint, MpbModeSolverConfig
from ...validation import validate_numeric_expression
from ..common import _log_error, _set_invalid
from ..scope import parameter_names


def replace_cfg(panel, cfg: MpbModeSolverConfig) -> None:
    analysis = panel.store.state.analysis
    panel.store.state.analysis = AnalysisConfig(
        kind=analysis.kind,
        field_animation=analysis.field_animation,
        harminv=analysis.harminv,
        transmission_spectrum=analysis.transmission_spectrum,
        frequency_domain_solver=analysis.frequency_domain_solver,
        meep_k_points=analysis.meep_k_points,
        mpb_modesolver=cfg,
    )
    panel.store.notify()


def cfg_with_updates(panel, *, kpoints=None, field_kpoints=None, run_tm=None, run_te=None):
    current = panel.store.state.analysis.mpb_modesolver
    return MpbModeSolverConfig(
        lattice_x=current.lattice_x,
        lattice_y=current.lattice_y,
        basis1_x=current.basis1_x,
        basis1_y=current.basis1_y,
        basis2_x=current.basis2_x,
        basis2_y=current.basis2_y,
        num_bands=current.num_bands,
        resolution=current.resolution,
        unit_cells=current.unit_cells,
        kpoint_interp=current.kpoint_interp,
        max_mode_images=current.max_mode_images,
        run_tm=current.run_tm if run_tm is None else run_tm,
        run_te=current.run_te if run_te is None else run_te,
        kpoints=list(current.kpoints if kpoints is None else kpoints),
        field_kpoints=list(current.field_kpoints if field_kpoints is None else field_kpoints),
    )


def validate_kpoint_widgets(panel, widgets: tuple[tuple[object, str], ...]) -> bool:
    allowed = parameter_names(panel.store)
    ok = True
    for widget, label in widgets:
        result = validate_numeric_expression(widget.text().strip(), allowed)
        _set_invalid(widget, not result.ok)
        if not result.ok:
            _log_error(panel.store, f"{label}: {result.message}", panel)
            ok = False
    return ok


def load_config(panel, cfg: MpbModeSolverConfig) -> None:
    panel._ready = False
    panel.lattice_x.setText(cfg.lattice_x)
    panel.lattice_y.setText(cfg.lattice_y)
    panel.basis1_x.setText(cfg.basis1_x)
    panel.basis1_y.setText(cfg.basis1_y)
    panel.basis2_x.setText(cfg.basis2_x)
    panel.basis2_y.setText(cfg.basis2_y)
    panel.num_bands.setText(cfg.num_bands)
    panel.resolution.setText(cfg.resolution)
    panel.unit_cells.setText(cfg.unit_cells)
    panel.kpoint_interp.setText(cfg.kpoint_interp)
    panel.max_mode_images.setText(cfg.max_mode_images)
    panel.run_tm.setChecked(cfg.run_tm)
    panel.run_te.setChecked(cfg.run_te)
    panel.k_table.setRowCount(0)
    for kp in cfg.kpoints:
        row = panel.k_table.rowCount()
        panel.k_table.insertRow(row)
        panel.k_table.setItem(row, 0, panel._item(kp.kx))
        panel.k_table.setItem(row, 1, panel._item(kp.ky))
    panel.field_k_table.setRowCount(0)
    for kp in cfg.field_kpoints:
        row = panel.field_k_table.rowCount()
        panel.field_k_table.insertRow(row)
        panel.field_k_table.setItem(row, 0, panel._item(kp.kx))
        panel.field_k_table.setItem(row, 1, panel._item(kp.ky))
    panel._ready = True


def validate_panel(panel) -> bool:
    allowed = parameter_names(panel.store)
    fields = [
        (panel.lattice_x, "Lattice X"),
        (panel.lattice_y, "Lattice Y"),
        (panel.basis1_x, "Basis1 X"),
        (panel.basis1_y, "Basis1 Y"),
        (panel.basis2_x, "Basis2 X"),
        (panel.basis2_y, "Basis2 Y"),
        (panel.num_bands, "Num Bands"),
        (panel.resolution, "Resolution"),
        (panel.unit_cells, "Unit Cells"),
        (panel.kpoint_interp, "K-Point Interp"),
        (panel.max_mode_images, "Max Mode Images"),
    ]
    ok = True
    for widget, label in fields:
        result = validate_numeric_expression(widget.text().strip(), allowed)
        _set_invalid(widget, not result.ok)
        if not result.ok:
            _log_error(panel.store, f"{label}: {result.message}", panel)
            ok = False
    if not panel.run_tm.isChecked() and not panel.run_te.isChecked():
        _log_error(panel.store, "Select at least one polarization (TM and/or TE).", panel)
        ok = False
    return ok


def build_kpoint(x_widget, y_widget) -> KPoint:
    return KPoint(kx=x_widget.text().strip(), ky=y_widget.text().strip())
