"""Request/response models for the JSON API.

Length caps bound the work a single request can cause: at most ``MAX_ROWS`` rows of ``MAX_FIELD`` characters each.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from timesheet_calc.core import ClockMode

MAX_ROWS = 100
MAX_FIELD = 16

TimeText = Annotated[str, Field(max_length=MAX_FIELD)]


class EntryIn(BaseModel):
    """One start/end row. Blank strings mean the field is empty."""

    start: TimeText = ""
    end: TimeText = ""


class CalcRequest(BaseModel):
    """Payload for ``POST /api/calc``."""

    entries: list[EntryIn] = Field(max_length=MAX_ROWS)
    mode: ClockMode = ClockMode.INFER


class SumRequest(BaseModel):
    """Payload for ``POST /api/sum``."""

    durations: list[TimeText] = Field(max_length=MAX_ROWS)


class LineResult(BaseModel):
    """Outcome for one row. All fields are null for a blank row; ``error`` is set for an invalid one."""

    duration: str | None = None
    decimal_hours: str | None = None
    error: str | None = None


class TotalResponse(BaseModel):
    """Per-row results plus the total of every valid row."""

    results: list[LineResult]
    total: str
    total_decimal_hours: str
    error_count: int


class MeResponse(BaseModel):
    """Payload for ``GET /api/me``."""

    user: str | None
    auth_mode: str
