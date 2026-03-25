from __future__ import annotations

import pytest

from meep_gui.validation import NameRegistry, parse_parameter_import_text


def _registry() -> NameRegistry:
    return NameRegistry(
        parameters=set(),
        materials={"mat1"},
        geometries={"geo1"},
        sources={"src1"},
    )


def test_parse_parameter_import_text_accepts_valid_assignments() -> None:
    parsed = parse_parameter_import_text("a = 1\nb=a+1\nc = log(8, 2)\n", _registry())
    assert parsed == [("a", "1"), ("b", "a+1"), ("c", "log(8, 2)")]


def test_parse_parameter_import_text_rejects_invalid_line_format() -> None:
    with pytest.raises(ValueError, match=r"Line 2: expected 'name = expression'\."):
        parse_parameter_import_text("a = 1\nthis is not valid\n", _registry())


def test_parse_parameter_import_text_rejects_empty_file() -> None:
    with pytest.raises(ValueError, match=r"Import file is empty\."):
        parse_parameter_import_text("", _registry())


def test_parse_parameter_import_text_rejects_blank_and_comment_lines() -> None:
    with pytest.raises(ValueError, match=r"Line 2: blank lines are not allowed\."):
        parse_parameter_import_text("a = 1\n\nb = 2\n", _registry())
    with pytest.raises(ValueError, match=r"Line 2: expected 'name = expression'\."):
        parse_parameter_import_text("a = 1\n# comment\nb = 2\n", _registry())


def test_parse_parameter_import_text_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match=r"Line 2: Name 'a' is already in use\."):
        parse_parameter_import_text("a = 1\na = 2\n", _registry())


def test_parse_parameter_import_text_rejects_name_collisions_with_other_objects() -> None:
    with pytest.raises(ValueError, match=r"Line 1: Name 'mat1' is already in use\."):
        parse_parameter_import_text("mat1 = 2\n", _registry())


def test_parse_parameter_import_text_rejects_forward_reference() -> None:
    with pytest.raises(ValueError, match=r"Line 1: Unknown name: a"):
        parse_parameter_import_text("b = a + 1\na = 1\n", _registry())
