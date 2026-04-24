from __future__ import annotations

import ast
from collections.abc import Callable, Iterable, Mapping
import math
import random
from dataclasses import dataclass

from .errors import ValidationResult

_ALLOWED_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "random": random.random,
}

_FUNC_ARG_COUNTS = {
    "sin": (1,),
    "cos": (1,),
    "tan": (1,),
    "exp": (1,),
    "sqrt": (1,),
    "log": (1, 2),
    "log10": (1,),
    "random": (0,),
}

_COMPLEX_LITERAL_ERROR = "Phase must be a complex literal like 1, -1, 1-1j, or 9j."


@dataclass(frozen=True)
class ParameterEvalResult:
    name: str
    ok: bool
    value: float | None = None
    message: str = ""


def _prepare_expr(expr: str) -> str:
    if expr is None:
        raise ValueError("Expression is required.")
    expr = str(expr).strip()
    if not expr:
        raise ValueError("Expression is required.")
    return expr.replace("^", "**")


def _check_node(node: ast.AST, allowed_names: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _check_node(node.body, allowed_names)
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            raise ValueError("Unsupported operator.")
        _check_node(node.left, allowed_names)
        _check_node(node.right, allowed_names)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.UAdd, ast.USub)):
            raise ValueError("Unsupported unary operator.")
        _check_node(node.operand, allowed_names)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Unsupported function call.")
        func_name = node.func.id
        if func_name not in _ALLOWED_FUNCTIONS:
            raise ValueError(f"Unknown function: {func_name}")
        allowed_counts = _FUNC_ARG_COUNTS[func_name]
        if len(node.args) not in allowed_counts:
            counts = ", ".join(str(c) for c in allowed_counts)
            raise ValueError(f"Function '{func_name}' requires {counts} arguments.")
        for arg in node.args:
            _check_node(arg, allowed_names)
        return
    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_FUNCTIONS:
            raise ValueError(f"Function '{node.id}' must be called with ().")
        if node.id not in allowed_names:
            raise ValueError(f"Unknown name: {node.id}")
        return
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            raise ValueError("Unsupported constant.")
        if not isinstance(value, (int, float)):
            raise ValueError("Unsupported constant.")
        return
    raise ValueError("Unsupported expression.")


def _parse_expr(
    expr: str,
    allowed_names: set[str],
) -> ast.Expression:
    prepared = _prepare_expr(expr)
    try:
        tree = ast.parse(prepared, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid expression.") from exc
    _check_node(tree, allowed_names)
    return tree


def _combined_names(
    allowed_names: Iterable[str],
    extra_names: Iterable[str] = (),
) -> set[str]:
    return set(allowed_names) | set(extra_names)


def validate_numeric_expression(
    expr: str,
    allowed_names: Iterable[str],
    *,
    extra_names: Iterable[str] = (),
) -> ValidationResult:
    try:
        _parse_expr(expr, _combined_names(allowed_names, extra_names))
    except ValueError as exc:
        return ValidationResult(False, str(exc))
    return ValidationResult(True, "")


def _eval_numeric_tree(
    tree: ast.AST,
    variables: Mapping[str, float],
    expr: str,
) -> float:
    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
        if isinstance(node, ast.UnaryOp):
            value = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.USub):
                return -value
        if isinstance(node, ast.Call):
            func = _ALLOWED_FUNCTIONS[node.func.id]
            args = [_eval(arg) for arg in node.args]
            return float(func(*args))
        if isinstance(node, ast.Name):
            return float(variables[node.id])
        if isinstance(node, ast.Constant):
            return float(node.value)
        raise ValueError("Unsupported expression.")

    try:
        return float(_eval(tree))
    except Exception as exc:
        raise ValueError(f"Invalid expression: {expr}") from exc


def evaluate_numeric_expression(
    expr: str,
    variables: Mapping[str, float],
    *,
    extra_values: Mapping[str, float] | None = None,
) -> float:
    names = _combined_names(variables.keys(), () if extra_values is None else extra_values.keys())
    tree = _parse_expr(expr, names)
    combined = dict(variables)
    if extra_values:
        combined.update(extra_values)
    return _eval_numeric_tree(tree, combined, expr)


def compile_numeric_expression(
    expr: str,
    allowed_names: Iterable[str],
    *,
    extra_names: Iterable[str] = (),
) -> Callable[[Mapping[str, float], Mapping[str, float] | None], float]:
    tree = _parse_expr(expr, _combined_names(allowed_names, extra_names))

    def _evaluate(
        variables: Mapping[str, float],
        extra_values: Mapping[str, float] | None = None,
    ) -> float:
        combined = dict(variables)
        if extra_values:
            combined.update(extra_values)
        return _eval_numeric_tree(tree, combined, expr)

    return _evaluate


