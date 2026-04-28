from __future__ import annotations

import ast
from dataclasses import dataclass, field
import math
from typing import Any

MAX_LOOP_ITERATIONS = 10000
MAX_LOOP_DEPTH = 3
MAX_OPERATIONS = 200000
MAX_IMPLICIT_DIMENSION = 512
MAX_IMPLICIT_CELLS = 100000
MAX_EMITTED_POLYGONS = 2000
MAX_VERTICES_PER_POLYGON = 4096
MAX_TOTAL_VERTICES = 50000
MAX_LIST_LENGTH = 10000
MAX_COORDINATE_MAGNITUDE = 1e6


@dataclass(frozen=True)
class MaterialRef:
    name: str


@dataclass(frozen=True)
class EmittedPolygon:
    name: str
    material: str
    vertices: tuple[tuple[float, float], ...]
    priority: int = 0
    height: float = 0.0
    z: float = 0.0


@dataclass(frozen=True)
class GeometryScriptResult:
    polygons: tuple[EmittedPolygon, ...] = ()
    referenced_parameters: tuple[str, ...] = ()
    referenced_materials: tuple[str, ...] = ()
    emitted_count: int = 0
    vertex_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeometryScriptValidation:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    referenced_parameters: tuple[str, ...] = ()
    referenced_materials: tuple[str, ...] = ()
    emitted_count: int = 0
    vertex_count: int = 0


@dataclass
class _ShapelyAPI:
    Polygon: Any
    Point: Any
    LineString: Any
    GeometryCollection: Any
    box: Any
    unary_union: Any
    triangulate: Any
    translate: Any
    rotate: Any
    scale: Any


_SHAPELY: _ShapelyAPI | None = None


class GeometryScriptError(ValueError):
    def __init__(self, message: str, node: ast.AST | None = None) -> None:
        if node is not None and getattr(node, "lineno", None) is not None:
            message = f"Line {node.lineno}, column {getattr(node, 'col_offset', 0) + 1}: {message}"
        super().__init__(message)


class _GeometryValue:
    def __init__(self, geom) -> None:
        self.geom = geom


class _ReadOnlyParams:
    def __init__(self, values: dict[str, float], referenced: set[str]) -> None:
        self._values = values
        self._referenced = referenced

    def __getitem__(self, name: str) -> float:
        key = str(name)
        if key not in self._values:
            raise KeyError(key)
        self._referenced.add(key)
        return float(self._values[key])


class _ReadOnlyMaterials:
    def __init__(self, names: set[str], referenced: set[str]) -> None:
        self._names = names
        self._referenced = referenced

    def __getitem__(self, name: str) -> MaterialRef:
        key = str(name)
        if key not in self._names:
            raise KeyError(key)
        self._referenced.add(key)
        return MaterialRef(key)


def _require_shapely() -> _ShapelyAPI:
    global _SHAPELY
    if _SHAPELY is not None:
        return _SHAPELY
    try:
        from shapely.affinity import rotate, scale, translate
        from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box
        from shapely.ops import triangulate, unary_union
    except ModuleNotFoundError as exc:
        raise GeometryScriptError(
            "Shapely is required for scripted geometry. Install it with conda-forge shapely."
        ) from exc
    _SHAPELY = _ShapelyAPI(
        Polygon=Polygon,
        Point=Point,
        LineString=LineString,
        GeometryCollection=GeometryCollection,
        box=box,
        unary_union=unary_union,
        triangulate=triangulate,
        translate=translate,
        rotate=rotate,
        scale=scale,
    )
    return _SHAPELY


def run_geometry_script(
    source: str,
    *,
    parameter_values: dict[str, float],
    material_names: set[str],
    name_prefix: str = "scripted",
) -> GeometryScriptResult:
    interpreter = _Interpreter(
        source=source,
        parameter_values=parameter_values,
        material_names=material_names,
        name_prefix=name_prefix,
    )
    return interpreter.run()


