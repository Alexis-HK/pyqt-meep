from math import sqrt, exp, sin, cos, tan, log, log10
import csv
import os
import math
import meep as mp
from shapely.affinity import rotate as _shapely_rotate
from shapely.affinity import scale as _shapely_scale
from shapely.affinity import translate as _shapely_translate
from shapely.geometry import GeometryCollection as _ShapelyGeometryCollection
from shapely.geometry import LineString as _ShapelyLineString
from shapely.geometry import Polygon as _ShapelyPolygon
from shapely.geometry import box as _shapely_box
from shapely.ops import triangulate as _shapely_triangulate
from shapely.ops import unary_union as _shapely_unary_union

script_dir = os.path.dirname(os.path.abspath(__file__))

def _eval_numeric(expr, scope):
    env = dict(globals())
    env.update(scope)
    return eval(str(expr), {'__builtins__': {}}, env)

def _build_parameter_values(overrides=None):
    parameter_overrides = dict(overrides or {})
    parameter_values = {}
    if 'wg_width' in parameter_overrides:
        parameter_values['wg_width'] = _eval_numeric(str(parameter_overrides['wg_width']), parameter_values)
    else:
        parameter_values['wg_width'] = _eval_numeric('0.5', parameter_values)
    if 'taper_length' in parameter_overrides:
        parameter_values['taper_length'] = _eval_numeric(str(parameter_overrides['taper_length']), parameter_values)
    else:
        parameter_values['taper_length'] = _eval_numeric('6.0', parameter_values)
    if 'grating_length' in parameter_overrides:
        parameter_values['grating_length'] = _eval_numeric(str(parameter_overrides['grating_length']), parameter_values)
    else:
        parameter_values['grating_length'] = _eval_numeric('8.0', parameter_values)
    if 'grating_width' in parameter_overrides:
        parameter_values['grating_width'] = _eval_numeric(str(parameter_overrides['grating_width']), parameter_values)
    else:
        parameter_values['grating_width'] = _eval_numeric('8.0', parameter_values)
    if 'period' in parameter_overrides:
        parameter_values['period'] = _eval_numeric(str(parameter_overrides['period']), parameter_values)
    else:
        parameter_values['period'] = _eval_numeric('0.72', parameter_values)
    if 'duty' in parameter_overrides:
        parameter_values['duty'] = _eval_numeric(str(parameter_overrides['duty']), parameter_values)
    else:
        parameter_values['duty'] = _eval_numeric('0.45', parameter_values)
    if 'periods' in parameter_overrides:
        parameter_values['periods'] = _eval_numeric(str(parameter_overrides['periods']), parameter_values)
    else:
        parameter_values['periods'] = _eval_numeric('10', parameter_values)
    if 'input_length' in parameter_overrides:
        parameter_values['input_length'] = _eval_numeric(str(parameter_overrides['input_length']), parameter_values)
    else:
        parameter_values['input_length'] = _eval_numeric('4.0', parameter_values)
    if 'thickness' in parameter_overrides:
        parameter_values['thickness'] = _eval_numeric(str(parameter_overrides['thickness']), parameter_values)
    else:
        parameter_values['thickness'] = _eval_numeric('0.22', parameter_values)
    return parameter_values

_SCRIPTED_MAX_IMPLICIT_DIMENSION = 512
_SCRIPTED_MAX_IMPLICIT_CELLS = 100000
_SCRIPTED_MAX_EMITTED_POLYGONS = 2000
_SCRIPTED_MAX_VERTICES_PER_POLYGON = 4096
_SCRIPTED_MAX_TOTAL_VERTICES = 50000
_SCRIPTED_MAX_LIST_LENGTH = 10000
_SCRIPTED_MAX_COORDINATE_MAGNITUDE = 1e6
_scripted_pi = math.pi

