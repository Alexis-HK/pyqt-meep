from __future__ import annotations

from .base import GeometryKindSpec, PrimitiveField

GEOMETRY_REGISTRY: dict[str, GeometryKindSpec]


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


def _block_to_shape(obj, eps, context, eval_required):
    from ..specs.simulation import Shape

    if obj.geometry.block is None:
        raise ValueError(f"Geometry '{obj.name}': missing block parameters.")
    return Shape(
        kind="rect",
        center_x=eval_required(obj.transform.center_x_expr, context, "center_x"),
        center_y=eval_required(obj.transform.center_y_expr, context, "center_y"),
        size_x=eval_required(obj.geometry.block.size_x_expr, context, "size_x"),
        size_y=eval_required(obj.geometry.block.size_y_expr, context, "size_y"),
        eps=eps,
    )


def _circle_to_shape(obj, eps, context, eval_required):
    from ..specs.simulation import Shape

    if obj.geometry.circle is None:
        raise ValueError(f"Geometry '{obj.name}': missing circle parameters.")
    return Shape(
        kind="circle",
        center_x=eval_required(obj.transform.center_x_expr, context, "center_x"),
        center_y=eval_required(obj.transform.center_y_expr, context, "center_y"),
        radius=eval_required(obj.geometry.circle.radius_expr, context, "radius"),
        eps=eps,
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


def _build_block_mpb(obj, medium, mp, context, eval_required):
    if obj.geometry.block is None:
        raise ValueError(f"Geometry '{obj.name}': missing block parameters.")
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


def _build_circle_mpb(obj, medium, mp, context, eval_required):
    if obj.geometry.circle is None:
        raise ValueError(f"Geometry '{obj.name}': missing circle parameters.")
    return mp.Cylinder(
        radius=eval_required(obj.geometry.circle.radius_expr, context, "radius"),
        height=mp.inf,
        center=mp.Vector3(
            eval_required(obj.transform.center_x_expr, context, "center_x"),
            eval_required(obj.transform.center_y_expr, context, "center_y"),
        ),
        material=medium,
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

