FIELD_COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")

GEOMETRY_KINDS = ("circle", "block")
GEOMETRY_FIELDS = {
    "circle": ("radius", "center_x", "center_y"),
    "block": ("size_x", "size_y", "center_x", "center_y"),
}

SOURCE_KINDS = ("continuous", "gaussian")
SOURCE_FIELDS = {
    "continuous": ("center_x", "center_y", "size_x", "size_y", "fcen"),
    "gaussian": ("center_x", "center_y", "size_x", "size_y", "fcen", "df"),
}

PML_MODES = ("x", "y", "both", "none")
SYMMETRY_KINDS = ("mirror", "rotate2", "rotate4")
SYMMETRY_DIRECTIONS = ("x", "y", "z")

RUN_STATE_VALUES = ("idle", "running", "cancelling", "finished", "failed")
RUN_STATUS_VALUES = ("completed", "failed", "canceled")
