from __future__ import annotations

from .common import line


def emit_meep_k_points(lines: list[str], state) -> None:
    cfg = state.analysis.meep_k_points

    prefix = (cfg.output_prefix.strip() or "meep_k_points").replace("\\", "_").replace("/", "_")

    line(lines, "# Meep k points")
    for text in (
        "input_k_points = [",
    ):
        line(lines, text)
    for kp in cfg.kpoints:
        line(lines, f"    mp.Vector3({kp.kx}, {kp.ky}, 0),")
    line(lines, "]")
    if cfg.kpoint_interp.strip() == "0":
        line(lines, "k_points = input_k_points")
    else:
        line(lines, f"k_points = mp.interpolate(int({cfg.kpoint_interp}), input_k_points)")
    for text in (
        f"all_freqs = sim.run_k_points({cfg.run_time}, k_points)",
        "import matplotlib.pyplot as plt",
        f"band_csv = os.path.join(out_dir, '{prefix}_bands.csv')",
        "with open(band_csv, 'w', newline='', encoding='utf-8') as f:",
        "    writer = csv.writer(f)",
        "    writer.writerow(['k_index', 'kx', 'ky', 'mode', 'freq_real', 'freq_imag'])",
        "    scatter_x = []",
        "    scatter_y = []",
        "    for k_index, kp in enumerate(k_points):",
        "        point_freqs = []",
        "        if all_freqs is not None and k_index < len(all_freqs):",
        "            value = all_freqs[k_index]",
        "            if isinstance(value, (str, bytes)):",
        "                value = []",
        "            try:",
        "                point_freqs = list(value)",
        "            except TypeError:",
        "                point_freqs = [value]",
        "        for mode, freq in enumerate(point_freqs, start=1):",
        "            cval = complex(freq)",
        "            writer.writerow([k_index, float(kp.x), float(kp.y), mode, float(cval.real), float(cval.imag)])",
        "            scatter_x.append(k_index)",
        "            scatter_y.append(float(cval.real))",
        f"band_png = os.path.join(out_dir, '{prefix}_bands.png')",
        "plt.figure(figsize=(6, 4), dpi=120)",
        "if scatter_x:",
        "    plt.scatter(scatter_x, scatter_y, s=18, color='#1f77b4')",
        "plt.title('Meep K-Points Band Diagram')",
        "plt.xlabel('k-index')",
        "plt.ylabel('Frequency')",
        "plt.grid(True, linestyle=':', linewidth=0.5)",
        "plt.tight_layout()",
        "plt.savefig(band_png)",
        "plt.close()",
    ):
        line(lines, text)
