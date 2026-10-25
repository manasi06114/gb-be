"""E6 & E7: Actual vs forecast comparison endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_comparison_service
from app.api.routers.validators import (
    resolve_delivery_window,
    validate_date_range,
    validate_delivery_window,
    validate_single_date,
)
from app.core.config import Settings, get_settings
from app.domain.decision_time import parse_cutoff_time
from app.schemas.comparison import ComparisonRangeResponse, ComparisonResponse
from app.services.comparison_service import ComparisonService

router = APIRouter(tags=["Comparison"])


@router.get(
    "/comparison",
    summary="Actual vs latest-at-cutoff forecast for one delivery day (E6)",
    description=(
        "Returns 48 half-hourly comparison points pairing actual wind generation "
        "with the latest forecast available at the decision cutoff on D-1. "
        "Includes summary KPIs (MAE, RMSE, bias) and an uncertainty band (± RMSE)."
    ),
    response_model=ComparisonResponse,
)
def get_comparison(
    delivery_date: Annotated[
        date,
        Query(description="Delivery date D (YYYY-MM-DD)", examples=["2026-01-15"]),
    ],
    cutoff: Annotated[
        str,
        Query(
            description="Decision cutoff time (HH:MM) in Europe/London on D-1", examples=["09:00"]
        ),
    ] = "09:00",
    service: ComparisonService = Depends(get_comparison_service),
    settings: Settings = Depends(get_settings),
) -> ComparisonResponse:
    """Return actual vs forecast comparison for a single delivery day."""
    parse_cutoff_time(cutoff)
    win_start, win_end = resolve_delivery_window(
        service.repo, settings.delivery_start, settings.delivery_end
    )
    validate_single_date(delivery_date, win_start, win_end)
    return service.get_comparison_for_day(delivery_date, cutoff)


@router.get(
    "/comparison/range",
    summary="Actual vs forecast comparison over a date range (E7)",
    description=(
        "Returns comparison points for all half-hour periods in the specified delivery date range. "
        "Useful for month-view charts and scatter plots of actual vs forecast."
    ),
    response_model=ComparisonRangeResponse,
)
def get_comparison_range(
    date_from: Annotated[
        date,
        Query(description="Inclusive start delivery date (YYYY-MM-DD)", examples=["2026-01-01"]),
    ],
    date_to: Annotated[
        date,
        Query(description="Inclusive end delivery date (YYYY-MM-DD)", examples=["2026-01-31"]),
    ],
    cutoff: Annotated[
        str,
        Query(
            description="Decision cutoff time (HH:MM) in Europe/London on D-1", examples=["09:00"]
        ),
    ] = "09:00",
    service: ComparisonService = Depends(get_comparison_service),
    settings: Settings = Depends(get_settings),
) -> ComparisonRangeResponse:
    """Return actual vs forecast comparison across a range of delivery days."""
    parse_cutoff_time(cutoff)
    validate_date_range(date_from, date_to)
    win_start, win_end = resolve_delivery_window(
        service.repo, settings.delivery_start, settings.delivery_end
    )
    validate_delivery_window(date_from, date_to, win_start, win_end)
    return service.get_comparison_for_range(date_from, date_to, cutoff)
