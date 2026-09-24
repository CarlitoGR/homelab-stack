# timesheet-calc

Timesheet calculator: elapsed time from start/end pairs and H:MM duration sums. Pure standard library, no runtime
dependencies. Input rules are compatible with the miraclesalad.com timesheet tool, with its ambiguities made explicit.

## Install

```bash
pip install -e ".[dev]"      # core + web + test tooling
```

## CLI

```bash
timesheet calc 7:45-11 12:10-3 4-4:30          # per-entry elapsed + total (6:35)
timesheet calc 2200-0600 --mode strict --decimal
timesheet sum 6:35 8:15 26:15 --decimal         # 41:05 (41.08 h)
python -m timesheet_calc --help
```

Exit codes: `0` success, `2` bad input (message on stderr).

## Web app

A recreation of the miraclesalad.com timesheet page: live per-row results, running totals, adjustable rows (without
losing data), a mode switch for AM/PM handling, decimal-hours display, and a button that sends the Calculate total into
Sum. The browser holds no time logic; every calculation goes through `timesheet_calc.core` via the JSON API.

```bash
pip install -e ".[web]"
timesheet-web --reload                 # http://127.0.0.1:8000  (API docs: /api/docs)
```

Docker:

```bash
docker build -t timesheet-calc .
docker run --rm -p 8000:8000 timesheet-calc
```

| Endpoint           | Body                                                   | Notes                          |
|--------------------|--------------------------------------------------------|--------------------------------|
| `POST /api/calc`   | `{"entries": [{"start": "7:45", "end": "11"}], "mode": "infer"}` | per-row `duration`/`error` |
| `POST /api/sum`    | `{"durations": ["6:35", "8:15"]}`                      | per-row `duration`/`error`     |
| `GET /api/healthz` |                                                        | liveness probe                 |

Requests are capped at 100 rows of 16 characters per field (HTTP 422 beyond that). Blank rows are skipped; invalid
rows report an error without affecting the total of the valid ones.

## Authentication

The app does not handle passwords. A reverse proxy signs the user in and passes the username in a header; the app
verifies that header is present. See `../nas-stack` for the full Caddy + Authelia deployment.

| Variable | Default | Meaning |
|---|---|---|
| `TIMESHEET_AUTH_MODE` | `none` | `header` requires a proxy-authenticated user on every API call (401 if missing) |
| `TIMESHEET_AUTH_USER_HEADER` | `Remote-User` | Header holding the username; `Tailscale-User-Login` behind Tailscale Serve |
| `TIMESHEET_AUTH_ALLOWED_USERS` | empty | Optional comma-separated allowlist, case-insensitive (403 if not listed) |

**In header mode, the container must not publish a port.** Anyone who can reach the app directly can set the header
themselves. An invalid `TIMESHEET_AUTH_MODE` stops the app at startup rather than running with the wrong policy.
`/api/healthz` stays open for health checks, and `GET /api/me` reports who the proxy signed in.

## Input rules

| Input  | Means  | Rule                                          |
|--------|--------|-----------------------------------------------|
| `8`    | 8:00   | 1-2 bare digits = hours                       |
| `130`  | 1:30   | 3-4 bare digits = H:MM / HH:MM                |
| `7.15` | 7:15   | `.` equals `:`                                |
| `7.5`  | 7:05   | after the delimiter is MINUTES, not a decimal |

## Clock modes

- `infer` (default): emulates the original. An end before the start is first tried as PM (`12:10-3` = 2:50), then as
  overnight (`22-6` = 8:00).
- `strict`: pure 24-hour clock. An end before the start is always overnight (`12:10-3` = 14:50).

Equal start and end (`6-6`) is rejected in both modes. It could mean 0, 12, or 24 hours, so enter `6-18` or `0-24`.

## Library

```python
from timesheet_calc import ClockMode, Duration, TimeEntry, sum_durations

entries = [TimeEntry.parse(raw) for raw in ("7:45-11", "12:10-3", "4-4:30")]
total = sum_durations(entry.duration(ClockMode.INFER) for entry in entries)
print(total, total.decimal_hours())  # 6:35 6.58
```

## Development

```bash
pytest && ruff check . && ruff format --check . && mypy src tests
```
