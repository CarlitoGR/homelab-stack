"""Trusted-header authentication.

A reverse proxy (Caddy + Authelia, or Tailscale Serve) authenticates the user and passes the username in a header.
This module only reads that header. It is safe ONLY when the app cannot be reached except through that proxy:
publish no port for this container, and put it on a network shared with the proxy alone.

Environment:
    TIMESHEET_AUTH_MODE           ``none`` (default, local dev) or ``header`` (required behind a proxy).
    TIMESHEET_AUTH_USER_HEADER    Header carrying the username. Default ``Remote-User`` (Authelia);
                                  use ``Tailscale-User-Login`` behind Tailscale Serve.
    TIMESHEET_AUTH_ALLOWED_USERS  Optional comma-separated allowlist (case-insensitive). Empty allows any
                                  user the proxy authenticated.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status

if TYPE_CHECKING:
    from collections.abc import Mapping

ENV_MODE = "TIMESHEET_AUTH_MODE"
ENV_USER_HEADER = "TIMESHEET_AUTH_USER_HEADER"
ENV_ALLOWED_USERS = "TIMESHEET_AUTH_ALLOWED_USERS"
DEFAULT_USER_HEADER = "Remote-User"


class AuthMode(StrEnum):
    """Whether requests must carry a proxy-authenticated user."""

    NONE = "none"
    HEADER = "header"


@dataclass(frozen=True, slots=True)
class AuthSettings:
    """Validated authentication settings. Invalid configuration fails at startup, never per request."""

    mode: AuthMode = AuthMode.NONE
    user_header: str = DEFAULT_USER_HEADER
    allowed_users: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> AuthSettings:
        """Build settings from environment variables.

        Raises:
            ValueError: If the mode is unknown or the header name is blank.
        """
        env = os.environ if environ is None else environ
        raw_mode = env.get(ENV_MODE, AuthMode.NONE.value).strip().lower()
        try:
            mode = AuthMode(raw_mode)
        except ValueError as exc:
            choices = ", ".join(member.value for member in AuthMode)
            msg = f"{ENV_MODE} must be one of: {choices} (got {raw_mode!r})"
            raise ValueError(msg) from exc

        user_header = env.get(ENV_USER_HEADER, DEFAULT_USER_HEADER).strip()
        if not user_header:
            msg = f"{ENV_USER_HEADER} cannot be blank"
            raise ValueError(msg)

        allowed = frozenset(name.strip().lower() for name in env.get(ENV_ALLOWED_USERS, "").split(",") if name.strip())
        return cls(mode=mode, user_header=user_header, allowed_users=allowed)


def current_user(request: Request) -> str | None:
    """FastAPI dependency: return the authenticated username, or ``None`` when auth is disabled.

    Fails closed: in header mode a missing or blank header is 401 and a user outside the allowlist is 403.
    """
    settings: AuthSettings = request.app.state.auth
    if settings.mode is AuthMode.NONE:
        return None

    user = request.headers.get(settings.user_header, "").strip()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")
    if settings.allowed_users and user.lower() not in settings.allowed_users:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not allowed here.")
    return user