def validate_geometry_script(
    source: str,
    *,
    parameter_values: dict[str, float],
    material_names: set[str],
    name_prefix: str = "scripted",
) -> GeometryScriptValidation:
    try:
        result = run_geometry_script(
            source,
            parameter_values=parameter_values,
            material_names=material_names,
            name_prefix=name_prefix,
        )
    except Exception as exc:
        return GeometryScriptValidation(ok=False, errors=(str(exc),))
    return GeometryScriptValidation(
        ok=True,
        warnings=result.warnings,
        referenced_parameters=result.referenced_parameters,
        referenced_materials=result.referenced_materials,
        emitted_count=result.emitted_count,
        vertex_count=result.vertex_count,
    )


@dataclass
class _EmitRecord:
    geom: Any
    material: str
    height: float
    z: float
    priority: int


class _Interpreter:
    def __init__(
        self,
        *,
        source: str,
        parameter_values: dict[str, float],
        material_names: set[str],
        name_prefix: str,
    ) -> None:
        self.source = source or ""
        self.parameter_values = {str(k): float(v) for k, v in parameter_values.items()}
        self.material_names = {str(name) for name in material_names}
        self.name_prefix = name_prefix or "scripted"
        self.referenced_parameters: set[str] = set()
        self.referenced_materials: set[str] = set()
        self.shapely = _require_shapely()
        self.env: dict[str, Any] = {
            "params": _ReadOnlyParams(self.parameter_values, self.referenced_parameters),
            "materials": _ReadOnlyMaterials(self.material_names, self.referenced_materials),
            "pi": math.pi,
        }
        self.functions = self._build_functions()
        self.emits: list[_EmitRecord] = []
        self.operation_count = 0
        self.loop_iterations = 0
        self.loop_depth = 0

    def run(self) -> GeometryScriptResult:
        if not self.source.strip():
            raise GeometryScriptError("Script source is required.")
        try:
            module = ast.parse(self.source, mode="exec")
        except SyntaxError as exc:
            raise GeometryScriptError(f"Invalid syntax: {exc.msg}") from exc
        for stmt in module.body:
            self._exec_stmt(stmt)
        polygons = self._emits_to_polygons()
        if not polygons:
            raise GeometryScriptError("Script emitted no polygons.")
        return GeometryScriptResult(
            polygons=tuple(polygons),
            referenced_parameters=tuple(sorted(self.referenced_parameters)),
            referenced_materials=tuple(sorted(self.referenced_materials)),
            emitted_count=len(polygons),
            vertex_count=sum(len(poly.vertices) for poly in polygons),
        )

    def _build_functions(self) -> dict[str, Any]:
        return {
            "rect": self._func_rect,
            "circle": self._func_circle,
            "ellipse": self._func_ellipse,
            "polygon": self._func_polygon,
            "path": self._func_path,
            "region": self._func_region,
            "union": self._func_union,
            "difference": self._func_difference,
            "intersection": self._func_intersection,
            "move": self._func_move,
            "rotate": self._func_rotate,
            "scale": self._func_scale,
            "mirror_x": self._func_mirror_x,
            "mirror_y": self._func_mirror_y,
            "clean": self._func_clean,
            "simplify": self._func_simplify,
            "emit": self._func_emit,
            "linspace": self._func_linspace,
            "reverse": self._func_reverse,
            "range": self._func_range,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "sqrt": math.sqrt,
            "abs": abs,
            "exp": math.exp,
            "log": math.log,
            "min": min,
            "max": max,
        }

    def _tick(self, node: ast.AST | None = None) -> None:
        self.operation_count += 1
        if self.operation_count > MAX_OPERATIONS:
            raise GeometryScriptError("Operation limit exceeded.", node)

    def _exec_stmt(self, stmt: ast.stmt) -> None:
        self._tick(stmt)
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                raise GeometryScriptError("Only simple local assignments are allowed.", stmt)
            name = stmt.targets[0].id
            self._validate_local_name(name, stmt)
            self.env[name] = self._eval_expr(stmt.value)
            return
        if isinstance(stmt, ast.Expr):
            if self._try_append(stmt.value):
                return
            value = self._eval_expr(stmt.value)
            if value is not None:
                return
            return
        if isinstance(stmt, ast.If):
            branch = stmt.body if bool(self._eval_expr(stmt.test)) else stmt.orelse
            for child in branch:
                self._exec_stmt(child)
            return
        if isinstance(stmt, ast.For):
            self._exec_for(stmt)
            return
        if isinstance(stmt, ast.Pass):
            return
        raise GeometryScriptError(f"Unsupported syntax: {type(stmt).__name__}", stmt)

    def _exec_for(self, stmt: ast.For) -> None:
        if not isinstance(stmt.target, ast.Name):
            raise GeometryScriptError("For-loop target must be a local name.", stmt)
        self._validate_local_name(stmt.target.id, stmt.target)
        if stmt.orelse:
            raise GeometryScriptError("For-loop else blocks are not supported.", stmt)
        self.loop_depth += 1
        if self.loop_depth > MAX_LOOP_DEPTH:
            raise GeometryScriptError("Loop nesting limit exceeded.", stmt)
        try:
            values = self._eval_expr(stmt.iter)
            if not isinstance(values, (list, tuple, range)):
                raise GeometryScriptError("For loops may only iterate over range() or linspace() results.", stmt)
            for value in values:
                self.loop_iterations += 1
                if self.loop_iterations > MAX_LOOP_ITERATIONS:
                    raise GeometryScriptError("Loop iteration limit exceeded.", stmt)
                self.env[stmt.target.id] = value
                for child in stmt.body:
                    self._exec_stmt(child)
        finally:
            self.loop_depth -= 1

    def _try_append(self, expr: ast.AST) -> bool:
        if not isinstance(expr, ast.Call):
            return False
        if not isinstance(expr.func, ast.Attribute) or expr.func.attr != "append":
            if isinstance(expr.func, ast.Attribute):
                raise GeometryScriptError("Only list.append(...) method calls are allowed.", expr)
            return False
        if not isinstance(expr.func.value, ast.Name):
            raise GeometryScriptError("Only local_list.append(value) is allowed.", expr)
        if expr.keywords or len(expr.args) != 1:
            raise GeometryScriptError("list.append requires exactly one positional argument.", expr)
        target = self.env.get(expr.func.value.id)
        if not isinstance(target, list):
            raise GeometryScriptError("append target must be a local list.", expr)
        if len(target) >= MAX_LIST_LENGTH:
            raise GeometryScriptError("List length limit exceeded.", expr)
        target.append(self._eval_expr(expr.args[0]))
        return True

    def _eval_expr(self, expr: ast.AST, *, extra_env: dict[str, Any] | None = None, region: bool = False) -> Any:
        if not region:
            self._tick(expr)
        env = self.env if extra_env is None else {**self.env, **extra_env}
        if isinstance(expr, ast.Constant):
            value = expr.value
            if isinstance(value, (int, float, str, bool)) or value is None:
                return value
            raise GeometryScriptError("Unsupported constant.", expr)
        if isinstance(expr, ast.Name):
            name = expr.id
            self._validate_name_reference(name, expr)
            if region:
                if extra_env is not None and name in extra_env:
                    return extra_env[name]
                if name == "pi":
                    return math.pi
                if name in self.parameter_values:
                    self.referenced_parameters.add(name)
                    return self.parameter_values[name]
                if name in self.env:
                    return self._number(self.env[name], expr)
                raise GeometryScriptError(f"Unknown name: {name}", expr)
            if name in env:
                return env[name]
            if not region and name in self.functions:
                raise GeometryScriptError(f"Function '{name}' must be called.", expr)
            raise GeometryScriptError(f"Unknown name: {name}", expr)
        if isinstance(expr, ast.List):
            values = [self._eval_expr(item, extra_env=extra_env, region=region) for item in expr.elts]
            self._check_list_length(values, expr)
            return values
        if isinstance(expr, ast.Tuple):
            values = tuple(self._eval_expr(item, extra_env=extra_env, region=region) for item in expr.elts)
            self._check_list_length(values, expr)
            return values
        if isinstance(expr, ast.Subscript):
            return self._eval_subscript(expr, env, region=region)
        if isinstance(expr, ast.UnaryOp):
            value = self._eval_expr(expr.operand, extra_env=extra_env, region=region)
            if isinstance(expr.op, ast.UAdd):
                return +self._number(value, expr)
            if isinstance(expr.op, ast.USub):
                return -self._number(value, expr)
            if isinstance(expr.op, ast.Not):
                return not bool(value)
            raise GeometryScriptError("Unsupported unary operator.", expr)
        if isinstance(expr, ast.BinOp):
            return self._eval_binop(expr, extra_env=extra_env, region=region)
        if isinstance(expr, ast.BoolOp):
            return self._eval_boolop(expr, extra_env=extra_env, region=region)
        if isinstance(expr, ast.Compare):
            return self._eval_compare(expr, extra_env=extra_env, region=region)
        if isinstance(expr, ast.Call):
            if region:
                return self._eval_region_call(expr, extra_env=extra_env)
            return self._eval_call(expr)
        if isinstance(expr, ast.Attribute):
            raise GeometryScriptError("Attribute access is not allowed.", expr)
        if isinstance(expr, ast.Lambda):
            raise GeometryScriptError("Lambda expressions are not allowed.", expr)
        raise GeometryScriptError(f"Unsupported expression: {type(expr).__name__}", expr)

    def _eval_subscript(self, expr: ast.Subscript, env: dict[str, Any], *, region: bool) -> Any:
        if not isinstance(expr.value, ast.Name):
            raise GeometryScriptError("Only params[...] and materials[...] subscriptions are allowed.", expr)
        target_name = expr.value.id
        if target_name not in {"params", "materials"}:
            raise GeometryScriptError("Only params[...] and materials[...] subscriptions are allowed.", expr)
        if region and target_name == "materials":
            raise GeometryScriptError("materials[...] is not allowed in region expressions.", expr)
        key = self._eval_expr(expr.slice, region=region)
        if not isinstance(key, str):
            raise GeometryScriptError("params/materials keys must be strings.", expr)
        try:
            return env[target_name][key]
        except KeyError as exc:
            label = "parameter" if target_name == "params" else "material"
            raise GeometryScriptError(f"Unknown {label}: {key}", expr) from exc

    def _eval_binop(self, expr: ast.BinOp, *, extra_env: dict[str, Any] | None, region: bool) -> Any:
        left = self._eval_expr(expr.left, extra_env=extra_env, region=region)
        right = self._eval_expr(expr.right, extra_env=extra_env, region=region)
        if isinstance(expr.op, ast.Add):
            if isinstance(left, list) and isinstance(right, list):
                value = left + right
                self._check_list_length(value, expr)
                return value
            if isinstance(left, tuple) and isinstance(right, tuple):
                value = left + right
                self._check_list_length(value, expr)
                return value
            return self._number(left, expr) + self._number(right, expr)
        if isinstance(expr.op, ast.Sub):
            return self._number(left, expr) - self._number(right, expr)
        if isinstance(expr.op, ast.Mult):
            return self._number(left, expr) * self._number(right, expr)
        if isinstance(expr.op, ast.Div):
            return self._number(left, expr) / self._number(right, expr)
        if isinstance(expr.op, ast.Pow):
            return self._number(left, expr) ** self._number(right, expr)
        if isinstance(expr.op, ast.Mod):
            return self._number(left, expr) % self._number(right, expr)
        raise GeometryScriptError("Unsupported arithmetic operator.", expr)

    def _eval_boolop(self, expr: ast.BoolOp, *, extra_env: dict[str, Any] | None, region: bool) -> bool:
        if isinstance(expr.op, ast.And):
            for value_node in expr.values:
                if not bool(self._eval_expr(value_node, extra_env=extra_env, region=region)):
                    return False
            return True
        if isinstance(expr.op, ast.Or):
            for value_node in expr.values:
                if bool(self._eval_expr(value_node, extra_env=extra_env, region=region)):
                    return True
            return False
        raise GeometryScriptError("Unsupported boolean operator.", expr)

    def _eval_compare(self, expr: ast.Compare, *, extra_env: dict[str, Any] | None, region: bool) -> bool:
        left = self._eval_expr(expr.left, extra_env=extra_env, region=region)
        for op, comparator in zip(expr.ops, expr.comparators):
            right = self._eval_expr(comparator, extra_env=extra_env, region=region)
            if isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            else:
                raise GeometryScriptError("Unsupported comparison operator.", expr)
            if not ok:
                return False
            left = right
        return True

    def _eval_call(self, expr: ast.Call) -> Any:
        if not isinstance(expr.func, ast.Name):
            raise GeometryScriptError("Only whitelisted function calls are allowed.", expr)
        name = expr.func.id
        self._validate_name_reference(name, expr.func)
        if name not in self.functions:
            raise GeometryScriptError(f"Unknown function: {name}", expr)
        args = self._eval_call_args(expr)
        kwargs = self._eval_call_kwargs(expr)
        try:
            return self.functions[name](*args, **kwargs)
        except GeometryScriptError as exc:
            if str(exc).startswith("Line "):
                raise
            raise GeometryScriptError(str(exc), expr) from exc
        except Exception as exc:
            raise GeometryScriptError(str(exc), expr) from exc

    def _eval_region_call(self, expr: ast.Call, *, extra_env: dict[str, Any] | None) -> Any:
        if not isinstance(expr.func, ast.Name):
            raise GeometryScriptError("Only math function calls are allowed in region expressions.", expr)
        name = expr.func.id
        if name not in {"sin", "cos", "tan", "sqrt", "abs", "exp", "log", "min", "max"}:
            raise GeometryScriptError(f"Unknown region function: {name}", expr)
        args = [
            self._eval_expr(arg, extra_env=extra_env, region=True)
            for arg in expr.args
        ]
        if any(keyword.arg is None for keyword in expr.keywords):
            raise GeometryScriptError("Keyword expansion is not allowed.", expr)
        kwargs = {
            keyword.arg: self._eval_expr(keyword.value, extra_env=extra_env, region=True)
            for keyword in expr.keywords
        }
        try:
            return self.functions[name](*args, **kwargs)
        except GeometryScriptError as exc:
            if str(exc).startswith("Line "):
                raise
            raise GeometryScriptError(str(exc), expr) from exc
        except Exception as exc:
            raise GeometryScriptError(str(exc), expr) from exc

    def _eval_call_args(self, expr: ast.Call) -> list[Any]:
        args: list[Any] = []
        for arg in expr.args:
            if isinstance(arg, ast.Starred):
                value = self._eval_expr(arg.value)
                if not isinstance(value, (list, tuple)):
                    raise GeometryScriptError("Starred arguments must expand a list or tuple.", arg)
                args.extend(value)
            else:
                args.append(self._eval_expr(arg))
        return args

    def _eval_call_kwargs(self, expr: ast.Call) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        for keyword in expr.keywords:
            if keyword.arg is None:
                raise GeometryScriptError("Keyword expansion is not allowed.", expr)
            kwargs[keyword.arg] = self._eval_expr(keyword.value)
        return kwargs

    def _validate_local_name(self, name: str, node: ast.AST) -> None:
        self._validate_name_reference(name, node)
        if name in {"params", "materials", "pi"} or name in self.functions:
            raise GeometryScriptError(f"Cannot assign to reserved name: {name}", node)

    def _validate_name_reference(self, name: str, node: ast.AST) -> None:
        if "__" in name:
            raise GeometryScriptError("Dunder names are not allowed.", node)
        if name.startswith("_"):
            raise GeometryScriptError("Private names are not allowed.", node)

    def _check_list_length(self, value, node: ast.AST) -> None:
        if len(value) > MAX_LIST_LENGTH:
            raise GeometryScriptError("List length limit exceeded.", node)

    def _number(self, value: Any, node: ast.AST | None = None) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise GeometryScriptError("Expected a number.", node)
        value = float(value)
        if not math.isfinite(value):
            raise GeometryScriptError("Expected a finite number.", node)
        return value

    def _int_value(self, value: Any, node: ast.AST | None = None) -> int:
        numeric = self._number(value, node)
        rounded = round(numeric)
        if abs(numeric - rounded) > 1e-9:
            raise GeometryScriptError("Expected an integer.", node)
        return int(rounded)

    def _point(self, value: Any) -> tuple[float, float]:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise GeometryScriptError("Expected a 2D point.")
        x = self._number(value[0])
        y = self._number(value[1])
        self._check_coordinate(x)
        self._check_coordinate(y)
        return x, y

    def _points(self, value: Any) -> list[tuple[float, float]]:
        if not isinstance(value, (list, tuple)):
            raise GeometryScriptError("Expected a list of points.")
        points = [self._point(point) for point in value]
        self._check_list_length(points, None)  # type: ignore[arg-type]
        return points

    def _check_coordinate(self, value: float) -> None:
        if abs(value) > MAX_COORDINATE_MAGNITUDE:
            raise GeometryScriptError("Coordinate magnitude limit exceeded.")

    def _geometry(self, value: Any) -> Any:
        if not isinstance(value, _GeometryValue):
            raise GeometryScriptError("Expected geometry.")
        return value.geom

    def _wrap_geom(self, geom) -> _GeometryValue:
        if geom is None:
            raise GeometryScriptError("Geometry operation produced no geometry.")
        if not geom.is_empty and not geom.is_valid:
            raise GeometryScriptError("Invalid geometry. Use clean(...) to repair it explicitly.")
        return _GeometryValue(geom)

    def _func_rect(self, *, center=(0, 0), size=(1, 1)) -> _GeometryValue:
        cx, cy = self._point(center)
        sx, sy = self._point(size)
        if sx <= 0 or sy <= 0:
            raise GeometryScriptError("rect size must be positive.")
        return self._wrap_geom(self.shapely.box(cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2))

    def _regular_polygon(self, center, rx: float, ry: float, segments: int) -> _GeometryValue:
        cx, cy = self._point(center)
        if rx <= 0 or ry <= 0:
            raise GeometryScriptError("Radius must be positive.")
        if segments < 8 or segments > MAX_VERTICES_PER_POLYGON:
            raise GeometryScriptError("segments must be between 8 and the vertex limit.")
        points = [
            (
                cx + rx * math.cos(2 * math.pi * i / segments),
                cy + ry * math.sin(2 * math.pi * i / segments),
            )
            for i in range(segments)
        ]
        return self._func_polygon(points=points)

    def _func_circle(self, *, center=(0, 0), radius=1, segments=32) -> _GeometryValue:
        r = self._number(radius)
        return self._regular_polygon(center, r, r, self._int_value(segments))

    def _func_ellipse(self, *, center=(0, 0), radius=(1, 1), segments=32) -> _GeometryValue:
        rx, ry = self._point(radius)
        return self._regular_polygon(center, rx, ry, self._int_value(segments))

    def _func_polygon(self, *, points) -> _GeometryValue:
        point_list = self._points(points)
        if len(point_list) < 3:
            raise GeometryScriptError("polygon requires at least three points.")
        geom = self.shapely.Polygon(point_list)
        return self._wrap_geom(geom)

    def _func_path(self, *, points, width, cap="round", join="round", segments=8) -> _GeometryValue:
        point_list = self._points(points)
        if len(point_list) < 2:
            raise GeometryScriptError("path requires at least two points.")
        width_value = self._number(width)
        if width_value <= 0:
            raise GeometryScriptError("path width must be positive.")
        quad_segs = self._int_value(segments)
        cap_style = {"round": 1, "flat": 2, "square": 3}.get(str(cap))
        join_style = {"round": 1, "mitre": 2, "miter": 2, "bevel": 3}.get(str(join))
        if cap_style is None:
            raise GeometryScriptError("Unsupported path cap.")
        if join_style is None:
            raise GeometryScriptError("Unsupported path join.")
        geom = self.shapely.LineString(point_list).buffer(
            width_value / 2,
            quad_segs=quad_segs,
            cap_style=cap_style,
            join_style=join_style,
        )
        return self._wrap_geom(geom)

    def _func_union(self, *items) -> _GeometryValue:
        if not items:
            raise GeometryScriptError("union requires at least one geometry.")
        return self._wrap_geom(self.shapely.unary_union([self._geometry(item) for item in items]))

    def _func_difference(self, first, *rest) -> _GeometryValue:
        geom = self._geometry(first)
        if rest:
            geom = geom.difference(self.shapely.unary_union([self._geometry(item) for item in rest]))
        return self._wrap_geom(geom)

    def _func_intersection(self, first, *rest) -> _GeometryValue:
        geom = self._geometry(first)
        for item in rest:
            geom = geom.intersection(self._geometry(item))
        return self._wrap_geom(geom)

    def _func_move(self, g, *, dx=0, dy=0) -> _GeometryValue:
        return self._wrap_geom(self.shapely.translate(self._geometry(g), xoff=self._number(dx), yoff=self._number(dy)))

    def _func_rotate(self, g, *, angle=0, origin=(0, 0), degrees=True) -> _GeometryValue:
        return self._wrap_geom(
            self.shapely.rotate(
                self._geometry(g),
                self._number(angle),
                origin=self._point(origin),
                use_radians=not bool(degrees),
            )
        )

    def _func_scale(self, g, *, sx=1, sy=1, origin=(0, 0)) -> _GeometryValue:
        return self._wrap_geom(
            self.shapely.scale(
                self._geometry(g),
                xfact=self._number(sx),
                yfact=self._number(sy),
                origin=self._point(origin),
            )
        )

    def _func_mirror_x(self, g, *, x=0) -> _GeometryValue:
        x0 = self._number(x)
        geom = self.shapely.scale(self._geometry(g), xfact=-1, yfact=1, origin=(x0, 0))
        return self._wrap_geom(geom)

    def _func_mirror_y(self, g, *, y=0) -> _GeometryValue:
        y0 = self._number(y)
        geom = self.shapely.scale(self._geometry(g), xfact=1, yfact=-1, origin=(0, y0))
        return self._wrap_geom(geom)

    def _func_clean(self, g) -> _GeometryValue:
        geom = self._geometry(g).buffer(0)
        return self._wrap_geom(geom)

    def _func_simplify(self, g, tolerance) -> _GeometryValue:
        geom = self._geometry(g).simplify(self._number(tolerance), preserve_topology=True)
        return self._wrap_geom(geom)

    def _func_emit(self, g, *, material, height=0, z=0, priority=0) -> None:
        if not isinstance(material, MaterialRef):
            raise GeometryScriptError("emit material must be materials[\"name\"].")
        self.emits.append(
            _EmitRecord(
                geom=self._geometry(g),
                material=material.name,
                height=self._number(height),
                z=self._number(z),
                priority=self._int_value(priority),
            )
        )
        return None

    def _func_linspace(self, start, stop, count) -> list[float]:
        count_int = self._int_value(count)
        if count_int <= 0:
            raise GeometryScriptError("linspace count must be positive.")
        if count_int > MAX_LIST_LENGTH:
            raise GeometryScriptError("linspace count exceeds the list length limit.")
        start_value = self._number(start)
        stop_value = self._number(stop)
        if count_int == 1:
            return [float(stop_value)]
        step = (stop_value - start_value) / (count_int - 1)
        return [start_value + i * step for i in range(count_int)]

    def _func_reverse(self, points) -> list[Any]:
        if not isinstance(points, (list, tuple)):
            raise GeometryScriptError("reverse expects a list or tuple.")
        return list(reversed(points))

    def _func_range(self, *args) -> list[int]:
        if not 1 <= len(args) <= 3:
            raise GeometryScriptError("range expects one to three arguments.")
        int_args = [self._int_value(arg) for arg in args]
        values = list(range(*int_args))
        if len(values) > MAX_LIST_LENGTH:
            raise GeometryScriptError("range exceeds the list length limit.")
        return values

    def _func_region(self, expr, *, bounds, resolution=256) -> _GeometryValue:
        if not isinstance(expr, str):
            raise GeometryScriptError("region expr must be a string.")
        bounds_tuple = self._bounds(bounds)
        nx, ny = self._resolution(resolution)
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as exc:
            raise GeometryScriptError(f"Invalid region expression: {exc.msg}") from exc
        xmin, ymin, xmax, ymax = bounds_tuple
        dx = (xmax - xmin) / nx
        dy = (ymax - ymin) / ny
        rects = []
        for j in range(ny):
            run_start: int | None = None
            y_center = ymin + (j + 0.5) * dy
            for i in range(nx):
                self._tick()
                x_center = xmin + (i + 0.5) * dx
                value = self._eval_expr(
                    tree.body,
                    extra_env={"x": x_center, "y": y_center},
                    region=True,
                )
                if not isinstance(value, bool):
                    raise GeometryScriptError("region expression must evaluate to a boolean.")
                if value and run_start is None:
                    run_start = i
                if (not value or i == nx - 1) and run_start is not None:
                    end = i + 1 if value and i == nx - 1 else i
                    rects.append(
                        self.shapely.box(
                            xmin + run_start * dx,
                            ymin + j * dy,
                            xmin + end * dx,
                            ymin + (j + 1) * dy,
                        )
                    )
                    run_start = None
        if not rects:
            return self._wrap_geom(self.shapely.GeometryCollection())
        return self._wrap_geom(self.shapely.unary_union(rects))

    def _bounds(self, value) -> tuple[float, float, float, float]:
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            raise GeometryScriptError("bounds must be (xmin, ymin, xmax, ymax).")
        xmin, ymin, xmax, ymax = (self._number(item) for item in value)
        if xmax <= xmin or ymax <= ymin:
            raise GeometryScriptError("bounds max values must be greater than min values.")
        for coord in (xmin, ymin, xmax, ymax):
            self._check_coordinate(coord)
        return xmin, ymin, xmax, ymax

    def _resolution(self, value) -> tuple[int, int]:
        if isinstance(value, (list, tuple)):
            if len(value) != 2:
                raise GeometryScriptError("resolution tuple must have two values.")
            nx, ny = self._int_value(value[0]), self._int_value(value[1])
        else:
            nx = ny = self._int_value(value)
        if nx <= 0 or ny <= 0:
            raise GeometryScriptError("resolution must be positive.")
        if nx > MAX_IMPLICIT_DIMENSION or ny > MAX_IMPLICIT_DIMENSION:
            raise GeometryScriptError("resolution dimension limit exceeded.")
        if nx * ny > MAX_IMPLICIT_CELLS:
            raise GeometryScriptError("resolution cell limit exceeded.")
        return nx, ny

    def _emits_to_polygons(self) -> list[EmittedPolygon]:
        polygons: list[EmittedPolygon] = []
        total_vertices = 0
        for emit_idx, record in enumerate(self.emits, start=1):
            for poly_idx, polygon in enumerate(self._flatten_polygons(record.geom), start=1):
                vertices = self._polygon_vertices(polygon)
                if not vertices:
                    continue
                if len(vertices) > MAX_VERTICES_PER_POLYGON:
                    raise GeometryScriptError("Polygon vertex limit exceeded.")
                total_vertices += len(vertices)
                if total_vertices > MAX_TOTAL_VERTICES:
                    raise GeometryScriptError("Total vertex limit exceeded.")
                if len(polygons) >= MAX_EMITTED_POLYGONS:
                    raise GeometryScriptError("Generated polygon limit exceeded.")
                polygons.append(
                    EmittedPolygon(
                        name=f"{self.name_prefix}_emit{emit_idx}_poly{poly_idx}",
                        material=record.material,
                        vertices=tuple(vertices),
                        priority=record.priority,
                        height=record.height,
                        z=record.z,
                    )
                )
        return polygons

    def _flatten_polygons(self, geom) -> list[Any]:
        if geom.is_empty:
            return []
        geom_type = geom.geom_type
        if geom_type == "Polygon":
            return self._polygon_components(geom)
        if geom_type in {"MultiPolygon", "GeometryCollection"}:
            items: list[Any] = []
            for part in geom.geoms:
                items.extend(self._flatten_polygons(part))
            return items
        raise GeometryScriptError(f"Unsupported emitted geometry type: {geom_type}")

    def _polygon_components(self, poly) -> list[Any]:
        if poly.is_empty:
            return []
        if not poly.is_valid:
            raise GeometryScriptError("Invalid emitted polygon. Use clean(...) to repair it.")
        if not poly.interiors:
            return [poly]
        pieces: list[Any] = []
        for tri in self.shapely.triangulate(poly):
            clipped = tri.intersection(poly)
            if clipped.is_empty:
                continue
            for part in self._flatten_polygons_no_holes(clipped):
                if part.area > 1e-18:
                    pieces.append(part)
        return pieces

    def _flatten_polygons_no_holes(self, geom) -> list[Any]:
        if geom.is_empty:
            return []
        if geom.geom_type == "Polygon":
            if geom.interiors:
                raise GeometryScriptError("Could not decompose polygon holes.")
            return [geom]
        if geom.geom_type in {"MultiPolygon", "GeometryCollection"}:
            result: list[Any] = []
            for part in geom.geoms:
                result.extend(self._flatten_polygons_no_holes(part))
            return result
        return []

    def _polygon_vertices(self, polygon) -> list[tuple[float, float]]:
        coords = list(polygon.exterior.coords)
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]
        vertices = [(float(x), float(y)) for x, y, *_rest in coords]
        for x, y in vertices:
            self._check_coordinate(x)
            self._check_coordinate(y)
        return vertices
