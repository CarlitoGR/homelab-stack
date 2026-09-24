"""FastAPI application: JSON API under ``/api`` and the single-page UI at ``/``.

All time math lives in ``timesheet_calc.core``. This module only translates between HTTP and that API, reporting
errors per row so one bad entry never blanks out the rest of the sheet.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from timesheet_calc import __version__
from timesheet_calc.core import ClockTime, Duration, TimeEntry, sum_durations
from timesheet_calc.web.auth import AuthSettings, current_user
from timesheet_calc.web.schemas import CalcRequest, EntryIn, LineResult, MeResponse, SumRequest, TotalResponse

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

STATIC_DIR = Path(__file__).parent / "static"

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}

# Protected routes require an authenticated user when TIMESHEET_AUTH_MODE=header.
router = APIRouter(dependencies=[Depends(current_user)])
# Public routes: the health probe must work without a user so Docker and Uptime Kuma can reach it.
public_router = APIRouter()


def _ok(duration: Duration) -> LineResult:
    return LineResult(duration=str(duration), decimal_hours=str(duration.decimal_hours()))


def _calc_line(entry: EntryIn, request: CalcRequest) -> tuple[LineResult, Duration | None]:
    start, end = entry.start.strip(), entry.end.strip()
    if not start and not end:
        return LineResult(), None
    if not start or not end:
        return LineResult(error="Enter both a start and an end time."), None
    try:
        duration = TimeEntry(ClockTime.parse(start), ClockTime.parse(end)).duration(request.mode)
    except ValueError as exc:
        return LineResult(error=str(exc)), None
    return _ok(duration), duration


def _sum_line(text: str) -> tuple[LineResult, Duration | None]:
    if not text.strip():
        return LineResult(), None
    try:
        duration = Duration.parse(text)
    except ValueError as exc:
        return LineResult(error=str(exc)), None
    return _ok(duration), duration


def _build_response(lines: list[tuple[LineResult, Duration | None]]) -> TotalResponse:
    total = sum_durations(duration for _, duration in lines if duration is not None)
    return TotalResponse(
        results=[result for result, _ in lines],
        total=str(total),
        total_decimal_hours=str(total.decimal_hours()),
        error_count=sum(1 for result, _ in lines if result.error),
    )


@router.post("/calc")
def calculate_hours(request: CalcRequest) -> TotalResponse:
    """Elapsed time for each start/end row, plus the total of all valid rows."""
    return _build_response([_calc_line(entry, request) for entry in request.entries])


@router.post("/sum")
def sum_hours(request: SumRequest) -> TotalResponse:
    """Sum H:MM durations, reporting invalid entries per row."""
    return _build_response([_sum_line(text) for text in request.durations])


@router.get("/me")
def me(user: Annotated[str | None, Depends(current_user)], request: Request) -> MeResponse:
    """Report who the proxy authenticated. ``user`` is null when auth is disabled."""
    settings: AuthSettings = request.app.state.auth
    return MeResponse(user=user, auth_mode=settings.mode.value)


@public_router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe for Docker and load balancers."""
    return {"status": "ok"}


def create_app(auth: AuthSettings | None = None) -> FastAPI:
    """Build the application. Docs live under ``/api`` so the UI owns ``/``.

    Args:
        auth: Authentication settings. Defaults to the environment, so a misconfigured container fails at
            startup instead of serving requests with the wrong policy.
    """
    app = FastAPI(
        title="Timesheet Calculator",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.auth = auth if auth is not None else AuthSettings.from_env()

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    app.include_router(public_router, prefix="/api")
    app.include_router(router, prefix="/api")
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
