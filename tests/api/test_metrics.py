"""API integration tests for E8-E12 metrics endpoints."""

from fastapi.testclient import TestClient


def test_kpi_metrics_golden(client: TestClient) -> None:
    """E8: KPI metrics match hand-calculated golden fixture values.

    Fixture errors: +100, -200, +300, 0
    MAE = 150.0, RMSE ≈ 187.08, Bias = 50.0
    Coverage = 4/48 = 8.33% (fixture only populates 4 of 48 half-hours)
    """
    resp = client.get("/api/metrics?date_from=2026-01-15&date_to=2026-01-15&cutoff=09:00")
    assert resp.status_code == 200
    data = resp.json()

    assert data["date_from"] == "2026-01-15"
    assert data["date_to"] == "2026-01-15"
    assert data["cutoff_local"] == "09:00"
    assert data["mae_mw"] == 150.0
    assert abs(data["rmse_mw"] - 187.08) < 0.1
    assert data["bias_mw"] == 50.0
    assert data["n"] == 4
    assert data["bias_direction"] == "over_forecast"
    # Fixture has 4 actual records, expected_count = 1 day * 48 = 48
    # Coverage = 4/48 * 100 = 8.33
    assert abs(data["coverage_pct"] - 8.33) < 0.1

    # Full schema check
    for field in [
        "mae_mw",
        "rmse_mw",
        "bias_mw",
        "nmae_pct",
        "mean_actual_mw",
        "mean_forecast_mw",
        "error_p05_mw",
        "error_p50_mw",
        "error_p95_mw",
        "max_over_forecast_mw",
        "max_under_forecast_mw",
        "coverage_pct",
        "n",
        "bias_direction",
    ]:
        assert field in data, f"Missing field: {field}"


def test_kpi_metrics_validation_errors(client: TestClient) -> None:
    """E8: Validation errors return 422 standard error body."""
    # date_from > date_to
    resp = client.get("/api/metrics?date_from=2026-01-31&date_to=2026-01-01&cutoff=09:00")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body

    # bad cutoff
    resp2 = client.get("/api/metrics?date_from=2026-01-15&date_to=2026-01-15&cutoff=invalid")
    assert resp2.status_code == 422


def test_daily_metrics_structure(client: TestClient) -> None:
    """E9: Daily metrics returns rows with required fields."""
    resp = client.get("/api/metrics/daily?date_from=2026-01-15&date_to=2026-01-15&cutoff=09:00")
    assert resp.status_code == 200
    data = resp.json()

    assert "rows" in data
    rows = data["rows"]
    assert len(rows) == 1

    row = rows[0]
    for field in ["delivery_date", "mae_mw", "rmse_mw", "bias_mw", "mean_actual_mw", "n"]:
        assert field in row, f"Missing field: {field}"

    assert row["delivery_date"] == "2026-01-15"
    assert row["mae_mw"] == 150.0
    assert row["n"] == 4


def test_hourly_metrics_structure(client: TestClient) -> None:
    """E10: Hourly heatmap and profile are returned."""
    resp = client.get("/api/metrics/by-hour?date_from=2026-01-15&date_to=2026-01-15&cutoff=09:00")
    assert resp.status_code == 200
    data = resp.json()

    assert "cells" in data
    assert "by_hour_of_day" in data
    assert isinstance(data["cells"], list)
    assert isinstance(data["by_hour_of_day"], list)

    for cell in data["cells"]:
        assert "delivery_date" in cell
        assert "hour" in cell
        assert "mean_error_mw" in cell
        assert "mae_mw" in cell


def test_horizon_metrics_structure(client: TestClient) -> None:
    """E11: Horizon bucket metrics are returned.

    Fixture: two publish times per target (08:00 and 08:30)
    - 08:00 publish for 00:00 startTime: horizon = 16 hours
    - 08:30 publish for 00:00 startTime: horizon = 15.5 hours
    All within the 15-18h range.
    """
    resp = client.get(
        "/api/metrics/by-horizon?date_from=2026-01-15&date_to=2026-01-15&bucket_hours=3"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["bucket_hours"] == 3
    assert "rows" in data
    assert isinstance(data["rows"], list)

    for row in data["rows"]:
        for field in ["horizon_from_h", "horizon_to_h", "mae_mw", "rmse_mw", "bias_mw", "n"]:
            assert field in row, f"Missing field: {field}"


def test_error_distribution_structure(client: TestClient) -> None:
    """E12: Error distribution returns bins and summary."""
    resp = client.get(
        "/api/errors/distribution?date_from=2026-01-15&date_to=2026-01-15&cutoff=09:00&bins=10"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "bins" in data
    assert "mean_mw" in data
    assert "p05_mw" in data
    assert "p50_mw" in data
    assert "p95_mw" in data
    assert "n" in data
    assert data["n"] == 4

    bins = data["bins"]
    assert len(bins) == 10
    total = sum(b["count"] for b in bins)
    assert total == 4  # all 4 error points distributed across bins

    for b in bins:
        assert "from_mw" in b
        assert "to_mw" in b
        assert "count" in b


def test_distribution_bins_param(client: TestClient) -> None:
    """E12: Custom bins parameter is respected."""
    resp = client.get(
        "/api/errors/distribution?date_from=2026-01-15&date_to=2026-01-15&cutoff=09:00&bins=5"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["bins"]) == 5
