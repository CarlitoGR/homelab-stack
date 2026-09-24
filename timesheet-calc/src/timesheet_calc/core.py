"""Core parsing and arithmetic for timesheet calculations.

All values are stored as integer minutes. Floats never touch the arithmetic, so there is no rounding drift;
conversion to decimal hours happens only at output time via ``Decimal``.

Input rules (compatible with the miraclesalad.com timesheet tool):
    * ``:`` or ``.`` delimits hours and minutes. The segment after the delimiter is MINUTES, not a
      decimal fraction: ``12.8`` is 12:08 and ``7.5`` is 7:05.
    * 1-2 bare digits are whole hours: ``8`` is 8:00.
    * 3-4 bare digits are H:MM / HH:MM: ``130`` is 1:30, ``1500`` is 15:00.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

MINUTES_PER_HOUR = 60
MINUTES_PER_HALF_DAY = 12 * MINUTES_PER_HOUR
MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR
_MAX_HOUR_DIGITS = 2

_DELIMITED = re.compile(r"(?P<hours>\d+)[:.](?P<minutes>\d{1,2})")
_BARE = re.compile(r"\d{1,4}")


class TimeParseError(ValueError):
    """Raised when input text cannot be interpreted as a time value."""


class AmbiguousTimeError(ValueError):
    """Raised when a start/end pair cannot be resolved to a single elapsed time."""


class ClockMode(StrEnum):
    """How to resolve an end time that falls before its start time.

    INFER:  Emulates the original tool. Times are read as a 12-hour dial first: if adding 12 hours to an
            AM-looking end time puts it after the start, use that (12:10 -> 3 means 3 PM). Otherwise the
            shift is treated as overnight (22 -> 6 is 8 hours).
    STRICT: Inputs are 24-hour clock times, full stop. An end before the start is always overnight
            (13 -> 3 is 14 hours).
    """

    INFER = "infer"
    STRICT = "strict"


def _split(text: str) -> tuple[int, int]:
    """Split raw input into (hours, minutes) using the documented rules.

    Args:
        text: Raw user input, e.g. ``"7:45"``, ``"7.45"``, ``"745"``, or ``"7"``.

    Returns:
        Tuple of (hours, minutes). Hours are not range-checked here; callers apply their own limits.

    Raises:
        TimeParseError: If the format is unrecognized or minutes are 60 or more.
    """
    cleaned = text.strip()
    if not cleaned:
        msg = "empty time value"
        raise TimeParseError(msg)

    if match := _DELIMITED.fullmatch(cleaned):
        hours, minutes = int(match["hours"]), int(match["minutes"])
    elif _BARE.fullmatch(cleaned):
        if len(cleaned) <= _MAX_HOUR_DIGITS:
            hours, minutes = int(cleaned), 0
        else:
            hours, minutes = int(cleaned[:-2]), int(cleaned[-2:])
    else:
        msg = f"unrecognized time format: {text!r} (use H:MM, H.MM, H, HMM, or HHMM)"
        raise TimeParseError(msg)

    if minutes >= MINUTES_PER_HOUR:
        msg = f"minutes must be 0-59 in {text!r}"
        raise TimeParseError(msg)
    return hours, minutes


def _format_hm(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, MINUTES_PER_HOUR)
    return f"{hours}:{minutes:02d}"


@dataclass(frozen=True, slots=True, order=True)
class ClockTime:
    """A wall-clock time, stored as minutes since midnight (0:00 through 24:00 inclusive)."""

    minutes: int

    def __post_init__(self) -> None:
        """Validate the range."""
        if not 0 <= self.minutes <= MINUTES_PER_DAY:
            msg = f"clock time out of range: {self.minutes} minutes"
            raise ValueError(msg)

    @classmethod
    def parse(cls, text: str) -> ClockTime:
        """Parse a clock time such as ``"7:45"``, ``"12.8"``, ``"1500"``, or ``"6"``.

        Raises:
            TimeParseError: If the input is malformed or outside 0:00-24:00.
        """
        hours, minutes = _split(text)
        total = hours * MINUTES_PER_HOUR + minutes
        if total > MINUTES_PER_DAY:
            msg = f"clock time must be between 0:00 and 24:00: {text!r}"
            raise TimeParseError(msg)
        return cls(total)

    def __str__(self) -> str:
        """Render as H:MM."""
        return _format_hm(self.minutes)


@dataclass(frozen=True, slots=True, order=True)
class Duration:
    """A non-negative span of time, stored as whole minutes. Hours are unbounded (e.g. 41:05)."""

    minutes: int

    def __post_init__(self) -> None:
        """Reject negative spans."""
        if self.minutes < 0:
            msg = f"duration cannot be negative: {self.minutes} minutes"
            raise ValueError(msg)

    @classmethod
    def parse(cls, text: str) -> Duration:
        """Parse a duration such as ``"26:15"``, ``"8.15"``, or ``"6"``.

        Raises:
            TimeParseError: If the input is malformed.
        """
        hours, minutes = _split(text)
        return cls(hours * MINUTES_PER_HOUR + minutes)

    def __add__(self, other: Duration) -> Duration:
        """Add two durations."""
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(self.minutes + other.minutes)

    def decimal_hours(self, places: int = 2) -> Decimal:
        """Convert to decimal hours for payroll systems (41:05 -> 41.08), rounded half-up.

        Args:
            places: Number of decimal places to keep.
        """
        quantum = Decimal(1).scaleb(-places)
        return (Decimal(self.minutes) / MINUTES_PER_HOUR).quantize(quantum, rounding=ROUND_HALF_UP)

    def __str__(self) -> str:
        """Render as H:MM."""
        return _format_hm(self.minutes)


def elapsed(start: ClockTime, end: ClockTime, mode: ClockMode = ClockMode.INFER) -> Duration:
    """Compute the time between two clock readings.

    Args:
        start: Start of the block.
        end: End of the block.
        mode: How to resolve an end that is not after the start. See ``ClockMode``.

    Returns:
        The elapsed duration, always less than 24 hours unless ``end`` is 24:00.

    Raises:
        AmbiguousTimeError: If start equals end. The span could be 0, 12, or 24 hours. The original tool
            guesses; this one refuses and makes you say what you mean.
    """
    if end.minutes > start.minutes:
        return Duration(end.minutes - start.minutes)

    if end.minutes == start.minutes:
        msg = f"start and end are both {start}; use 24-hour times (e.g. 6-18) or 0-24 for a full day"
        raise AmbiguousTimeError(msg)

    if mode is ClockMode.INFER and end.minutes < MINUTES_PER_HALF_DAY:
        as_pm = end.minutes + MINUTES_PER_HALF_DAY
        if as_pm > start.minutes:
            return Duration(as_pm - start.minutes)

    return Duration(end.minutes + MINUTES_PER_DAY - start.minutes)


@dataclass(frozen=True, slots=True)
class TimeEntry:
    """One worked block: a start/end pair."""

    start: ClockTime
    end: ClockTime

    @classmethod
    def parse(cls, text: str) -> TimeEntry:
        """Parse a ``START-END`` string such as ``"7:45-11"`` or ``"2200-0600"``.

        Raises:
            TimeParseError: If the pair is malformed.
        """
        start_text, separator, end_text = text.partition("-")
        if not separator or "-" in end_text:
            msg = f"expected START-END, got {text!r}"
            raise TimeParseError(msg)
        return cls(ClockTime.parse(start_text), ClockTime.parse(end_text))

    def duration(self, mode: ClockMode = ClockMode.INFER) -> Duration:
        """Elapsed time for this entry."""
        return elapsed(self.start, self.end, mode)


def sum_durations(durations: Iterable[Duration]) -> Duration:
    """Total a sequence of durations. An empty sequence totals 0:00."""
    return Duration(sum(duration.minutes for duration in durations))
