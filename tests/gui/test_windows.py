from __future__ import annotations

import time

import pytest

PyQt5 = pytest.importorskip("PyQt5")
pytest.importorskip("pytestqt")
from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore

from meep_gui.analysis import RunResult
from meep_gui.model import (
    AnalysisConfig,
    FrequencyDomainSolverConfig,
    FluxMonitorConfig,
    KPoint,
    MeepKPointsConfig,
    MpbModeSolverConfig,
    Parameter,
    PlotRecord,
    ResultArtifact,
    RunRecord,
    SourceItem,
    SymmetryItem,
    SweepConfig,
    SweepParameter,
    TransmissionDomainState,
    TransmissionSpectrumConfig,
)
from meep_gui.script import generate_script
from meep_gui.store import ProjectStore
from meep_gui.ui.panels.field_animation import FieldAnimationPanel
from meep_gui.ui.dialogs.symmetry import SymmetryEditDialog
from meep_gui.ui.panels.frequency_domain import FrequencyDomainPanel
from meep_gui.ui.panels.harminv import HarminvPanel
from meep_gui.ui.panels.meep_k_points import MeepKPointsPanel
from meep_gui.ui.panels.mpb import MpbPanel
from meep_gui.ui.panels.transmission import TransmissionSpectrumPanel
from meep_gui.ui.tabs.analysis import AnalysisTab
import meep_gui.ui.tabs.analysis as analysis_tab_module
from meep_gui.ui.tabs.domain import DomainTab
import meep_gui.ui.tabs.domain as domain_tab_module
from meep_gui.ui.tabs.flux_monitors import FluxMonitorsTab
from meep_gui.ui.tabs.parameters import ParametersTab
from meep_gui.ui.tabs.sweep import SweepTab
from meep_gui.ui.windows import OutputWindow


def test_analysis_tab_run_and_result_record(qtbot, monkeypatch) -> None:
    store = ProjectStore()

    def _fake_runner(state, log, cancel):
        time.sleep(0.05)
        return RunResult(
            status="completed",
            message="ok",
            artifacts=[ResultArtifact(kind="text", label="x", path="")],
        )

    monkeypatch.setattr(analysis_tab_module, "default_run_by_kind", _fake_runner)
    tab = AnalysisTab(store)
    qtbot.addWidget(tab)

    qtbot.mouseClick(tab.run_button, QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: len(store.state.results) == 1, timeout=3000)
    assert store.state.results[0].status == "completed"


def test_output_window_export_all_copies_multiple_artifacts_to_folder(qtbot, monkeypatch, tmp_path) -> None:
    store = ProjectStore()
    source_a = tmp_path / "a.csv"
    source_a.write_text("x,y\n1,2\n", encoding="utf-8")
    source_b = tmp_path / "b.png"
    image = QtGui.QImage(16, 16, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor("#ffffff"))
    assert image.save(str(source_b), "PNG")

    store.state.results.append(
        RunRecord(
            run_id="r1",
            analysis_kind="transmission_spectrum",
            status="completed",
            created_at="2026-02-06T10:00:00",
            message="done",
            artifacts=[
                ResultArtifact(kind="transmission_csv", label="a.csv", path=str(source_a)),
                ResultArtifact(kind="plot_png", label="b.png", path=str(source_b)),
            ],
        )
    )

    export_parent = tmp_path / "exports"
    export_parent.mkdir()
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(export_parent),
    )

    win = OutputWindow(store)
    qtbot.addWidget(win)
    store.result_changed.emit()

    qtbot.waitUntil(lambda: win.run_list.count() == 1, timeout=3000)
    qtbot.waitUntil(lambda: win.artifact_list.count() == 2, timeout=3000)
    assert win.export_all_button.isEnabled()

    qtbot.mouseClick(win.export_all_button, QtCore.Qt.LeftButton)

    created_dirs = [path for path in export_parent.iterdir() if path.is_dir()]
    assert len(created_dirs) == 1
    assert created_dirs[0].name == "transmission_spectrum [completed] 2026-02-06T10-00-00"
    exported_names = {path.name for path in created_dirs[0].iterdir()}
    assert "a.csv" in exported_names
    assert "b.png" in exported_names


def test_output_window_export_all_runs_button_requires_completed_runs(qtbot) -> None:
    store = ProjectStore()
    win = OutputWindow(store)
    qtbot.addWidget(win)

    assert not win.export_all_runs_button.isEnabled()

    store.state.results.append(
        RunRecord(
            run_id="failed1",
            analysis_kind="harminv",
            status="failed",
            created_at="2026-02-06T10:00:00",
            message="failed",
        )
    )
    store.state.results.append(
        RunRecord(
            run_id="canceled1",
            analysis_kind="harminv",
            status="canceled",
            created_at="2026-02-06T10:01:00",
            message="canceled",
        )
    )
    store.result_changed.emit()

    qtbot.waitUntil(lambda: win.run_list.count() == 2, timeout=3000)
    assert not win.export_all_runs_button.isEnabled()

    store.state.results.append(
        RunRecord(
            run_id="completed1",
            analysis_kind="harminv",
            status="completed",
            created_at="2026-02-06T10:02:00",
            message="done",
        )
    )
    store.result_changed.emit()

    qtbot.waitUntil(lambda: win.run_list.count() == 3, timeout=3000)
    qtbot.waitUntil(lambda: win.export_all_runs_button.isEnabled(), timeout=3000)


