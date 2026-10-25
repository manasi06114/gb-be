"""E3: Raw actual wind generation series endpoint."""

from datetime import date
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_repository
from app.api.routers.validators import (
    resolve_delivery_window,
    validate_date_range,
    validate_delivery_window,
)
from app.core.config import Settings, get_settings
from app.repositories.data_repository import DataRepository
from app.schemas.series import ActualRecord

router = APIRouter(tags=["Data Series"])


@router.get(
    "/actuals",
    summary="Raw actual wind generation series",
    description=(
        "Returns raw actual wind generation records from the Elexon FUELHH dataset "
        "filtered by delivery date range. Useful for data transparency and debugging."
    ),
    response_model=list[ActualRecord],
)
def get_actuals(
    date_from: Annotated[
        date,
        Query(description="Inclusive start delivery date (YYYY-MM-DD)", examples=["2026-01-01"]),
    ],
    date_to: Annotated[
        date,
        Query(description="Inclusive end delivery date (YYYY-MM-DD)", examples=["2026-01-31"]),
    ],
    repo: DataRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> list[ActualRecord]:
    """Return raw actual wind generation records for the specified delivery date range."""
    validate_date_range(date_from, date_to)
    win_start, win_end = resolve_delivery_window(
        repo, settings.delivery_start, settings.delivery_end
    )
    validate_delivery_window(date_from, date_to, win_start, win_end)

    df = repo.get_actuals(date_from, date_to)

    records: list[ActualRecord] = []
    for _, row in df.iterrows():
        ts = str(row["startTime"]).replace("+00:00", "Z").replace(" ", "T")
        records.append(
            ActualRecord(
                start_time=ts,
                generation_mw=float(row["generation"]),
                settlement_date=str(row.get("settlementDate"))
                if "settlementDate" in row and not pd.isna(row.get("settlementDate"))
                else None,
                settlement_period=int(row["settlementPeriod"])
                if "settlementPeriod" in row and not pd.isna(row.get("settlementPeriod"))
                else None,
            )
        )

    return records
