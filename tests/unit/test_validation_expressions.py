from __future__ import annotations

from meep_gui.validation import (
    evaluate_numeric_expression,
    parse_complex_literal,
    validate_complex_literal,
    validate_numeric_expression,
)


def test_validate_numeric_expression_accepts_allowed_math() -> None:
    result = validate_numeric_expression("sqrt(4)+sin(0)+2^3", [])
    assert result.ok


def test_validate_numeric_expression_rejects_unknown_name() -> None:
    result = validate_numeric_expression("foo + 1", [])
    assert not result.ok
    assert "Unknown name" in result.message


def test_evaluate_numeric_expression_with_variables() -> None:
    value = evaluate_numeric_expression("a*2 + log10(100)", {"a": 3.0})
    assert abs(value - 8.0) < 1e-9


def test_validate_complex_literal_accepts_supported_literals() -> None:
    for value in ("1", "-1", "1j", "9j", "1-1j", "1+1j", "(1-1j)"):
        result = validate_complex_literal(value)
        assert result.ok, value


def test_validate_complex_literal_rejects_non_literal_forms() -> None:
    for value in ("a", "sqrt(-1)", "1/2+1j", "1j*2", "random()", ""):
        result = validate_complex_literal(value)
        assert not result.ok, value
        assert "complex literal" in result.message


def test_parse_complex_literal_returns_complex_values() -> None:
    assert parse_complex_literal("1-1j") == complex(1, -1)
    assert parse_complex_literal("9j") == complex(0, 9)
