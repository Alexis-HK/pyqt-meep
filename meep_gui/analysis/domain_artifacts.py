from __future__ import annotations

import os

from ..model import ProjectState
from ..preview.domain_render import save_domain_preview_png
from .types import ArtifactResult, LogFn


def create_domain_preview_artifacts(
    state: ProjectState,
    out_dir: str,
    log: LogFn,
    *,
    export_dir: str = "",
    build_sim_impl=None,
) -> list[ArtifactResult]:
    previews: list[tuple[str | None, str]] = []
    if state.analysis.kind == "mpb_modesolver":
        return []
    if state.analysis.kind == "transmission_spectrum":
        previews = [
            ("reference", "domain_preview_reference.png"),
            ("scattering", "domain_preview_scattering.png"),
        ]
    else:
        previews = [(None, "domain_preview.png")]

    artifacts: list[ArtifactResult] = []
    for preview_domain, file_name in previews:
        path = os.path.join(out_dir, file_name)
        try:
            issues = save_domain_preview_png(
                path,
                state,
                preview_domain=preview_domain,
                build_sim_impl=build_sim_impl,
            )
        except Exception as exc:
            log(f"Warning: could not save domain preview '{file_name}': {exc}")
            continue
        for issue in issues:
            log(issue.message)
        meta = {"export_name": file_name}
        if export_dir:
            meta["export_dir"] = export_dir
        if preview_domain:
            meta["domain"] = preview_domain
        artifacts.append(
            ArtifactResult(
                kind="domain_preview_png",
                label=file_name,
                path=path,
                meta=meta,
            )
        )
    return artifacts
