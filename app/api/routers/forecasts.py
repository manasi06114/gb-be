"""E4 & E5: Raw forecast series and latest-at-cutoff forecast endpoints."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_repository
from app.api.routers.validators import (
    resolve_delivery_window,
    validate_date_range,
    validate_delivery_window,
    validate_single_date,
)
from app.core.config import Settings, get_settings
from app.domain.decision_time import cutoff_for, parse_cutoff_time
from app.domain.forecast_selector import select_latest_forecasts
from app.repositories.data_repository import DataRepository
from app.schemas.series import ForecastRecord, LatestForecastRecord

router = APIRouter(tags=["Forecasts"])


@router.get(
    "/forecasts",
    summary="Raw WINDFOR forecast series (all publish times)",
    description=(
        "Returns raw forecast records from the Elexon WINDFOR dataset filtered "
        "by target delivery date range and optionally by publish datetime range. "
        "Supports pagination via limit/offset."
    ),
    response_model=list[ForecastRecord],
)
def get_forecasts(
    date_from: Annotated[
        date,
        Query(description="Inclusive start delivery date (YYYY-MM-DD)", examples=["2026-01-01"]),
    ],
    date_to: Annotated[
        date,
        Query(description="Inclusive end delivery date (YYYY-MM-DD)", examples=["2026-01-31"]),
    ],
    publish_from: Annotated[
        datetime | None,
        Query(
            description="Optional publish datetime lower bound (ISO UTC)",
            examples=["2026-01-01T00:00:00Z"],
        ),
    ] = None,
    publish_to: Annotated[
        datetime | None,
        Query(
            description="Optional publish datetime upper bound (ISO UTC)",
            examples=["2026-01-31T23:59:59Z"],
        ),
    ] = None,
    limit: Annotated[
        int | None,
        Query(description="Maximum number of records to return (pagination)", ge=1, le=10000),
    ] = None,
    offset: Annotated[
        int,
        Query(description="Number of records to skip (pagination)", ge=0),
    ] = 0,
    repo: DataRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> list[ForecastRecord]:
    """Return raw forecast records for the specified delivery date range."""
    validate_date_range(date_from, date_to)
    win_start, win_end = resolve_delivery_window(
        repo, settings.delivery_start, settings.delivery_end
    )
    validate_delivery_window(date_from, date_to, win_start, win_end)

    df = repo.get_forecasts(
        date_from=date_from,
        date_to=date_to,
        publish_from=publish_from,
        publish_to=publish_to,
        limit=limit,
        offset=offset,
    )

    records: list[ForecastRecord] = []
    for _, row in df.iterrows():
        st = str(row["startTime"]).replace("+00:00", "Z").replace(" ", "T")
        pt = str(row["publishTime"]).replace("+00:00", "Z").replace(" ", "T")
        records.append(
            ForecastRecord(
                start_time=st,
                publish_time=pt,
                generation_mw=float(row["generation"]),
            )
        )

    return records


@router.get(
    "/forecasts/latest",
    summary="Latest-at-cutoff forecast per target period (E5)",
    description=(
        "Returns, for each target half-hour period of the delivery day, the latest "
        "forecast published at or before the specified decision cutoff on D-1. "
        "This is the key 'what did the buyer see?' endpoint."
    ),
    response_model=list[LatestForecastRecord],
)
def get_latest_forecasts(
    delivery_date: Annotated[
        date,
        Query(description="Target delivery date D (YYYY-MM-DD)", examples=["2026-01-15"]),
    ],
    cutoff: Annotated[
        str,
        Query(
            description="Decision cutoff time in Europe/London on D-1 (HH:MM)", examples=["09:00"]
        ),
    ] = "09:00",
    repo: DataRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> list[LatestForecastRecord]:
    """Return the latest available forecast for each half-hour of delivery day at the cutoff."""
    parse_cutoff_time(cutoff)  # validates format, raises ValidationAppError on bad input
    win_start, win_end = resolve_delivery_window(
        repo, settings.delivery_start, settings.delivery_end
    )
    validate_single_date(delivery_date, win_start, win_end)

    cutoff_dt = cutoff_for(delivery_date, cutoff, settings.cutoff_timezone)
    forecasts_df = repo.get_forecasts(date_from=delivery_date, date_to=delivery_date)
    selected = select_latest_forecasts(forecasts_df, cutoff_dt)

    records: list[LatestForecastRecord] = []
    for _, row in selected.iterrows():
        st = str(row["startTime"]).replace("+00:00", "Z").replace(" ", "T")
        pt = str(row["forecast_publish_time"]).replace("+00:00", "Z").replace(" ", "T")
        records.append(
            LatestForecastRecord(
                start_time=st,
                forecast_publish_time=pt,
                forecast_mw=float(row["forecast_mw"]),
                horizon_hours=float(row["horizon_hours"]),
            )
        )

    return records
