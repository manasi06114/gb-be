"""Tests for the admin endpoints."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_admin_refresh_disabled_by_default() -> None:
    """When ADMIN_TOKEN is not configured, /api/admin/refresh should return 401."""
    resp = client.post("/api/admin/refresh")
    assert resp.status_code == 401
    assert "ADMIN_TOKEN not configured" in resp.text


def test_admin_refresh_invalid_token() -> None:
    """When ADMIN_TOKEN is configured but token mismatch, should return 401."""
    settings = get_settings()
    original_token = settings.admin_token
    try:
        settings.admin_token = "secret123"
        resp = client.post("/api/admin/refresh", headers={"X-Admin-Token": "wrong"})
        assert resp.status_code == 401
        assert "Invalid X-Admin-Token" in resp.text
    finally:
        settings.admin_token = original_token


def test_resolve_delivery_window_fallback() -> None:
    """Test fallback when repo lacks get_delivery_bounds."""
    from datetime import date
    from app.api.routers.validators import resolve_delivery_window

    d_start = date(2026, 1, 1)
    d_end = date(2026, 1, 31)
    res_start, res_end = resolve_delivery_window(None, d_start, d_end)
    assert res_start == d_start
    assert res_end == d_end


def test_metrics_by_hour_custom_cutoff() -> None:
    """Test /api/metrics/by-hour with 12:00 cutoff."""
    with TestClient(app) as client:
        resp = client.get(
            "/api/metrics/by-hour",
            params={"date_from": "2026-01-01", "date_to": "2026-01-05", "cutoff": "12:00"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["by_hour_of_day"]) == 24
