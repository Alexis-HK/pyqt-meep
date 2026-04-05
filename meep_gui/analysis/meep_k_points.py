from __future__ import annotations

import copy
import csv
import os

from ..model import ProjectState
from .domain_artifacts import create_domain_preview_artifacts
from .types import CancelFn, LogFn, PlotResult, RunResult
from .workspace import create_run_output_dir


def _eval_nonnegative_int(expr: str, values: dict[str, float], label: str, *, deps) -> int:
    value = deps._eval_required(expr, values, label)
    rounded = int(round(value))
    if abs(value - rounded) > 1e-9:
        raise ValueError(f"{label} must be an integer.")
    if rounded < 0:
        raise ValueError(f"{label} must be >= 0.")
    return rounded


def _eval_positive_float(expr: str, values: dict[str, float], label: str, *, deps) -> float:
    value = deps._eval_required(expr, values, label)
    if value <= 0:
        raise ValueError(f"{label} must be > 0.")
    return value


def _row_freqs(values) -> list[complex]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        return []
    try:
        items = list(values)
    except TypeError:
        items = [values]

    freqs: list[complex] = []
    for item in items:
        try:
            freqs.append(complex(item))
        except Exception:
            continue
    return freqs


def run_meep_k_points_impl(
    state: ProjectState,
    log: LogFn,
    cancel_requested: CancelFn,
    *,
    deps,
) -> RunResult:
    state = copy.deepcopy(state)
    cfg = state.analysis.meep_k_points

    values, results = deps.evaluate_parameters(state.parameters)
    for result in results:
        if not result.ok:
            raise ValueError(f"Parameter '{result.name}': {result.message}")

    kpoint_interp = _eval_nonnegative_int(cfg.kpoint_interp, values, "kpoint_interp", deps=deps)
    run_time = _eval_positive_float(cfg.run_time, values, "run_time", deps=deps)

    entered_points = []
    for idx, kp in enumerate(cfg.kpoints, start=1):
        entered_points.append(
            (
                deps._eval_required(kp.kx, values, f"kpoint[{idx}].kx"),
                deps._eval_required(kp.ky, values, f"kpoint[{idx}].ky"),
            )
        )
    if len(entered_points) < 2:
        raise ValueError("Meep k points requires at least two input k-points.")

    params = deps._build_sim_params(state)
    sim = deps.build_sim(params, log)
    mp = deps._import_meep()

    if not hasattr(sim, "run_k_points"):
        raise RuntimeError("Meep Simulation.run_k_points() is unavailable.")

    raw_points = [mp.Vector3(kx, ky, 0) for kx, ky in entered_points]
    if len(raw_points) > 1 and kpoint_interp > 0:
        if not hasattr(mp, "interpolate"):
            raise RuntimeError("Meep interpolate() is unavailable.")
        interp_k_points = list(mp.interpolate(kpoint_interp, raw_points))
    else:
        interp_k_points = list(raw_points)

    if cancel_requested():
        return deps._run_canceled()

    log("Running Meep k-point analysis...")
    all_freqs = sim.run_k_points(run_time, interp_k_points)

    if cancel_requested():
        return deps._run_canceled()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = create_run_output_dir("meep_gui_meep_k_points_")
    prefix = cfg.output_prefix.strip() or "meep_k_points"
    csv_path = os.path.join(out_dir, f"{prefix}_bands.csv")
    png_path = os.path.join(out_dir, f"{prefix}_bands.png")

    rows: list[list[float | int]] = []
    first_freq_real = ""
    for k_index, kp in enumerate(interp_k_points):
        point_freqs = []
        if all_freqs is not None and k_index < len(all_freqs):
            point_freqs = _row_freqs(all_freqs[k_index])
        for mode, freq in enumerate(point_freqs, start=1):
            freq_real = float(freq.real)
            freq_imag = float(freq.imag)
            if first_freq_real == "":
                first_freq_real = f"{freq_real:.12g}"
            rows.append([k_index, float(kp.x), float(kp.y), mode, freq_real, freq_imag])

    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["k_index", "kx", "ky", "mode", "freq_real", "freq_imag"])
        writer.writerows(rows)

    fig = plt.figure(figsize=(6, 4), dpi=120)
    ax = fig.add_subplot(111)
    if rows:
        ax.scatter([row[0] for row in rows], [row[4] for row in rows], s=18, color="#1f77b4")
    ax.set_title("Meep K-Points Band Diagram")
    ax.set_xlabel("k-index")
    ax.set_ylabel("Frequency")
    ax.grid(True, linestyle=":", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)

    message = "Meep k points completed."
    if not rows:
        message = "Meep k points completed. No frequencies were found."
    artifacts = create_domain_preview_artifacts(
        state,
        out_dir,
        log,
        build_sim_impl=getattr(deps, "build_sim", None),
    )
    return RunResult(
        status="completed",
        message=message,
        artifacts=artifacts,
        plots=[
            PlotResult(
                title="Meep K-Points Bands",
                x_label="k-index",
                y_label="Frequency",
                csv_path=csv_path,
                png_path=png_path,
                meta={
                    "input_point_count": str(len(entered_points)),
                    "interpolated_point_count": str(len(interp_k_points)),
                    "mode_count": str(len(rows)),
                    "primary_frequency": first_freq_real,
                },
            )
        ],
        meta={
            "input_point_count": str(len(entered_points)),
            "interpolated_point_count": str(len(interp_k_points)),
            "mode_count": str(len(rows)),
            "primary_frequency": first_freq_real,
        },
    )
