"""Unit tests for aggregation domain logic."""

import pandas as pd

from app.domain.aggregations import (
    aggregate_by_day,
    aggregate_by_horizon,
    aggregate_by_hour,
    compute_error_distribution,
)


def test_aggregate_by_day() -> None:
    """Verify daily error aggregations."""
    df = pd.DataFrame(
        {
            "startTime": [
                pd.Timestamp("2026-01-15T00:00:00Z"),
                pd.Timestamp("2026-01-15T00:30:00Z"),
                pd.Timestamp("2026-01-16T00:00:00Z"),
            ],
            "actual_mw": [1000.0, 1000.0, 2000.0],
            "forecast_mw": [1100.0, 950.0, 2100.0],
            "error_mw": [100.0, -50.0, 100.0],
        }
    )

    daily = aggregate_by_day(df)
    assert len(daily) == 2

    day1 = daily[0]
    assert day1["delivery_date"] == "2026-01-15"
    assert day1["mae_mw"] == 75.0
    assert day1["bias_mw"] == 25.0
    assert day1["n"] == 2

    day2 = daily[1]
    assert day2["delivery_date"] == "2026-01-16"
    assert day2["mae_mw"] == 100.0
    assert day2["n"] == 1


def test_aggregate_by_hour() -> None:
    """Verify hour x day heatmap cells and 24-hour profile."""
    df = pd.DataFrame(
        {
            "startTime": [
                pd.Timestamp("2026-01-15T08:00:00Z"),
                pd.Timestamp("2026-01-15T08:30:00Z"),
                pd.Timestamp("2026-01-15T09:00:00Z"),
            ],
            "actual_mw": [100.0, 200.0, 300.0],
            "forecast_mw": [120.0, 210.0, 310.0],
            "error_mw": [20.0, 10.0, 10.0],
        }
    )

    cells, by_hour = aggregate_by_hour(df)
    assert len(cells) == 2  # hour 8 and hour 9
    assert len(by_hour) == 2

    hour8 = [h for h in by_hour if h["hour"] == 8][0]
    assert hour8["mae_mw"] == 15.0
    assert hour8["bias_mw"] == 15.0


def test_aggregate_by_horizon() -> None:
    """Verify horizon buckets across all forecast rows (BR-3)."""
    t = pd.Timestamp("2026-01-15T12:00:00Z")
    forecasts = pd.DataFrame(
        {
            "startTime": [t, t],
            "publishTime": [
                pd.Timestamp("2026-01-15T10:00:00Z"),  # horizon 2 hours -> bucket [0, 3)
                pd.Timestamp("2026-01-15T07:00:00Z"),  # horizon 5 hours -> bucket [3, 6)
            ],
            "generation": [5100.0, 5200.0],
        }
    )
    actuals = pd.DataFrame({"startTime": [t], "generation": [5000.0]})

    buckets = aggregate_by_horizon(forecasts, actuals, bucket_hours=3)
    assert len(buckets) == 2

    b0_3 = buckets[0]
    assert b0_3["horizon_from_h"] == 0.0
    assert b0_3["horizon_to_h"] == 3.0
    assert b0_3["mae_mw"] == 100.0
    assert b0_3["n"] == 1

    b3_6 = buckets[1]
    assert b3_6["horizon_from_h"] == 3.0
    assert b3_6["horizon_to_h"] == 6.0
    assert b3_6["mae_mw"] == 200.0
    assert b3_6["n"] == 1


def test_compute_error_distribution() -> None:
    """Verify histogram bins and distribution summary."""
    errors = pd.Series([-50.0, -10.0, 0.0, 10.0, 50.0])
    bins, summary = compute_error_distribution(errors, num_bins=5)

    assert len(bins) == 5
    total_count = sum(b["count"] for b in bins)
    assert total_count == 5
    assert summary["n"] == 5
    assert summary["mean_mw"] == 0.0
