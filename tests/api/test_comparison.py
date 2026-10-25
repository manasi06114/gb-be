"""API integration tests for E6-E7 comparison endpoints.

Golden fixture expected values for delivery_date=2026-01-15, cutoff=09:00:
Errors (forecast - actual): +100, -200, +300, 0
MAE = (100 + 200 + 300 + 0) / 4 = 150.0
RMSE = sqrt((10000 + 40000 + 90000 + 0) / 4) = sqrt(35000) ≈ 187.08
Bias = (100 - 200 + 300 + 0) / 4 = 50.0
"""

from fastapi.testclient import TestClient


def test_comparison_single_day_golden(client: TestClient) -> None:
    """E6: Comparison endpoint returns correct golden-fixture metrics.

    Verifies BR-1 (no future forecasts) and BR-2 (latest selected).
    """
    resp = client.get("/api/comparison?delivery_date=2026-01-15&cutoff=09:00")
    assert resp.status_code == 200
    data = resp.json()

    assert data["delivery_date"] == "2026-01-15"
    assert data["cutoff_local"] == "09:00"
    assert "2026-01-14T09:00:00Z" in data["cutoff_utc"]

    points = data["points"]
    assert isinstance(points, list)
    assert len(points) == 4  # fixture: 4 target periods

    # Verify error values using golden fixture
    error_vals = sorted(p["error_mw"] for p in points if p["error_mw"] is not None)
    assert error_vals == [-200.0, 0.0, 100.0, 300.0]

    summary = data["summary"]
    assert summary["mae_mw"] == 150.0
    assert abs(summary["rmse_mw"] - 187.08) < 0.1
    assert summary["bias_mw"] == 50.0
    assert summary["n"] == 4
    assert summary["coverage_pct"] == 100.0

    uncertainty = data["uncertainty"]
    assert uncertainty["basis"] == "historical_rmse"
    assert uncertainty["rmse_mw"] == summary["rmse_mw"]
    assert uncertainty["lower_offset_mw"] < 0
    assert uncertainty["upper_offset_mw"] > 0


def test_comparison_single_day_structure(client: TestClient) -> None:
    """E6: Response schema shape is correct."""
    resp = client.get("/api/comparison?delivery_date=2026-01-15&cutoff=09:00")
    data = resp.json()

    # Check all required fields are present
    required_point_fields = {
        "start_time",
        "actual_mw",
        "forecast_mw",
        "forecast_publish_time",
        "horizon_hours",
        "error_mw",
        "abs_error_mw",
    }
    for point in data["points"]:
        for field in required_point_fields:
            assert field in point, f"Missing field: {field}"


def test_comparison_no_cutoff_uses_default(client: TestClient) -> None:
    """E6: Omitting cutoff parameter uses the default 09:00 value."""
    resp = client.get("/api/comparison?delivery_date=2026-01-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cutoff_local"] == "09:00"


def test_comparison_range_returns_points(client: TestClient) -> None:
    """E7: Range comparison returns comparison points."""
    resp = client.get("/api/comparison/range?date_from=2026-01-15&date_to=2026-01-15&cutoff=09:00")
    assert resp.status_code == 200
    data = resp.json()

    assert data["date_from"] == "2026-01-15"
    assert data["date_to"] == "2026-01-15"
    assert data["cutoff_local"] == "09:00"
    assert isinstance(data["points"], list)
    assert len(data["points"]) == 4


def test_comparison_invalid_date_range(client: TestClient) -> None:
    """E6/E7: Invalid date ranges return 422."""
    resp = client.get("/api/comparison?delivery_date=2025-12-01&cutoff=09:00")
    assert resp.status_code == 422

    resp2 = client.get("/api/comparison/range?date_from=2026-01-31&date_to=2026-01-01")
    assert resp2.status_code == 422


def test_comparison_all_br1_no_future_forecasts(client: TestClient) -> None:
    """BR-1: None of the forecast_publish_times must be after the cutoff."""
    resp = client.get("/api/comparison?delivery_date=2026-01-15&cutoff=09:00")
    data = resp.json()
    cutoff_ts = "2026-01-14T09:00:00Z"

    for point in data["points"]:
        if point["forecast_publish_time"] is not None:
            assert point["forecast_publish_time"] <= cutoff_ts, (
                f"Published at {point['forecast_publish_time']} is after cutoff {cutoff_ts}"
            )
