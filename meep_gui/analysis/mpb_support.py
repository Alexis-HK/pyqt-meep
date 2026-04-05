from __future__ import annotations

import csv

from ..model import ProjectState
from ..primitives import geometry_kind, material_kind
from ..scene import compile_project_scene
from ..scene.runtime import eval_required


def build_mpb_geometry(state: ProjectState, mp, values: dict[str, float], *, deps) -> list[object]:
    compiled = compile_project_scene(state, parameter_values=values)
    materials: dict[str, float] = {}
    for medium in compiled.scene.media:
        if medium.name:
            materials[medium.name] = material_kind(medium.kind).resolve_index(
                medium,
                compiled.context,
                eval_required,
            )

    geometry = []
    for obj in compiled.scene.objects:
        if obj.spatial_material.kind != "uniform":
            raise ValueError(f"Geometry '{obj.name}': unsupported spatial material kind.")
        medium_name = obj.spatial_material.medium_name
        if medium_name not in materials:
            raise ValueError(f"Geometry '{obj.name}': unknown material '{medium_name}'")
        medium = mp.Medium(index=materials[medium_name])
        geometry.append(
            geometry_kind(obj.geometry.kind).build_mpb_object(
                obj,
                medium,
                mp,
                compiled.context,
                eval_required,
            )
        )
    return geometry


def run_modesolver(ms) -> None:
    if hasattr(ms, "run"):
        ms.run()
    elif hasattr(ms, "run_tm"):
        ms.run_tm()
    else:
        raise RuntimeError("ModeSolver run method is unavailable.")


def run_modesolver_pol(ms, polarization: str, mpb_module=None, *, fix_phase: bool = False) -> None:
    callbacks = []
    if fix_phase and mpb_module is not None:
        callback_name = "fix_efield_phase" if polarization == "tm" else "fix_hfield_phase"
        callback = getattr(mpb_module, callback_name, None)
        if callable(callback):
            callbacks.append(callback)
    if polarization == "tm" and hasattr(ms, "run_tm"):
        ms.run_tm(*callbacks)
    elif polarization == "te" and hasattr(ms, "run_te"):
        ms.run_te(*callbacks)
    else:
        run_modesolver(ms)


def fix_field_phase(ms, polarization: str) -> None:
    method = getattr(ms, "fix_field_phase", None)
    if callable(method):
        try:
            method()
            return
        except Exception:
            pass
    specific = "fix_efield_phase" if polarization == "tm" else "fix_hfield_phase"
    method = getattr(ms, specific, None)
    if callable(method):
        try:
            method()
        except Exception:
            pass


def get_field_data(ms, polarization: str, band_idx: int):
    method = getattr(ms, "get_efield" if polarization == "tm" else "get_hfield", None)
    if method is None:
        return None
    try:
        return method(band_idx, bloch_phase=True)
    except TypeError:
        return method(band_idx)
    except Exception:
        return None


def component_from_field_array(data, _polarization: str):
    import numpy as np

    arr = np.asarray(data)
    if arr.ndim >= 1 and arr.shape[-1] >= 3:
        arr = arr[..., 2]
    return arr


def save_band_csv(path: str, k_points: list[object], bands_by_pol: dict[str, object]) -> None:
    import numpy as np

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["polarization", "k_index", "kx", "ky", "band", "frequency"])
        for pol in ("tm", "te"):
            all_freqs = bands_by_pol.get(pol)
            if all_freqs is None:
                continue
            for k_idx, kp in enumerate(k_points):
                row_vals = np.atleast_1d(all_freqs[k_idx] if k_idx < len(all_freqs) else [])
                for band_idx, freq in enumerate(row_vals, start=1):
                    writer.writerow([pol, k_idx, float(kp.x), float(kp.y), band_idx, float(freq)])


def save_band_plot(path: str, k_points: list[object], bands_by_pol: dict[str, object]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig = plt.figure(figsize=(6, 4), dpi=120)
    ax = fig.add_subplot(111)
    colors = {"te": "red", "tm": "blue"}
    labels = {"te": "TE", "tm": "TM"}
    shown_labels: set[str] = set()
    x = list(range(len(k_points)))
    for pol in ("te", "tm"):
        all_freqs = bands_by_pol.get(pol)
        if all_freqs is None:
            continue
        arr = np.asarray(all_freqs, dtype=float)
        if arr.ndim == 1:
            arr = arr[:, np.newaxis]
        if arr.ndim != 2 or not arr.size:
            continue
        xvals = x[: min(len(x), arr.shape[0])]
        for band_idx in range(arr.shape[1]):
            ax.plot(
                xvals,
                arr[: len(xvals), band_idx],
                "-",
                linewidth=1.2,
                color=colors[pol],
                alpha=0.9,
                label=labels[pol] if pol not in shown_labels else None,
            )
            shown_labels.add(pol)
    ax.set_title("MPB Band Diagram")
    ax.set_xlabel("k-index")
    ax.set_ylabel("Frequency")
    ax.grid(True, linestyle=":", linewidth=0.5)
    if shown_labels:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_image(path: str, data, title: str, cmap: str = "binary", interpolation: str = "nearest") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = np.asarray(data)
    if arr.ndim > 2:
        arr = arr[..., 0]
    arr = np.squeeze(arr)
    if np.iscomplexobj(arr):
        arr = np.abs(arr)
    if arr.ndim != 2:
        arr = np.atleast_2d(arr)
    arr = np.asarray(arr, dtype=float)

    fig = plt.figure(figsize=(5, 4), dpi=120)
    ax = fig.add_subplot(111)
    ax.imshow(arr.T, origin="lower", interpolation=interpolation, cmap=cmap)
    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_epsilon_image(path: str, converted_eps, title: str = "MPB Epsilon") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(5, 4), dpi=120)
    ax = fig.add_subplot(111)
    ax.imshow(converted_eps.T, interpolation="spline36", cmap="binary")
    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
