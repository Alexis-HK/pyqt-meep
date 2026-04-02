from __future__ import annotations

import os
import tempfile

from ..run_protocol import RUN_WORKSPACE_ENV


def create_run_output_dir(prefix: str) -> str:
    base_dir = os.environ.get(RUN_WORKSPACE_ENV, "").strip()
    if base_dir:
        os.makedirs(base_dir, exist_ok=True)
        return tempfile.mkdtemp(prefix=prefix, dir=base_dir)
    return tempfile.mkdtemp(prefix=prefix)