def test_output_window_export_all_runs_exports_completed_run_bundle(
    qtbot, monkeypatch, tmp_path
) -> None:
    store = ProjectStore()
    source_csv = tmp_path / "bundle.csv"
    source_csv.write_text("x,y\n1,2\n", encoding="utf-8")
    missing_png = tmp_path / "missing.png"

    store.state.results.extend(
        [
            RunRecord(
                run_id="r1",
                analysis_kind="transmission_spectrum",
                status="completed",
                created_at="2026-02-06T10:00:00",
                message="done",
                artifacts=[
                    ResultArtifact(kind="transmission_csv", label="bundle.csv", path=str(source_csv)),
                    ResultArtifact(
                        kind="text",
                        label="notes",
                        path="",
                        meta={"lines": "line one\nline two"},
                    ),
                ],
            ),
            RunRecord(
                run_id="r2",
                analysis_kind="harminv",
                status="completed",
                created_at="2026-02-06T10:01:00",
                message="done",
                meta={"sweep_label": "a=2"},
                artifacts=[
                    ResultArtifact(kind="plot_png", label="missing.png", path=str(missing_png)),
                ],
            ),
            RunRecord(
                run_id="r3",
                analysis_kind="frequency_domain_solver",
                status="failed",
                created_at="2026-02-06T10:02:00",
                message="failed",
                artifacts=[
                    ResultArtifact(kind="frequency_domain_field_csv", label="ignored.csv", path=str(source_csv)),
                ],
            ),
            RunRecord(
                run_id="r4",
                analysis_kind="meep_k_points",
                status="canceled",
                created_at="2026-02-06T10:03:00",
                message="canceled",
                artifacts=[
                    ResultArtifact(kind="text", label="ignored", path="", meta={"lines": "skip me"}),
                ],
            ),
        ]
    )

    export_parent = tmp_path / "exports"
    export_parent.mkdir()
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(export_parent),
    )

    win = OutputWindow(store)
    qtbot.addWidget(win)
    store.result_changed.emit()

    qtbot.waitUntil(lambda: win.run_list.count() == 4, timeout=3000)
    qtbot.waitUntil(lambda: win.export_all_runs_button.isEnabled(), timeout=3000)

    qtbot.mouseClick(win.export_all_runs_button, QtCore.Qt.LeftButton)

    bundle_dir = export_parent / "all_runs"
    assert bundle_dir.is_dir()

    run_dirs = {path.name: path for path in bundle_dir.iterdir() if path.is_dir()}
    assert set(run_dirs) == {
        "transmission_spectrum [completed] 2026-02-06T10-00-00",
        "a=2 - harminv [completed] 2026-02-06T10-01-00",
    }

    exported_names = {
        path.name
        for path in run_dirs["transmission_spectrum [completed] 2026-02-06T10-00-00"].iterdir()
    }
    assert exported_names == {"bundle.csv", "notes.txt"}
    assert (
        run_dirs["transmission_spectrum [completed] 2026-02-06T10-00-00"] / "notes.txt"
    ).read_text(encoding="utf-8") == ("line one\nline two\n")
    assert list(run_dirs["a=2 - harminv [completed] 2026-02-06T10-01-00"].iterdir()) == []

    assert any(
        "Exported 2 completed runs (2 artifacts)" in message
        and "1 artifacts were skipped or missing" in message
        for message in store.log_history
    )


