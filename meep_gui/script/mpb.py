from __future__ import annotations

from .common import line


def emit_mpb(lines: list[str], state) -> None:
    cfg = state.analysis.mpb_modesolver
    line(lines, "# MPB")
    if state.domain.symmetry_enabled and state.domain.symmetries:
        line(lines, "# Note: domain symmetries are FDTD-only and are not applied to MPB.")
    for text in (
        "out_dir = os.path.join(script_dir, 'mpb_outputs')",
        "os.makedirs(out_dir, exist_ok=True)",
        "geometry_lattice = mp.Lattice("
        f"size=mp.Vector3({cfg.lattice_x}, {cfg.lattice_y}, 0), "
        f"basis1=mp.Vector3({cfg.basis1_x}, {cfg.basis1_y}, 0), "
        f"basis2=mp.Vector3({cfg.basis2_x}, {cfg.basis2_y}, 0))",
        "k_points_raw = [",
    ):
        line(lines, text)
    for kp in cfg.kpoints or []:
        line(lines, f"    mp.Vector3({kp.kx}, {kp.ky}, 0),")
    if not cfg.kpoints:
        line(lines, "    mp.Vector3(0, 0, 0),")
        line(lines, "    mp.Vector3(0.5, 0, 0),")
    for text in (
        "]",
        f"if len(k_points_raw) > 1 and int({cfg.kpoint_interp}) > 0:",
        f"    k_points = mp.interpolate(int({cfg.kpoint_interp}), k_points_raw)",
        "else:",
        "    k_points = k_points_raw",
        "field_k_points = [",
    ):
        line(lines, text)
    for kp in cfg.field_kpoints:
        line(lines, f"    mp.Vector3({kp.kx}, {kp.ky}, 0),")
    for text in (
        "]",
        "run_pols = []",
    ):
        line(lines, text)
    if cfg.run_tm:
        line(lines, "run_pols.append('tm')")
    if cfg.run_te:
        line(lines, "run_pols.append('te')")
    for text in (
        "if not run_pols:",
        "    raise ValueError('Select at least one polarization (TM and/or TE).')",
        "def _run_pol(ms, pol, fix_phase=False):",
        "    callbacks = []",
        "    if fix_phase:",
        "        cb_name = 'fix_efield_phase' if pol == 'tm' else 'fix_hfield_phase'",
        "        cb = getattr(mpb, cb_name, None)",
        "        if callable(cb):",
        "            callbacks.append(cb)",
        "    if pol == 'tm' and hasattr(ms, 'run_tm'):",
        "        ms.run_tm(*callbacks)",
        "        return",
        "    if pol == 'te' and hasattr(ms, 'run_te'):",
        "        ms.run_te(*callbacks)",
        "        return",
        "    ms.run()",
        "",
        "def _get_field(ms, pol, band):",
        "    getter = ms.get_efield if pol == 'tm' else ms.get_hfield",
        "    try:",
        "        return getter(band, bloch_phase=True)",
        "    except TypeError:",
        "        return getter(band)",
        "",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "bands = {}",
        "eps_solver = None",
        "for pol in run_pols:",
        "    ms = mpb.ModeSolver("
        "geometry_lattice=geometry_lattice, "
        "geometry=geometry, "
        "k_points=k_points, "
        f"resolution={cfg.resolution}, "
        f"num_bands={cfg.num_bands})",
        "    _run_pol(ms, pol)",
        "    bands[pol] = ms.all_freqs",
        "    if eps_solver is None:",
        "        eps_solver = ms",
        "band_csv = os.path.join(out_dir, 'mpb_bands.csv')",
        "with open(band_csv, 'w', newline='', encoding='utf-8') as f:",
        "    writer = csv.writer(f)",
        "    writer.writerow(['polarization', 'k_index', 'kx', 'ky', 'band', 'frequency'])",
        "    for pol in ('tm', 'te'):",
        "        if pol not in bands:",
        "            continue",
        "        arr = np.asarray(bands[pol], dtype=float)",
        "        if arr.ndim == 1:",
        "            arr = arr[:, np.newaxis]",
        "        for i, kp in enumerate(k_points):",
        "            if i >= arr.shape[0]:",
        "                break",
        "            for b, freq in enumerate(arr[i], start=1):",
        "                writer.writerow([pol, i, kp.x, kp.y, b, float(freq)])",
        "band_png = os.path.join(out_dir, 'mpb_bands.png')",
        "plt.figure(figsize=(6, 4), dpi=120)",
        "x = list(range(len(k_points)))",
        "if 'te' in bands:",
        "    arr = np.asarray(bands['te'], dtype=float)",
        "    if arr.ndim == 1:",
        "        arr = arr[:, np.newaxis]",
        "    for b in range(arr.shape[1]):",
        "        plt.plot(x[:arr.shape[0]], arr[:, b], '-', color='red', linewidth=1.2, label='TE' if b == 0 else None)",
        "if 'tm' in bands:",
        "    arr = np.asarray(bands['tm'], dtype=float)",
        "    if arr.ndim == 1:",
        "        arr = arr[:, np.newaxis]",
        "    for b in range(arr.shape[1]):",
        "        plt.plot(x[:arr.shape[0]], arr[:, b], '-', color='blue', linewidth=1.2, label='TM' if b == 0 else None)",
        "plt.title('MPB Band Diagram')",
        "plt.xlabel('k-index')",
        "plt.ylabel('Frequency')",
        "plt.grid(True, linestyle=':', linewidth=0.5)",
        "plt.legend(loc='best')",
        "plt.tight_layout()",
        "plt.savefig(band_png)",
        "plt.close()",
        f"md = mpb.MPBData(rectify=True, periods=int({cfg.unit_cells}), resolution=int({cfg.resolution}))",
        "eps_solver.init_params(mp.NO_PARITY, True)",
        "converted_eps = md.convert(eps_solver.get_epsilon())",
        "plt.figure(figsize=(5, 4), dpi=120)",
        "plt.imshow(converted_eps.T, interpolation='spline36', cmap='binary')",
        "plt.axis('off')",
        "plt.tight_layout()",
        "plt.savefig(os.path.join(out_dir, 'mpb_epsilon.png'))",
        "plt.close()",
        f"num_bands_int = int({cfg.num_bands})",
        f"unit_cells_int = int({cfg.unit_cells})",
        f"resolution_int = int({cfg.resolution})",
        f"max_mode_images = max(1, int({cfg.max_mode_images}))",
        "total_mode_images = len(field_k_points) * num_bands_int * len(run_pols)",
        "mode_limit = min(total_mode_images, max_mode_images)",
        "generated_modes = 0",
        "# Field images are only generated for explicitly configured field_k_points.",
        "if field_k_points and mode_limit < total_mode_images:",
        "    print(f\"Mode image generation capped at {mode_limit} of {total_mode_images}.\")",
        "for pol in run_pols:",
        "    if generated_modes >= mode_limit:",
        "        break",
        "    field_component = 'Ez' if pol == 'tm' else 'Hz'",
        "    for k_idx, kp in enumerate(field_k_points):",
        "        if generated_modes >= mode_limit:",
        "            break",
        "        ms_k = mpb.ModeSolver(",
        "            geometry_lattice=geometry_lattice,",
        "            geometry=geometry,",
        "            k_points=[kp],",
        "            resolution=resolution_int,",
        "            num_bands=num_bands_int,",
        "        )",
        "        _run_pol(ms_k, pol, fix_phase=True)",
        "        if hasattr(ms_k, 'fix_field_phase'):",
        "            try:",
        "                ms_k.fix_field_phase()",
        "            except Exception:",
        "                pass",
        "        md_field = mpb.MPBData(rectify=True, periods=unit_cells_int, resolution=resolution_int)",
        "        try:",
        "            converted_eps_field = md_field.convert(eps_solver.get_epsilon())",
        "        except Exception:",
        "            converted_eps_field = converted_eps",
        "        for band in range(1, num_bands_int + 1):",
        "            if generated_modes >= mode_limit:",
        "                break",
        "            field_raw = _get_field(ms_k, pol, band)",
        "            if field_raw is None:",
        "                continue",
        "            try:",
        "                field_data = md_field.convert(field_raw)",
        "            except Exception:",
        "                field_data = field_raw",
        "            arr = np.asarray(field_data)",
        "            if arr.ndim >= 1 and arr.shape[-1] >= 3:",
        "                arr = arr[..., 2]",
        "            arr = np.squeeze(arr)",
        "            if np.iscomplexobj(arr):",
        "                arr = np.real(arr)",
        "            if arr.ndim != 2:",
        "                arr = np.atleast_2d(arr)",
        "            eps_arr = np.asarray(converted_eps_field)",
        "            eps_arr = np.squeeze(eps_arr)",
        "            if np.iscomplexobj(eps_arr):",
        "                eps_arr = np.real(eps_arr)",
        "            if eps_arr.ndim != 2:",
        "                eps_arr = np.atleast_2d(eps_arr)",
        "            vmax = np.nanmax(np.abs(arr)) if arr.size else 1.0",
        "            if not np.isfinite(vmax) or vmax == 0:",
        "                vmax = 1.0",
        "            kx = float(kp.x)",
        "            ky = float(kp.y)",
        "            plt.figure(figsize=(5, 4), dpi=120)",
        "            plt.imshow(eps_arr.T, interpolation='spline36', cmap='binary')",
        "            plt.imshow(arr.T, interpolation='spline36', cmap='RdBu', alpha=0.85, vmin=-vmax, vmax=vmax)",
        "            plt.title(f\"{pol.upper()} {field_component} k=({kx:.4g}, {ky:.4g}) band={band}\")",
        "            plt.axis('off')",
        "            plt.tight_layout()",
        "            out_png = os.path.join(out_dir, f\"mode_{pol}_k{k_idx:03d}_b{band:03d}.png\")",
        "            plt.savefig(out_png)",
        "            plt.close()",
        "            generated_modes += 1",
    ):
        line(lines, text)
