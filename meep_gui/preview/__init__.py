from __future__ import annotations

__all__ = ["DomainPreviewWidget", "RenderIssue"]


def __getattr__(name: str):
    if name == "DomainPreviewWidget":
        from .domain import DomainPreviewWidget

        return DomainPreviewWidget
    if name == "RenderIssue":
        from .domain_render import RenderIssue

        return RenderIssue
    raise AttributeError(name)
