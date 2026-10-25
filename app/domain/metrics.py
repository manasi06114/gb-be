"""Pure domain metrics calculations for forecast accuracy and error statistics."""

from typing import Any

import numpy as np
import pandas as pd


def compute_mae(errors: pd.Series | np.ndarray) -> float | None:
    """Compute Mean Absolute Error (MW).

    Args:
        errors: Series or array of forecast - actual errors.

    Returns:
        MAE as float rounded to 2 decimal places, or None if empty.
    """
    arr = np.asarray(errors, dtype=float)
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return None
    return round(float(np.mean(np.abs(valid))), 2)


def compute_rmse(errors: pd.Series | np.ndarray) -> float | None:
    """Compute Root Mean Squared Error (MW).

    Args:
        errors: Series or array of forecast - actual errors.

    Returns:
        RMSE as float rounded to 2 decimal places, or None if empty.
    """
    arr = np.asarray(errors, dtype=float)
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return None
    return round(float(np.sqrt(np.mean(np.square(valid)))), 2)


def compute_bias(errors: pd.Series | np.ndarray) -> float | None:
    """Compute Mean Bias (signed error in MW). Positive indicates over-forecasting.

    Args:
        errors: Series or array of forecast - actual errors.

    Returns:
        Bias as float rounded to 2 decimal places, or None if empty.
    """
    arr = np.asarray(errors, dtype=float)
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return None
    return round(float(np.mean(valid)), 2)


def compute_nmae(mae: float | None, mean_actual: float | None) -> float | None:
    """Compute Normalised MAE as percentage: (MAE / mean(actual)) * 100.

    Args:
        mae: MAE in MW.
        mean_actual: Mean actual generation in MW.

    Returns:
        nMAE percentage rounded to 2 decimal places, or None if undefined.
    """
    if mae is None or mean_actual is None or mean_actual <= 0:
        return None
    return round(float((mae / mean_actual) * 100.0), 2)


def compute_percentiles(errors: pd.Series | np.ndarray) -> dict[str, float | None]:
    """Compute P05, P50, and P95 percentiles of error distribution.

    Args:
        errors: Series or array of errors.

    Returns:
        Dictionary with keys 'p05', 'p50', 'p95'.
    """
    arr = np.asarray(errors, dtype=float)
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return {"p05": None, "p50": None, "p95": None}
    return {
        "p05": round(float(np.percentile(valid, 5)), 2),
        "p50": round(float(np.percentile(valid, 50)), 2),
        "p95": round(float(np.percentile(valid, 95)), 2),
    }


def compute_bias_direction(bias: float | None, threshold: float = 0.5) -> str:
    """Determine descriptive direction of bias."""
    if bias is None:
        return "neutral"
    if bias > threshold:
        return "over_forecast"
    if bias < -threshold:
        return "under_forecast"
    return "neutral"


def compute_kpi_summary(
    df: pd.DataFrame,
    expected_count: int,
) -> dict[str, Any]:
    """Compute comprehensive KPI summary metrics over a paired DataFrame.

    Requires DataFrame with columns 'actual_mw', 'forecast_mw', and 'error_mw'.

    Args:
        df: Paired DataFrame containing forecast and actual generation.
        expected_count: Total expected half-hourly periods in the window.

    Returns:
        Dictionary matching the E8 /api/metrics response model.
    """
    valid = df.dropna(subset=["actual_mw", "forecast_mw", "error_mw"])
    n = len(valid)

    if n == 0:
        coverage_pct = 0.0 if expected_count > 0 else 100.0
        return {
            "mae_mw": 0.0,
            "rmse_mw": 0.0,
            "bias_mw": 0.0,
            "nmae_pct": 0.0,
            "mean_actual_mw": 0.0,
            "mean_forecast_mw": 0.0,
            "error_p05_mw": 0.0,
            "error_p50_mw": 0.0,
            "error_p95_mw": 0.0,
            "max_over_forecast_mw": 0.0,
            "max_under_forecast_mw": 0.0,
            "coverage_pct": coverage_pct,
            "n": 0,
            "bias_direction": "neutral",
        }

    errors = valid["error_mw"].to_numpy()
    actuals = valid["actual_mw"].to_numpy()
    forecasts = valid["forecast_mw"].to_numpy()

    mae = compute_mae(errors) or 0.0
    rmse = compute_rmse(errors) or 0.0
    bias = compute_bias(errors) or 0.0
    mean_actual = round(float(np.mean(actuals)), 2)
    mean_forecast = round(float(np.mean(forecasts)), 2)
    nmae = compute_nmae(mae, mean_actual) or 0.0

    percentiles = compute_percentiles(errors)
    p05 = percentiles["p05"] or 0.0
    p50 = percentiles["p50"] or 0.0
    p95 = percentiles["p95"] or 0.0

    max_over = round(float(np.max(errors)), 2)
    max_under = round(float(np.min(errors)), 2)
    coverage = round(float((n / max(expected_count, 1)) * 100.0), 2)
    bias_dir = compute_bias_direction(bias)

    return {
        "mae_mw": mae,
        "rmse_mw": rmse,
        "bias_mw": bias,
        "nmae_pct": nmae,
        "mean_actual_mw": mean_actual,
        "mean_forecast_mw": mean_forecast,
        "error_p05_mw": p05,
        "error_p50_mw": p50,
        "error_p95_mw": p95,
        "max_over_forecast_mw": max_over,
        "max_under_forecast_mw": max_under,
        "coverage_pct": coverage,
        "n": n,
        "bias_direction": bias_dir,
    }
