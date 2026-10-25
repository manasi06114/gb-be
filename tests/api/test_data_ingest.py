"""API integration tests for dynamic data ingestion and field mapping."""

from fastapi.testclient import TestClient


def test_dynamic_ingest_with_custom_field_names(client: TestClient) -> None:
    """Test dynamic ingestion where frontend specifies custom field names."""
    from app.api import deps

    repo = client.app.dependency_overrides[deps.get_repository]()
    orig_act = repo._actuals_df.copy()
    orig_fc = repo._forecasts_df.copy()
    orig_meta = dict(repo._meta)
    orig_win = getattr(repo, "_custom_window", None)

    try:
        payload = {
            "actuals": {
                "fields": {
                    "start_time": "target_time",
                    "generation": "power_mw",
                    "fuel_type_field": "source",
                    "fuel_type_value": "WIND_ONSHORE",
                },
                "records": [
                    {
                        "target_time": "2026-02-01T00:00:00Z",
                        "power_mw": 500.0,
                        "source": "WIND_ONSHORE",
                    },
                    {
                        "target_time": "2026-02-01T00:30:00Z",
                        "power_mw": 550.0,
                        "source": "WIND_ONSHORE",
                    },
                    # Excluded by fuel type filter
                    {
                        "target_time": "2026-02-01T01:00:00Z",
                        "power_mw": 999.0,
                        "source": "SOLAR",
                    },
                ],
            },
            "forecasts": {
                "fields": {
                    "start_time": "target_period",
                    "publish_time": "forecast_created_at",
                    "generation": "forecasted_mw",
                },
                "records": [
                    {
                        "target_period": "2026-02-01T00:00:00Z",
                        "forecast_created_at": "2026-01-31T08:00:00Z",
                        "forecasted_mw": 520.0,
                    },
                    {
                        "target_period": "2026-02-01T00:30:00Z",
                        "forecast_created_at": "2026-01-31T08:00:00Z",
                        "forecasted_mw": 540.0,
                    },
                ],
            },
            "save_as_snapshot": False,
        }

        resp = client.post("/api/data/fetch", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "success"
        assert data["actual_rows"] == 2
        assert data["forecast_rows"] == 2
        assert data["actual_fields_mapped"]["startTime"] == "target_time"
        assert data["actual_fields_mapped"]["generation"] == "power_mw"
        assert data["forecast_fields_mapped"]["publishTime"] == "forecast_created_at"
        assert data["delivery_window"]["start"] == "2026-02-01"
        assert data["delivery_window"]["end"] == "2026-02-01"

        # Verify that the newly loaded data is immediately queryable via standard endpoints!
        act_resp = client.get("/api/actuals?date_from=2026-02-01&date_to=2026-02-01")
        assert act_resp.status_code == 200
        act_data = act_resp.json()
        assert len(act_data) == 2
        assert act_data[0]["generation_mw"] == 500.0

        # Verify comparison endpoint against the new dynamic data
        comp_resp = client.get("/api/comparison?delivery_date=2026-02-01&cutoff=09:00")
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert comp_data["summary"]["n"] == 2
    finally:
        repo._actuals_df = orig_act
        repo._forecasts_df = orig_fc
        repo._meta = orig_meta
        repo._custom_window = orig_win


def test_dynamic_ingest_missing_specified_field_returns_422(client: TestClient) -> None:
    """When frontend declares a field name that is missing in records, return 422."""
    payload = {
        "actuals": {
            "fields": {
                "start_time": "non_existent_column",
                "generation": "generation",
            },
            "records": [{"startTime": "2026-01-01T00:00:00Z", "generation": 100}],
        },
        "forecasts": {
            "fields": {
                "start_time": "startTime",
                "publish_time": "publishTime",
                "generation": "generation",
            },
            "records": [
                {
                    "startTime": "2026-01-01T00:00:00Z",
                    "publishTime": "2025-12-31T09:00:00Z",
                    "generation": 100,
                }
            ],
        },
    }
    resp = client.post("/api/data/fetch", json=payload)
    assert resp.status_code == 422
    assert "non_existent_column" in resp.json()["error"]["message"]


def test_dynamic_ingest_missing_source_returns_422(client: TestClient) -> None:
    """Providing neither records nor url returns 422."""
    payload = {
        "actuals": {"records": None, "url": None},
        "forecasts": {"records": None, "url": None},
    }
    resp = client.post("/api/data/fetch", json=payload)
    assert resp.status_code == 422
