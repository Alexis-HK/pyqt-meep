from __future__ import annotations

import os

from .common import line


def emit_frequency_domain(lines: list[str], state) -> None:
    cfg = state.analysis.frequency_domain_solver
    output_name = os.path.basename(cfg.output_name.strip() or "frequency_domain_field.png")

    line(lines, "# Frequency-domain solver")
    line(lines, "out_dir = os.path.join(script_dir, 'frequency_domain_outputs')")
    line(lines, "os.makedirs(out_dir, exist_ok=True)")
    if not state.sources:
        line(
            lines,
            "print('Warning: no sources are configured; frequency-domain solve may produce a zero field.')",
        )
    for text in (
        f"field_component = mp.{cfg.component}",
        "sim.init_sim()",
        f"sim.solve_cw({cfg.tolerance}, int({cfg.max_iters}), int({cfg.bicgstab_l}))",
        f"sample_size = mp.Vector3({state.domain.cell_x}, {state.domain.cell_y}, 0)",
        "sample_center = mp.Vector3()",
        "eps_data = sim.get_array(center=sample_center, size=sample_size, component=mp.Dielectric)",
        "try:",
        "    field_data = sim.get_array(",
        "        center=sample_center,",
        "        size=sample_size,",
        "        component=field_component,",
        "        cmplx=True,",
        "    )",
        "except TypeError:",
        "    field_data = sim.get_array(",
        "        center=sample_center,",
        "        size=sample_size,",
        "        component=field_component,",
        "    )",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "field_arr = np.asarray(field_data)",
        "field_arr = np.squeeze(np.real(field_arr))",
        "if field_arr.ndim != 2:",
        "    field_arr = np.atleast_2d(field_arr)",
        "eps_arr = np.asarray(eps_data)",
        "eps_arr = np.squeeze(np.real(eps_arr))",
        "if eps_arr.ndim != 2:",
        "    eps_arr = np.atleast_2d(eps_arr)",
        f"field_csv = os.path.join(out_dir, \"{os.path.splitext(output_name)[0] or 'frequency_domain_field'}.csv\")",
        "np.savetxt(field_csv, field_arr.T, delimiter=',')",
        "vmax = float(np.nanmax(np.abs(field_arr))) if field_arr.size else 1.0",
        "if not np.isfinite(vmax) or vmax == 0:",
        "    vmax = 1.0",
        f"field_out = os.path.join(out_dir, \"{output_name}\")",
        "if hasattr(sim, 'plot2D'):",
        "    fig = plt.figure(figsize=(6, 5), dpi=120)",
        "    ax = fig.add_subplot(111)",
        "    sim.plot2D(",
        "        ax=ax,",
        "        fields=field_component,",
        "        field_parameters={",
        "            'alpha': 0.85,",
        "            'cmap': 'RdBu',",
        "            'interpolation': 'spline36',",
        "            'post_process': np.real,",
        "        },",
        "    )",
        f"    ax.set_title('Frequency-Domain {cfg.component} (real)')",
        "    fig.tight_layout()",
        "    fig.savefig(field_out)",
        "    plt.close(fig)",
        "else:",
        "    plt.figure(figsize=(5, 4), dpi=120)",
        "    plt.imshow(eps_arr.T, interpolation='spline36', cmap='binary')",
        "    plt.imshow(field_arr.T, interpolation='spline36', cmap='RdBu', alpha=0.85, vmin=-vmax, vmax=vmax)",
        f"    plt.title('Frequency-Domain {cfg.component} (real)')",
        "    plt.axis('off')",
        "    plt.tight_layout()",
        "    plt.savefig(field_out)",
        "    plt.close()",
    ):
        line(lines, text)
