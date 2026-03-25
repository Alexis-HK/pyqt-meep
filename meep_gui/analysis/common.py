from __future__ import annotations

import csv
import os

from ..specs.analysis import FluxMonitorResult
from ..validation import evaluate_numeric_expression
from .types import LogFn, PlotResult, RunResult


def harminv_lines(harminv_obj) -> list[str]:
    lines: list[str] = []
    modes = getattr(harminv_obj, "modes", None)
    if not modes:
        return ["harminv: no modes found"]
    for mode in modes:
        freq = getattr(mode, "freq", getattr(mode, "frequency", None))
        decay = getattr(mode, "decay", None)
        qval = getattr(mode, "Q", None)
        amp = getattr(mode, "amplitude", getattr(mode, "amp", None))
        parts = []
        if freq is not None:
            parts.append(f"freq={freq:.6g}")
        if decay is not None:
            parts.append(f"decay={decay:.6g}")
        if qval is not None:
            parts.append(f"Q={qval:.6g}")
        if amp is not None:
            parts.append(f"amp={amp:.6g}")
        lines.append("harminv: " + " ".join(parts or ["mode"]))
    return lines


def eval_required(expr: str, values: dict[str, float], label: str) -> float:
    try:
        return evaluate_numeric_expression(expr, values)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def run_canceled(message: str = "Run canceled by user.") -> RunResult:
    return RunResult(status="canceled", message=message)


def require_gaussian_sources(state, analysis_kind: str) -> None:
    if analysis_kind == "meep_k_points":
        if not state.sources:
            raise ValueError("Meep k points requires at least one Gaussian (pulsed) source.")
        if any(src.kind == "continuous" for src in state.sources):
            raise ValueError(
                "Meep k points requires Gaussian (pulsed) sources. "
                "Continuous sources are not supported."
            )
        return
    if any(src.kind == "continuous" for src in state.sources):
        if analysis_kind == "harminv":
            raise ValueError(
                "Harminv requires Gaussian (pulsed) sources. Continuous sources are not supported."
            )
        if analysis_kind == "transmission_spectrum":
            raise ValueError(
                "Transmission spectrum requires Gaussian (pulsed) sources. "
                "Continuous sources are not supported."
            )


def require_continuous_sources(state, analysis_kind: str) -> None:
    if any(src.kind != "continuous" for src in state.sources):
        if analysis_kind == "frequency_domain_solver":
            raise ValueError(
                "Frequency-domain solver supports only continuous sources. "
                "Gaussian (pulsed) sources are not supported."
            )


def export_flux_plots(
    flux_results: list[FluxMonitorResult],
    output_dir: str,
    log: LogFn,
) -> list[PlotResult]:
    if not flux_results:
        return []

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots: list[PlotResult] = []
    for flux in flux_results:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in flux.name) or "flux"
        csv_path = os.path.join(output_dir, f"{safe}_flux.csv")
        png_path = os.path.join(output_dir, f"{safe}_flux.png")

        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["frequency", "flux"])
            for freq, value in zip(flux.freqs, flux.values):
                writer.writerow([freq, value])

        fig = plt.figure(figsize=(6, 4), dpi=120)
        ax = fig.add_subplot(111)
        ax.plot(flux.freqs, flux.values, linewidth=1.5)
        ax.set_title(f"Flux Monitor: {flux.name}")
        ax.set_xlabel("Frequency")
        ax.set_ylabel("Flux")
        ax.grid(True, linestyle=":", linewidth=0.5)
        fig.tight_layout()
        fig.savefig(png_path)
        plt.close(fig)

        plots.append(
            PlotResult(
                title=f"Flux: {flux.name}",
                x_label="Frequency",
                y_label="Flux",
                csv_path=csv_path,
                png_path=png_path,
                meta={"monitor": flux.name},
            )
        )
        log(f"Flux monitor exported: {flux.name}")

    return plots
