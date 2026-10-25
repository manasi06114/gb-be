"""Schemas for metadata and methodology definitions."""

from pydantic import BaseModel, Field

from app.schemas.common import DeliveryWindow


class SnapshotMeta(BaseModel):
    """Metadata regarding pre-loaded snapshot data."""

    fetched_at: str = Field(..., description="ISO UTC timestamp when snapshot was fetched")
    actual_rows: int = Field(..., description="Number of actual wind records loaded")
    forecast_rows: int = Field(..., description="Number of forecast records loaded")
    source: str = Field(..., description="Data source attribution")


class MetaResponse(BaseModel):
    """E2 /api/meta response schema."""

    delivery_window: DeliveryWindow
    default_cutoff: str = Field(..., examples=["09:00"], description="Default decision cutoff time")
    cutoff_timezone: str = Field(..., examples=["Europe/London"], description="Timezone for cutoff")
    available_cutoffs: list[str] = Field(..., description="Predefined available cutoff options")
    snapshot: SnapshotMeta
    definitions: dict[str, str] = Field(..., description="Metric and calculation definitions")