class _GeometryCollector:
    def __init__(self):
        self._entries = []
        self._order = 0

    def append(self, item, priority=0):
        self._entries.append((int(priority), self._order, item))
        self._order += 1

    def objects(self):
        return [item for _priority, _order, item in sorted(self._entries)]

class _ScriptedMaterialRef:
    def __init__(self, name, material):
        self.name = name
        self.material = material

class _ScriptedMaterials:
    def __init__(self, materials):
        self._materials = materials

    def __getitem__(self, name):
        key = str(name)
        if key not in self._materials:
            raise KeyError(key)
        return _ScriptedMaterialRef(key, self._materials[key])

def _scripted_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Expected a number.')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Expected a finite number.')
    return value

def _scripted_int(value):
    numeric = _scripted_number(value)
    rounded = round(numeric)
    if abs(numeric - rounded) > 1e-9:
        raise ValueError('Expected an integer.')
    return int(rounded)

def _scripted_check_coordinate(value):
    if abs(float(value)) > _SCRIPTED_MAX_COORDINATE_MAGNITUDE:
        raise ValueError('Coordinate magnitude limit exceeded.')

def _scripted_point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('Expected a 2D point.')
    x = _scripted_number(value[0])
    y = _scripted_number(value[1])
    _scripted_check_coordinate(x)
    _scripted_check_coordinate(y)
    return x, y

def _scripted_points(value):
    if not isinstance(value, (list, tuple)):
        raise ValueError('Expected a list of points.')
    if len(value) > _SCRIPTED_MAX_LIST_LENGTH:
        raise ValueError('List length limit exceeded.')
    return [_scripted_point(point) for point in value]

def _scripted_wrap(geom):
    if geom is None:
        raise ValueError('Geometry operation produced no geometry.')
    if not geom.is_empty and not geom.is_valid:
        raise ValueError('Invalid geometry. Use clean(...) to repair it explicitly.')
    return geom

def _scripted_rect(*, center=(0, 0), size=(1, 1)):
    cx, cy = _scripted_point(center)
    sx, sy = _scripted_point(size)
    if sx <= 0 or sy <= 0:
        raise ValueError('rect size must be positive.')
    return _scripted_wrap(_shapely_box(cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2))

def _scripted_regular_polygon(center, rx, ry, segments):
    cx, cy = _scripted_point(center)
    rx = _scripted_number(rx)
    ry = _scripted_number(ry)
    segments = _scripted_int(segments)
    if rx <= 0 or ry <= 0:
        raise ValueError('Radius must be positive.')
    if segments < 8 or segments > _SCRIPTED_MAX_VERTICES_PER_POLYGON:
        raise ValueError('segments must be between 8 and the vertex limit.')
    points = [
        (cx + rx * math.cos(2 * math.pi * i / segments), cy + ry * math.sin(2 * math.pi * i / segments))
        for i in range(segments)
    ]
    return _scripted_polygon(points=points)

def _scripted_circle(*, center=(0, 0), radius=1, segments=32):
    return _scripted_regular_polygon(center, radius, radius, segments)

def _scripted_ellipse(*, center=(0, 0), radius=(1, 1), segments=32):
    rx, ry = _scripted_point(radius)
    return _scripted_regular_polygon(center, rx, ry, segments)

def _scripted_polygon(*, points):
    point_list = _scripted_points(points)
    if len(point_list) < 3:
        raise ValueError('polygon requires at least three points.')
    return _scripted_wrap(_ShapelyPolygon(point_list))

def _scripted_path(*, points, width, cap='round', join='round', segments=8):
    point_list = _scripted_points(points)
    if len(point_list) < 2:
        raise ValueError('path requires at least two points.')
    width_value = _scripted_number(width)
    if width_value <= 0:
        raise ValueError('path width must be positive.')
    cap_style = {'round': 1, 'flat': 2, 'square': 3}.get(str(cap))
    join_style = {'round': 1, 'mitre': 2, 'miter': 2, 'bevel': 3}.get(str(join))
    if cap_style is None:
        raise ValueError('Unsupported path cap.')
    if join_style is None:
        raise ValueError('Unsupported path join.')
    return _scripted_wrap(_ShapelyLineString(point_list).buffer(
        width_value / 2,
        quad_segs=_scripted_int(segments),
        cap_style=cap_style,
        join_style=join_style,
    ))

