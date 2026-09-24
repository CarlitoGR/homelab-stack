"""Run the web server: ``timesheet-web`` or ``python -m timesheet_calc.web``."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Parse server options and start uvicorn."""
    parser = argparse.ArgumentParser(prog="timesheet-web", description="Serve the timesheet calculator web app.")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (use 0.0.0.0 inside a container)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (development only)")
    args = parser.parse_args(argv)
    uvicorn.run("timesheet_calc.web.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
