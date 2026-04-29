from __future__ import annotations

import random

from meep_gui.model import Parameter
from meep_gui.validation import (
    build_project_rng,
    evaluate_complex_expression,
    evaluate_numeric_expression,
    parse_complex_literal,
    validate_complex_expression,
    validate_complex_literal,
    validate_numeric_expression,
)


def test_validate_numeric_expression_accepts_allowed_math() -> None:
    result = validate_numeric_expression("sqrt(4)+sin(0)+uniform(0, 1)+gauss(0, 1)+2^3", [])
    assert result.ok


def test_validate_numeric_expression_rejects_removed_random_function() -> None:
    result = validate_numeric_expression("random()", [])

    assert not result.ok
    assert "Unknown function: random" in result.message


def test_validate_numeric_expression_checks_random_function_arity() -> None:
    result = validate_numeric_expression("uniform(0)", [])

    assert not result.ok
    assert "requires 2 arguments" in result.message


def test_validate_numeric_expression_rejects_unknown_name() -> None:
    result = validate_numeric_expression("foo + 1", [])
    assert not result.ok
    assert "Unknown name" in result.message


def test_evaluate_numeric_expression_with_variables() -> None:
    value = evaluate_numeric_expression("a*2 + log10(100)", {"a": 3.0})
    assert abs(value - 8.0) < 1e-9


def test_evaluate_random_functions_use_supplied_rng() -> None:
    rng = random.Random(123)
    expected = random.Random(123)

    value = evaluate_numeric_expression("uniform(0, 1) + gauss(0, 1)", {}, rng=rng)

    assert abs(value - (expected.uniform(0, 1) + expected.gauss(0, 1))) < 1e-12


def test_project_rng_seed_accepts_deterministic_parameter_dependencies() -> None:
    params = [Parameter(name="base", expr="10"), Parameter(name="seed_param", expr="base + 5")]

    rng = build_project_rng(params, "seed_param")

    assert rng.random() == random.Random(15.0).random()


def test_project_rng_rejects_randomized_seed_dependencies() -> None:
    params = [Parameter(name="seed_param", expr="uniform(1, 2)")]

    try:
        build_project_rng(params, "seed_param")
    except ValueError as exc:
        assert "uniform" in str(exc) or "randomized parameter" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected randomized seed dependency to fail.")


def test_evaluate_complex_expression_accepts_parameters_and_literals() -> None:
    result = validate_complex_expression("amp * (1 + 1j) / sqrt(2)", ["amp"])
    value = evaluate_complex_expression("amp * (1 + 1j) / sqrt(2)", {"amp": 2.0})

    assert result.ok
    assert abs(value.real - 2**0.5) < 1e-9
    assert abs(value.imag - 2**0.5) < 1e-9


def test_validate_complex_expression_rejects_unknown_names() -> None:
    result = validate_complex_expression("missing + 1j", [])

    assert not result.ok
    assert "Unknown name" in result.message


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
