from .dumpers import dump_state_dict
from .loaders import load_state_dict


def state_to_dict(state):
    return dump_state_dict(state)


def state_from_dict(raw):
    return load_state_dict(raw)


__all__ = ["state_from_dict", "state_to_dict"]
