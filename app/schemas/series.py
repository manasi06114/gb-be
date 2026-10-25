"""Schemas for raw actuals and forecast timeseries."""

from pydantic import BaseModel, Field


class ActualRecord(BaseModel):
    """E3 /api/actuals record schema."""

    start_time: str = Field(..., description="Target half-hour start time in ISO UTC")
    generation_mw: float = Field(..., description="Actual wind generation in MW")
    settlement_date: str | None = Field(default=None, description="Settlement date (YYYY-MM-DD)")
    settlement_period: int | None = Field(default=None, description="Settlement period (1..48)")


class ForecastRecord(BaseModel):
    """E4 /api/forecasts record schema."""

    start_time: str = Field(..., description="Target half-hour start time in ISO UTC")
    publish_time: str = Field(..., description="Publish time of forecast in ISO UTC")
    generation_mw: float = Field(..., description="Forecasted wind generation in MW")


class LatestForecastRecord(BaseModel):
    """E5 /api/forecasts/latest record schema."""

    start_time: str = Field(..., description="Target half-hour start time in ISO UTC")
    forecast_publish_time: str = Field(
        ..., description="Publish time of selected forecast in ISO UTC"
    )
    forecast_mw: float = Field(..., description="Forecasted wind generation in MW")
    horizon_hours: float = Field(
        ..., description="Forecast horizon in hours (startTime - publishTime)"
    )
