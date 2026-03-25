from __future__ import annotations


def _prepare_real_2d_array(data):
    import numpy as np

    arr = np.asarray(data)
    arr = np.squeeze(arr)
    if np.iscomplexobj(arr):
        arr = np.real(arr)
    if arr.ndim != 2:
        arr = np.atleast_2d(arr)
    return arr


def save_field_array_csv(path: str, field_component) -> None:
    import numpy as np

    arr = _prepare_real_2d_array(field_component)
    np.savetxt(path, arr.T, delimiter=",")


def save_plot2d_field_image(path: str, sim, component, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig = plt.figure(figsize=(6, 5), dpi=120)
    ax = fig.add_subplot(111)
    sim.plot2D(
        ax=ax,
        fields=component,
        field_parameters={
            "alpha": 0.85,
            "cmap": "RdBu",
            "interpolation": "spline36",
            "post_process": np.real,
        },
    )
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_field_overlay_image(path: str, field_component, converted_eps, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    field_arr = _prepare_real_2d_array(field_component)

    eps_arr = _prepare_real_2d_array(converted_eps)

    import numpy as np

    vmax = float(np.nanmax(np.abs(field_arr))) if field_arr.size else 1.0
    if not vmax or vmax != vmax:
        vmax = 1.0

    fig = plt.figure(figsize=(5, 4), dpi=120)
    ax = fig.add_subplot(111)
    ax.imshow(eps_arr.T, interpolation="spline36", cmap="binary")
    ax.imshow(
        field_arr.T,
        interpolation="spline36",
        cmap="RdBu",
        alpha=0.85,
        vmin=-vmax,
        vmax=vmax,
    )
    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
