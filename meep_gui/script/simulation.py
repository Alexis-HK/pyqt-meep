from __future__ import annotations

from ..primitives import geometry_kind, geometry_priority, material_kind, monitor_kind, source_kind
from ..validation import parse_complex_literal
from .common import line


def scene_uses_scripted_geometry(scene) -> bool:
    return any(obj.geometry.kind == "scripted" for obj in scene.objects)


def emit_scripted_geometry_helpers(lines: list[str]) -> None:
    for text in (
        "_SCRIPTED_MAX_IMPLICIT_DIMENSION = 512",
        "_SCRIPTED_MAX_IMPLICIT_CELLS = 100000",
        "_SCRIPTED_MAX_EMITTED_POLYGONS = 2000",
        "_SCRIPTED_MAX_VERTICES_PER_POLYGON = 4096",
        "_SCRIPTED_MAX_TOTAL_VERTICES = 50000",
        "_SCRIPTED_MAX_LIST_LENGTH = 10000",
        "_SCRIPTED_MAX_COORDINATE_MAGNITUDE = 1e6",
        "_scripted_pi = math.pi",
        "",
        "class _GeometryCollector:",
        "    def __init__(self):",
        "        self._entries = []",
        "        self._order = 0",
        "",
        "    def append(self, item, priority=0):",
        "        self._entries.append((int(priority), self._order, item))",
        "        self._order += 1",
        "",
        "    def objects(self):",
        "        return [item for _priority, _order, item in sorted(self._entries)]",
        "",
        "class _ScriptedMaterialRef:",
        "    def __init__(self, name, material):",
        "        self.name = name",
        "        self.material = material",
        "",
        "class _ScriptedMaterials:",
        "    def __init__(self, materials):",
        "        self._materials = materials",
        "",
        "    def __getitem__(self, name):",
        "        key = str(name)",
        "        if key not in self._materials:",
        "            raise KeyError(key)",
        "        return _ScriptedMaterialRef(key, self._materials[key])",
        "",
        "def _scripted_number(value):",
        "    if isinstance(value, bool) or not isinstance(value, (int, float)):",
        "        raise ValueError('Expected a number.')",
        "    value = float(value)",
        "    if not math.isfinite(value):",
        "        raise ValueError('Expected a finite number.')",
        "    return value",
        "",
        "def _scripted_int(value):",
        "    numeric = _scripted_number(value)",
        "    rounded = round(numeric)",
        "    if abs(numeric - rounded) > 1e-9:",
        "        raise ValueError('Expected an integer.')",
        "    return int(rounded)",
        "",
        "def _scripted_check_coordinate(value):",
        "    if abs(float(value)) > _SCRIPTED_MAX_COORDINATE_MAGNITUDE:",
        "        raise ValueError('Coordinate magnitude limit exceeded.')",
        "",
        "def _scripted_point(value):",
        "    if not isinstance(value, (list, tuple)) or len(value) != 2:",
        "        raise ValueError('Expected a 2D point.')",
        "    x = _scripted_number(value[0])",
        "    y = _scripted_number(value[1])",
        "    _scripted_check_coordinate(x)",
        "    _scripted_check_coordinate(y)",
        "    return x, y",
        "",
        "def _scripted_points(value):",
        "    if not isinstance(value, (list, tuple)):",
        "        raise ValueError('Expected a list of points.')",
        "    if len(value) > _SCRIPTED_MAX_LIST_LENGTH:",
        "        raise ValueError('List length limit exceeded.')",
        "    return [_scripted_point(point) for point in value]",
        "",
        "def _scripted_wrap(geom):",
        "    if geom is None:",
        "        raise ValueError('Geometry operation produced no geometry.')",
        "    if not geom.is_empty and not geom.is_valid:",
        "        raise ValueError('Invalid geometry. Use clean(...) to repair it explicitly.')",
        "    return geom",
        "",
        "def _scripted_rect(*, center=(0, 0), size=(1, 1)):",
        "    cx, cy = _scripted_point(center)",
        "    sx, sy = _scripted_point(size)",
        "    if sx <= 0 or sy <= 0:",
        "        raise ValueError('rect size must be positive.')",
        "    return _scripted_wrap(_shapely_box(cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2))",
        "",
        "def _scripted_regular_polygon(center, rx, ry, segments):",
        "    cx, cy = _scripted_point(center)",
        "    rx = _scripted_number(rx)",
        "    ry = _scripted_number(ry)",
        "    segments = _scripted_int(segments)",
        "    if rx <= 0 or ry <= 0:",
        "        raise ValueError('Radius must be positive.')",
        "    if segments < 8 or segments > _SCRIPTED_MAX_VERTICES_PER_POLYGON:",
        "        raise ValueError('segments must be between 8 and the vertex limit.')",
        "    points = [",
        "        (cx + rx * math.cos(2 * math.pi * i / segments), cy + ry * math.sin(2 * math.pi * i / segments))",
        "        for i in range(segments)",
        "    ]",
        "    return _scripted_polygon(points=points)",
        "",
        "def _scripted_circle(*, center=(0, 0), radius=1, segments=32):",
        "    return _scripted_regular_polygon(center, radius, radius, segments)",
        "",
        "def _scripted_ellipse(*, center=(0, 0), radius=(1, 1), segments=32):",
        "    rx, ry = _scripted_point(radius)",
        "    return _scripted_regular_polygon(center, rx, ry, segments)",
        "",
        "def _scripted_polygon(*, points):",
        "    point_list = _scripted_points(points)",
        "    if len(point_list) < 3:",
        "        raise ValueError('polygon requires at least three points.')",
        "    return _scripted_wrap(_ShapelyPolygon(point_list))",
        "",
        "def _scripted_path(*, points, width, cap='round', join='round', segments=8):",
        "    point_list = _scripted_points(points)",
        "    if len(point_list) < 2:",
        "        raise ValueError('path requires at least two points.')",
        "    width_value = _scripted_number(width)",
        "    if width_value <= 0:",
        "        raise ValueError('path width must be positive.')",
        "    cap_style = {'round': 1, 'flat': 2, 'square': 3}.get(str(cap))",
        "    join_style = {'round': 1, 'mitre': 2, 'miter': 2, 'bevel': 3}.get(str(join))",
        "    if cap_style is None:",
        "        raise ValueError('Unsupported path cap.')",
        "    if join_style is None:",
        "        raise ValueError('Unsupported path join.')",
        "    return _scripted_wrap(_ShapelyLineString(point_list).buffer(",
        "        width_value / 2,",
        "        quad_segs=_scripted_int(segments),",
        "        cap_style=cap_style,",
        "        join_style=join_style,",
        "    ))",
        "",
        "def _scripted_union(*items):",
        "    if not items:",
        "        raise ValueError('union requires at least one geometry.')",
        "    return _scripted_wrap(_shapely_unary_union(list(items)))",
        "",
        "def _scripted_difference(first, *rest):",
        "    geom = first",
        "    if rest:",
        "        geom = geom.difference(_shapely_unary_union(list(rest)))",
        "    return _scripted_wrap(geom)",
        "",
        "def _scripted_intersection(first, *rest):",
        "    geom = first",
        "    for item in rest:",
        "        geom = geom.intersection(item)",
        "    return _scripted_wrap(geom)",
        "",
        "def _scripted_move(g, *, dx=0, dy=0):",
        "    return _scripted_wrap(_shapely_translate(g, xoff=_scripted_number(dx), yoff=_scripted_number(dy)))",
        "",
        "def _scripted_rotate(g, *, angle=0, origin=(0, 0), degrees=True):",
        "    return _scripted_wrap(_shapely_rotate(",
        "        g, _scripted_number(angle), origin=_scripted_point(origin), use_radians=not bool(degrees)",
        "    ))",
        "",
        "def _scripted_scale(g, *, sx=1, sy=1, origin=(0, 0)):",
        "    return _scripted_wrap(_shapely_scale(",
        "        g, xfact=_scripted_number(sx), yfact=_scripted_number(sy), origin=_scripted_point(origin)",
        "    ))",
        "",
        "def _scripted_mirror_x(g, *, x=0):",
        "    return _scripted_wrap(_shapely_scale(g, xfact=-1, yfact=1, origin=(_scripted_number(x), 0)))",
        "",
        "def _scripted_mirror_y(g, *, y=0):",
        "    return _scripted_wrap(_shapely_scale(g, xfact=1, yfact=-1, origin=(0, _scripted_number(y))))",
        "",
        "def _scripted_clean(g):",
        "    return _scripted_wrap(g.buffer(0))",
        "",
        "def _scripted_simplify(g, tolerance):",
        "    return _scripted_wrap(g.simplify(_scripted_number(tolerance), preserve_topology=True))",
        "",
        "def _scripted_linspace(start, stop, count):",
        "    count_int = _scripted_int(count)",
        "    if count_int <= 0:",
        "        raise ValueError('linspace count must be positive.')",
        "    if count_int > _SCRIPTED_MAX_LIST_LENGTH:",
        "        raise ValueError('linspace count exceeds the list length limit.')",
        "    start_value = _scripted_number(start)",
        "    stop_value = _scripted_number(stop)",
        "    if count_int == 1:",
        "        return [float(stop_value)]",
        "    step = (stop_value - start_value) / (count_int - 1)",
        "    return [start_value + i * step for i in range(count_int)]",
        "",
        "def _scripted_reverse(points):",
        "    if not isinstance(points, (list, tuple)):",
        "        raise ValueError('reverse expects a list or tuple.')",
        "    return list(reversed(points))",
        "",
        "def _scripted_range(*args):",
        "    if not 1 <= len(args) <= 3:",
        "        raise ValueError('range expects one to three arguments.')",
        "    values = list(range(*[_scripted_int(arg) for arg in args]))",
        "    if len(values) > _SCRIPTED_MAX_LIST_LENGTH:",
        "        raise ValueError('range exceeds the list length limit.')",
        "    return values",
        "",
        "def _scripted_bounds(value):",
        "    if not isinstance(value, (list, tuple)) or len(value) != 4:",
        "        raise ValueError('bounds must be (xmin, ymin, xmax, ymax).')",
        "    xmin, ymin, xmax, ymax = (_scripted_number(item) for item in value)",
        "    if xmax <= xmin or ymax <= ymin:",
        "        raise ValueError('bounds max values must be greater than min values.')",
        "    for coord in (xmin, ymin, xmax, ymax):",
        "        _scripted_check_coordinate(coord)",
        "    return xmin, ymin, xmax, ymax",
        "",
        "def _scripted_resolution(value):",
        "    if isinstance(value, (list, tuple)):",
        "        if len(value) != 2:",
        "            raise ValueError('resolution tuple must have two values.')",
        "        nx, ny = _scripted_int(value[0]), _scripted_int(value[1])",
        "    else:",
        "        nx = ny = _scripted_int(value)",
        "    if nx <= 0 or ny <= 0:",
        "        raise ValueError('resolution must be positive.')",
        "    if nx > _SCRIPTED_MAX_IMPLICIT_DIMENSION or ny > _SCRIPTED_MAX_IMPLICIT_DIMENSION:",
        "        raise ValueError('resolution dimension limit exceeded.')",
        "    if nx * ny > _SCRIPTED_MAX_IMPLICIT_CELLS:",
        "        raise ValueError('resolution cell limit exceeded.')",
        "    return nx, ny",
        "",
        "def _scripted_region(expr, *, parameter_values, bounds, resolution=256, rng=None):",
        "    xmin, ymin, xmax, ymax = _scripted_bounds(bounds)",
        "    nx, ny = _scripted_resolution(resolution)",
        "    dx = (xmax - xmin) / nx",
        "    dy = (ymax - ymin) / ny",
        "    env_base = dict(parameter_values)",
        "    env_base.update({",
        "        'pi': math.pi,",
        "        'sin': math.sin,",
        "        'cos': math.cos,",
        "        'tan': math.tan,",
        "        'sqrt': math.sqrt,",
        "        'abs': abs,",
        "        'exp': math.exp,",
        "        'log': math.log,",
        "        'min': min,",
        "        'max': max,",
        "        'params': parameter_values,",
        "    })",
        "    if rng is not None:",
        "        env_base.update({'uniform': rng.uniform, 'gauss': rng.gauss})",
        "    rects = []",
        "    for j in range(ny):",
        "        run_start = None",
        "        y_center = ymin + (j + 0.5) * dy",
        "        for i in range(nx):",
        "            x_center = xmin + (i + 0.5) * dx",
        "            env = dict(env_base)",
        "            env.update({'x': x_center, 'y': y_center})",
        "            value = eval(str(expr), {'__builtins__': {}}, env)",
        "            if not isinstance(value, bool):",
        "                raise ValueError('region expression must evaluate to a boolean.')",
        "            if value and run_start is None:",
        "                run_start = i",
        "            if (not value or i == nx - 1) and run_start is not None:",
        "                end = i + 1 if value and i == nx - 1 else i",
        "                rects.append(_shapely_box(",
        "                    xmin + run_start * dx, ymin + j * dy, xmin + end * dx, ymin + (j + 1) * dy",
        "                ))",
        "                run_start = None",
        "    if not rects:",
        "        return _scripted_wrap(_ShapelyGeometryCollection())",
        "    return _scripted_wrap(_shapely_unary_union(rects))",
        "",
        "def _scripted_flatten_polygons_no_holes(geom):",
        "    if geom.is_empty:",
        "        return []",
        "    if geom.geom_type == 'Polygon':",
        "        if geom.interiors:",
        "            raise ValueError('Could not decompose polygon holes.')",
        "        return [geom]",
        "    if geom.geom_type in {'MultiPolygon', 'GeometryCollection'}:",
        "        result = []",
        "        for part in geom.geoms:",
        "            result.extend(_scripted_flatten_polygons_no_holes(part))",
        "        return result",
        "    return []",
        "",
        "def _scripted_polygon_components(poly):",
        "    if poly.is_empty:",
        "        return []",
        "    if not poly.is_valid:",
        "        raise ValueError('Invalid emitted polygon. Use clean(...) to repair it.')",
        "    if not poly.interiors:",
        "        return [poly]",
        "    pieces = []",
        "    for tri in _shapely_triangulate(poly):",
        "        clipped = tri.intersection(poly)",
        "        if clipped.is_empty:",
        "            continue",
        "        for part in _scripted_flatten_polygons_no_holes(clipped):",
        "            if part.area > 1e-18:",
        "                pieces.append(part)",
        "    return pieces",
        "",
        "def _scripted_flatten_polygons(geom):",
        "    if geom.is_empty:",
        "        return []",
        "    if geom.geom_type == 'Polygon':",
        "        return _scripted_polygon_components(geom)",
        "    if geom.geom_type in {'MultiPolygon', 'GeometryCollection'}:",
        "        items = []",
        "        for part in geom.geoms:",
        "            items.extend(_scripted_flatten_polygons(part))",
        "        return items",
        "    raise ValueError(f'Unsupported emitted geometry type: {geom.geom_type}')",
        "",
        "def _scripted_polygon_vertices(polygon):",
        "    coords = list(polygon.exterior.coords)",
        "    if len(coords) > 1 and coords[0] == coords[-1]:",
        "        coords = coords[:-1]",
        "    vertices = [(float(x), float(y)) for x, y, *_rest in coords]",
        "    for x, y in vertices:",
        "        _scripted_check_coordinate(x)",
        "        _scripted_check_coordinate(y)",
        "    return vertices",
        "",
        "def _append_scripted_records(target, records):",
        "    total_vertices = 0",
        "    emitted_count = 0",
        "    for geom, material_name, material, _height, _z, priority in records:",
        "        for polygon in _scripted_flatten_polygons(geom):",
        "            vertices_xy = _scripted_polygon_vertices(polygon)",
        "            if not vertices_xy:",
        "                continue",
        "            if len(vertices_xy) > _SCRIPTED_MAX_VERTICES_PER_POLYGON:",
        "                raise ValueError('Polygon vertex limit exceeded.')",
        "            total_vertices += len(vertices_xy)",
        "            if total_vertices > _SCRIPTED_MAX_TOTAL_VERTICES:",
        "                raise ValueError('Total vertex limit exceeded.')",
        "            if emitted_count >= _SCRIPTED_MAX_EMITTED_POLYGONS:",
        "                raise ValueError('Generated polygon limit exceeded.')",
        "            prism = mp.Prism(",
        "                vertices=[mp.Vector3(x, y, 0) for x, y in vertices_xy],",
        "                height=mp.inf,",
        "                material=material,",
        "            )",
        "            target.append(prism, priority=priority)",
        "            emitted_count += 1",
        "    if emitted_count == 0:",
        "        raise ValueError('Script emitted no polygons.')",
        "",
    ):
        line(lines, text)


