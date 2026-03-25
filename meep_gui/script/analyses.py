from __future__ import annotations

import os

from .common import line


def emit_field_animation(lines: list[str], cfg) -> None:
    output_name = os.path.basename(cfg.output_name.strip() or "animation.mp4")
    line(lines, "# Field animation")
    line(lines, f"animate = mp.Animate2D(fields=mp.{cfg.component}, realtime=False)")
    line(lines, f"sim.run(mp.at_every({cfg.interval}, animate), until={cfg.duration})")
    line(lines, f"anim_out = os.path.join(script_dir, \"{output_name}\")")
    line(lines, f"animate.to_mp4({cfg.fps}, anim_out)")


def emit_harminv(lines: list[str], cfg) -> None:
    output_name = os.path.basename(cfg.output_name.strip() or "harminv_animation.mp4")
    log_name = os.path.basename(cfg.harminv_log_path.strip() or "harminv.txt")
    for text in (
        "# Harminv",
        "out_dir = os.path.join(script_dir, 'harminv_outputs')",
        "os.makedirs(out_dir, exist_ok=True)",
        "harminv = mp.Harminv("
        f"mp.{cfg.component}, mp.Vector3({cfg.point_x}, {cfg.point_y}), "
        f"{cfg.fcen}, {cfg.df})",
        f"animate = mp.Animate2D(fields=mp.{cfg.component}, realtime=False)",
        "sim.run("
        f"mp.at_every({cfg.animation_interval}, animate), "
        "mp.after_sources(harminv), "
        f"until_after_sources={cfg.until_after_sources})",
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
        "    for line in _harminv_lines(harminv):",
        "        f.write(line + '\\n')",
        "print(f'Harminv log saved to {harminv_out}')",
    ):
        line(lines, text)


def emit_flux_exports(lines: list[str]) -> None:
    for text in (
        "",
        "# Export flux monitor data",
        "for monitor_name, monitor_obj in flux_monitors:",
        "    freqs = mp.get_flux_freqs(monitor_obj)",
        "    vals = mp.get_fluxes(monitor_obj)",
        "    csv_path = os.path.join(script_dir, f'{monitor_name}_flux.csv')",
        "    with open(csv_path, 'w', newline='', encoding='utf-8') as f:",
        "        writer = csv.writer(f)",
        "        writer.writerow(['frequency', 'flux'])",
        "        for x, y in zip(freqs, vals):",
        "            writer.writerow([x, y])",
    ):
        line(lines, text)
