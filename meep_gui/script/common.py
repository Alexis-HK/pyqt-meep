from __future__ import annotations


def analysis_label(kind: str) -> str:
    return {
        "field_animation": "Field Animation",
        "harminv": "Harminv",
        "transmission_spectrum": "Transmission Spectrum",
        "frequency_domain_solver": "Frequency Domain Solver",
        "meep_k_points": "Meep K Points",
        "mpb_modesolver": "MPB",
    }.get(kind, kind)


def line(lines: list[str], text: str = "") -> None:
    lines.append(text)
