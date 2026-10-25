"""API integration tests for E1 health and E2 meta endpoints."""

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    """E1: Health endpoint returns 200 when data is loaded."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["data_loaded"] is True
    assert data["snapshot_fetched_at"] is not None


def test_meta_structure(client: TestClient) -> None:
    """E2: Meta endpoint returns required fields and structure."""
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    data = resp.json()

    assert "delivery_window" in data
    assert data["delivery_window"]["start"] == "2026-01-01"
    assert data["delivery_window"]["end"] == "2026-01-31"

    assert "default_cutoff" in data
    assert data["default_cutoff"] == "09:00"

    assert "cutoff_timezone" in data
    assert data["cutoff_timezone"] == "Europe/London"

    assert "available_cutoffs" in data
    assert "09:00" in data["available_cutoffs"]

    assert "snapshot" in data
    snap = data["snapshot"]
    assert "fetched_at" in snap
    assert isinstance(snap["actual_rows"], int)
    assert isinstance(snap["forecast_rows"], int)

    assert "definitions" in data
    assert "error" in data["definitions"]
    assert "mae" in data["definitions"]
    assert "rmse" in data["definitions"]
    assert "bias" in data["definitions"]
