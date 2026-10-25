"""Domain logic for selecting the latest available forecast at decision cutoff."""

from datetime import datetime, timezone

import pandas as pd


def select_latest_forecasts(forecasts_df: pd.DataFrame, cutoff_utc: datetime) -> pd.DataFrame:
    """Select the latest forecast for each target period available at or before cutoff.

    Guarantees:
    - Never includes forecasts with publishTime > cutoff_utc (BR-1).
    - For target periods with multiple forecasts, picks the row with greatest
      publishTime <= cutoff_utc (BR-2).
    - Ties broken deterministically by index order.

    Args:
        forecasts_df: DataFrame containing at least ['startTime', 'publishTime', 'generation'].
        cutoff_utc: Datetime in UTC representing the cutoff moment on D-1.

    Returns:
        DataFrame containing one row per available startTime with columns:
        ['startTime', 'forecast_publish_time', 'forecast_mw', 'horizon_hours'].
    """
    expected_cols = ["startTime", "forecast_publish_time", "forecast_mw", "horizon_hours"]
    if forecasts_df.empty:
        return pd.DataFrame(columns=expected_cols)

    df = forecasts_df.copy()
    if df["publishTime"].dt.tz is None:
        df["publishTime"] = df["publishTime"].dt.tz_localize(timezone.utc)
    if cutoff_utc.tzinfo is None:
        cutoff_utc = cutoff_utc.replace(tzinfo=timezone.utc)

    # Filter strictly to forecasts published at or before cutoff
    eligible = df[df["publishTime"] <= cutoff_utc].copy()
    if eligible.empty:
        return pd.DataFrame(columns=expected_cols)

    # Sort deterministically: earliest startTime first, then ascending publishTime
    eligible = eligible.sort_values(by=["startTime", "publishTime"], ascending=[True, True])

    # Select the last published forecast for each startTime
    latest = eligible.groupby("startTime", as_index=False).last()

    # Calculate forecast lead horizon in hours
    time_diff = latest["startTime"] - latest["publishTime"]
    horizon_hours = (time_diff.dt.total_seconds() / 3600.0).round(2)

    result = pd.DataFrame(
        {
            "startTime": latest["startTime"],
            "forecast_publish_time": latest["publishTime"],
            "forecast_mw": latest["generation"].astype(float),
            "horizon_hours": horizon_hours,
        }
    )

    return result
