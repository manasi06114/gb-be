"""Common Pydantic models and error response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Uniform error body structure."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional context or validation errors"
    )


class ErrorResponse(BaseModel):
    """Standard API error wrapper."""

    error: ErrorBody


class DeliveryWindow(BaseModel):
    """Delivery date boundary model."""

    start: str = Field(..., examples=["2026-01-01"], description="Start date (YYYY-MM-DD)")
    end: str = Field(..., examples=["2026-01-31"], description="End date (YYYY-MM-DD)")
