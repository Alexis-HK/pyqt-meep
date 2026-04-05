from __future__ import annotations

from .base import AnalysisRecipe
from .field_animation import FieldAnimationRecipe
from .frequency_domain import FrequencyDomainSolverRecipe
from .harminv import HarminvRecipe
from .meep_k_points import MeepKPointsRecipe
from .mpb_modesolver import MpbModeSolverRecipe
from .transmission import TransmissionSpectrumRecipe

RECIPE_REGISTRY: dict[str, AnalysisRecipe] = {
    "field_animation": FieldAnimationRecipe(
        recipe_id="field_animation",
        display_name="Field Animation",
        backend="meep_fdtd",
    ),
    "harminv": HarminvRecipe(
        recipe_id="harminv",
        display_name="Harminv",
        backend="meep_fdtd",
    ),
    "transmission_spectrum": TransmissionSpectrumRecipe(
        recipe_id="transmission_spectrum",
        display_name="Transmission Spectrum",
        backend="meep_fdtd",
    ),
    "frequency_domain_solver": FrequencyDomainSolverRecipe(
        recipe_id="frequency_domain_solver",
        display_name="Frequency Domain Solver",
        backend="meep_fdtd",
    ),
    "meep_k_points": MeepKPointsRecipe(
        recipe_id="meep_k_points",
        display_name="Meep K Points",
        backend="meep_fdtd",
    ),
    "mpb_modesolver": MpbModeSolverRecipe(
        recipe_id="mpb_modesolver",
        display_name="MPB",
        backend="mpb",
    ),
}


def get_recipe(kind: str) -> AnalysisRecipe:
    try:
        return RECIPE_REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported analysis kind: {kind}") from exc