def test_output_window_export_all_runs_uses_unique_bundle_name_on_collision(
    qtbot, monkeypatch, tmp_path
) -> None:
    store = ProjectStore()
    store.state.results.append(
        RunRecord(
            run_id="r1",
            analysis_kind="harminv",
            status="completed",
            created_at="2026-02-06T10:00:00",
            message="done",
            artifacts=[
                ResultArtifact(kind="text", label="summary", path="", meta={"lines": "hello"}),
            ],
        )
    )

    export_parent = tmp_path / "exports"
    export_parent.mkdir()
    (export_parent / "all_runs").mkdir()
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(export_parent),
    )

    win = OutputWindow(store)
    qtbot.addWidget(win)
    store.result_changed.emit()

    qtbot.waitUntil(lambda: win.export_all_runs_button.isEnabled(), timeout=3000)
    qtbot.mouseClick(win.export_all_runs_button, QtCore.Qt.LeftButton)

    created_bundle = export_parent / "all_runs_2"
    assert created_bundle.is_dir()
    run_dirs = [path for path in created_bundle.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    assert run_dirs[0].name == "harminv [completed] 2026-02-06T10-00-00"
    assert (run_dirs[0] / "summary.txt").read_text(encoding="utf-8") == "hello\n"


def test_output_window_clears_preview_after_last_run_removed(qtbot) -> None:
    store = ProjectStore()
    store.state.results.append(
        RunRecord(
            run_id="r1",
            analysis_kind="harminv",
            status="completed",
            created_at="2026-02-06T10:00:00",
            message="done",
            artifacts=[
                ResultArtifact(
                    kind="harminv_text",
                    label="harminv.txt",
                    path="",
                    meta={"lines": "harminv: freq=0.2"},
                )
            ],
        )
    )

    win = OutputWindow(store)
    qtbot.addWidget(win)
    store.result_changed.emit()

    preview = win.browser.preview
    qtbot.waitUntil(lambda: win.run_list.count() == 1, timeout=3000)
    qtbot.waitUntil(lambda: "harminv:" in preview.text_preview.toPlainText(), timeout=3000)

    qtbot.mouseClick(win.remove_run_button, QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: win.run_list.count() == 0, timeout=3000)

    assert preview.text_preview.toPlainText() == ""
    assert preview.image_label.text() == "No preview"


def test_output_window_shows_plot_files_in_results_artifact_list(qtbot, tmp_path) -> None:
    store = ProjectStore()
    csv_path = tmp_path / "tx_spectrum.csv"
    csv_path.write_text("frequency,T\n0.62,0.9\n", encoding="utf-8")
    png_path = tmp_path / "tx_spectrum.png"
    image = QtGui.QImage(16, 16, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor("#ffffff"))
    assert image.save(str(png_path), "PNG")

    store.state.results.append(
        RunRecord(
            run_id="tx1",
            analysis_kind="transmission_spectrum",
            status="completed",
            created_at="2026-02-09T12:00:00",
            message="done",
            plots=[
                PlotRecord(
                    title="Transmission Spectrum",
                    x_label="Frequency",
                    y_label="Normalized Response",
                    csv_path=str(csv_path),
                    png_path=str(png_path),
                )
            ],
        )
    )

    win = OutputWindow(store)
    qtbot.addWidget(win)
    store.result_changed.emit()

    qtbot.waitUntil(lambda: win.run_list.count() == 1, timeout=3000)
    qtbot.waitUntil(lambda: win.artifact_list.count() == 2, timeout=3000)

    labels = [win.artifact_list.item(i).text() for i in range(win.artifact_list.count())]
    assert "Transmission Spectrum (PNG)" in labels
    assert "Transmission Spectrum (CSV)" in labels

    png_row = next(i for i, text in enumerate(labels) if text == "Transmission Spectrum (PNG)")
    win.artifact_list.setCurrentRow(png_row)
    qtbot.waitUntil(lambda: win.browser.preview.preview_stack.currentIndex() == 1, timeout=3000)
    assert win.export_artifact_button.isEnabled()


def test_sweep_tab_removes_limit_controls_and_uses_step_size_label(qtbot) -> None:
    store = ProjectStore()
    store.state.parameters = [Parameter(name="a", expr="1")]

    tab = SweepTab(store)
    qtbot.addWidget(tab)

    assert tab.param_name.isEditable() is False
    assert tab.table.horizontalHeaderItem(3).text() == "Step Size"

    checkbox_texts = {box.text() for box in tab.findChildren(QtWidgets.QCheckBox)}
    assert "Enable sweep" in checkbox_texts
    assert "Allow points above max" not in checkbox_texts

    label_texts = {label.text() for label in tab.findChildren(QtWidgets.QLabel)}
    assert "Step Size" in label_texts
    assert "Max Points" not in label_texts


def test_analysis_tab_publishes_sweep_results_incrementally_to_output_window(qtbot, monkeypatch) -> None:
    store = ProjectStore()
    store.state.parameters = [Parameter(name="a", expr="1")]
    store.state.sweep = SweepConfig(
        enabled=True,
        params=[SweepParameter(name="a", start="1", stop="2", steps="1")],
    )
    store.state.analysis = AnalysisConfig(kind="field_animation")

    publish_count = {"count": 0}

    def _fake_runner(state, log, cancel, publish_result=None):
        assert publish_result is not None
        publish_result(
            RunResult(
                status="completed",
                message="point one",
                artifacts=[ResultArtifact(kind="text", label="a=1 | first.txt", path="")],
                meta={"sweep_label": "a=1"},
            )
        )
        publish_count["count"] += 1
        time.sleep(0.05)
        publish_result(
            RunResult(
                status="completed",
                message="point two",
                artifacts=[ResultArtifact(kind="text", label="a=2 | second.txt", path="")],
                meta={"sweep_label": "a=2"},
            )
        )
        publish_count["count"] += 1
        return RunResult(status="completed", message="Sweep completed.", meta={"skip_store": "1"})

    monkeypatch.setattr(analysis_tab_module, "default_run_by_kind", _fake_runner)

    tab = AnalysisTab(store)
    win = OutputWindow(store)
    qtbot.addWidget(tab)
    qtbot.addWidget(win)

    qtbot.mouseClick(tab.run_button, QtCore.Qt.LeftButton)

    qtbot.waitUntil(lambda: len(store.state.results) == 1, timeout=3000)
    qtbot.waitUntil(lambda: win.run_list.count() == 1, timeout=3000)
    assert win.run_list.currentRow() == 0

    qtbot.waitUntil(lambda: len(store.state.results) == 2, timeout=3000)
    qtbot.waitUntil(lambda: win.run_list.count() == 2, timeout=3000)
    qtbot.waitUntil(lambda: win.run_list.currentRow() == 1, timeout=3000)

    assert publish_count["count"] == 2
    assert store.state.results[0].analysis_kind == "field_animation"
    assert store.state.results[1].meta["sweep_label"] == "a=2"
    assert win.run_list.item(1).text().startswith("a=2 | field_animation [completed]")
    assert win.artifact_list.item(0).text() == "text: a=2 | second.txt"


def test_output_window_auto_follows_latest_sweep_run_while_active(qtbot) -> None:
    store = ProjectStore()
    win = OutputWindow(store)
    qtbot.addWidget(win)

    store.state.results.append(
        RunRecord(
            run_id="r1",
            analysis_kind="harminv",
            status="completed",
            created_at="2026-02-09T12:00:00",
            message="done",
            meta={"sweep_label": "a=1"},
        )
    )
    store.run_manager._state = "running"
    store.result_changed.emit()
    qtbot.waitUntil(lambda: win.run_list.currentRow() == 0, timeout=3000)

    store.state.results.append(
        RunRecord(
            run_id="r2",
            analysis_kind="harminv",
            status="completed",
            created_at="2026-02-09T12:01:00",
            message="done",
            meta={"sweep_label": "a=2"},
        )
    )
    store.result_changed.emit()

    qtbot.waitUntil(lambda: win.run_list.currentRow() == 1, timeout=3000)
    assert win.run_list.item(1).text().startswith("a=2 | harminv [completed]")
    store.run_manager._state = "idle"


def test_domain_tab_routes_updates_to_reference_domain(qtbot) -> None:
    store = ProjectStore()
    tx_cfg = TransmissionSpectrumConfig(preview_domain="reference")
    store.state.analysis = AnalysisConfig(kind="transmission_spectrum", transmission_spectrum=tx_cfg)

    tab = DomainTab(store)
    qtbot.addWidget(tab)
    tab.cell_x.setText("22")
    tab.cell_y.setText("9")
    tab.resolution.setText("30")
    tab.pml_width.setText("2")
    tab._on_apply()

    assert store.state.analysis.transmission_spectrum.reference_state.domain.cell_x == "22"
    assert store.state.domain.cell_x == "10"


def test_symmetry_dialog_accepts_complex_literal_and_rejects_non_literal(qtbot, monkeypatch) -> None:
    store = ProjectStore()
    dialog = SymmetryEditDialog(
        store,
        SymmetryItem(name="", kind="mirror", direction="x", phase="1"),
        set(),
    )
    qtbot.addWidget(dialog)
    dialog.name_input.setText("mx")
    dialog.phase_input.setText("1-1j")
    dialog._on_save()

    assert dialog.result is not None
    assert dialog.result.phase == "1-1j"

    warning_calls: list[tuple[str, str]] = []

    def _warn(_parent, title: str, msg: str) -> None:
        warning_calls.append((title, msg))

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", _warn)
    bad_dialog = SymmetryEditDialog(
        store,
        SymmetryItem(name="", kind="mirror", direction="x", phase="1"),
        set(),
    )
    qtbot.addWidget(bad_dialog)
    bad_dialog.name_input.setText("my")
    bad_dialog.phase_input.setText("a*1j")
    bad_dialog._on_save()

    assert bad_dialog.result is None
    assert warning_calls
    assert "complex literal" in warning_calls[-1][1]


def test_domain_tab_add_update_remove_symmetry_uses_literal_phase(qtbot, monkeypatch) -> None:
    store = ProjectStore()
    tab = DomainTab(store)
    qtbot.addWidget(tab)
    tab.symmetry_enabled.setChecked(True)

    class _AddDialog:
        def __init__(self, *_args, **_kwargs) -> None:
            self.result = SymmetryItem(name="mx", kind="mirror", direction="x", phase="1-1j")

        def exec_(self) -> int:
            return QtWidgets.QDialog.Accepted

    class _UpdateDialog:
        def __init__(self, *_args, **_kwargs) -> None:
            self.result = SymmetryItem(name="mx", kind="mirror", direction="x", phase="9j")

        def exec_(self) -> int:
            return QtWidgets.QDialog.Accepted

    monkeypatch.setattr(domain_tab_module, "SymmetryEditDialog", _AddDialog)
    qtbot.mouseClick(tab.add_symmetry, QtCore.Qt.LeftButton)
    assert len(store.state.domain.symmetries) == 1
    assert store.state.domain.symmetries[0].phase == "1-1j"

    tab.symmetry_table.setCurrentCell(0, 0)
    monkeypatch.setattr(domain_tab_module, "SymmetryEditDialog", _UpdateDialog)
    qtbot.mouseClick(tab.update_symmetry, QtCore.Qt.LeftButton)
    assert store.state.domain.symmetries[0].phase == "9j"

    qtbot.mouseClick(tab.remove_symmetry, QtCore.Qt.LeftButton)
    assert store.state.domain.symmetries == []


def test_frequency_domain_panel_updates_config(qtbot) -> None:
    store = ProjectStore()
    panel = FrequencyDomainPanel(store)
    qtbot.addWidget(panel)
    panel.load_from_config(store.state.analysis.frequency_domain_solver)

    panel.component.setCurrentText("Hz")
    panel.tolerance.setText("1e-9")
    panel.max_iters.setText("2048")
    panel.bicgstab_l.setText("12")

    assert panel.apply() is True
    cfg = store.state.analysis.frequency_domain_solver
    assert cfg.component == "Hz"
    assert cfg.tolerance == "1e-9"
    assert cfg.max_iters == "2048"
    assert cfg.bicgstab_l == "12"


def test_flux_monitor_tab_routes_adds_to_reference_domain(qtbot) -> None:
    store = ProjectStore()
    tx_cfg = TransmissionSpectrumConfig(preview_domain="reference")
    store.state.analysis = AnalysisConfig(kind="transmission_spectrum", transmission_spectrum=tx_cfg)

    tab = FluxMonitorsTab(store)
    qtbot.addWidget(tab)
    tab.name_input.setText("ref_flux")
    tab.center_x.setText("0")
    tab.center_y.setText("0")
    tab.size_x.setText("1")
    tab.size_y.setText("0")
    tab.fcen.setText("0.15")
    tab.df.setText("0.1")
    tab.nfreq.setText("32")

    qtbot.mouseClick(tab.add_button, QtCore.Qt.LeftButton)
    qtbot.waitUntil(
        lambda: len(store.state.analysis.transmission_spectrum.reference_state.flux_monitors) == 1,
        timeout=3000,
    )

    assert store.state.analysis.transmission_spectrum.reference_state.flux_monitors[0].name == "ref_flux"
    assert store.state.flux_monitors == []


def test_mpb_panel_updates_polarization_and_field_kpoints(qtbot) -> None:
    store = ProjectStore()
    panel = MpbPanel(store)
    qtbot.addWidget(panel)
    panel.load_from_config(store.state.analysis.mpb_modesolver)

    panel.run_te.setChecked(True)
    panel.run_tm.setChecked(False)
    panel.field_kx.setText("0.2")
    panel.field_ky.setText("0.1")
    qtbot.mouseClick(panel.add_field_k, QtCore.Qt.LeftButton)

    cfg = store.state.analysis.mpb_modesolver
    assert cfg.run_te is True
    assert cfg.run_tm is False
    assert len(cfg.field_kpoints) == 1
    assert cfg.field_kpoints[0] == KPoint(kx="0.2", ky="0.1")
    assert not hasattr(panel, "force_all_modes")
    checkbox_texts = {box.text() for box in panel.findChildren(QtWidgets.QCheckBox)}
    assert "Force all mode images" not in checkbox_texts


def test_meep_k_points_panel_updates_config_and_points(qtbot) -> None:
    store = ProjectStore()
    panel = MeepKPointsPanel(store)
    qtbot.addWidget(panel)
    panel.load_from_config(store.state.analysis.meep_k_points)

    panel.kpoint_interp.setText("7")
    panel.run_time.setText("450")
    panel.kx.setText("0")
    panel.ky.setText("0")
    qtbot.mouseClick(panel.add_k, QtCore.Qt.LeftButton)
    panel.kx.setText("0.5")
    panel.ky.setText("0")
    qtbot.mouseClick(panel.add_k, QtCore.Qt.LeftButton)

    assert panel.apply() is True
    cfg = store.state.analysis.meep_k_points
    assert cfg.kpoint_interp == "7"
    assert cfg.run_time == "450"
    assert cfg.kpoints == [KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]


def test_output_window_lists_only_non_field_mpb_artifacts_when_no_field_kpoints(qtbot, tmp_path) -> None:
    store = ProjectStore()
    csv_path = tmp_path / "mpb_bands.csv"
    csv_path.write_text("polarization,k_index,kx,ky,band,frequency\nTM,0,0,0,1,0.2\n", encoding="utf-8")
    band_png = tmp_path / "mpb_bands.png"
    eps_png = tmp_path / "mpb_epsilon.png"
    image = QtGui.QImage(16, 16, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor("#ffffff"))
    assert image.save(str(band_png), "PNG")
    assert image.save(str(eps_png), "PNG")

    store.state.results.append(
        RunRecord(
            run_id="mpb1",
            analysis_kind="mpb_modesolver",
            status="completed",
            created_at="2026-02-10T12:00:00",
            message="done",
            artifacts=[
                ResultArtifact(kind="mpb_band_csv", label="Band CSV", path=str(csv_path)),
                ResultArtifact(kind="mpb_band_png", label="Band Plot", path=str(band_png)),
                ResultArtifact(kind="mpb_epsilon_png", label="Epsilon", path=str(eps_png)),
            ],
            meta={"field_kpoint_count": "0", "mode_images": "0"},
        )
    )

    win = OutputWindow(store)
    qtbot.addWidget(win)
    store.result_changed.emit()

    qtbot.waitUntil(lambda: win.run_list.count() == 1, timeout=3000)
    qtbot.waitUntil(lambda: win.artifact_list.count() == 3, timeout=3000)

    labels = [win.artifact_list.item(i).text() for i in range(win.artifact_list.count())]
    assert all("mpb_mode_png" not in text for text in labels)


def test_transmission_preview_switch_bootstraps_reference_monitors(qtbot, monkeypatch) -> None:
    store = ProjectStore()
    store.state.flux_monitors = [FluxMonitorConfig(name="dev_inc")]
    store.state.analysis = AnalysisConfig(
        kind="transmission_spectrum",
        transmission_spectrum=TransmissionSpectrumConfig(preview_domain="scattering"),
    )

    warning_calls: list[tuple[str, str]] = []

    def _warn(_parent, title: str, msg: str) -> None:
        warning_calls.append((title, msg))

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", _warn)
    panel = TransmissionSpectrumPanel(store)
    qtbot.addWidget(panel)
    panel.load_from_config(store.state.analysis.transmission_spectrum)

    panel.preview_domain.setCurrentText("reference")

    assert store.state.analysis.transmission_spectrum.preview_domain == "reference"
    assert len(store.state.analysis.transmission_spectrum.reference_state.flux_monitors) == 1
    assert store.state.analysis.transmission_spectrum.reference_state.flux_monitors[0].name == "dev_inc"
    assert panel.incident_monitor.findText("dev_inc") >= 0
    assert warning_calls == []


def test_transmission_panel_places_reference_reflection_before_reflection_monitor(qtbot) -> None:
    store = ProjectStore()
    panel = TransmissionSpectrumPanel(store)
    qtbot.addWidget(panel)

    form = panel.layout().itemAt(0).layout()
    assert isinstance(form, QtWidgets.QFormLayout)

    labels: list[str] = []
    for row in range(form.rowCount()):
        item = form.itemAt(row, QtWidgets.QFormLayout.LabelRole)
        if item is None or item.widget() is None:
            continue
        labels.append(item.widget().text())

    assert labels.index("Reference Reflection (optional)") < labels.index(
        "Reflection Monitor (optional)"
    )


def test_analysis_panels_omit_old_descriptive_prose(qtbot) -> None:
    store = ProjectStore()
    panels = [
        FieldAnimationPanel(store),
        HarminvPanel(store),
        FrequencyDomainPanel(store),
        MeepKPointsPanel(store),
        TransmissionSpectrumPanel(store),
    ]
    for panel in panels:
        qtbot.addWidget(panel)

    panel_texts = [
        {label.text() for label in panel.findChildren(QtWidgets.QLabel)}
        for panel in panels
    ]

    assert "Artifacts are exported from the Output window. Analysis output paths are auto-managed." not in panel_texts[0]
    assert "Artifacts are exported from the Output window. Analysis output paths are auto-managed." not in panel_texts[1]
    assert (
        "Runs Meep's steady-state frequency-domain solver and produces a single field PNG. "
        "Artifacts are exported from the Output window."
    ) not in panel_texts[2]
    assert (
        "Runs Meep's run_k_points(...) with Gaussian sources and produces one band plot PNG "
        "plus one CSV. The entered k-points are used only for interpolation input."
    ) not in panel_texts[3]
    assert (
        "Runs two simulations: reference and scattering domains with independent geometry, sources, "
        "and monitors. Artifacts are exported from the Output window."
    ) not in panel_texts[4]


def test_transmission_reuse_dropdown_filters_compatible_runs_and_updates_config(
    qtbot, tmp_path
) -> None:
    store = ProjectStore()
    store.state.analysis = AnalysisConfig(
        kind="transmission_spectrum",
        transmission_spectrum=TransmissionSpectrumConfig(
            incident_monitor="ref_inc",
            transmission_monitor="dev_tx",
            reference_state=TransmissionDomainState(
                flux_monitors=[FluxMonitorConfig(name="ref_inc", fcen="0.2", df="0.1", nfreq="50")]
            ),
        ),
    )
    store.state.flux_monitors = [FluxMonitorConfig(name="dev_tx", fcen="0.2", df="0.1", nfreq="50")]

    ok_csv = tmp_path / "ok.csv"
    ok_csv.write_text("frequency,incident\n0.62,2.0\n", encoding="utf-8")
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("frequency,incident\n0.62,2.0\n", encoding="utf-8")

    store.state.results.extend(
        [
            RunRecord(
                run_id="ok_run",
                analysis_kind="transmission_spectrum",
                status="completed",
                created_at="2026-02-10T09:00:00",
                artifacts=[ResultArtifact(kind="transmission_csv", label="ok.csv", path=str(ok_csv))],
                meta={
                    "incident_monitor": "old_ref",
                    "transmission_monitor": "old_tx",
                    "ref_incident_fcen": "0.2",
                    "ref_incident_df": "0.1",
                    "ref_incident_nfreq": "50",
                    "dev_trans_fcen": "0.2",
                    "dev_trans_df": "0.1",
                    "dev_trans_nfreq": "50",
                },
            ),
            RunRecord(
                run_id="bad_run",
                analysis_kind="transmission_spectrum",
                status="completed",
                created_at="2026-02-10T09:05:00",
                artifacts=[ResultArtifact(kind="transmission_csv", label="bad.csv", path=str(bad_csv))],
                meta={
                    "ref_incident_fcen": "0.2",
                    "ref_incident_df": "0.1",
                    "ref_incident_nfreq": "50",
                    "dev_trans_fcen": "0.2",
                    "dev_trans_df": "0.1",
                    "dev_trans_nfreq": "10",
                },
            ),
        ]
    )

    panel = TransmissionSpectrumPanel(store)
    qtbot.addWidget(panel)
    panel.load_from_config(store.state.analysis.transmission_spectrum)

    assert panel.reuse_reference.count() == 2
    ok_idx = panel.reuse_reference.findData("ok_run")
    assert ok_idx >= 0
    assert panel.reuse_reference.findData("bad_run") < 0

    panel.animate_reference.setChecked(True)
    panel.reuse_reference.setCurrentIndex(ok_idx)

    assert not panel.animate_reference.isChecked()
    assert not panel.animate_reference.isEnabled()
    cfg = store.state.analysis.transmission_spectrum
    assert cfg.reuse_reference_run_id == "ok_run"
    assert cfg.reuse_reference_csv_name == "ok.csv"


def test_analysis_tab_blocks_frequency_domain_run_with_gaussian_source(qtbot, monkeypatch) -> None:
    store = ProjectStore()
    store.state.sources = [
        SourceItem(
            name="pulse",
            kind="gaussian",
            component="Ez",
            props={"fcen": "0.2", "df": "0.1"},
        )
    ]
    store.state.analysis = AnalysisConfig(
        kind="frequency_domain_solver",
        frequency_domain_solver=FrequencyDomainSolverConfig(),
    )

    warning_calls: list[tuple[str, str]] = []
    run_calls: list[str] = []

    def _warn(_parent, title: str, msg: str) -> None:
        warning_calls.append((title, msg))

    def _fake_runner(state, log, cancel):
        run_calls.append("called")
        return RunResult(status="completed")

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", _warn)
    monkeypatch.setattr(analysis_tab_module, "default_run_by_kind", _fake_runner)

    tab = AnalysisTab(store)
    qtbot.addWidget(tab)
    tab.kind.setCurrentText("frequency_domain_solver")

    qtbot.mouseClick(tab.run_button, QtCore.Qt.LeftButton)

    assert run_calls == []
    assert warning_calls
    assert "continuous sources" in warning_calls[-1][1]
    assert store.state.results == []


def test_analysis_tab_blocks_meep_k_points_without_source(qtbot, monkeypatch) -> None:
    store = ProjectStore()
    store.state.analysis = AnalysisConfig(
        kind="meep_k_points",
        meep_k_points=MeepKPointsConfig(
            kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
        ),
    )

    warning_calls: list[tuple[str, str]] = []
    run_calls: list[str] = []

    def _warn(_parent, title: str, msg: str) -> None:
        warning_calls.append((title, msg))

    def _fake_runner(state, log, cancel):
        run_calls.append("called")
        return RunResult(status="completed")

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", _warn)
    monkeypatch.setattr(analysis_tab_module, "default_run_by_kind", _fake_runner)

    tab = AnalysisTab(store)
    qtbot.addWidget(tab)
    tab.kind.setCurrentText("meep_k_points")

    qtbot.mouseClick(tab.run_button, QtCore.Qt.LeftButton)

    assert run_calls == []
    assert warning_calls
    assert "at least one Gaussian" in warning_calls[-1][1]


def test_analysis_tab_blocks_meep_k_points_with_continuous_source(qtbot, monkeypatch) -> None:
    store = ProjectStore()
    store.state.sources = [
        SourceItem(name="cw", kind="continuous", component="Ez", props={"fcen": "0.2"})
    ]
    store.state.analysis = AnalysisConfig(
        kind="meep_k_points",
        meep_k_points=MeepKPointsConfig(
            kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
        ),
    )

    warning_calls: list[tuple[str, str]] = []

    def _warn(_parent, title: str, msg: str) -> None:
        warning_calls.append((title, msg))

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", _warn)

    tab = AnalysisTab(store)
    qtbot.addWidget(tab)
    tab.kind.setCurrentText("meep_k_points")

    qtbot.mouseClick(tab.run_button, QtCore.Qt.LeftButton)

    assert warning_calls
    assert "Continuous sources are not supported" in warning_calls[-1][1]


def test_analysis_tab_logs_capability_warnings_before_running_mpb(qtbot, monkeypatch) -> None:
    store = ProjectStore()
    store.state.domain.symmetry_enabled = True
    store.state.domain.symmetries = [
        SymmetryItem(name="mx", kind="mirror", direction="x", phase="-1")
    ]
    store.state.sources = [
        SourceItem(
            name="pulse",
            kind="gaussian",
            component="Ez",
            props={"fcen": "0.2", "df": "0.1"},
        )
    ]
    store.state.flux_monitors = [FluxMonitorConfig(name="tx")]
    store.state.analysis = AnalysisConfig(
        kind="mpb_modesolver",
        mpb_modesolver=MpbModeSolverConfig(run_tm=True, run_te=False),
    )

    def _fake_runner(state, log, cancel):
        return RunResult(status="completed", message="ok")

    monkeypatch.setattr(analysis_tab_module, "default_run_by_kind", _fake_runner)

    tab = AnalysisTab(store)
    qtbot.addWidget(tab)
    tab.kind.setCurrentText("mpb_modesolver")

    qtbot.mouseClick(tab.run_button, QtCore.Qt.LeftButton)

    qtbot.waitUntil(lambda: len(store.state.results) == 1, timeout=3000)
    assert any("ignored by this analysis" in message for message in store.log_history)
    assert store.state.results[0].status == "completed"


def test_frequency_domain_zero_source_run_records_png_and_csv_and_previews_image(
    qtbot, monkeypatch, tmp_path
) -> None:
    store = ProjectStore()
    store.state.analysis = AnalysisConfig(
        kind="frequency_domain_solver",
        frequency_domain_solver=FrequencyDomainSolverConfig(),
    )

    png_path = tmp_path / "frequency_domain_field.png"
    image = QtGui.QImage(16, 16, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor("#ffffff"))
    assert image.save(str(png_path), "PNG")
    csv_path = tmp_path / "frequency_domain_field.csv"
    csv_path.write_text("1,2\n3,4\n", encoding="utf-8")

    run_calls: list[str] = []

    def _fake_runner(state, log, cancel):
        run_calls.append(state.analysis.kind)
        return RunResult(
            status="completed",
            message="ok",
            artifacts=[
                ResultArtifact(
                    kind="frequency_domain_field_png",
                    label="frequency_domain_field.png",
                    path=str(png_path),
                ),
                ResultArtifact(
                    kind="frequency_domain_field_csv",
                    label="frequency_domain_field.csv",
                    path=str(csv_path),
                ),
            ],
        )

    monkeypatch.setattr(analysis_tab_module, "default_run_by_kind", _fake_runner)

    tab = AnalysisTab(store)
    qtbot.addWidget(tab)
    win = OutputWindow(store)
    qtbot.addWidget(win)
    tab.kind.setCurrentText("frequency_domain_solver")

    qtbot.mouseClick(tab.run_button, QtCore.Qt.LeftButton)

    qtbot.waitUntil(lambda: len(store.state.results) == 1, timeout=3000)
    qtbot.waitUntil(lambda: win.run_list.count() == 1, timeout=3000)
    qtbot.waitUntil(lambda: win.artifact_list.count() == 2, timeout=3000)
    qtbot.waitUntil(lambda: win.browser.preview.preview_stack.currentIndex() == 1, timeout=3000)

    assert run_calls == ["frequency_domain_solver"]
    assert win.browser.preview.image_label.pixmap() is not None


def test_meep_k_points_run_records_plot_png_and_csv(qtbot, monkeypatch, tmp_path) -> None:
    store = ProjectStore()
    store.state.sources = [
        SourceItem(
            name="pulse",
            kind="gaussian",
            component="Ez",
            props={"fcen": "0.2", "df": "0.1"},
        )
    ]
    store.state.analysis = AnalysisConfig(
        kind="meep_k_points",
        meep_k_points=MeepKPointsConfig(
            kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
        ),
    )

    png_path = tmp_path / "meep_k_points_bands.png"
    image = QtGui.QImage(16, 16, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor("#ffffff"))
    assert image.save(str(png_path), "PNG")
    csv_path = tmp_path / "meep_k_points_bands.csv"
    csv_path.write_text("k_index,kx,ky,mode,freq_real,freq_imag\n0,0,0,1,0.2,0.0\n", encoding="utf-8")

    def _fake_runner(state, log, cancel):
        return RunResult(
            status="completed",
            message="ok",
            plots=[
                PlotRecord(
                    title="Meep K-Points Bands",
                    x_label="k-index",
                    y_label="Frequency",
                    csv_path=str(csv_path),
                    png_path=str(png_path),
                )
            ],
        )

    monkeypatch.setattr(analysis_tab_module, "default_run_by_kind", _fake_runner)

    tab = AnalysisTab(store)
    qtbot.addWidget(tab)
    win = OutputWindow(store)
    qtbot.addWidget(win)
    tab.kind.setCurrentText("meep_k_points")

    qtbot.mouseClick(tab.run_button, QtCore.Qt.LeftButton)

    qtbot.waitUntil(lambda: len(store.state.results) == 1, timeout=3000)
    qtbot.waitUntil(lambda: win.run_list.count() == 1, timeout=3000)
    qtbot.waitUntil(lambda: win.artifact_list.count() == 2, timeout=3000)

    labels = [win.artifact_list.item(i).text() for i in range(win.artifact_list.count())]
    assert "Meep K-Points Bands (PNG)" in labels
    assert "Meep K-Points Bands (CSV)" in labels


def test_parameters_tab_import_overwrites_and_invalid_import_is_atomic(
    qtbot, monkeypatch, tmp_path
) -> None:
    store = ProjectStore()
    store.state.parameters = [Parameter(name="old_a", expr="1"), Parameter(name="old_b", expr="2")]
    good_path = tmp_path / "params.txt"
    good_path.write_text("a = 1\nb = a + sqrt(4)\n", encoding="utf-8")

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(good_path), "Text Files (*.txt)"),
    )

    tab = ParametersTab(store)
    qtbot.addWidget(tab)
    qtbot.mouseClick(tab.import_button, QtCore.Qt.LeftButton)

    assert [(p.name, p.expr) for p in store.state.parameters] == [("a", "1"), ("b", "a + sqrt(4)")]
    script = generate_script(store.state)
    assert "a = 1" in script
    assert "b = a + sqrt(4)" in script

    bad_path = tmp_path / "bad_params.txt"
    bad_path.write_text("good = 1\n\nbad = good + 1\n", encoding="utf-8")
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(bad_path), "Text Files (*.txt)"),
    )
    warning_calls: list[tuple[str, str]] = []

    def _warn(_parent, title: str, msg: str) -> None:
        warning_calls.append((title, msg))

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", _warn)
    qtbot.mouseClick(tab.import_button, QtCore.Qt.LeftButton)

    assert [(p.name, p.expr) for p in store.state.parameters] == [("a", "1"), ("b", "a + sqrt(4)")]
    assert warning_calls
    assert "Parameter import failed: Line 2: blank lines are not allowed." in warning_calls[-1][1]
