"""Unit tests for pure domain metric calculations."""

import numpy as np
import pandas as pd

from app.domain.metrics import (
    compute_bias,
    compute_bias_direction,
    compute_kpi_summary,
    compute_mae,
    compute_nmae,
    compute_percentiles,
    compute_rmse,
)


def test_hand_calculated_metrics() -> None:
    """Verify MAE, RMSE, and bias against verified hand-calculated values."""
    # errors: 10, -20, 30, 0
    # abs_errors: 10, 20, 30, 0 -> sum = 60 -> mean = 15.0
    # squared: 100, 400, 900, 0 -> sum = 1400 -> mean = 350 -> sqrt(350) = 18.70828693... -> 18.71
    # signed sum: 10 - 20 + 30 + 0 = 20 -> mean = 5.0
    errors = np.array([10.0, -20.0, 30.0, 0.0])

    mae = compute_mae(errors)
    rmse = compute_rmse(errors)
    bias = compute_bias(errors)

    assert mae == 15.0
    assert rmse == 18.71
    assert bias == 5.0


def test_empty_and_nan_metrics() -> None:
    """Verify robust handling of empty arrays and NaN values."""
    assert compute_mae([]) is None
    assert compute_rmse([]) is None
    assert compute_bias([]) is None
    assert compute_nmae(None, 100.0) is None
    assert compute_nmae(10.0, None) is None
    assert compute_nmae(10.0, 0.0) is None

    # Array with NaNs should filter them out
    nan_arr = np.array([10.0, np.nan, -10.0])
    assert compute_mae(nan_arr) == 10.0
    assert compute_bias(nan_arr) == 0.0
    assert compute_rmse(nan_arr) == 10.0


def test_nmae_calculation() -> None:
    """Verify normalised MAE percentage calculation."""
    # MAE = 200 MW, Mean Actual = 2000 MW -> nMAE = 10%
    nmae = compute_nmae(200.0, 2000.0)
    assert nmae == 10.0


def test_percentiles_calculation() -> None:
    """Verify P05, P50, and P95 percentile outputs."""
    errors = np.linspace(-100, 100, 201)  # -100 to +100
    p = compute_percentiles(errors)
    assert p["p50"] == 0.0
    assert p["p05"] is not None and p["p05"] < 0
    assert p["p95"] is not None and p["p95"] > 0

    empty_p = compute_percentiles([])
    assert empty_p["p05"] is None
    assert empty_p["p50"] is None
    assert empty_p["p95"] is None


def test_bias_direction() -> None:
    """Verify directional label based on bias value."""
    assert compute_bias_direction(15.0) == "over_forecast"
    assert compute_bias_direction(-15.0) == "under_forecast"
    assert compute_bias_direction(0.1) == "neutral"
    assert compute_bias_direction(None) == "neutral"


def test_kpi_summary_empty() -> None:
    """Verify KPI summary for empty input dataframe."""
    df_empty = pd.DataFrame(columns=["actual_mw", "forecast_mw", "error_mw"])
    summary = compute_kpi_summary(df_empty, expected_count=48)
    assert summary["n"] == 0
    assert summary["mae_mw"] == 0.0
    assert summary["coverage_pct"] == 0.0
    assert summary["bias_direction"] == "neutral"


def test_kpi_summary_populated() -> None:
    """Verify KPI summary calculation over paired dataframe."""
    df = pd.DataFrame(
        {
            "actual_mw": [100.0, 200.0, 300.0, 400.0],
            "forecast_mw": [110.0, 180.0, 330.0, 400.0],
            "error_mw": [10.0, -20.0, 30.0, 0.0],
        }
    )
    summary = compute_kpi_summary(df, expected_count=4)
    assert summary["n"] == 4
    assert summary["mae_mw"] == 15.0
    assert summary["rmse_mw"] == 18.71
    assert summary["bias_mw"] == 5.0
    assert summary["coverage_pct"] == 100.0
    assert summary["mean_actual_mw"] == 250.0
    assert summary["mean_forecast_mw"] == 255.0
    assert summary["bias_direction"] == "over_forecast"
