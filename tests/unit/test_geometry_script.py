from __future__ import annotations

import pytest

pytest.importorskip("shapely")

from meep_gui.analysis.mpb_support import build_mpb_geometry
from meep_gui.geometry_script import (
    MAX_IMPLICIT_DIMENSION,
    run_geometry_script,
    validate_geometry_script,
)
from meep_gui.model import GeometryItem, Material, Parameter, ProjectState
from meep_gui.persistence import state_from_dict, state_to_dict
from meep_gui.scene import compile_project_scene, scene_to_sim_params
from meep_gui.script import generate_script


def _run(source: str, *, params=None, materials=None):
    return run_geometry_script(
        source,
        parameter_values=params or {"pitch": 1.0, "r": 0.25, "n": 3.0, "wg_width": 1.0},
        material_names=materials or {"silicon", "air"},
        name_prefix="scripted",
    )


@pytest.mark.parametrize(
    "source",
    [
        "import os",
        "open('x')",
        "eval('1')",
        "exec('1')",
        "def f():\n    pass",
        "class X:\n    pass",
        "lambda x: x",
        "while True:\n    pass",
        "try:\n    x = 1\nexcept Exception:\n    pass",
        "with x:\n    pass",
        "global x",
        "params['pitch'] = 2",
        "materials['silicon'] = 'air'",
        "__import__('os')",
        "params.__class__",
        "holes = []\nholes.clear()",
    ],
)
def test_geometry_script_rejects_forbidden_ast(source: str) -> None:
    result = validate_geometry_script(
        source,
        parameter_values={},
        material_names={"silicon"},
    )

    assert not result.ok


def test_geometry_script_uses_read_only_params_and_materials() -> None:
    result = _run(
        """
pitch = params["pitch"]
g = rect(center=(0, 0), size=(pitch, params["wg_width"]))
emit(g, material=materials["silicon"])
"""
    )

    assert result.emitted_count == 1
    assert result.referenced_parameters == ("pitch", "wg_width")
    assert result.referenced_materials == ("silicon",)


def test_geometry_script_reports_missing_param_and_material() -> None:
    missing_param = validate_geometry_script(
        'g = rect(size=(params["missing"], 1))\nemit(g, material=materials["silicon"])',
        parameter_values={},
        material_names={"silicon"},
    )
    missing_material = validate_geometry_script(
        'g = rect(size=(1, 1))\nemit(g, material=materials["missing"])',
        parameter_values={},
        material_names={"silicon"},
    )

    assert "Unknown parameter: missing" in missing_param.errors[0]
    assert "Unknown material: missing" in missing_material.errors[0]


def test_geometry_script_constructive_api_and_transforms() -> None:
    result = _run(
        """
base = rect(center=(0, 0), size=(2, 1))
hole = circle(center=(0, 0), radius=0.2, segments=16)
wg = difference(base, hole)
wg = move(rotate(scale(wg, sx=1, sy=1), angle=90), dx=1, dy=0)
wg = mirror_y(mirror_x(wg, x=0), y=0)
wg = simplify(clean(wg), 0.001)
emit(wg, material=materials["silicon"])
emit(union(ellipse(center=(0, 0), radius=(0.2, 0.1)), polygon(points=[(0, 0), (1, 0), (0, 1)])), material=materials["air"], priority=10)
"""
    )

    assert result.emitted_count >= 2
    assert result.vertex_count > 0
    assert result.polygons[-1].priority == 10


def test_geometry_script_path_and_append_loop_work() -> None:
    result = _run(
        """
pts = []
for i in range(5):
    pts.append((i, sin(i)))
g = path(points=pts, width=0.2)
emit(g, material=materials["silicon"])
"""
    )

    assert result.emitted_count == 1
    assert result.vertex_count > 3


def test_geometry_script_region_disk_and_sinusoidal_boundary() -> None:
    disk = _run(
        'g = region("x*x + y*y < r*r", bounds=(-2, -2, 2, 2), resolution=300)\n'
        'emit(g, material=materials["silicon"])',
        params={"r": 0.5},
        materials={"silicon"},
    )
    sinusoid = _run(
        'g = region("sin(2*pi*x/period) > y", bounds=(-1, -1, 1, 1), resolution=(40, 20))\n'
        'emit(g, material=materials["silicon"])',
        params={"period": 1.0},
        materials={"silicon"},
    )

    assert disk.emitted_count == 1
    assert disk.vertex_count > 0
    assert sinusoid.emitted_count >= 1


def test_geometry_script_region_limits_and_invalid_expression() -> None:
    too_large = validate_geometry_script(
        f'g = region("x < y", bounds=(0, 0, 1, 1), resolution={MAX_IMPLICIT_DIMENSION + 1})\n'
        'emit(g, material=materials["silicon"])',
        parameter_values={},
        material_names={"silicon"},
    )
    invalid = validate_geometry_script(
        'g = region("x + y", bounds=(0, 0, 1, 1), resolution=8)\n'
        'emit(g, material=materials["silicon"])',
        parameter_values={},
        material_names={"silicon"},
    )
    material_ref = validate_geometry_script(
        'g = region("materials[\\"silicon\\"] == materials[\\"silicon\\"]", bounds=(0, 0, 1, 1), resolution=8)\n'
        'emit(g, material=materials["silicon"])',
        parameter_values={},
        material_names={"silicon"},
    )

    assert "resolution dimension limit exceeded" in too_large.errors[0]
    assert "must evaluate to a boolean" in invalid.errors[0]
    assert "materials[...] is not allowed" in material_ref.errors[0]


def test_scripted_geometry_participates_in_scene_runtime_persistence_and_export() -> None:
    class _FakeMP:
        inf = "inf"

        @staticmethod
        def Medium(index=1):
            return ("Medium", index)

        @staticmethod
        def Vector3(x=0.0, y=0.0, z=0.0):
            return (x, y, z)

        @staticmethod
        def Prism(**kwargs):
            return {"kind": "Prism", **kwargs}

    state = ProjectState(
        parameters=[Parameter(name="r", expr="0.5")],
        materials=[Material(name="silicon", index_expr="3.4")],
        geometries=[
            GeometryItem(
                name="disk",
                kind="scripted",
                material="",
                props={
                    "source": (
                        'g = region("x*x + y*y < r*r", bounds=(-1, -1, 1, 1), resolution=24)\n'
                        'emit(g, material=materials["silicon"])'
                    )
                },
            )
        ],
    )

    round_tripped = state_from_dict(state_to_dict(state))
    compiled = compile_project_scene(round_tripped)
    params = scene_to_sim_params(compiled.scene, compiled.context)
    mpb_geometry = build_mpb_geometry(round_tripped, _FakeMP(), compiled.context.parameter_values, deps=None)
    code = generate_script(round_tripped)

    assert round_tripped.geometries[0].kind == "scripted"
    assert compiled.scene.objects[0].geometry.kind == "polygon"
    assert params.shapes[0].kind == "polygon"
    assert mpb_geometry[0]["kind"] == "Prism"
    assert "mp.Prism" in code
    assert "region(" not in code
