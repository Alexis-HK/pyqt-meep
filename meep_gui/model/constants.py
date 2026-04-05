from ..primitives import GEOMETRY_REGISTRY, SOURCE_REGISTRY

FIELD_COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")

GEOMETRY_KINDS = tuple(GEOMETRY_REGISTRY)
GEOMETRY_FIELDS = {
    kind: tuple(field.field_id for field in spec.fields)
    for kind, spec in GEOMETRY_REGISTRY.items()
}

SOURCE_KINDS = tuple(SOURCE_REGISTRY)
SOURCE_FIELDS = {
    kind: tuple(field.field_id for field in spec.fields)
    for kind, spec in SOURCE_REGISTRY.items()
}

PML_MODES = ("x", "y", "both", "none")
SYMMETRY_KINDS = ("mirror", "rotate2", "rotate4")
SYMMETRY_DIRECTIONS = ("x", "y", "z")

RUN_STATE_VALUES = ("idle", "running", "cancelling", "finished", "failed")
RUN_STATUS_VALUES = ("completed", "failed", "canceled")