def emit_parameters(lines: list[str], scene) -> None:
    if not scene.parameters:
        return
    line(lines, "# Parameters")
    for param in scene.parameters:
        if param.name and param.expr:
            line(lines, f"{param.name} = {param.expr}")
    line(lines)


def emit_materials(lines: list[str], scene) -> None:
    if scene.media:
        line(lines, "# Materials")
        line(lines, "materials = {}")
        for medium in scene.media:
            for statement in material_kind(medium.kind).emit_script_medium(medium):
                line(lines, statement)
        line(lines)
    else:
        line(lines, "materials = {}")
        line(lines)


def emit_geometry(lines: list[str], var_name: str, objects) -> None:
    use_collector = any(obj.geometry.kind == "scripted" for obj in objects)
    line(lines, f"{var_name} = _GeometryCollector()" if use_collector else f"{var_name} = []")
    ordered_objects = sorted(
        enumerate(objects),
        key=lambda item: (geometry_priority(item[1]), item[0]),
    )
    for idx, (_order, obj) in enumerate(ordered_objects, start=1):
        for statement in geometry_kind(obj.geometry.kind).emit_script_object(var_name, idx, obj):
            line(lines, statement)
    if use_collector:
        line(lines, f"{var_name} = {var_name}.objects()")


def emit_sources(lines: list[str], var_name: str, sources) -> None:
    line(lines, f"{var_name} = []")
    for idx, src in enumerate(sources, start=1):
        for statement in source_kind(src.kind).emit_script_source(var_name, idx, src):
            line(lines, statement)


