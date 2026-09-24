# timesheet-calc

Timesheet calculator as a Python library, a command-line tool, and a web app. It turns start/end times into hours
worked and adds durations up. The core has no runtime dependencies and uses integer minutes throughout, so totals
never drift.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/desktop-dark.png">
  <img alt="Web app with calculated rows, error messages on invalid rows, and totals" src="docs/screenshots/desktop-light.png" width="820">
</picture>

## Features

- **Fast entry.** Type `8`, `130`, `7.15`, or `1500`; the parser handles all of them (see [Input rules](#input-rules)).
- **AM/PM handled explicitly.** Choose between guessing (`12:10` to `3` is 2:50) and strict 24-hour time.
  Truly ambiguous entries such as `6` to `6` are rejected instead of guessed.
- **Per-row errors.** A bad entry is flagged on its own row; valid rows still count toward the total.
- **Decimal hours** for payroll systems, rounded half-up (41:05 is 41.08, not 41.05).
- **Web app:**
  - Live results as you type; rows add and remove without losing data.
  - Entries survive a page reload.
  - Responsive, with dark mode and full keyboard use.
- **Proxy authentication:** trusts a verified username header from Authelia or Tailscale and fails closed without it.
- **Typed and tested:** strict mypy, Ruff, and 97 tests.

## Quick start

```bash
pip install -e ".[web]"      # library + CLI + web app
timesheet-web                # http://127.0.0.1:8000   (API docs at /api/docs)
```

Or with Docker:

```bash
docker build -t timesheet-calc .
docker run --rm -p 8000:8000 timesheet-calc
```

To deploy with sign-in on a Synology NAS, see [`../nas-stack`](../nas-stack/).

## Input rules

| You type | Means | Rule |
|---|---|---|
| `8`, `12` | 8:00, 12:00 | One or two digits are whole hours |
| `130`, `1500` | 1:30, 15:00 | Three or four digits are hours and minutes |
| `7:15`, `7.15` | 7:15 | A period works like a colon |
| `7.5` | **7:05** | What follows the delimiter is minutes, not a decimal fraction |
| `7:60`, `25` | error | Minutes must be 0 to 59; clock times must be 0:00 to 24:00 |

### Clock modes

When the end time is earlier than the start time:

| Mode | `12:10` to `3` | `22` to `6` | Use when |
|---|---|---|---|
| `infer` (default) | 2:50 (reads 3 as 3 PM) | 8:00 (overnight) | Entering 12-hour times quickly |
| `strict` | 14:50 (overnight) | 8:00 (overnight) | Entering 24-hour times |

Equal start and end times are rejected in both modes. They could mean 0, 12, or 24 hours; enter `6-18` or `0-24`.

## Command line

```bash
timesheet calc 7:45-11 12:10-3 4-4:30
```

```
 7:45 -> 11:00  3:15
12:10 ->  3:00  2:50
 4:00 ->  4:30  0:30
         Total  6:35
```

```bash
timesheet calc 2200-0600 --mode strict --decimal    # 8:00 (8.00 h)
timesheet sum 6:35 8:15 26:15 --decimal             # Total  41:05 (41.08 h)
python -m timesheet_calc --help
```

Exit codes are `0` for success and `2` for invalid input, with the reason printed to stderr.

## Library

```python
from timesheet_calc import ClockMode, Duration, TimeEntry, sum_durations

entries = [TimeEntry.parse(raw) for raw in ("7:45-11", "12:10-3", "4-4:30")]
total = sum_durations(entry.duration(ClockMode.INFER) for entry in entries)
print(total, total.decimal_hours())  # 6:35 6.58

Duration.parse("26:15") + Duration.parse("8:15")  # Duration(minutes=2070) -> "34:30"
```

Invalid input raises `TimeParseError`; ambiguous pairs raise `AmbiguousTimeError`. Both subclass `ValueError`.

## Web API

| Endpoint | Request body | Response |
|---|---|---|
| `POST /api/calc` | `{"entries": [{"start": "7:45", "end": "11"}], "mode": "infer"}` | Per-row `duration`, `decimal_hours`, or `error`; `total`; `error_count` |
| `POST /api/sum` | `{"durations": ["6:35", "8:15"]}` | Same shape as `/api/calc` |
| `GET /api/me` | | The signed-in user, or `null` when auth is off |
| `GET /api/healthz` | | `{"status": "ok"}`; always public, for health checks |

- Blank rows are skipped.
- Requests are limited to 100 rows of 16 characters per field; anything larger returns 422.
- Interactive docs are at `/api/docs`.

The browser never does time math. Every calculation goes through `core.py`, so the CLI, library, and web app always
agree.

## Authentication

The app never handles passwords. A reverse proxy signs the user in and passes the username in a header, and the app
requires that header.

| Variable | Default | Meaning |
|---|---|---|
| `TIMESHEET_AUTH_MODE` | `none` | `header`: every API call needs a proxy-verified user (401 without one) |
| `TIMESHEET_AUTH_USER_HEADER` | `Remote-User` | Header with the username. `Remote-User` for Authelia, `Tailscale-User-Login` for Tailscale Serve |
| `TIMESHEET_AUTH_ALLOWED_USERS` | empty | Optional comma-separated allowlist, case-insensitive (403 if not listed) |

> [!WARNING]
> In `header` mode the container must **not** publish a port. Anyone who can reach the app directly can send the
> header themselves. [`nas-stack`](../nas-stack/) places the app on an internal network behind Caddy for this reason.

An invalid `TIMESHEET_AUTH_MODE` stops the app at startup instead of running with the wrong policy.

## Development

```bash
pip install -e ".[dev]"
pytest                                            # 97 tests
ruff check . && ruff format --check .             # lint and format (120-character lines)
mypy src tests                                    # strict typing
timesheet-web --reload                            # auto-reload while editing
```

### Project layout

```
src/timesheet_calc/
├── core.py          # parsing, ClockTime, Duration, elapsed(): all time math
├── cli.py           # argparse CLI
└── web/
    ├── app.py       # FastAPI routes and security headers
    ├── auth.py      # trusted-header authentication
    ├── schemas.py   # request/response models and size limits
    └── static/      # index.html, app.js, styles.css (no build step)
tests/
├── test_core.py     # parsing rules, clock modes, arithmetic, edge cases
├── test_cli.py      # output format and exit codes
├── test_web.py      # API behavior, limits, headers
└── test_auth.py     # settings, fail-closed behavior, allowlist
```

### Design decisions

- **Integer minutes, never floats.** Decimal hours are computed once, at output time, with `Decimal`, which rules out
  errors like 0.1 + 0.2 = 0.30000000000000004 in payroll totals.
- **Refuse instead of guessing.** The original tool silently picks a meaning for `6` to `6`. Here it's an error with
  a suggested fix, because a wrong guess on a timesheet costs more than a prompt.
- **Server-side math.** The UI sends raw text and displays results, so there is no second copy of the rules in
  JavaScript to drift out of sync.
- **Security headers on every response:** a strict content-security policy (no inline scripts), `nosniff`,
  frame-deny, and no referrer.

### Fonts

The page loads Archivo from Google Fonts and falls back to Helvetica/Arial when that's blocked. For networks that
block Google, or to avoid the external request:
1. Save the `.woff2` file into `web/static/`.
2. Replace the stylesheet link with an `@font-face` rule.
3. Remove the two Google domains from `SECURITY_HEADERS` in `web/app.py`.
