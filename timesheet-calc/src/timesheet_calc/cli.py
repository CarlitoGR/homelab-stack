"""Command-line interface.

Examples:
    timesheet calc 7:45-11 12:10-3 4-4:30
    timesheet calc 2200-0600 --mode strict --decimal
    timesheet sum 6:35 8:15 26:15
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from timesheet_calc import __version__
from timesheet_calc.core import ClockMode, Duration, TimeEntry, sum_durations

if TYPE_CHECKING:
    from collections.abc import Sequence

EXIT_OK = 0
EXIT_USAGE = 2
_PAIR_WIDTH = 14  # "HH:MM -> HH:MM"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timesheet",
        description="Timesheet calculator. Military (24-hour) time removes all AM/PM guesswork.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    calc = subparsers.add_parser("calc", help="elapsed time for START-END pairs, plus a total")
    calc.add_argument("entries", nargs="+", metavar="START-END", help="e.g. 7:45-11, 12.10-3, 2200-0600")
    calc.add_argument(
        "--mode",
        choices=[mode.value for mode in ClockMode],
        default=ClockMode.INFER.value,
        help="infer: 12-hour guessing like the original tool (default); strict: pure 24-hour clock",
    )
    calc.add_argument("--decimal", action="store_true", help="also show decimal hours")

    total = subparsers.add_parser("sum", help="add H:MM durations")
    total.add_argument("durations", nargs="+", metavar="H:MM", help="e.g. 6:35 8:15 26:15")
    total.add_argument("--decimal", action="store_true", help="also show decimal hours")

    return parser


def _format(duration: Duration, *, decimal: bool) -> str:
    return f"{duration} ({duration.decimal_hours()} h)" if decimal else str(duration)


def _run_calc(entries: Sequence[str], mode: ClockMode, *, decimal: bool) -> list[str]:
    lines: list[str] = []
    durations: list[Duration] = []
    for raw in entries:
        entry = TimeEntry.parse(raw)
        duration = entry.duration(mode)
        durations.append(duration)
        pair = f"{entry.start!s:>5} -> {entry.end!s:>5}"
        lines.append(f"{pair}  {_format(duration, decimal=decimal)}")
    lines.append(f"{'Total':>{_PAIR_WIDTH}}  {_format(sum_durations(durations), decimal=decimal)}")
    return lines


def _run_sum(values: Sequence[str], *, decimal: bool) -> list[str]:
    total = sum_durations(Duration.parse(value) for value in values)
    return [f"Total  {_format(total, decimal=decimal)}"]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "calc":
            lines = _run_calc(args.entries, ClockMode(args.mode), decimal=args.decimal)
        else:
            lines = _run_sum(args.durations, decimal=args.decimal)
    except ValueError as exc:
        sys.stderr.write(f"timesheet: error: {exc}\n")
        return EXIT_USAGE
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK
