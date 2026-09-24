"""Timesheet calculator: elapsed time from start/end pairs and H:MM duration sums."""

from timesheet_calc.core import (
    AmbiguousTimeError,
    ClockMode,
    ClockTime,
    Duration,
    TimeEntry,
    TimeParseError,
    elapsed,
    sum_durations,
)

__version__ = "1.2.0"

__all__ = [
    "AmbiguousTimeError",
    "ClockMode",
    "ClockTime",
    "Duration",
    "TimeEntry",
    "TimeParseError",
    "__version__",
    "elapsed",
    "sum_durations",
]
