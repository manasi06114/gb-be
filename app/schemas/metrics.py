"""Schemas for accuracy metrics, aggregations, and error distribution (E8 - E12)."""

from pydantic import BaseModel, Field


class KPIMetricsResponse(BaseModel):
    """E8 /api/metrics response schema for overall KPIs."""

    date_from: str = Field(..., examples=["2026-01-01"])
    date_to: str = Field(..., examples=["2026-01-31"])
    cutoff_local: str = Field(..., examples=["09:00"])
    mae_mw: float = Field(..., description="Mean Absolute Error in MW")
    rmse_mw: float = Field(..., description="Root Mean Squared Error in MW")
    bias_mw: float = Field(..., description="Signed bias in MW")
    nmae_pct: float = Field(..., description="Normalised MAE percentage")
    mean_actual_mw: float = Field(..., description="Mean actual wind generation in MW")
    mean_forecast_mw: float = Field(..., description="Mean forecast generation in MW")
    error_p05_mw: float = Field(..., description="5th percentile of error in MW")
    error_p50_mw: float = Field(..., description="50th percentile (median) error in MW")
    error_p95_mw: float = Field(..., description="95th percentile of error in MW")
    max_over_forecast_mw: float = Field(..., description="Maximum over-forecast error in MW")
    max_under_forecast_mw: float = Field(..., description="Maximum under-forecast error in MW")
    coverage_pct: float = Field(..., description="Forecast coverage percentage")
    n: int = Field(..., description="Total half-hours evaluated")
    bias_direction: str = Field(..., description="'over_forecast' | 'under_forecast' | 'neutral'")


class DailyMetricRow(BaseModel):
    """Daily evaluation row."""

    delivery_date: str = Field(..., examples=["2026-01-15"])
    mae_mw: float = Field(...)
    rmse_mw: float = Field(...)
    bias_mw: float = Field(...)
    mean_actual_mw: float = Field(...)
    n: int = Field(...)


class DailyMetricsResponse(BaseModel):
    """E9 /api/metrics/daily response schema."""

    rows: list[DailyMetricRow]


class HourlyHeatmapCell(BaseModel):
    """Single heatmap cell for day x hour."""

    delivery_date: str = Field(..., examples=["2026-01-15"])
    hour: int = Field(..., ge=0, le=23)
    mean_error_mw: float = Field(...)
    mae_mw: float = Field(...)


class HourlyProfileRow(BaseModel):
    """Hourly profile row across all days."""

    hour: int = Field(..., ge=0, le=23)
    mae_mw: float = Field(...)
    rmse_mw: float = Field(...)
    bias_mw: float = Field(...)


class HourlyMetricsResponse(BaseModel):
    """E10 /api/metrics/by-hour response schema."""

    cells: list[HourlyHeatmapCell]
    by_hour_of_day: list[HourlyProfileRow]


class HorizonMetricRow(BaseModel):
    """Accuracy metrics for a forecast horizon lead bucket."""

    horizon_from_h: float = Field(..., description="Start of lead bucket in hours")
    horizon_to_h: float = Field(..., description="End of lead bucket in hours")
    mae_mw: float = Field(...)
    rmse_mw: float = Field(...)
    bias_mw: float = Field(...)
    n: int = Field(...)


class HorizonMetricsResponse(BaseModel):
    """E11 /api/metrics/by-horizon response schema."""

    bucket_hours: int = Field(..., examples=[3])
    rows: list[HorizonMetricRow]


class DistributionBin(BaseModel):
    """Histogram bin for error distribution."""

    from_mw: float = Field(..., description="Bin lower bound in MW")
    to_mw: float = Field(..., description="Bin upper bound in MW")
    count: int = Field(..., description="Number of error occurrences in this bin")


class ErrorDistributionResponse(BaseModel):
    """E12 /api/errors/distribution response schema."""

    bins: list[DistributionBin]
    mean_mw: float = Field(...)
    p05_mw: float = Field(...)
    p50_mw: float = Field(...)
    p95_mw: float = Field(...)
    n: int = Field(...)
