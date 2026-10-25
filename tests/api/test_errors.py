"""API integration tests for error handling and validation responses."""

from fastapi.testclient import TestClient


def test_invalid_date_format_returns_422(client: TestClient) -> None:
    """All endpoints should return 422 for malformed date parameters."""
    resp = client.get("/api/actuals?date_from=not-a-date&date_to=2026-01-15")
    assert resp.status_code == 422
    body = resp.json()
    # FastAPI's own validation gives error object
    assert "error" in body or "detail" in body


def test_standard_error_body_on_validation(client: TestClient) -> None:
    """Validation errors use the standard { error: { code, message, details } } body."""
    resp = client.get("/api/comparison?delivery_date=2025-06-01&cutoff=09:00")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    error = body["error"]
    assert "code" in error
    assert "message" in error
    assert "details" in error


def test_invalid_cutoff_format(client: TestClient) -> None:
    """All cutoff-sensitive endpoints should reject invalid HH:MM formats."""
    for endpoint in [
        "/api/forecasts/latest?delivery_date=2026-01-15&cutoff=9:00",
        "/api/comparison?delivery_date=2026-01-15&cutoff=abc",
        "/api/metrics?date_from=2026-01-15&date_to=2026-01-15&cutoff=99:00",
    ]:
        resp = client.get(endpoint)
        assert resp.status_code == 422, f"Expected 422 for {endpoint}, got {resp.status_code}"


def test_date_from_after_date_to(client: TestClient) -> None:
    """date_from > date_to returns 422 with standard error body."""
    resp = client.get("/api/comparison/range?date_from=2026-01-31&date_to=2026-01-01&cutoff=09:00")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_out_of_delivery_window(client: TestClient) -> None:
    """Dates outside the configured delivery window return 422."""
    resp = client.get("/api/metrics?date_from=2025-01-01&date_to=2025-01-31&cutoff=09:00")
    assert resp.status_code == 422


def test_custom_exception_classes():
    from app.core.errors import (
        DataUnavailableError,
        NotFoundAppError,
        UnauthorizedAppError,
    )

    e1 = NotFoundAppError("Item not found", details={"id": 123})
    assert e1.code == "NOT_FOUND"
    assert e1.status_code == 404
    assert e1.details == {"id": 123}

    e2 = DataUnavailableError("Data missing", details={"source": "bmrs"})
    assert e2.code == "DATA_UNAVAILABLE"
    assert e2.status_code == 503

    e3 = UnauthorizedAppError()
    assert e3.code == "UNAUTHORIZED"
    assert e3.status_code == 401
