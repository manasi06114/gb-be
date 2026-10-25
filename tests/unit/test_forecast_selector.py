"""Unit tests for latest-forecast-at-cutoff selection logic."""

from datetime import datetime, timezone

import pandas as pd

from app.domain.forecast_selector import select_latest_forecasts


def test_forecast_selector_adversarial_future_cutoff() -> None:
    """BR-1: Ensure forecasts published after the cutoff are NEVER selected."""
    target_time = pd.Timestamp("2026-01-15T12:00:00Z")
    cutoff = pd.Timestamp("2026-01-14T09:00:00Z").to_pydatetime()

    # Create 3 forecasts:
    # 1. 2026-01-14 06:00 (before cutoff) -> generation 5000
    # 2. 2026-01-14 09:00 (exact cutoff)  -> generation 5200
    # 3. 2026-01-14 09:01 (after cutoff)  -> generation 9999 (adversarial)
    # 4. 2026-01-15 08:00 (delivery day)  -> generation 10000 (adversarial)
    data = pd.DataFrame(
        {
            "startTime": [target_time] * 4,
            "publishTime": [
                pd.Timestamp("2026-01-14T06:00:00Z"),
                pd.Timestamp("2026-01-14T09:00:00Z"),
                pd.Timestamp("2026-01-14T09:01:00Z"),
                pd.Timestamp("2026-01-15T08:00:00Z"),
            ],
            "generation": [5000.0, 5200.0, 9999.0, 10000.0],
        }
    )

    result = select_latest_forecasts(data, cutoff)
    assert len(result) == 1
    selected = result.iloc[0]

    # Must be the exact cutoff row (5200.0), never the future ones (9999 or 10000)
    assert selected["forecast_mw"] == 5200.0
    assert selected["forecast_publish_time"] == pd.Timestamp("2026-01-14T09:00:00Z")
    assert selected["forecast_publish_time"] <= pd.Timestamp(cutoff)
    assert selected["horizon_hours"] == 27.0


def test_forecast_selector_multiple_target_periods() -> None:
    """BR-2: Ensure max publishTime <= cutoff is picked for each distinct target time."""
    t1 = pd.Timestamp("2026-01-15T00:00:00Z")
    t2 = pd.Timestamp("2026-01-15T00:30:00Z")
    cutoff = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)

    data = pd.DataFrame(
        {
            "startTime": [t1, t1, t2, t2],
            "publishTime": [
                pd.Timestamp("2026-01-14T07:00:00Z"),
                pd.Timestamp("2026-01-14T08:30:00Z"),  # Latest for t1
                pd.Timestamp("2026-01-14T08:00:00Z"),
                pd.Timestamp("2026-01-14T08:45:00Z"),  # Latest for t2
            ],
            "generation": [4000.0, 4200.0, 4500.0, 4700.0],
        }
    )

    result = select_latest_forecasts(data, cutoff)
    assert len(result) == 2

    row_t1 = result[result["startTime"] == t1].iloc[0]
    assert row_t1["forecast_mw"] == 4200.0
    assert row_t1["forecast_publish_time"] == pd.Timestamp("2026-01-14T08:30:00Z")

    row_t2 = result[result["startTime"] == t2].iloc[0]
    assert row_t2["forecast_mw"] == 4700.0
    assert row_t2["forecast_publish_time"] == pd.Timestamp("2026-01-14T08:45:00Z")


def test_forecast_selector_empty_and_no_eligible() -> None:
    """Verify empty input or no forecasts prior to cutoff."""
    cutoff = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
    empty_df = pd.DataFrame(columns=["startTime", "publishTime", "generation"])
    assert select_latest_forecasts(empty_df, cutoff).empty

    # All forecasts after cutoff
    late_df = pd.DataFrame(
        {
            "startTime": [pd.Timestamp("2026-01-15T00:00:00Z")],
            "publishTime": [pd.Timestamp("2026-01-14T10:00:00Z")],
            "generation": [5000.0],
        }
    )
    result = select_latest_forecasts(late_df, cutoff)
    assert result.empty
