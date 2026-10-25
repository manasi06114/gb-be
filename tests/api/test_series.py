"""API integration tests for E3-E5 actuals and forecast series endpoints."""

from fastapi.testclient import TestClient


def test_actuals_returns_records(client: TestClient) -> None:
    """E3: Actuals endpoint returns generation records for valid date range."""
    resp = client.get("/api/actuals?date_from=2026-01-15&date_to=2026-01-15")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 4  # fixture has 4 rows on 2026-01-15
    # Check field presence
    for rec in data:
        assert "start_time" in rec
        assert "generation_mw" in rec
        assert isinstance(rec["generation_mw"], (int, float))


def test_actuals_bad_date_range(client: TestClient) -> None:
    """E3: date_from > date_to returns 422 validation error."""
    resp = client.get("/api/actuals?date_from=2026-01-31&date_to=2026-01-01")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_actuals_out_of_window(client: TestClient) -> None:
    """E3: Dates outside delivery window return 422."""
    resp = client.get("/api/actuals?date_from=2025-12-01&date_to=2025-12-15")
    assert resp.status_code == 422


def test_forecasts_returns_records(client: TestClient) -> None:
    """E4: Forecasts endpoint returns records for valid date range."""
    resp = client.get("/api/forecasts?date_from=2026-01-15&date_to=2026-01-15")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 8  # fixture has 8 forecast rows

    for rec in data:
        assert "start_time" in rec
        assert "publish_time" in rec
        assert "generation_mw" in rec


def test_forecasts_latest_at_cutoff(client: TestClient) -> None:
    """E5: Latest-at-cutoff selects the correct forecast per period.

    Fixture: cutoff = 09:00 on 2026-01-14 UTC
    Two publish times per target: 08:00 and 08:30 (both <= 09:00)
    Latest should be 08:30 publish rows:
    - t0: generation 5100 -> error = 5100 - 5000 = +100
    - t1: generation 5000 -> error = 5000 - 5200 = -200
    - t2: generation 5100 -> error = 5100 - 4800 = +300
    - t3: generation 5100 -> error = 5100 - 5100 = 0
    """
    resp = client.get("/api/forecasts/latest?delivery_date=2026-01-15&cutoff=09:00")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 4

    for rec in data:
        assert "start_time" in rec
        assert "forecast_publish_time" in rec
        assert "forecast_mw" in rec
        assert "horizon_hours" in rec

    # Verify the latest forecasts have publish_time 08:30 (not 08:00)
    publish_times = {r["forecast_publish_time"] for r in data}
    assert all("T08:30" in pt for pt in publish_times)

    # Verify generation values from the 08:30 batch
    gen_vals = sorted(r["forecast_mw"] for r in data)
    assert gen_vals == [5000.0, 5100.0, 5100.0, 5100.0]


def test_forecasts_latest_invalid_cutoff(client: TestClient) -> None:
    """E5: Invalid cutoff format returns 422."""
    resp = client.get("/api/forecasts/latest?delivery_date=2026-01-15&cutoff=25:00")
    assert resp.status_code == 422

    resp2 = client.get("/api/forecasts/latest?delivery_date=2026-01-15&cutoff=9:0")
    assert resp2.status_code == 422
