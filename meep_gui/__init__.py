"""PyQt-Meep package.

The package root stays headless-importable so model, persistence, validation,
script, and scene modules can be used without Qt installed. GUI entrypoints
remain explicit via ``meep_gui.app`` / ``meep_gui.bootstrap``.
"""


def main() -> int:
    from .app import main as app_main

    return app_main()


__all__ = ["main"]
