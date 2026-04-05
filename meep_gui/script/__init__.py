from __future__ import annotations


def generate_script(*args, **kwargs):
    from .generator import generate_script as _generate_script

    return _generate_script(*args, **kwargs)


__all__ = ["generate_script"]