def _check_complex_node(node: ast.AST, allowed_names: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _check_complex_node(node.body, allowed_names)
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            raise ValueError("Unsupported operator.")
        _check_complex_node(node.left, allowed_names)
        _check_complex_node(node.right, allowed_names)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.UAdd, ast.USub)):
            raise ValueError("Unsupported unary operator.")
        _check_complex_node(node.operand, allowed_names)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Unsupported function call.")
        func_name = node.func.id
        if func_name not in _ALLOWED_FUNCTIONS:
            raise ValueError(f"Unknown function: {func_name}")
        allowed_counts = _FUNC_ARG_COUNTS[func_name]
        if len(node.args) not in allowed_counts:
            counts = ", ".join(str(c) for c in allowed_counts)
            raise ValueError(f"Function '{func_name}' requires {counts} arguments.")
        for arg in node.args:
            _check_complex_node(arg, allowed_names)
        return
    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_FUNCTIONS:
            raise ValueError(f"Function '{node.id}' must be called with ().")
        if node.id not in allowed_names:
            raise ValueError(f"Unknown name: {node.id}")
        return
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            raise ValueError("Unsupported constant.")
        if not isinstance(value, (int, float, complex)):
            raise ValueError("Unsupported constant.")
        return
    raise ValueError("Unsupported expression.")


def _parse_complex_expr(
    expr: str,
    allowed_names: set[str],
) -> ast.Expression:
    prepared = _prepare_expr(expr)
    try:
        tree = ast.parse(prepared, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid expression.") from exc
    _check_complex_node(tree, allowed_names)
    return tree


def validate_complex_expression(
    expr: str,
    allowed_names: Iterable[str],
    *,
    extra_names: Iterable[str] = (),
) -> ValidationResult:
    try:
        _parse_complex_expr(expr, _combined_names(allowed_names, extra_names))
    except ValueError as exc:
        return ValidationResult(False, str(exc))
    return ValidationResult(True, "")


def _eval_complex_tree(
    tree: ast.AST,
    variables: Mapping[str, float | complex],
    expr: str,
) -> complex:
    def _real_arg(value: complex, expr: str) -> float:
        if abs(value.imag) > 1e-15:
            raise ValueError(f"Invalid expression: {expr}")
        return float(value.real)

    def _eval(node: ast.AST) -> complex:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
        if isinstance(node, ast.UnaryOp):
            value = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.USub):
                return -value
        if isinstance(node, ast.Call):
            func = _ALLOWED_FUNCTIONS[node.func.id]
            args = [_real_arg(_eval(arg), expr) for arg in node.args]
            return complex(func(*args))
        if isinstance(node, ast.Name):
            return complex(float(variables[node.id]))
        if isinstance(node, ast.Constant):
            return complex(node.value)
        raise ValueError("Unsupported expression.")

    try:
        return complex(_eval(tree))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Invalid expression: {expr}") from exc


def evaluate_complex_expression(
    expr: str,
    variables: Mapping[str, float | complex],
    *,
    extra_values: Mapping[str, float | complex] | None = None,
) -> complex:
    names = _combined_names(variables.keys(), () if extra_values is None else extra_values.keys())
    tree = _parse_complex_expr(expr, names)
    combined: dict[str, float | complex] = dict(variables)
    if extra_values:
        combined.update(extra_values)
    return _eval_complex_tree(tree, combined, expr)


def compile_complex_expression(
    expr: str,
    allowed_names: Iterable[str],
    *,
    extra_names: Iterable[str] = (),
) -> Callable[[Mapping[str, float | complex], Mapping[str, float | complex] | None], complex]:
    tree = _parse_complex_expr(expr, _combined_names(allowed_names, extra_names))

    def _evaluate(
        variables: Mapping[str, float | complex],
        extra_values: Mapping[str, float | complex] | None = None,
    ) -> complex:
        combined: dict[str, float | complex] = dict(variables)
        if extra_values:
            combined.update(extra_values)
        return _eval_complex_tree(tree, combined, expr)

    return _evaluate


def _normalize_complex_literal(expr: str) -> str:
    if expr is None:
        raise ValueError(_COMPLEX_LITERAL_ERROR)
    text = str(expr).strip()
    if not text:
        raise ValueError(_COMPLEX_LITERAL_ERROR)
    return "".join(ch for ch in text if not ch.isspace())


def validate_complex_literal(expr: str) -> ValidationResult:
    try:
        parse_complex_literal(expr)
    except ValueError as exc:
        return ValidationResult(False, str(exc))
    return ValidationResult(True, "")


def parse_complex_literal(expr: str) -> complex:
    try:
        return complex(_normalize_complex_literal(expr))
    except Exception as exc:
        raise ValueError(_COMPLEX_LITERAL_ERROR) from exc


def evaluate_parameters(params: Iterable[object]) -> tuple[dict[str, float], list[ParameterEvalResult]]:
    values: dict[str, float] = {}
    results: list[ParameterEvalResult] = []

    for param in params:
        name = getattr(param, "name", "")
        expr = getattr(param, "expr", "")
        try:
            value = evaluate_numeric_expression(expr, values)
            values[name] = value
            results.append(ParameterEvalResult(name=name, ok=True, value=value))
        except ValueError as exc:
            results.append(ParameterEvalResult(name=name, ok=False, message=str(exc)))

    return values, results
