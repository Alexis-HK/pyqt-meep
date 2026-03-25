from __future__ import annotations


def import_meep():
    try:
        import meep as mp
    except Exception as exc:
        raise RuntimeError(f"Meep import failed: {exc}") from exc
    if not hasattr(mp, "Simulation"):
        source = getattr(mp, "__file__", "<unknown>")
        raise RuntimeError(
            "Imported module 'meep' is not the pymeep package. "
            f"Loaded from: {source}. "
            "If this points to a local meep.py file, rename it."
        )
    return mp


def component_map(mp):
    def get_component(name: str):
        return getattr(mp, name, getattr(mp, "Ez", None))

    return {
        "Ex": get_component("Ex"),
        "Ey": get_component("Ey"),
        "Ez": get_component("Ez"),
        "Hx": get_component("Hx"),
        "Hy": get_component("Hy"),
        "Hz": get_component("Hz"),
    }
