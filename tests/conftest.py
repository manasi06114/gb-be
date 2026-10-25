"""Test fixtures and TestClient setup for API integration tests."""

import threading
from collections.abc import Generator

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.repositories.data_repository import DataRepository


def make_test_repo() -> DataRepository:
    """Build a synthetic in-memory DataRepository with known test data.

    Golden fixture: 4 half-hour periods on 2026-01-15
    Errors (forecast - actual): +100, -200, +300, 0
    MAE = (100+200+300+0)/4 = 150.0
    RMSE = sqrt((10000+40000+90000+0)/4) = sqrt(35000) ≈ 187.08
    Bias = (100-200+300+0)/4 = 50.0
    """
    # Build a real DataRepository instance then bypass load()
    repo = DataRepository.__new__(DataRepository)
    repo._lock = threading.RLock()
    repo.data_dir = None  # type: ignore[assignment]
    repo._loaded = True

    target_times = [
        pd.Timestamp("2026-01-15T00:00:00Z"),
        pd.Timestamp("2026-01-15T00:30:00Z"),
        pd.Timestamp("2026-01-15T01:00:00Z"),
        pd.Timestamp("2026-01-15T01:30:00Z"),
    ]

    actuals_data = {
        "startTime": target_times,
        "generation": [5000.0, 5200.0, 4800.0, 5100.0],
        "fuelType": ["WIND"] * 4,
        "settlementDate": ["2026-01-15"] * 4,
        "settlementPeriod": [1, 2, 3, 4],
        "publishTime": [
            pd.Timestamp("2026-01-15T00:30:00Z"),
            pd.Timestamp("2026-01-15T01:00:00Z"),
            pd.Timestamp("2026-01-15T01:30:00Z"),
            pd.Timestamp("2026-01-15T02:00:00Z"),
        ],
    }

    # Two publish times per target: 08:00 (early) and 08:30 (latest)
    # Cutoff = 09:00 on D-1 (2026-01-14T09:00:00Z) -> both are eligible, 08:30 is selected
    # Selected forecast values -> errors vs actuals:
    #   t0: 5100 - 5000 = +100
    #   t1: 5000 - 5200 = -200
    #   t2: 5100 - 4800 = +300
    #   t3: 5100 - 5100 = 0
    forecast_data = {
        "startTime": target_times * 2,
        "publishTime": [
            pd.Timestamp("2026-01-14T08:00:00Z"),
            pd.Timestamp("2026-01-14T08:00:00Z"),
            pd.Timestamp("2026-01-14T08:00:00Z"),
            pd.Timestamp("2026-01-14T08:00:00Z"),
            pd.Timestamp("2026-01-14T08:30:00Z"),  # latest -> selected for each target
            pd.Timestamp("2026-01-14T08:30:00Z"),
            pd.Timestamp("2026-01-14T08:30:00Z"),
            pd.Timestamp("2026-01-14T08:30:00Z"),
        ],
        "generation": [
            4900.0,
            5000.0,
            4700.0,
            5000.0,  # early values (should NOT be selected)
            5100.0,
            5000.0,
            5100.0,
            5100.0,  # latest values -> selected
        ],
    }

    repo._actuals_df = pd.DataFrame(actuals_data)
    repo._forecasts_df = (
        pd.DataFrame(forecast_data).sort_values(["startTime", "publishTime"]).reset_index(drop=True)
    )
    repo._meta = {
        "fetched_at": "2026-02-01T00:00:00Z",
        "actual_rows": 4,
        "forecast_rows": 8,
        "source": "Test Fixture",
    }

    return repo


@pytest.fixture(scope="session")
def test_repo() -> DataRepository:
    """Provide a shared synthetic data repository for all tests."""
    return make_test_repo()


@pytest.fixture(scope="session")
def client(test_repo: DataRepository) -> Generator[TestClient, None, None]:
    """Provide a TestClient with the synthetic repository injected via DI override."""
    from app.main import app

    # Override the DI dependency BEFORE the TestClient boots the lifespan
    app.dependency_overrides[deps.get_repository] = lambda: test_repo

    with TestClient(app) as c:
        yield c

    # Restore after session
    app.dependency_overrides.clear()