def emit_boundary_layers(lines: list[str], var_name: str, domain) -> None:
    line(lines, f"{var_name} = []")
    if domain.pml_mode in {"x", "both"}:
        line(lines, f"{var_name}.append(mp.PML(thickness={domain.pml_width_expr}, direction=mp.X))")
    if domain.pml_mode in {"y", "both"}:
        line(lines, f"{var_name}.append(mp.PML(thickness={domain.pml_width_expr}, direction=mp.Y))")


def simulation_k_point_expr(domain) -> str | None:
    if not getattr(domain, "periodic_enabled", False):
        return None
    return (
        f"mp.Vector3({domain.k_point_x_expr}, {domain.k_point_y_expr}, {domain.k_point_z_expr})"
    )


def simulation_cylindrical_kwargs(domain) -> tuple[str, ...]:
    if not getattr(domain, "cylindrical_enabled", False):
        return ()
    return ("dimensions=mp.CYLINDRICAL", f"m={domain.cylindrical_m_expr}")


def emit_symmetries(lines: list[str], var_name: str, symmetries) -> None:
    line(lines, f"{var_name} = []")
    for symmetry in symmetries:
        kind = symmetry.kind.lower()
        ctor = {"mirror": "Mirror", "rotate2": "Rotate2", "rotate4": "Rotate4"}.get(kind)
        if ctor:
            phase = symmetry.phase_expr.strip()
            try:
                parse_complex_literal(phase)
            except ValueError as exc:
                raise ValueError(f"symmetry '{symmetry.name}' phase: {exc}") from exc
            line(
                lines,
                f"{var_name}.append(mp.{ctor}(mp.{symmetry.direction.upper()}, "
                f"phase={phase}))",
            )


def emit_flux_handles(lines: list[str], handles_var: str, sim_var: str, monitors) -> None:
    line(lines, f"{handles_var} = {{}}")
    for mon in monitors:
        line(
            lines,
            f"{handles_var}['{mon.name}'] = {monitor_kind(mon.kind).script_add_flux_expr(sim_var, mon)}",
        )
