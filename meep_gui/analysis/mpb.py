from __future__ import annotations

import copy
import os
import shutil
import tempfile

from ..model import ProjectState
from .images import save_field_overlay_image
from .mpb_support import (
    build_mpb_geometry,
    component_from_field_array,
    fix_field_phase,
    get_field_data,
    run_modesolver_pol,
    save_band_csv,
    save_band_plot,
    save_epsilon_image,
    save_image,
)
from .types import ArtifactResult, CancelFn, LogFn, RunResult

_save_image = save_image


def run_mpb_modesolver_impl(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    *,
    deps,
) -> RunResult:
    state = copy.deepcopy(state)
    cfg = state.analysis.mpb_modesolver

    values, results = deps.evaluate_parameters(state.parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")

    mp, mpb = deps._import_mpb()

    lattice_x = deps._eval_required(cfg.lattice_x, values, "lattice_x")
    lattice_y = deps._eval_required(cfg.lattice_y, values, "lattice_y")
    basis1_x = deps._eval_required(cfg.basis1_x, values, "basis1_x")
    basis1_y = deps._eval_required(cfg.basis1_y, values, "basis1_y")
    basis2_x = deps._eval_required(cfg.basis2_x, values, "basis2_x")
    basis2_y = deps._eval_required(cfg.basis2_y, values, "basis2_y")
    num_bands = max(1, int(deps._eval_required(cfg.num_bands, values, "num_bands")))
    resolution = max(2, int(deps._eval_required(cfg.resolution, values, "resolution")))
    unit_cells = max(1, int(deps._eval_required(cfg.unit_cells, values, "unit_cells")))
    kpoint_interp = max(0, int(deps._eval_required(cfg.kpoint_interp, values, "kpoint_interp")))
    max_mode_images = max(1, int(deps._eval_required(cfg.max_mode_images, values, "max_mode_images")))

    selected_pols: list[str] = []
    if cfg.run_tm:
        selected_pols.append("tm")
    if cfg.run_te:
        selected_pols.append("te")
    if not selected_pols:
        raise ValueError("Select at least one polarization (TM and/or TE).")

    k_points_raw = []
    for kp in cfg.kpoints:
        kx = deps._eval_required(kp.kx, values, "kpoint.kx")
        ky = deps._eval_required(kp.ky, values, "kpoint.ky")
        k_points_raw.append(mp.Vector3(kx, ky, 0))
    if not k_points_raw:
        k_points_raw = [mp.Vector3(0, 0, 0), mp.Vector3(0.5, 0, 0)]

    if len(k_points_raw) > 1 and kpoint_interp > 0:
        band_k_points = list(mp.interpolate(kpoint_interp, k_points_raw))
    else:
        band_k_points = list(k_points_raw)

    field_k_points = []
    for idx, kp in enumerate(cfg.field_kpoints, start=1):
        kx = deps._eval_required(kp.kx, values, f"field_kpoint[{idx}].kx")
        ky = deps._eval_required(kp.ky, values, f"field_kpoint[{idx}].ky")
        field_k_points.append(mp.Vector3(kx, ky, 0))

    geometry = build_mpb_geometry(state, mp, values, deps=deps)
    lattice = mp.Lattice(
        size=mp.Vector3(lattice_x, lattice_y, 0),
        basis1=mp.Vector3(basis1_x, basis1_y, 0),
        basis2=mp.Vector3(basis2_x, basis2_y, 0),
    )

    out_dir = tempfile.mkdtemp(prefix="meep_gui_mpb_")
    band_csv_path = os.path.join(out_dir, "mpb_bands.csv")
    band_png_path = os.path.join(out_dir, "mpb_bands.png")
    eps_png_path = os.path.join(out_dir, "mpb_epsilon.png")

    if cancel_requested():
        shutil.rmtree(out_dir, ignore_errors=True)
        return deps._run_canceled()

    band_data: dict[str, object] = {}
    eps_solver = None
    for pol in selected_pols:
        ms = mpb.ModeSolver(
            geometry_lattice=lattice,
            geometry=geometry,
            k_points=band_k_points,
            resolution=resolution,
            num_bands=num_bands,
        )
        log(f"Running MPB {pol.upper()} bands...")
        run_modesolver_pol(ms, pol, mpb)
        band_data[pol] = getattr(ms, "all_freqs", [])
        if eps_solver is None:
            eps_solver = ms

    save_band_csv(band_csv_path, band_k_points, band_data)
    save_band_plot(band_png_path, band_k_points, band_data)

    if eps_solver is None:
        raise RuntimeError("MPB failed to initialize mode solver.")
    eps_solver.init_params(mp.NO_PARITY, True)
    md = mpb.MPBData(rectify=True, periods=unit_cells, resolution=resolution)
    eps = eps_solver.get_epsilon()
    converted_eps = md.convert(eps)
    save_epsilon_image(eps_png_path, converted_eps, "MPB Epsilon")

    mode_artifacts: list[ArtifactResult] = []
    total_modes = len(field_k_points) * num_bands * len(selected_pols)
    if not field_k_points:
        log("No field k-points configured; skipping MPB field image generation.")
    mode_limit = min(total_modes, max_mode_images)
    if mode_limit < total_modes:
        log(f"Mode image generation capped at {mode_limit} of {total_modes}.")

    generated = 0
    for pol in selected_pols:
        field_component = "Ez" if pol == "tm" else "Hz"
        for k_idx, kp in enumerate(field_k_points):
            if generated >= mode_limit:
                break
            if cancel_requested():
                shutil.rmtree(out_dir, ignore_errors=True)
                return deps._run_canceled()

            ms_k = mpb.ModeSolver(
                geometry_lattice=lattice,
                geometry=geometry,
                k_points=[kp],
                resolution=resolution,
                num_bands=num_bands,
            )
            run_modesolver_pol(ms_k, pol, mpb, fix_phase=True)
            fix_field_phase(ms_k, pol)
            md_field = mpb.MPBData(rectify=True, periods=unit_cells, resolution=resolution)
            try:
                converted_eps_field = md_field.convert(eps)
            except Exception:
                converted_eps_field = converted_eps

            freqs = []
            all_freqs_k = getattr(ms_k, "all_freqs", None)
            if all_freqs_k is not None and len(all_freqs_k) > 0:
                freqs = list(all_freqs_k[0])

            for band_idx in range(1, num_bands + 1):
                if generated >= mode_limit:
                    break
                if cancel_requested():
                    shutil.rmtree(out_dir, ignore_errors=True)
                    return deps._run_canceled()

                raw_field = get_field_data(ms_k, pol, band_idx)
                if raw_field is None:
                    continue
                try:
                    converted_field = md_field.convert(raw_field)
                except Exception:
                    converted_field = raw_field
                field_to_plot = component_from_field_array(converted_field, pol)

                mode_path = os.path.join(
                    out_dir, f"mode_{pol}_k{k_idx:03d}_b{band_idx:03d}.png"
                )
                kx_val = float(kp.x)
                ky_val = float(kp.y)
                save_field_overlay_image(
                    mode_path,
                    field_to_plot,
                    converted_eps_field,
                    f"{pol.upper()} {field_component} k=({kx_val:.4g}, {ky_val:.4g}) band={band_idx}",
                )
                freq_text = ""
                if band_idx - 1 < len(freqs):
                    freq_text = f"{float(freqs[band_idx - 1]):.8g}"
                mode_artifacts.append(
                    ArtifactResult(
                        kind="mpb_mode_png",
                        label=f"{pol.upper()} k=({kx_val:.4g}, {ky_val:.4g}) band={band_idx}",
                        path=mode_path,
                        meta={
                            "polarization": pol,
                            "field_component": field_component,
                            "k_index": str(k_idx),
                            "kx": f"{float(kp.x):.8g}",
                            "ky": f"{float(kp.y):.8g}",
                            "band": str(band_idx),
                            "frequency": freq_text,
                        },
                    )
                )
                generated += 1

    artifacts = [
        ArtifactResult(kind="mpb_band_csv", label="Band CSV", path=band_csv_path),
        ArtifactResult(kind="mpb_band_png", label="Band Plot", path=band_png_path),
        ArtifactResult(kind="mpb_epsilon_png", label="Epsilon", path=eps_png_path),
        *mode_artifacts,
    ]

    pol_text = "/".join(pol.upper() for pol in selected_pols)
    return RunResult(
        status="completed",
        message=f"MPB mode solver completed ({pol_text}).",
        artifacts=artifacts,
        plots=[],
        meta={
            "kpoint_count": str(len(band_k_points)),
            "field_kpoint_count": str(len(field_k_points)),
            "polarizations": pol_text,
            "num_bands": str(num_bands),
            "mode_images": str(generated),
        },
    )
