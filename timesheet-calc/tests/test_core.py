from decimal import Decimal

import pytest

from timesheet_calc import (
    AmbiguousTimeError,
    ClockMode,
    ClockTime,
    Duration,
    TimeEntry,
    TimeParseError,
    elapsed,
    sum_durations,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("7:45", 7 * 60 + 45),
        ("7.15", 7 * 60 + 15),
        ("12.8", 12 * 60 + 8),  # minutes, not a decimal fraction
        ("7.5", 7 * 60 + 5),  # the trap: NOT 7:30
        ("8", 8 * 60),
        ("12", 12 * 60),
        ("130", 90),
        ("1207", 12 * 60 + 7),
        ("1500", 15 * 60),
        ("0", 0),
        ("24", 24 * 60),
        ("  9:05  ", 9 * 60 + 5),
    ],
)
def test_clock_parse(text: str, expected: int) -> None:
    assert ClockTime.parse(text).minutes == expected


@pytest.mark.parametrize("text", ["", "abc", "7:60", "12.80", "25", "24:01", "12345", "7:", ":30", "-3", "7:5:1"])
def test_clock_parse_rejects(text: str) -> None:
    with pytest.raises(TimeParseError):
        ClockTime.parse(text)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("7:45", "11", "3:15"),
        ("12:10", "3", "2:50"),  # 3 inferred as 15:00
        ("4", "4:30", "0:30"),
        ("6", "18", "12:00"),
        ("22", "6", "8:00"),  # +12 still before start -> overnight
        ("13", "2", "1:00"),  # 1 PM -> 2 PM
        ("13", "12:30", "23:30"),  # end already PM-range -> overnight
        ("0", "24", "24:00"),
    ],
)
def test_elapsed_infer(start: str, end: str, expected: str) -> None:
    assert str(elapsed(ClockTime.parse(start), ClockTime.parse(end), ClockMode.INFER)) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("12:10", "3", "14:50"),
        ("13", "2", "13:00"),
        ("2200", "0600", "8:00"),
        ("8", "17", "9:00"),
    ],
)
def test_elapsed_strict(start: str, end: str, expected: str) -> None:
    assert str(elapsed(ClockTime.parse(start), ClockTime.parse(end), ClockMode.STRICT)) == expected


@pytest.mark.parametrize("mode", list(ClockMode))
def test_equal_times_are_ambiguous(mode: ClockMode) -> None:
    with pytest.raises(AmbiguousTimeError):
        elapsed(ClockTime.parse("6"), ClockTime.parse("6"), mode)


def test_page_example_chains_into_sum() -> None:
    entries = [TimeEntry.parse(raw) for raw in ("7:45-11", "12:10-3", "4-4:30")]
    assert str(sum_durations(entry.duration() for entry in entries)) == "6:35"


def test_sum_carries_minutes() -> None:
    total = sum_durations(Duration.parse(value) for value in ("6:35", "8:15", "26:15"))
    assert str(total) == "41:05"
    assert total.decimal_hours() == Decimal("41.08")


def test_sum_empty() -> None:
    assert sum_durations([]) == Duration(0)


def test_duration_add() -> None:
    assert Duration(50) + Duration(20) == Duration(70)


def test_duration_add_rejects_other_types() -> None:
    with pytest.raises(TypeError):
        Duration(1) + 1  # type: ignore[operator]


@pytest.mark.parametrize(
    ("minutes", "places", "expected"),
    [(45, 2, "0.75"), (5, 2, "0.08"), (1, 2, "0.02"), (20, 3, "0.333"), (0, 2, "0.00")],
)
def test_decimal_hours(minutes: int, places: int, expected: str) -> None:
    assert Duration(minutes).decimal_hours(places) == Decimal(expected)


def test_negative_duration_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        Duration(-1)


def test_clock_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="out of range"):
        ClockTime(24 * 60 + 1)


@pytest.mark.parametrize("text", ["7:45", "7:45-11-12", "-11", "7:45-"])
def test_entry_parse_rejects(text: str) -> None:
    with pytest.raises(TimeParseError):
        TimeEntry.parse(text)
