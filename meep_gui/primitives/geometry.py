from __future__ import annotations

from .base import GeometryKindSpec, PrimitiveField

GEOMETRY_REGISTRY: dict[str, GeometryKindSpec]


def _prop_text(props: dict[str, str], field_id: str, default: str) -> str:
    return str(props.get(field_id, default))


def _material_eps(obj, eps_by_material: dict[str, float], material_name: str, label: str) -> float:
    if not material_name:
        raise ValueError(f"Geometry '{obj.name}': {label} is required.")
    try:
        return eps_by_material[material_name]
    except KeyError as exc:
        raise ValueError(f"Geometry '{obj.name}': unknown {label} '{material_name}'.") from exc


def _main_material_eps(obj, eps_by_material: dict[str, float]) -> float:
    if not isinstance(eps_by_material, dict):
        return float(eps_by_material)
    return _material_eps(
        obj,
        eps_by_material,
        obj.spatial_material.medium_name,
        "material",
    )


def _material_object(obj, materials: dict[str, object], material_name: str, label: str):
    if not material_name:
        raise ValueError(f"Geometry '{obj.name}': {label} is required.")
    try:
        return materials[material_name]
    except KeyError as exc:
        raise ValueError(f"Geometry '{obj.name}': unknown {label} '{material_name}'.") from exc


def _main_material_object(obj, materials: dict[str, object]):
    if not isinstance(materials, dict):
        return materials
    return _material_object(
        obj,
        materials,
        obj.spatial_material.medium_name,
        "material",
    )


def _compile_block(item):
    from ..scene.types import BlockGeometrySpec, GeometrySpec, SceneObject, SpatialMaterialSpec, TransformSpec

    props = getattr(item, "props", {}) or {}
    return SceneObject(
        name=getattr(item, "name", ""),
        geometry=GeometrySpec(
            kind="block",
            block=BlockGeometrySpec(
                size_x_expr=props.get("size_x", "0"),
                size_y_expr=props.get("size_y", "0"),
            ),
        ),
        spatial_material=SpatialMaterialSpec(kind="uniform", medium_name=getattr(item, "material", "")),
        transform=TransformSpec(
            center_x_expr=props.get("center_x", "0"),
            center_y_expr=props.get("center_y", "0"),
        ),
    )


def _compile_circle(item):
    from ..scene.types import CircleGeometrySpec, GeometrySpec, SceneObject, SpatialMaterialSpec, TransformSpec

    props = getattr(item, "props", {}) or {}
    return SceneObject(
        name=getattr(item, "name", ""),
        geometry=GeometrySpec(
            kind="circle",
            circle=CircleGeometrySpec(radius_expr=props.get("radius", "0")),
        ),
        spatial_material=SpatialMaterialSpec(kind="uniform", medium_name=getattr(item, "material", "")),
        transform=TransformSpec(
            center_x_expr=props.get("center_x", "0"),
            center_y_expr=props.get("center_y", "0"),
        ),
    )


def _compile_ring(item):
    from ..scene.types import GeometrySpec, RingGeometrySpec, SceneObject, SpatialMaterialSpec, TransformSpec

    props = getattr(item, "props", {}) or {}
    return SceneObject(
        name=getattr(item, "name", ""),
        geometry=GeometrySpec(
            kind="ring",
            ring=RingGeometrySpec(
                radius_expr=_prop_text(props, "radius", "0"),
                width_expr=_prop_text(props, "width", "0"),
                inner_medium_name=_prop_text(props, "inner_material", ""),
            ),
        ),
        spatial_material=SpatialMaterialSpec(kind="uniform", medium_name=getattr(item, "material", "")),
        transform=TransformSpec(
            center_x_expr=_prop_text(props, "center_x", "0"),
            center_y_expr=_prop_text(props, "center_y", "0"),
        ),
    )


def _ring_radii(obj, context, eval_required) -> tuple[float, float]:
    if obj.geometry.ring is None:
        raise ValueError(f"Geometry '{obj.name}': missing ring parameters.")
    radius = eval_required(obj.geometry.ring.radius_expr, context, "radius")
    width = eval_required(obj.geometry.ring.width_expr, context, "width")
    if width <= 0:
        raise ValueError(f"Geometry '{obj.name}': width must be positive.")
    inner_radius = radius - width / 2
    if inner_radius <= 0:
        raise ValueError(f"Geometry '{obj.name}': inner radius must be positive.")
    outer_radius = radius + width / 2
    return outer_radius, inner_radius


