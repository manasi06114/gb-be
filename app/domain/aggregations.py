"""Pure aggregation functions for temporal, horizon, and distributional error analysis."""

from typing import Any

import numpy as np
import pandas as pd

from app.domain.metrics import compute_bias, compute_mae, compute_percentiles, compute_rmse


def aggregate_by_day(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate paired error data by delivery date.

    Args:
        df: DataFrame with 'startTime', 'actual_mw', 'forecast_mw', 'error_mw'.

    Returns:
        List of daily summary records with mae_mw, rmse_mw, bias_mw, mean_actual_mw, and n.
    """
    if df.empty:
        return []

    valid = df.dropna(subset=["actual_mw", "forecast_mw", "error_mw"]).copy()
    if valid.empty:
        return []

    valid["delivery_date"] = valid["startTime"].dt.strftime("%Y-%m-%d")
    grouped = valid.groupby("delivery_date", sort=True)

    rows: list[dict[str, Any]] = []
    for day_str, group in grouped:
        errors = group["error_mw"].to_numpy()
        actuals = group["actual_mw"].to_numpy()
        mae = compute_mae(errors) or 0.0
        rmse = compute_rmse(errors) or 0.0
        bias = compute_bias(errors) or 0.0
        mean_actual = round(float(np.mean(actuals)), 2)

        rows.append(
            {
                "delivery_date": day_str,
                "mae_mw": mae,
                "rmse_mw": rmse,
                "bias_mw": bias,
                "mean_actual_mw": mean_actual,
                "n": len(group),
            }
        )

    return rows


def aggregate_by_hour(df: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Aggregate paired forecast errors into heatmap cells (day x hour) and hourly profile.

    Args:
        df: DataFrame with 'startTime', 'error_mw'.

    Returns:
        Tuple of (cells, by_hour_of_day).
    """
    if df.empty:
        return [], []

    valid = df.dropna(subset=["error_mw"]).copy()
    if valid.empty:
        return [], []

    valid["delivery_date"] = valid["startTime"].dt.strftime("%Y-%m-%d")
    valid["hour"] = valid["startTime"].dt.hour

    # Cells: delivery_date x hour
    cells: list[dict[str, Any]] = []
    day_hour_group = valid.groupby(["delivery_date", "hour"], sort=True)
    for (day_str, hour), group in day_hour_group:
        errors = group["error_mw"].to_numpy()
        cells.append(
            {
                "delivery_date": day_str,
                "hour": int(hour),
                "mean_error_mw": compute_bias(errors) or 0.0,
                "mae_mw": compute_mae(errors) or 0.0,
            }
        )

    # By hour of day (0..23)
    by_hour_of_day: list[dict[str, Any]] = []
    hour_group = valid.groupby("hour", sort=True)
    for hour, group in hour_group:
        errors = group["error_mw"].to_numpy()
        by_hour_of_day.append(
            {
                "hour": int(hour),
                "mae_mw": compute_mae(errors) or 0.0,
                "rmse_mw": compute_rmse(errors) or 0.0,
                "bias_mw": compute_bias(errors) or 0.0,
            }
        )

    return cells, by_hour_of_day


def aggregate_by_horizon(
    forecasts_df: pd.DataFrame,
    actuals_df: pd.DataFrame,
    bucket_hours: int = 3,
) -> list[dict[str, Any]]:
    """Aggregate error metrics across all available forecasts grouped by lead horizon buckets.

    Uses all forecasts (BR-3), not merely the latest-at-cutoff.

    Args:
        forecasts_df: DataFrame with ['startTime', 'publishTime', 'generation'].
        actuals_df: DataFrame with ['startTime', 'generation'].
        bucket_hours: Horizon bin size in hours (default: 3).

    Returns:
        List of horizon bucket statistics.
    """
    if forecasts_df.empty or actuals_df.empty:
        return []

    # Merge forecasts and actuals on target startTime
    f_df = forecasts_df[["startTime", "publishTime", "generation"]].rename(
        columns={"generation": "forecast_mw"}
    )
    a_df = actuals_df[["startTime", "generation"]].rename(columns={"generation": "actual_mw"})

    merged = pd.merge(f_df, a_df, on="startTime", how="inner").dropna(
        subset=["forecast_mw", "actual_mw"]
    )
    if merged.empty:
        return []

    # Calculate horizon in hours
    diff_h = (merged["startTime"] - merged["publishTime"]).dt.total_seconds() / 3600.0
    merged["horizon_h"] = diff_h
    # Consider lead times >= 0
    valid = merged[merged["horizon_h"] >= 0].copy()
    if valid.empty:
        return []

    valid["error_mw"] = valid["forecast_mw"] - valid["actual_mw"]

    max_h = int(np.ceil(valid["horizon_h"].max()))
    max_h = max(max_h, bucket_hours)

    results: list[dict[str, Any]] = []
    for start_h in range(0, max_h, bucket_hours):
        end_h = start_h + bucket_hours
        bucket_data = valid[(valid["horizon_h"] >= start_h) & (valid["horizon_h"] < end_h)]
        if not bucket_data.empty:
            errors = bucket_data["error_mw"].to_numpy()
            results.append(
                {
                    "horizon_from_h": float(start_h),
                    "horizon_to_h": float(end_h),
                    "mae_mw": compute_mae(errors) or 0.0,
                    "rmse_mw": compute_rmse(errors) or 0.0,
                    "bias_mw": compute_bias(errors) or 0.0,
                    "n": len(bucket_data),
                }
            )

    return results


def compute_error_distribution(
    errors: pd.Series | np.ndarray,
    num_bins: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compute histogram bins and percentile summary for error distribution.

    Args:
        errors: Series or array of forecast - actual errors.
        num_bins: Number of equal-width bins (default: 20).

    Returns:
        Tuple of (bins, summary_dict).
    """
    arr = np.asarray(errors, dtype=float)
    valid = arr[~np.isnan(arr)]
    n = len(valid)

    if n == 0:
        return [], {
            "mean_mw": 0.0,
            "p05_mw": 0.0,
            "p50_mw": 0.0,
            "p95_mw": 0.0,
            "n": 0,
        }

    counts, bin_edges = np.histogram(valid, bins=num_bins)

    bins: list[dict[str, Any]] = []
    for i in range(len(counts)):
        bins.append(
            {
                "from_mw": round(float(bin_edges[i]), 2),
                "to_mw": round(float(bin_edges[i + 1]), 2),
                "count": int(counts[i]),
            }
        )

    percentiles = compute_percentiles(valid)
    summary = {
        "mean_mw": round(float(np.mean(valid)), 2),
        "p05_mw": percentiles["p05"] or 0.0,
        "p50_mw": percentiles["p50"] or 0.0,
        "p95_mw": percentiles["p95"] or 0.0,
        "n": n,
    }

    return bins, summary
