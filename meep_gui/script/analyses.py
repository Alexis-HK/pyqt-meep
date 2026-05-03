from __future__ import annotations

import os

from .common import line


def emit_field_animation(lines: list[str], cfg) -> None:
    output_name = os.path.basename(cfg.output_name.strip() or "animation.mp4")
    line(lines, "# Field animation")
    line(lines, f"animate = mp.Animate2D(fields=mp.{cfg.component}, realtime=False)")
    line(lines, f"sim.run(mp.at_every({cfg.interval}, animate), until={cfg.duration})")
    line(lines, f"anim_out = os.path.join(out_dir, \"{output_name}\")")
    line(lines, f"animate.to_mp4({cfg.fps}, anim_out)")


def emit_harminv(lines: list[str], cfg) -> None:
    output_name = os.path.basename(cfg.output_name.strip() or "harminv_animation.mp4")
    log_name = os.path.basename(cfg.harminv_log_path.strip() or "harminv.txt")
    line(lines, "# Harminv")
    line(lines, "harminv_monitors = []")
    for idx, monitor in enumerate(cfg.monitors, start=1):
        line(
            lines,
            "harminv_monitors.append(("
            f"'h{idx}', "
            "mp.Harminv("
            f"mp.{monitor.component}, "
            f"mp.Vector3({monitor.point_x}, {monitor.point_y}), "
            f"{monitor.fcen}, {monitor.df}"
            ")))",
        )
    for text in (
        "if not harminv_monitors:",
        "    raise ValueError('Harminv requires at least one monitor.')",
        f"animate = mp.Animate2D(fields=mp.{cfg.animation_component}, realtime=False)",
        "harminv_callbacks = ["
        f"mp.at_every({cfg.animation_interval}, animate)"
        "]",
        "harminv_callbacks.extend(mp.after_sources(hobj) for _label, hobj in harminv_monitors)",
        f"sim.run(*harminv_callbacks, until_after_sources={cfg.until_after_sources})",
        f"anim_out = os.path.join(out_dir, \"{output_name}\")",
        f"animate.to_mp4({cfg.animation_fps}, anim_out)",
        f"harminv_out = os.path.join(out_dir, \"{log_name}\")",
        "def _harminv_lines(hobj):",
        "    modes = getattr(hobj, 'modes', None)",
        "    if not modes:",
        "        return ['harminv: no modes found']",
        "    lines_out = []",
        "    for mode in modes:",
        "        freq = getattr(mode, 'freq', getattr(mode, 'frequency', None))",
        "        decay = getattr(mode, 'decay', None)",
        "        qval = getattr(mode, 'Q', None)",
        "        amp = getattr(mode, 'amplitude', getattr(mode, 'amp', None))",
        "        parts = []",
        "        if freq is not None:",
        "            parts.append(f'freq={freq:.6g}')",
        "        if decay is not None:",
        "            parts.append(f'decay={decay:.6g}')",
        "        if qval is not None:",
        "            parts.append(f'Q={qval:.6g}')",
        "        if amp is not None:",
        "            parts.append(f'amp={amp:.6g}')",
        "        if not parts:",
        "            parts = ['mode']",
        "        lines_out.append('harminv: ' + ' '.join(parts))",
        "    return lines_out",
        "with open(harminv_out, 'w', encoding='utf-8') as f:",
        "    for idx, (label, hobj) in enumerate(harminv_monitors):",
        "        if idx:",
        "            f.write('\\n')",
        "        f.write(f'========={label} MODES========\\n')",
        "        for line in _harminv_lines(hobj):",
        "            f.write(line + '\\n')",
        "print(f'Harminv log saved to {harminv_out}')",
    ):
        line(lines, text)


def emit_flux_exports(lines: list[str]) -> None:
    for text in (
        "",
        "# Export flux monitor data",
        "import matplotlib.pyplot as plt",
        "for monitor_name, monitor_obj in flux_monitors:",
        "    freqs = mp.get_flux_freqs(monitor_obj)",
        "    vals = mp.get_fluxes(monitor_obj)",
        "    csv_path = os.path.join(out_dir, f'{monitor_name}_flux.csv')",
        "    png_path = os.path.join(out_dir, f'{monitor_name}_flux.png')",
        "    with open(csv_path, 'w', newline='', encoding='utf-8') as f:",
        "        writer = csv.writer(f)",
        "        writer.writerow(['frequency', 'flux'])",
        "        for x, y in zip(freqs, vals):",
        "            writer.writerow([x, y])",
        "    fig = plt.figure(figsize=(6, 4), dpi=120)",
        "    ax = fig.add_subplot(111)",
        "    ax.plot(freqs, vals, linewidth=1.5)",
        "    ax.set_title(f'Flux Monitor: {monitor_name}')",
        "    ax.set_xlabel('Frequency')",
        "    ax.set_ylabel('Flux')",
        "    ax.grid(True, linestyle=':', linewidth=0.5)",
        "    fig.tight_layout()",
        "    fig.savefig(png_path)",
        "    plt.close(fig)",
    ):
        line(lines, text)