def _block_to_shape(obj, eps_by_material, context, eval_required):
    from ..specs.simulation import Shape

    if obj.geometry.block is None:
        raise ValueError(f"Geometry '{obj.name}': missing block parameters.")
    eps = _main_material_eps(obj, eps_by_material)
    return Shape(
        kind="rect",
        center_x=eval_required(obj.transform.center_x_expr, context, "center_x"),
        center_y=eval_required(obj.transform.center_y_expr, context, "center_y"),
        size_x=eval_required(obj.geometry.block.size_x_expr, context, "size_x"),
        size_y=eval_required(obj.geometry.block.size_y_expr, context, "size_y"),
        eps=eps,
    )


def _circle_to_shape(obj, eps_by_material, context, eval_required):
    from ..specs.simulation import Shape

    if obj.geometry.circle is None:
        raise ValueError(f"Geometry '{obj.name}': missing circle parameters.")
    eps = _main_material_eps(obj, eps_by_material)
    return Shape(
        kind="circle",
        center_x=eval_required(obj.transform.center_x_expr, context, "center_x"),
        center_y=eval_required(obj.transform.center_y_expr, context, "center_y"),
        radius=eval_required(obj.geometry.circle.radius_expr, context, "radius"),
        eps=eps,
    )


def _ring_to_shape(obj, eps_by_material, context, eval_required):
    from ..specs.simulation import Shape

    if obj.geometry.ring is None:
        raise ValueError(f"Geometry '{obj.name}': missing ring parameters.")
    outer_eps = _main_material_eps(obj, eps_by_material)
    inner_eps = _material_eps(
        obj,
        eps_by_material,
        obj.geometry.ring.inner_medium_name,
        "inner material",
    )
    outer_radius, inner_radius = _ring_radii(obj, context, eval_required)
    center_x = eval_required(obj.transform.center_x_expr, context, "center_x")
    center_y = eval_required(obj.transform.center_y_expr, context, "center_y")
    return (
        Shape(kind="circle", center_x=center_x, center_y=center_y, radius=outer_radius, eps=outer_eps),
        Shape(kind="circle", center_x=center_x, center_y=center_y, radius=inner_radius, eps=inner_eps),
    )


def _emit_block_script(var_name: str, idx: int, obj) -> tuple[str, ...]:
    if obj.geometry.block is None:
        raise ValueError(f"Geometry '{obj.name}': missing block parameters.")
    name = f"{var_name}_shape_{idx}"
    material = obj.spatial_material.medium_name or "None"
    center_x = obj.transform.center_x_expr
    center_y = obj.transform.center_y_expr
    size_x = obj.geometry.block.size_x_expr
    size_y = obj.geometry.block.size_y_expr
    return (
        f"{name} = mp.Block(size=mp.Vector3({size_x}, {size_y}, mp.inf), "
        f"center=mp.Vector3({center_x}, {center_y}), material=materials.get('{material}'))",
        f"{var_name}.append({name})",
    )


def _emit_circle_script(var_name: str, idx: int, obj) -> tuple[str, ...]:
    if obj.geometry.circle is None:
        raise ValueError(f"Geometry '{obj.name}': missing circle parameters.")
    name = f"{var_name}_shape_{idx}"
    material = obj.spatial_material.medium_name or "None"
    center_x = obj.transform.center_x_expr
    center_y = obj.transform.center_y_expr
    radius = obj.geometry.circle.radius_expr
    return (
        f"{name} = mp.Cylinder(radius={radius}, height=mp.inf, "
        f"center=mp.Vector3({center_x}, {center_y}), material=materials.get('{material}'))",
        f"{var_name}.append({name})",
    )


def _emit_ring_script(var_name: str, idx: int, obj) -> tuple[str, ...]:
    if obj.geometry.ring is None:
        raise ValueError(f"Geometry '{obj.name}': missing ring parameters.")
    name = f"{var_name}_shape_{idx}"
    material = obj.spatial_material.medium_name
    inner_material = obj.geometry.ring.inner_medium_name
    if not material:
        raise ValueError(f"Geometry '{obj.name}': material is required.")
    if not inner_material:
        raise ValueError(f"Geometry '{obj.name}': inner material is required.")
    center_x = obj.transform.center_x_expr
    center_y = obj.transform.center_y_expr
    radius = obj.geometry.ring.radius_expr
    width = obj.geometry.ring.width_expr
    return (
        f"{name}_width = {width}",
        f"if {name}_width <= 0:",
        f"    raise ValueError(\"Geometry '{obj.name}': width must be positive.\")",
        f"{name}_outer_radius = ({radius}) + {name}_width / 2",
        f"{name}_inner_radius = ({radius}) - {name}_width / 2",
        f"if {name}_inner_radius <= 0:",
        f"    raise ValueError(\"Geometry '{obj.name}': inner radius must be positive.\")",
        f"if '{material}' not in materials:",
        f"    raise ValueError(\"Geometry '{obj.name}': unknown material '{material}'.\")",
        f"if '{inner_material}' not in materials:",
        f"    raise ValueError(\"Geometry '{obj.name}': unknown inner material '{inner_material}'.\")",
        f"{name}_outer = mp.Cylinder(radius={name}_outer_radius, height=mp.inf, "
        f"center=mp.Vector3({center_x}, {center_y}), material=materials['{material}'])",
        f"{var_name}.append({name}_outer)",
        f"{name}_inner = mp.Cylinder(radius={name}_inner_radius, height=mp.inf, "
        f"center=mp.Vector3({center_x}, {center_y}), material=materials['{inner_material}'])",
        f"{var_name}.append({name}_inner)",
    )


