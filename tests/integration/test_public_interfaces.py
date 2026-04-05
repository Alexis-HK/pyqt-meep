from __future__ import annotations

import importlib
import importlib.util

import pytest


def test_supported_headless_public_modules_import_and_expose_expected_names() -> None:
    import meep_gui
    from meep_gui import analysis, model, persistence, scene, script, validation
    from meep_gui.analysis import recipes

    assert callable(meep_gui.main)
    assert hasattr(model, "ProjectState")
    assert callable(analysis.run_by_kind)
    assert callable(analysis.prepare_runtime_analysis)
    assert callable(script.generate_script)
    assert callable(persistence.state_from_dict)
    assert callable(scene.compile_project_scene)
    assert callable(recipes.get_recipe)
    assert callable(validation.evaluate_parameters)


@pytest.mark.skipif(importlib.util.find_spec("PyQt5") is None, reason="PyQt5 not installed")
def test_supported_gui_public_modules_import_and_expose_expected_names() -> None:
    from meep_gui import ui
    from meep_gui.app import main as app_main
    from meep_gui.ui.windows import DomainWindow, LogWindow, OutputWindow, WorkflowWindow

    assert callable(app_main)
    assert ui.WorkflowWindow is WorkflowWindow
    assert ui.OutputWindow is OutputWindow
    assert ui.LogWindow is LogWindow
    assert ui.DomainWindow is DomainWindow


@pytest.mark.parametrize(
    "module_name",
    [
        "meep_gui.analysis_runner",
        "meep_gui.serialization",
        "meep_gui.script_gen",
        "meep_gui.ui_windows",
    ],
)
def test_legacy_v1_modules_are_not_recreated(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
