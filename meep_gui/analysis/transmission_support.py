from __future__ import annotations

import copy
import csv
import os

from ..model import ProjectState
from .types import ArtifactResult, PlotResult


def find_flux_spec_by_name(specs, name: str):
    for spec in specs:
        if spec.name == name:
            return spec
    return None


def find_run_record_by_id(state: ProjectState, run_id: str):
    for record in state.results:
        if record.run_id == run_id:
            return record
    return None


def artifact_path_by_kind(run_record, kind: str) -> str:
    for artifact in getattr(run_record, "artifacts", []):
        if getattr(artifact, "kind", "") != kind:
            continue
        path = str(getattr(artifact, "path", "") or "").strip()
        if path:
            return path
    return ""


def load_incident_data_from_transmission_csv(csv_path: str) -> tuple[list[float], list[float]]:
    if not os.path.exists(csv_path):
        raise ValueError(
            f"Selected cached reference file does not exist: {csv_path}. "
            "Clear reuse selection or rerun a fresh reference."
        )

    freqs: list[float] = []
    incident: list[float] = []
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            required = {"frequency", "incident"}
            if not required.issubset(fieldnames):
                raise ValueError(
                    "Cached transmission CSV must contain 'frequency' and 'incident' columns."
                )
            for line_no, row in enumerate(reader, start=2):
                try:
                    freq_value = float(str(row.get("frequency", "")).strip())
                    incident_value = float(str(row.get("incident", "")).strip())
                except Exception as exc:
                    raise ValueError(
                        f"Cached transmission CSV has invalid numeric data on line {line_no}."
                    ) from exc
                freqs.append(freq_value)
                incident.append(incident_value)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Failed to read cached transmission CSV '{csv_path}': {exc}") from exc

    if not freqs or not incident:
        raise ValueError("Cached transmission CSV has no usable incident rows.")
    if len(freqs) != len(incident):
        raise ValueError("Cached transmission CSV has mismatched frequency and incident columns.")
    return freqs, incident


def _meta_float(meta: dict[str, str], key: str, run_id: str) -> float:
    raw = str(meta.get(key, "")).strip()
    if not raw:
        raise ValueError(f"Selected cached run '{run_id}' is missing metadata key '{key}'.")
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(
            f"Selected cached run '{run_id}' has invalid metadata value for '{key}'."
        ) from exc


def _meta_int(meta: dict[str, str], key: str, run_id: str) -> int:
    raw = str(meta.get(key, "")).strip()
    if not raw:
        raise ValueError(f"Selected cached run '{run_id}' is missing metadata key '{key}'.")
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"Selected cached run '{run_id}' has invalid metadata value for '{key}'."
        ) from exc


def ensure_reuse_monitor_compatibility(meta: dict[str, str], incident_spec, transmission_spec, run_id: str) -> None:
    ref_incident_fcen = _meta_float(meta, "ref_incident_fcen", run_id)
    ref_incident_df = _meta_float(meta, "ref_incident_df", run_id)
    ref_incident_nfreq = _meta_int(meta, "ref_incident_nfreq", run_id)
    dev_trans_fcen = _meta_float(meta, "dev_trans_fcen", run_id)
    dev_trans_df = _meta_float(meta, "dev_trans_df", run_id)
    dev_trans_nfreq = _meta_int(meta, "dev_trans_nfreq", run_id)
    tol = 1e-12
    compatible = (
        abs(ref_incident_fcen - float(incident_spec.fcen)) <= tol
        and abs(ref_incident_df - float(incident_spec.df)) <= tol
        and int(ref_incident_nfreq) == int(incident_spec.nfreq)
        and abs(dev_trans_fcen - float(transmission_spec.fcen)) <= tol
        and abs(dev_trans_df - float(transmission_spec.df)) <= tol
        and int(dev_trans_nfreq) == int(transmission_spec.nfreq)
    )
    if not compatible:
        raise ValueError(
            f"Selected cached run '{run_id}' is incompatible with current monitor "
            "spectral settings (fcen/df/nfreq). Clear reuse selection or rerun reference."
        )


def ensure_exact_frequency_grid(expected_freqs: list[float], actual_freqs: list[float]) -> None:
    if len(expected_freqs) != len(actual_freqs):
        raise RuntimeError(
            "Cached reference incident data length does not match scattering monitor output. "
            "Clear reuse selection or rerun a fresh reference."
        )
    for idx, (cached, actual) in enumerate(zip(expected_freqs, actual_freqs)):
        if abs(float(cached) - float(actual)) > 1e-12:
            raise RuntimeError(
                "Cached reference frequency grid does not match scattering monitor frequencies "
                f"(first mismatch at index {idx}). Clear reuse selection or rerun a fresh reference."
            )


def flux_by_name(flux_results) -> dict[str, object]:
    return {item.name: item for item in flux_results}


def safe_ratio(num: float, den: float) -> float:
    if abs(den) < 1e-18:
        return float("nan")
    return num / den


def build_transmission_reference_state(state: ProjectState) -> ProjectState:
    reference_state = copy.deepcopy(state)
    reference_cfg = copy.deepcopy(state.analysis.transmission_spectrum.reference_state)
    reference_state.domain = reference_cfg.domain
    reference_state.geometries = list(reference_cfg.geometries)
    reference_state.sources = list(reference_cfg.sources)
    reference_state.flux_monitors = list(reference_cfg.flux_monitors)
    return reference_state


def export_transmission_outputs(
    *,
    output_dir: str,
    output_prefix: str,
    freqs: list[float],
    incident: list[float],
    transmitted: list[float],
    reflection: list[float] | None,
    trans_ratio: list[float],
    refl_ratio: list[float] | None,
) -> tuple[ArtifactResult, PlotResult]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    safe_prefix = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in output_prefix) or "transmission"
    csv_path = os.path.join(output_dir, f"{safe_prefix}_spectrum.csv")
    png_path = os.path.join(output_dir, f"{safe_prefix}_spectrum.png")

    headers = ["frequency", "incident", "transmitted", "T"]
    if reflection is not None:
        headers.extend(["reflected", "R", "T_plus_R"])

    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for i, freq in enumerate(freqs):
            row: list[float] = [freq, incident[i], transmitted[i], trans_ratio[i]]
            if reflection is not None and refl_ratio is not None:
                row.extend([reflection[i], refl_ratio[i], trans_ratio[i] + refl_ratio[i]])
            writer.writerow(row)

    fig = plt.figure(figsize=(6.5, 4.5), dpi=120)
    ax = fig.add_subplot(111)
    ax.plot(freqs, trans_ratio, linewidth=1.6, label="T")
    if reflection is not None and refl_ratio is not None:
        ax.plot(freqs, refl_ratio, linewidth=1.6, label="R")
        ax.plot(
            freqs,
            [trans_ratio[i] + refl_ratio[i] for i in range(len(freqs))],
            linewidth=1.2,
            linestyle="--",
            label="T+R",
        )
    ax.set_xlabel("Frequency")
    ax.set_ylabel("Normalized Response")
    ax.set_title("Transmission Spectrum")
    ax.grid(True, linestyle=":", linewidth=0.5)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)

    artifact = ArtifactResult(kind="transmission_csv", label=os.path.basename(csv_path), path=csv_path)
    plot = PlotResult(
        title="Transmission Spectrum",
        x_label="Frequency",
        y_label="Normalized Response",
        csv_path=csv_path,
        png_path=png_path,
    )
    return artifact, plot
