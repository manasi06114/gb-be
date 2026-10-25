"""Unit tests for DataRepository."""

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from app.core.errors import DataUnavailableError
from app.repositories.data_repository import DataRepository


def test_data_repository_load_and_queries(tmp_path: Path):
    # Test uninitialized repository
    repo = DataRepository(data_dir=tmp_path)
    assert not repo.is_loaded()
    with pytest.raises(DataUnavailableError):
        repo.get_actuals()
    with pytest.raises(DataUnavailableError):
        repo.get_forecasts()
    with pytest.raises(DataUnavailableError):
        repo.get_all_actuals()
    with pytest.raises(DataUnavailableError):
        repo.get_all_forecasts()

    # Load from missing files
    with pytest.raises(DataUnavailableError):
        repo.load()

    # Create dummy parquet files
    actuals_df = pd.DataFrame(
        {
            "startTime": pd.date_range("2026-01-01T00:00:00Z", periods=10, freq="30min", tz="UTC"),
            "publishTime": pd.date_range(
                "2026-01-01T00:00:00Z", periods=10, freq="30min", tz="UTC"
            ),
            "generation": [100.0 + i for i in range(10)],
        }
    )
    actuals_df.to_parquet(tmp_path / "actuals_wind.parquet")

    forecasts_df = pd.DataFrame(
        {
            "startTime": pd.date_range("2026-01-01T00:00:00Z", periods=10, freq="1h", tz="UTC"),
            "publishTime": pd.date_range("2025-12-31T09:00:00Z", periods=10, freq="1h", tz="UTC"),
            "generation": [110.0 + i for i in range(10)],
        }
    )
    forecasts_df.to_parquet(tmp_path / "forecasts_wind.parquet")

    # Load without meta json (fallback to default meta dict)
    repo.load()
    assert repo.is_loaded()
    meta = repo.get_snapshot_meta()
    assert meta["actual_rows"] == 10
    assert meta["forecast_rows"] == 10

    # Test get_all
    assert len(repo.get_all_actuals()) == 10
    assert len(repo.get_all_forecasts()) == 10

    # Test filtering actuals
    filtered_act = repo.get_actuals(date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    assert len(filtered_act) == 10

    # Test filtering forecasts with publish date and limit/offset
    pub_from = datetime(2025, 12, 31, 9, 0, tzinfo=timezone.utc)
    pub_to = datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc)
    fc_filtered = repo.get_forecasts(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 1),
        publish_from=pub_from,
        publish_to=pub_to,
        limit=2,
        offset=1,
    )
    assert len(fc_filtered) <= 2
