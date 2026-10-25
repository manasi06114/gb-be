"""Schemas for actual vs forecast comparison endpoints (E6, E7)."""

from pydantic import BaseModel, Field


class ComparisonPoint(BaseModel):
    """Comparison point for a single settlement half-hour."""

    start_time: str = Field(..., description="Target settlement start time (ISO UTC)")
    actual_mw: float | None = Field(default=None, description="Actual wind generation in MW")
    forecast_mw: float | None = Field(
        default=None, description="Forecast wind generation at decision cutoff in MW"
    )
    forecast_publish_time: str | None = Field(
        default=None, description="Publish time of the selected forecast"
    )
    horizon_hours: float | None = Field(default=None, description="Forecast lead time in hours")
    error_mw: float | None = Field(
        default=None, description="Forecast error (forecast - actual) in MW"
    )
    abs_error_mw: float | None = Field(default=None, description="Absolute forecast error in MW")


class ComparisonSummary(BaseModel):
    """Statistical summary for the comparison day or range."""

    mae_mw: float = Field(..., description="Mean Absolute Error in MW")
    rmse_mw: float = Field(..., description="Root Mean Squared Error in MW")
    bias_mw: float = Field(..., description="Mean signed error (bias) in MW")
    coverage_pct: float = Field(..., description="Percentage of periods with forecast available")
    n: int = Field(..., description="Count of evaluated half-hour periods")


class UncertaintyBand(BaseModel):
    """Uncertainty interval parameters (+/- RMSE)."""

    basis: str = Field("historical_rmse", description="Calculation methodology")
    rmse_mw: float = Field(..., description="Calculated RMSE in MW")
    lower_offset_mw: float = Field(..., description="Negative offset from forecast (-RMSE)")
    upper_offset_mw: float = Field(..., description="Positive offset from forecast (+RMSE)")


class ComparisonResponse(BaseModel):
    """E6 /api/comparison response schema for a single delivery day."""

    delivery_date: str = Field(
        ..., examples=["2026-01-15"], description="Delivery day (YYYY-MM-DD)"
    )
    cutoff_local: str = Field(
        ..., examples=["09:00"], description="Cutoff time in Europe/London on D-1"
    )
    cutoff_utc: str = Field(..., description="Cutoff timestamp in ISO UTC")
    points: list[ComparisonPoint] = Field(..., description="48 half-hourly comparison points")
    summary: ComparisonSummary
    uncertainty: UncertaintyBand


class ComparisonRangeResponse(BaseModel):
    """E7 /api/comparison/range response schema across multiple delivery days."""

    date_from: str = Field(..., examples=["2026-01-01"], description="Range start date")
    date_to: str = Field(..., examples=["2026-01-31"], description="Range end date")
    cutoff_local: str = Field(
        ..., examples=["09:00"], description="Cutoff time in Europe/London on D-1"
    )
    points: list[ComparisonPoint] = Field(
        ..., description="Comparison points for all target periods"
    )
