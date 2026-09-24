import pytest
from fastapi.testclient import TestClient

from timesheet_calc.web.app import create_app
from timesheet_calc.web.auth import AuthMode, AuthSettings

CALC_BODY = {"entries": [{"start": "8", "end": "17"}]}


def header_client(**kwargs: object) -> TestClient:
    return TestClient(create_app(AuthSettings(mode=AuthMode.HEADER, **kwargs)))  # type: ignore[arg-type]


def test_settings_defaults_to_no_auth() -> None:
    assert AuthSettings.from_env({}) == AuthSettings()


def test_settings_from_env() -> None:
    settings = AuthSettings.from_env(
        {
            "TIMESHEET_AUTH_MODE": " Header ",
            "TIMESHEET_AUTH_USER_HEADER": "Tailscale-User-Login",
            "TIMESHEET_AUTH_ALLOWED_USERS": "Carlson, spouse@example.com ,,",
        }
    )
    assert settings.mode is AuthMode.HEADER
    assert settings.user_header == "Tailscale-User-Login"
    assert settings.allowed_users == frozenset({"carlson", "spouse@example.com"})


@pytest.mark.parametrize(
    ("environ", "message"),
    [
        ({"TIMESHEET_AUTH_MODE": "basic"}, "must be one of"),
        ({"TIMESHEET_AUTH_MODE": "header", "TIMESHEET_AUTH_USER_HEADER": "  "}, "cannot be blank"),
    ],
)
def test_invalid_settings_fail_fast(environ: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        AuthSettings.from_env(environ)


def test_create_app_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIMESHEET_AUTH_MODE", "header")
    assert TestClient(create_app()).post("/api/calc", json=CALC_BODY).status_code == 401


def test_misconfigured_environment_blocks_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIMESHEET_AUTH_MODE", "typo")
    with pytest.raises(ValueError, match="TIMESHEET_AUTH_MODE"):
        create_app()


def test_no_auth_mode_allows_anonymous() -> None:
    client = TestClient(create_app(AuthSettings()))
    assert client.post("/api/calc", json=CALC_BODY).status_code == 200
    assert client.get("/api/me").json() == {"user": None, "auth_mode": "none"}


@pytest.mark.parametrize(("path", "method"), [("/api/calc", "post"), ("/api/sum", "post"), ("/api/me", "get")])
@pytest.mark.parametrize("headers", [{}, {"Remote-User": ""}, {"Remote-User": "   "}])
def test_header_mode_fails_closed(path: str, method: str, headers: dict[str, str]) -> None:
    client = header_client()
    body = CALC_BODY if path == "/api/calc" else {"durations": ["1"]}
    response = client.request(method.upper(), path, json=body if method == "post" else None, headers=headers)
    assert response.status_code == 401


def test_header_mode_accepts_proxy_user() -> None:
    client = header_client()
    response = client.post("/api/calc", json=CALC_BODY, headers={"Remote-User": "carlson"})
    assert response.status_code == 200
    assert client.get("/api/me", headers={"Remote-User": "carlson"}).json() == {
        "user": "carlson",
        "auth_mode": "header",
    }


def test_allowlist_is_case_insensitive_and_enforced() -> None:
    client = header_client(allowed_users=frozenset({"carlson"}))
    assert client.post("/api/calc", json=CALC_BODY, headers={"Remote-User": "CARLSON"}).status_code == 200
    assert client.post("/api/calc", json=CALC_BODY, headers={"Remote-User": "intruder"}).status_code == 403


def test_custom_header_name_ignores_default_header() -> None:
    client = header_client(user_header="Tailscale-User-Login")
    assert client.post("/api/calc", json=CALC_BODY, headers={"Remote-User": "carlson"}).status_code == 401
    ok = client.post("/api/calc", json=CALC_BODY, headers={"Tailscale-User-Login": "carlson@github"})
    assert ok.status_code == 200


@pytest.mark.parametrize("path", ["/api/healthz", "/", "/app.js"])
def test_public_paths_need_no_user(path: str) -> None:
    assert header_client().get(path).status_code == 200
