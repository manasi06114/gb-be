"""E8 - E12: Accuracy metrics, aggregations, and error distribution endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_metrics_service
from app.api.routers.validators import (
    resolve_delivery_window,
    validate_date_range,
    validate_delivery_window,
)
from app.core.config import Settings, get_settings
from app.domain.decision_time import parse_cutoff_time
from app.schemas.metrics import (
    DailyMetricsResponse,
    ErrorDistributionResponse,
    HorizonMetricsResponse,
    HourlyMetricsResponse,
    KPIMetricsResponse,
)
from app.services.metrics_service import MetricsService

router = APIRouter(tags=["Metrics"])


def _common_params(
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
    settings: Settings = Depends(get_settings),
) -> tuple[date, date, str]:
    """Shared parameter validation for metrics endpoints."""
    parse_cutoff_time(cutoff)
    validate_date_range(date_from, date_to)
    validate_delivery_window(date_from, date_to, settings.delivery_start, settings.delivery_end)
    return date_from, date_to, cutoff


@router.get(
    "/metrics",
    summary="Overall accuracy KPIs for a delivery date range (E8)",
    description=(
        "Computes MAE, RMSE, bias, normalised MAE, percentiles, coverage, and extremes "
        "for the latest-at-cutoff forecasts across the specified delivery date range."
    ),
    response_model=KPIMetricsResponse,
)
def get_kpi_metrics(
    date_from: Annotated[
        date, Query(description="Inclusive start delivery date", examples=["2026-01-01"])
    ],
    date_to: Annotated[
        date, Query(description="Inclusive end delivery date", examples=["2026-01-31"])
    ],
    cutoff: Annotated[
        str, Query(description="Decision cutoff HH:MM", examples=["09:00"])
    ] = "09:00",
    service: MetricsService = Depends(get_metrics_service),
    settings: Settings = Depends(get_settings),
) -> KPIMetricsResponse:
    """Return overall accuracy KPIs for the delivery date range."""
    parse_cutoff_time(cutoff)
    validate_date_range(date_from, date_to)
    win_start, win_end = resolve_delivery_window(
        service.repo, settings.delivery_start, settings.delivery_end
    )
    validate_delivery_window(date_from, date_to, win_start, win_end)
    return service.get_kpi_metrics(date_from, date_to, cutoff)


@router.get(
    "/metrics/daily",
    summary="Per-delivery-day accuracy metrics (E9)",
    description="Returns MAE, RMSE, and bias broken down by individual delivery day.",
    response_model=DailyMetricsResponse,
)
def get_daily_metrics(
    date_from: Annotated[
        date, Query(description="Inclusive start delivery date", examples=["2026-01-01"])
    ],
    date_to: Annotated[
        date, Query(description="Inclusive end delivery date", examples=["2026-01-31"])
    ],
    cutoff: Annotated[
        str, Query(description="Decision cutoff HH:MM", examples=["09:00"])
    ] = "09:00",
    service: MetricsService = Depends(get_metrics_service),
    settings: Settings = Depends(get_settings),
) -> DailyMetricsResponse:
    """Return per-day accuracy metrics."""
    parse_cutoff_time(cutoff)
    validate_date_range(date_from, date_to)
    win_start, win_end = resolve_delivery_window(
        service.repo, settings.delivery_start, settings.delivery_end
    )
    validate_delivery_window(date_from, date_to, win_start, win_end)
    return service.get_daily_metrics(date_from, date_to, cutoff)


@router.get(
    "/metrics/by-hour",
    summary="Error heatmap by delivery day × hour, plus hourly profile (E10)",
    description=(
        "Returns a heatmap of mean error and MAE for each delivery-day × hour combination, "
        "plus an hourly profile aggregated across all days in the range."
    ),
    response_model=HourlyMetricsResponse,
)
def get_hourly_metrics(
    date_from: Annotated[
        date, Query(description="Inclusive start delivery date", examples=["2026-01-01"])
    ],
    date_to: Annotated[
        date, Query(description="Inclusive end delivery date", examples=["2026-01-31"])
    ],
    cutoff: Annotated[
        str, Query(description="Decision cutoff HH:MM", examples=["09:00"])
    ] = "09:00",
    service: MetricsService = Depends(get_metrics_service),
    settings: Settings = Depends(get_settings),
) -> HourlyMetricsResponse:
    """Return error heatmap by day x hour and by hour of day profile."""
    parse_cutoff_time(cutoff)
    validate_date_range(date_from, date_to)
    win_start, win_end = resolve_delivery_window(
        service.repo, settings.delivery_start, settings.delivery_end
    )
    validate_delivery_window(date_from, date_to, win_start, win_end)
    return service.get_hourly_metrics(date_from, date_to, cutoff)


@router.get(
    "/metrics/by-horizon",
    summary="Accuracy by forecast lead-time horizon bucket (E11)",
    description=(
        "Computes MAE, RMSE, and bias for all available forecast publish times grouped "
        "into horizon buckets. Uses ALL publish times (not only the latest-at-cutoff) "
        "to show how accuracy varies with lead time."
    ),
    response_model=HorizonMetricsResponse,
)
def get_horizon_metrics(
    date_from: Annotated[
        date, Query(description="Inclusive start delivery date", examples=["2026-01-01"])
    ],
    date_to: Annotated[
        date, Query(description="Inclusive end delivery date", examples=["2026-01-31"])
    ],
    bucket_hours: Annotated[
        int,
        Query(description="Horizon bin size in hours", ge=1, le=24),
    ] = 3,
    service: MetricsService = Depends(get_metrics_service),
    settings: Settings = Depends(get_settings),
) -> HorizonMetricsResponse:
    """Return accuracy metrics grouped by forecast horizon lead-time bucket."""
    validate_date_range(date_from, date_to)
    win_start, win_end = resolve_delivery_window(
        service.repo, settings.delivery_start, settings.delivery_end
    )
    validate_delivery_window(date_from, date_to, win_start, win_end)
    return service.get_horizon_metrics(date_from, date_to, bucket_hours)


@router.get(
    "/errors/distribution",
    summary="Error distribution histogram and percentile summary (E12)",
    description=(
        "Returns the full error distribution as equal-width histogram bins, "
        "along with mean, P05, P50, and P95 quantiles."
    ),
    response_model=ErrorDistributionResponse,
)
def get_error_distribution(
    date_from: Annotated[
        date, Query(description="Inclusive start delivery date", examples=["2026-01-01"])
    ],
    date_to: Annotated[
        date, Query(description="Inclusive end delivery date", examples=["2026-01-31"])
    ],
    cutoff: Annotated[
        str, Query(description="Decision cutoff HH:MM", examples=["09:00"])
    ] = "09:00",
    bins: Annotated[
        int,
        Query(description="Number of histogram bins", ge=5, le=100),
    ] = 20,
    service: MetricsService = Depends(get_metrics_service),
    settings: Settings = Depends(get_settings),
) -> ErrorDistributionResponse:
    """Return error distribution histogram and summary statistics."""
    parse_cutoff_time(cutoff)
    validate_date_range(date_from, date_to)
    win_start, win_end = resolve_delivery_window(
        service.repo, settings.delivery_start, settings.delivery_end
    )
    validate_delivery_window(date_from, date_to, win_start, win_end)
    return service.get_error_distribution(date_from, date_to, cutoff, num_bins=bins)