def _build_block_mpb(obj, materials, mp, context, eval_required):
    if obj.geometry.block is None:
        raise ValueError(f"Geometry '{obj.name}': missing block parameters.")
    medium = _main_material_object(obj, materials)
    return mp.Block(
        size=mp.Vector3(
            eval_required(obj.geometry.block.size_x_expr, context, "size_x"),
            eval_required(obj.geometry.block.size_y_expr, context, "size_y"),
            mp.inf,
        ),
        center=mp.Vector3(
            eval_required(obj.transform.center_x_expr, context, "center_x"),
            eval_required(obj.transform.center_y_expr, context, "center_y"),
        ),
        material=medium,
    )


def _build_circle_mpb(obj, materials, mp, context, eval_required):
    if obj.geometry.circle is None:
        raise ValueError(f"Geometry '{obj.name}': missing circle parameters.")
    medium = _main_material_object(obj, materials)
    return mp.Cylinder(
        radius=eval_required(obj.geometry.circle.radius_expr, context, "radius"),
        height=mp.inf,
        center=mp.Vector3(
            eval_required(obj.transform.center_x_expr, context, "center_x"),
            eval_required(obj.transform.center_y_expr, context, "center_y"),
        ),
        material=medium,
    )


def _build_ring_mpb(obj, materials, mp, context, eval_required):
    if obj.geometry.ring is None:
        raise ValueError(f"Geometry '{obj.name}': missing ring parameters.")
    outer_medium = _main_material_object(obj, materials)
    inner_medium = _material_object(
        obj,
        materials,
        obj.geometry.ring.inner_medium_name,
        "inner material",
    )
    outer_radius, inner_radius = _ring_radii(obj, context, eval_required)
    center = mp.Vector3(
        eval_required(obj.transform.center_x_expr, context, "center_x"),
        eval_required(obj.transform.center_y_expr, context, "center_y"),
    )
    return (
        mp.Cylinder(radius=outer_radius, height=mp.inf, center=center, material=outer_medium),
        mp.Cylinder(radius=inner_radius, height=mp.inf, center=center, material=inner_medium),
    )


GEOMETRY_REGISTRY = {
    "circle": GeometryKindSpec(
        kind_id="circle",
        display_name="Circle",
        fields=(
            PrimitiveField("radius", "Radius"),
            PrimitiveField("center_x", "Center X"),
            PrimitiveField("center_y", "Center Y"),
        ),
        compile_scene_object=_compile_circle,
        to_shape=_circle_to_shape,
        emit_script_object=_emit_circle_script,
        build_mpb_object=_build_circle_mpb,
    ),
    "ring": GeometryKindSpec(
        kind_id="ring",
        display_name="Ring",
        fields=(
            PrimitiveField("inner_material", "Inner Material", value_type="material"),
            PrimitiveField("radius", "Radius"),
            PrimitiveField("width", "Width"),
            PrimitiveField("center_x", "Center X"),
            PrimitiveField("center_y", "Center Y"),
        ),
        compile_scene_object=_compile_ring,
        to_shape=_ring_to_shape,
        emit_script_object=_emit_ring_script,
        build_mpb_object=_build_ring_mpb,
    ),
    "block": GeometryKindSpec(
        kind_id="block",
        display_name="Block",
        fields=(
            PrimitiveField("size_x", "Size X"),
            PrimitiveField("size_y", "Size Y"),
            PrimitiveField("center_x", "Center X"),
            PrimitiveField("center_y", "Center Y"),
        ),
        compile_scene_object=_compile_block,
        to_shape=_block_to_shape,
        emit_script_object=_emit_block_script,
        build_mpb_object=_build_block_mpb,
    ),
}


def geometry_kind(kind: str) -> GeometryKindSpec:
    try:
        return GEOMETRY_REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported geometry kind: {kind}") from exc