def _scripted_union(*items):
    if not items:
        raise ValueError('union requires at least one geometry.')
    return _scripted_wrap(_shapely_unary_union(list(items)))

def _scripted_difference(first, *rest):
    geom = first
    if rest:
        geom = geom.difference(_shapely_unary_union(list(rest)))
    return _scripted_wrap(geom)

def _scripted_intersection(first, *rest):
    geom = first
    for item in rest:
        geom = geom.intersection(item)
    return _scripted_wrap(geom)

def _scripted_move(g, *, dx=0, dy=0):
    return _scripted_wrap(_shapely_translate(g, xoff=_scripted_number(dx), yoff=_scripted_number(dy)))

def _scripted_rotate(g, *, angle=0, origin=(0, 0), degrees=True):
    return _scripted_wrap(_shapely_rotate(
        g, _scripted_number(angle), origin=_scripted_point(origin), use_radians=not bool(degrees)
    ))

def _scripted_scale(g, *, sx=1, sy=1, origin=(0, 0)):
    return _scripted_wrap(_shapely_scale(
        g, xfact=_scripted_number(sx), yfact=_scripted_number(sy), origin=_scripted_point(origin)
    ))

def _scripted_mirror_x(g, *, x=0):
    return _scripted_wrap(_shapely_scale(g, xfact=-1, yfact=1, origin=(_scripted_number(x), 0)))

def _scripted_mirror_y(g, *, y=0):
    return _scripted_wrap(_shapely_scale(g, xfact=1, yfact=-1, origin=(0, _scripted_number(y))))

def _scripted_clean(g):
    return _scripted_wrap(g.buffer(0))

def _scripted_simplify(g, tolerance):
    return _scripted_wrap(g.simplify(_scripted_number(tolerance), preserve_topology=True))

def _scripted_linspace(start, stop, count):
    count_int = _scripted_int(count)
    if count_int <= 0:
        raise ValueError('linspace count must be positive.')
    if count_int > _SCRIPTED_MAX_LIST_LENGTH:
        raise ValueError('linspace count exceeds the list length limit.')
    start_value = _scripted_number(start)
    stop_value = _scripted_number(stop)
    if count_int == 1:
        return [float(stop_value)]
    step = (stop_value - start_value) / (count_int - 1)
    return [start_value + i * step for i in range(count_int)]

def _scripted_reverse(points):
    if not isinstance(points, (list, tuple)):
        raise ValueError('reverse expects a list or tuple.')
    return list(reversed(points))

def _scripted_range(*args):
    if not 1 <= len(args) <= 3:
        raise ValueError('range expects one to three arguments.')
    values = list(range(*[_scripted_int(arg) for arg in args]))
    if len(values) > _SCRIPTED_MAX_LIST_LENGTH:
        raise ValueError('range exceeds the list length limit.')
    return values

