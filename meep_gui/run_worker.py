from __future__ import annotations

import argparse
import os
import sys
import traceback

from .analysis.types import RunResult
from .run_protocol import (
    RUN_WORKSPACE_ENV,
    encode_event,
    invoke_run_target,
    load_run_target,
    project_state_from_json,
    run_result_to_dict,
)


def _emit(stream, event_type: str, **payload) -> None:
    stream.write(encode_event(event_type, **payload) + "\n")
    stream.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a pyqt-meep analysis in a worker process.")
    parser.add_argument("--module", required=True)
    parser.add_argument("--qualname", required=True)
    parser.add_argument("--event-fd", required=True, type=int)
    parser.add_argument("--cancel-path", required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args(argv)

    state = project_state_from_json(sys.stdin.read())
    os.environ[RUN_WORKSPACE_ENV] = args.workspace

    with os.fdopen(args.event_fd, "w", encoding="utf-8", buffering=1) as stream:
        def log(message: str) -> None:
            _emit(stream, "log", message=str(message))

        def cancel_requested() -> bool:
            return os.path.exists(args.cancel_path)

        def publish_result(result: RunResult) -> None:
            if not isinstance(result, RunResult):
                raise TypeError("Worker publish_result only supports RunResult instances.")
            _emit(stream, "published", result=run_result_to_dict(result))

        try:
            target = load_run_target(args.module, args.qualname)
            result = invoke_run_target(
                target,
                state,
                log,
                cancel_requested,
                publish_result=publish_result,
            )
            if not isinstance(result, RunResult):
                raise TypeError("Worker target returned a non-RunResult object.")
            _emit(stream, "result", result=run_result_to_dict(result))
            return 0
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            _emit(stream, "error", message=str(exc))
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
