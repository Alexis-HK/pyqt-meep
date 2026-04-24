from __future__ import annotations

from typing import Callable

from ..specs.simulation import SimParams
from .imports import component_map, import_meep

LogFn = Callable[[str], None]


def build_geometry(params: SimParams, _log: LogFn, mp):
    geometry = []
    for shape in params.shapes:
        material = mp.Medium(epsilon=shape.eps)
        if shape.kind == "rect":
            geometry.append(
                mp.Block(
                    size=mp.Vector3(shape.size_x, shape.size_y, mp.inf),
                    center=mp.Vector3(shape.center_x, shape.center_y),
                    material=material,
                )
            )
        elif shape.kind == "circle":
            geometry.append(
                mp.Cylinder(
                    radius=shape.radius,
                    height=mp.inf,
                    center=mp.Vector3(shape.center_x, shape.center_y),
                    material=material,
                )
            )
    return geometry


def build_sim(params: SimParams, log: LogFn, *, force_complex_fields: bool = False):
    mp = import_meep()

    cell = mp.Vector3(params.cell_x, params.cell_y, 0)
    pml_layers = []
    if params.pml_x:
        pml_layers.append(mp.PML(thickness=params.pml, direction=mp.X))
    if params.pml_y:
        pml_layers.append(mp.PML(thickness=params.pml, direction=mp.Y))

    geometry = build_geometry(params, log, mp)
    components = component_map(mp)
    if any(value is None for value in components.values()):
        raise ValueError("Meep field components are unavailable. Check your Meep installation.")

    sources = []
    for spec in params.sources:
        source_time = spec.source_time
        if source_time is None:
            raise ValueError(f"Source '{spec.kind}' is missing a SourceTime.")

        def build_source_time():
            if source_time.kind == "gaussian":
                return mp.GaussianSource(frequency=source_time.frequency, fwidth=source_time.bandwidth)
            if source_time.kind == "continuous":
                return mp.ContinuousSource(frequency=source_time.frequency)
            if source_time.kind == "custom":
                if source_time.src_func is None:
                    raise ValueError("Custom source is missing src_func.")
                return mp.CustomSource(
                    src_func=source_time.src_func,
                    start_time=source_time.start_time,
                    end_time=source_time.end_time,
                    is_integrated=source_time.is_integrated,
                    center_frequency=source_time.center_frequency,
                    fwidth=source_time.fwidth,
                )
            if source_time.kind == "chirped_pulse":
                if source_time.src_func is None:
                    raise ValueError("Chirped pulse source is missing src_func.")
                return mp.CustomSource(
                    src_func=source_time.src_func,
                    center_frequency=source_time.center_frequency,
                )
            raise ValueError("Source references an unsupported SourceTime.")

        if spec.kind == "gaussian_beam":
            src_time = build_source_time()
            sources.append(
                mp.GaussianBeamSource(
                    src=src_time,
                    center=mp.Vector3(spec.center_x, spec.center_y, 0),
                    size=mp.Vector3(spec.width_x, spec.width_y, 0),
                    beam_x0=mp.Vector3(spec.beam_x0_x, spec.beam_x0_y, 0),
                    beam_kdir=mp.Vector3(spec.beam_kdir_x, spec.beam_kdir_y, 0),
                    beam_w0=spec.beam_w0,
                    beam_E0=mp.Vector3(spec.beam_e0_x, spec.beam_e0_y, spec.beam_e0_z),
                )
            )
            continue

        comp = components.get(spec.component, mp.Ez)
        src = build_source_time()
        source_kwargs = dict(
            src=src,
            component=comp,
            center=mp.Vector3(spec.center_x, spec.center_y),
            size=mp.Vector3(spec.width_x, spec.width_y, 0),
            amplitude=spec.amplitude,
        )
        if spec.amp_func is not None:
            source_kwargs["amp_func"] = lambda pos, fn=spec.amp_func: fn(pos.x, pos.y)
        sources.append(mp.Source(**source_kwargs))

    symmetries = []
    for spec in params.symmetries:
        direction = getattr(mp, spec.direction.upper(), None)
        if direction is None:
            raise ValueError(f"Unsupported symmetry direction: {spec.direction}")
        if spec.kind == "mirror":
            symmetries.append(mp.Mirror(direction, phase=spec.phase))
        elif spec.kind == "rotate2":
            symmetries.append(mp.Rotate2(direction, phase=spec.phase))
        elif spec.kind == "rotate4":
            symmetries.append(mp.Rotate4(direction, phase=spec.phase))
        else:
            raise ValueError(f"Unsupported symmetry kind: {spec.kind}")

    log("Building simulation...")
    sim_kwargs = dict(
        cell_size=cell,
        boundary_layers=pml_layers,
        geometry=geometry,
        sources=sources,
        symmetries=symmetries,
        resolution=params.resolution,
        force_complex_fields=force_complex_fields,
    )
    if params.k_point is not None:
        sim_kwargs["k_point"] = mp.Vector3(*params.k_point)
    if params.cylindrical_enabled:
        sim_kwargs["dimensions"] = mp.CYLINDRICAL
        sim_kwargs["m"] = params.cylindrical_m
    return mp.Simulation(
        **sim_kwargs,
    )