def _scripted_bounds(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError('bounds must be (xmin, ymin, xmax, ymax).')
    xmin, ymin, xmax, ymax = (_scripted_number(item) for item in value)
    if xmax <= xmin or ymax <= ymin:
        raise ValueError('bounds max values must be greater than min values.')
    for coord in (xmin, ymin, xmax, ymax):
        _scripted_check_coordinate(coord)
    return xmin, ymin, xmax, ymax

def _scripted_resolution(value):
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise ValueError('resolution tuple must have two values.')
        nx, ny = _scripted_int(value[0]), _scripted_int(value[1])
    else:
        nx = ny = _scripted_int(value)
    if nx <= 0 or ny <= 0:
        raise ValueError('resolution must be positive.')
    if nx > _SCRIPTED_MAX_IMPLICIT_DIMENSION or ny > _SCRIPTED_MAX_IMPLICIT_DIMENSION:
        raise ValueError('resolution dimension limit exceeded.')
    if nx * ny > _SCRIPTED_MAX_IMPLICIT_CELLS:
        raise ValueError('resolution cell limit exceeded.')
    return nx, ny

def _scripted_region(expr, *, parameter_values, bounds, resolution=256):
    xmin, ymin, xmax, ymax = _scripted_bounds(bounds)
    nx, ny = _scripted_resolution(resolution)
    dx = (xmax - xmin) / nx
    dy = (ymax - ymin) / ny
    env_base = dict(parameter_values)
    env_base.update({
        'pi': math.pi,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'sqrt': math.sqrt,
        'abs': abs,
        'exp': math.exp,
        'log': math.log,
        'min': min,
        'max': max,
        'params': parameter_values,
    })
    rects = []
    for j in range(ny):
        run_start = None
        y_center = ymin + (j + 0.5) * dy
        for i in range(nx):
            x_center = xmin + (i + 0.5) * dx
            env = dict(env_base)
            env.update({'x': x_center, 'y': y_center})
            value = eval(str(expr), {'__builtins__': {}}, env)
            if not isinstance(value, bool):
                raise ValueError('region expression must evaluate to a boolean.')
            if value and run_start is None:
                run_start = i
            if (not value or i == nx - 1) and run_start is not None:
                end = i + 1 if value and i == nx - 1 else i
                rects.append(_shapely_box(
                    xmin + run_start * dx, ymin + j * dy, xmin + end * dx, ymin + (j + 1) * dy
                ))
                run_start = None
    if not rects:
        return _scripted_wrap(_ShapelyGeometryCollection())
    return _scripted_wrap(_shapely_unary_union(rects))

def _scripted_flatten_polygons_no_holes(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        if geom.interiors:
            raise ValueError('Could not decompose polygon holes.')
        return [geom]
    if geom.geom_type in {'MultiPolygon', 'GeometryCollection'}:
        result = []
        for part in geom.geoms:
            result.extend(_scripted_flatten_polygons_no_holes(part))
        return result
    return []

def _scripted_polygon_components(poly):
    if poly.is_empty:
        return []
    if not poly.is_valid:
        raise ValueError('Invalid emitted polygon. Use clean(...) to repair it.')
    if not poly.interiors:
        return [poly]
    pieces = []
    for tri in _shapely_triangulate(poly):
        clipped = tri.intersection(poly)
        if clipped.is_empty:
            continue
        for part in _scripted_flatten_polygons_no_holes(clipped):
            if part.area > 1e-18:
                pieces.append(part)
    return pieces

def _scripted_flatten_polygons(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        return _scripted_polygon_components(geom)
    if geom.geom_type in {'MultiPolygon', 'GeometryCollection'}:
        items = []
        for part in geom.geoms:
            items.extend(_scripted_flatten_polygons(part))
        return items
    raise ValueError(f'Unsupported emitted geometry type: {geom.geom_type}')

def _scripted_polygon_vertices(polygon):
    coords = list(polygon.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    vertices = [(float(x), float(y)) for x, y, *_rest in coords]
    for x, y in vertices:
        _scripted_check_coordinate(x)
        _scripted_check_coordinate(y)
    return vertices

def _append_scripted_records(target, records):
    total_vertices = 0
    emitted_count = 0
    for geom, material_name, material, _height, _z, priority in records:
        for polygon in _scripted_flatten_polygons(geom):
            vertices_xy = _scripted_polygon_vertices(polygon)
            if not vertices_xy:
                continue
            if len(vertices_xy) > _SCRIPTED_MAX_VERTICES_PER_POLYGON:
                raise ValueError('Polygon vertex limit exceeded.')
            total_vertices += len(vertices_xy)
            if total_vertices > _SCRIPTED_MAX_TOTAL_VERTICES:
                raise ValueError('Total vertex limit exceeded.')
            if emitted_count >= _SCRIPTED_MAX_EMITTED_POLYGONS:
                raise ValueError('Generated polygon limit exceeded.')
            prism = mp.Prism(
                vertices=[mp.Vector3(x, y, 0) for x, y in vertices_xy],
                height=mp.inf,
                material=material,
            )
            target.append(prism, priority=priority)
            emitted_count += 1
    if emitted_count == 0:
        raise ValueError('Script emitted no polygons.')

def _preview_symmetry_summary(symmetry_specs):
    if not symmetry_specs:
        return 'Symmetries: none'
    parts = []
    for kind, direction, phase_expr in symmetry_specs:
        kind = str(kind).strip().lower()
        direction = str(direction).strip().lower()
        phase = str(phase_expr).strip()
        if kind == 'mirror':
            prefix = 'm'
        elif kind == 'rotate2':
            prefix = 'r2'
        elif kind == 'rotate4':
            prefix = 'r4'
        else:
            prefix = kind or 'sym'
        parts.append(f'{prefix}{direction}({phase})')
    return 'Symmetries: ' + ', '.join(parts)

def _resolve_preview_monitor_regions(monitor_specs, parameter_values):
    regions = []
    for center_x_expr, center_y_expr, size_x_expr, size_y_expr in monitor_specs:
        try:
            cx = _eval_numeric(center_x_expr, dict(parameter_values))
            cy = _eval_numeric(center_y_expr, dict(parameter_values))
            sx = _eval_numeric(size_x_expr, dict(parameter_values))
            sy = _eval_numeric(size_y_expr, dict(parameter_values))
        except Exception:
            continue
        regions.append((cx, cy, sx, sy))
    return regions

def _save_domain_preview_png(
    path,
    sim,
    parameter_values,
    monitor_specs,
    symmetry_specs,
    *,
    title='Domain Preview',
    marker_expr=None,
):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle
    fig = Figure(figsize=(6, 5), dpi=120)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    try:
        sim.plot2D(ax=ax)
        for cx, cy, sx, sy in _resolve_preview_monitor_regions(monitor_specs, parameter_values):
            ax.add_patch(
                Rectangle(
                    (cx - sx / 2, cy - sy / 2),
                    sx,
                    sy,
                    fill=False,
                    edgecolor='#f59e0b',
                    linewidth=1.1,
                    linestyle='--',
                )
            )
        if marker_expr is not None:
            try:
                hx = _eval_numeric(marker_expr[0], dict(parameter_values))
                hy = _eval_numeric(marker_expr[1], dict(parameter_values))
                ax.plot(hx, hy, marker='x', color='#006400', markersize=7, markeredgewidth=1.6)
            except Exception:
                pass
        ax.set_title(title)
        ax.text(
            0.02,
            0.98,
            _preview_symmetry_summary(symmetry_specs),
            transform=ax.transAxes,
            va='top',
            ha='left',
            fontsize=8.5,
            bbox={'facecolor': 'white', 'edgecolor': '#cccccc', 'alpha': 0.85, 'pad': 3},
        )
    except Exception as exc:
        ax.clear()
        ax.text(0.5, 0.5, f'Preview error:\n{exc}', transform=ax.transAxes, ha='center', va='center')
    fig.tight_layout()
    fig.savefig(path)

def run_analysis(out_dir, overrides=None):
    os.makedirs(out_dir, exist_ok=True)
    # Parameters
    parameter_values = _build_parameter_values(overrides)
    wg_width = parameter_values['wg_width']
    taper_length = parameter_values['taper_length']
    grating_length = parameter_values['grating_length']
    grating_width = parameter_values['grating_width']
    period = parameter_values['period']
    duty = parameter_values['duty']
    periods = parameter_values['periods']
    input_length = parameter_values['input_length']
    thickness = parameter_values['thickness']

    # Materials
    materials = {}
    air = mp.Medium(index=1)
    materials['air'] = air
    silicon = mp.Medium(index=3)
    materials['silicon'] = silicon

    # Geometry
    geometry = _GeometryCollector()
    def _build_geometry_scripted_1(target=geometry, parameter_values=parameter_values, material_map=materials):
        params = dict(parameter_values)
        materials = _ScriptedMaterials(material_map)
        records = []

        def emit(g, *, material, height=0, z=0, priority=0):
            if not isinstance(material, _ScriptedMaterialRef):
                raise ValueError('emit material must be materials["name"].')
            records.append((g, material.name, material.material, float(height), float(z), int(priority)))

        pi = _scripted_pi
        rect = _scripted_rect
        circle = _scripted_circle
        ellipse = _scripted_ellipse
        polygon = _scripted_polygon
        path = _scripted_path
        union = _scripted_union
        difference = _scripted_difference
        intersection = _scripted_intersection
        move = _scripted_move
        rotate = _scripted_rotate
        scale = _scripted_scale
        mirror_x = _scripted_mirror_x
        mirror_y = _scripted_mirror_y
        clean = _scripted_clean
        simplify = _scripted_simplify
        linspace = _scripted_linspace
        reverse = _scripted_reverse
        range = _scripted_range
        region = lambda expr, *, bounds, resolution=256: _scripted_region(
            expr, parameter_values=parameter_values, bounds=bounds, resolution=resolution
        )

        # Original scripted geometry source
        wg = params["wg_width"]
        taper_len = params["taper_length"]
        grating_len = params["grating_length"]
        grating_width = params["grating_width"]
        period = params["period"]
        duty = params["duty"]
        n = params["periods"]
        input_len = params["input_length"]

        input_wg = rect(
            center=(-input_len / 2, 0),
            size=(input_len, wg)
        )

        taper = polygon(points=[
            (0, -wg / 2),
            (taper_len, -grating_width / 2),
            (taper_len, grating_width / 2),
            (0, wg / 2)
        ])

        grating_base = rect(
            center=(taper_len + grating_len / 2, 0),
            size=(grating_len, grating_width)
        )

        silicon = union(input_wg, taper, grating_base)

        slots = []

        for i in range(n):
            x0 = taper_len + i * period
            slot_width = period * duty
            slot_center = x0 + slot_width / 2

            slots.append(rect(
                center=(slot_center, 0),
                size=(slot_width, grating_width)
            ))

        emit(silicon, material=materials["silicon"], height=params["thickness"])
        emit(union(*slots), material=materials["air"], height=params["thickness"], priority=10)

        _append_scripted_records(target, records)

    _build_geometry_scripted_1()
    geometry = geometry.objects()

    # Sources
    sources = []

    # Simulation
    boundary_layers = []
    boundary_layers.append(mp.PML(thickness=1, direction=mp.X))
    boundary_layers.append(mp.PML(thickness=1, direction=mp.Y))
    symmetries = []
    sim = mp.Simulation(cell_size=mp.Vector3(10, 10, 0), boundary_layers=boundary_layers, geometry=geometry, sources=sources, symmetries=symmetries, resolution=32)

    run_monitor_specs = [
    ]
    run_symmetry_specs = [
    ]
    run_domain_preview_out = os.path.join(out_dir, 'domain_preview.png')
    _save_domain_preview_png(
        run_domain_preview_out,
        sim,
        parameter_values,
        run_monitor_specs,
        run_symmetry_specs,
        title='Domain Preview',
        marker_expr=None,
    )
    # Field animation
    animate = mp.Animate2D(fields=mp.Ez, realtime=False)
    sim.run(mp.at_every(1, animate), until=200)
    anim_out = os.path.join(out_dir, "animation.mp4")
    animate.to_mp4(20, anim_out)

# Analysis type: Field Animation
if __name__ == '__main__':
    out_dir = script_dir
    run_analysis(out_dir)