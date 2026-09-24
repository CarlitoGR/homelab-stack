import pytest
from fastapi.testclient import TestClient

from timesheet_calc.web.app import SECURITY_HEADERS, create_app
from timesheet_calc.web.schemas import MAX_FIELD, MAX_ROWS


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_calc_page_example(client: TestClient) -> None:
    body = {"entries": [{"start": "7:45", "end": "11"}, {"start": "12:10", "end": "3"}, {"start": "4", "end": "4:30"}]}
    data = client.post("/api/calc", json=body).json()
    assert [result["duration"] for result in data["results"]] == ["3:15", "2:50", "0:30"]
    assert data["total"] == "6:35"
    assert data["total_decimal_hours"] == "6.58"
    assert data["error_count"] == 0


def test_calc_strict_mode(client: TestClient) -> None:
    body = {"entries": [{"start": "12:10", "end": "3"}], "mode": "strict"}
    assert client.post("/api/calc", json=body).json()["total"] == "14:50"


def test_calc_blank_and_bad_rows_do_not_block_valid_ones(client: TestClient) -> None:
    body = {
        "entries": [
            {"start": "8", "end": "17"},
            {"start": "", "end": ""},
            {"start": "9", "end": ""},
            {"start": "6", "end": "6"},
            {"start": "7:60", "end": "8"},
        ]
    }
    data = client.post("/api/calc", json=body).json()
    results = data["results"]
    assert results[0]["duration"] == "9:00"
    assert results[1] == {"duration": None, "decimal_hours": None, "error": None}
    assert results[2]["error"] == "Enter both a start and an end time."
    assert "both 6:00" in results[3]["error"]
    assert "minutes" in results[4]["error"]
    assert data["total"] == "9:00"
    assert data["error_count"] == 3


def test_sum(client: TestClient) -> None:
    data = client.post("/api/sum", json={"durations": ["6:35", "8:15", "", "26:15", "abc"]}).json()
    assert data["total"] == "41:05"
    assert data["total_decimal_hours"] == "41.08"
    assert data["error_count"] == 1
    assert data["results"][2]["duration"] is None


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/calc", {"entries": [{"start": "1", "end": "2"}] * (MAX_ROWS + 1)}),
        ("/api/calc", {"entries": [{"start": "1" * (MAX_FIELD + 1), "end": "2"}]}),
        ("/api/calc", {"entries": [], "mode": "bogus"}),
        ("/api/sum", {"durations": ["1"] * (MAX_ROWS + 1)}),
        ("/api/sum", {}),
    ],
)
def test_oversized_or_malformed_requests_rejected(client: TestClient, path: str, body: dict[str, object]) -> None:
    assert client.post(path, json=body).status_code == 422


def test_healthz(client: TestClient) -> None:
    assert client.get("/api/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/", "/app.js", "/styles.css"])
def test_static_assets_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200


def test_security_headers(client: TestClient) -> None:
    response = client.get("/")
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_openapi_under_api_prefix(client: TestClient) -> None:
    assert client.get("/api/openapi.json").status_code == 200
