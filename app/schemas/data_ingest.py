"""Schemas for dynamic data ingestion and field mapping from the frontend."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import DeliveryWindow


class ActualsFieldMapping(BaseModel):
    """Dynamic field name mappings for actual generation data."""

    start_time: str = Field(
        default="startTime",
        description="Target timestamp field name (e.g. 'startTime')",
        examples=["startTime"],
    )
    generation: str = Field(
        default="generation",
        description="Generation value field name (e.g. 'generation')",
        examples=["generation"],
    )
    fuel_type_field: str | None = Field(
        default="fuelType",
        description="Optional field to filter by fuel type",
        examples=["fuelType"],
    )
    fuel_type_value: str | None = Field(
        default="WIND",
        description="Fuel type value to filter on (e.g. 'WIND')",
        examples=["WIND"],
    )


class ForecastsFieldMapping(BaseModel):
    """Dynamic field name mappings for forecast generation data."""

    start_time: str = Field(
        default="startTime",
        description="Target timestamp field name (e.g. 'startTime')",
        examples=["startTime"],
    )
    publish_time: str = Field(
        default="publishTime",
        description="Publish/creation timestamp field name (e.g. 'publishTime')",
        examples=["publishTime"],
    )
    generation: str = Field(
        default="generation",
        description="Forecasted generation field name (e.g. 'generation')",
        examples=["generation"],
    )


class ActualsSourceRequest(BaseModel):
    """Source configuration and optional records for actuals."""

    url: str | None = Field(
        default=None,
        description="Direct API URL or stream endpoint (e.g. Elexon FUELHH stream)",
        examples=["https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream"],
    )
    date_from: date | None = Field(
        default=None,
        description="Delivery date range start (YYYY-MM-DD)",
        examples=["2026-01-01"],
    )
    date_to: date | None = Field(
        default=None,
        description="Delivery date range end (YYYY-MM-DD)",
        examples=["2026-01-31"],
    )
    fields: ActualsFieldMapping = Field(
        default_factory=ActualsFieldMapping,
        description="Dynamic field names in the incoming actuals payload/response",
    )
    records: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional direct JSON records supplied by frontend",
    )


class ForecastsSourceRequest(BaseModel):
    """Source configuration and optional records for forecasts."""

    url: str | None = Field(
        default=None,
        description="Direct API URL or stream endpoint (e.g. Elexon WINDFOR stream)",
        examples=["https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream"],
    )
    publish_from: datetime | None = Field(
        default=None,
        description="Publish datetime lower bound (ISO UTC)",
        examples=["2025-12-22T00:00:00Z"],
    )
    publish_to: datetime | None = Field(
        default=None,
        description="Publish datetime upper bound (ISO UTC)",
        examples=["2026-01-31T23:59:59Z"],
    )
    fields: ForecastsFieldMapping = Field(
        default_factory=ForecastsFieldMapping,
        description="Dynamic field names in the incoming forecast payload/response",
    )
    records: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional direct JSON records supplied by frontend",
    )


class DynamicIngestRequest(BaseModel):
    """Frontend request to fetch or ingest data dynamically with custom field mappings."""

    actuals: ActualsSourceRequest
    forecasts: ForecastsSourceRequest
    save_as_snapshot: bool = Field(
        default=True,
        description="Whether to persist to disk as the active Parquet snapshot",
    )


class DynamicIngestResponse(BaseModel):
    """Response returned after processing dynamic data ingestion."""

    status: str
    message: str
    actual_rows: int
    forecast_rows: int
    delivery_window: DeliveryWindow
    actual_fields_mapped: dict[str, str]
    forecast_fields_mapped: dict[str, str]
    fetched_at: str
