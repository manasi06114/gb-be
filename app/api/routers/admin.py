"""E13: Admin endpoint for refreshing the data snapshot (optional, token-protected)."""

import logging

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from app.api.deps import get_repository
from app.clients.elexon_client import ElexonClient
from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedAppError
from app.repositories.data_repository import DataRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin"])


class RefreshResponse(BaseModel):
    """Response for admin snapshot refresh."""

    status: str
    message: str
    actual_rows: int
    forecast_rows: int


@router.post(
    "/admin/refresh",
    summary="Re-fetch snapshot from Elexon and reload (E13)",
    description=(
        "Triggers a fresh data fetch from Elexon BMRS APIs and reloads the in-memory "
        "repository. Protected by X-Admin-Token header. Disabled if ADMIN_TOKEN is not set."
    ),
    response_model=RefreshResponse,
)
def refresh_snapshot(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    repo: DataRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> RefreshResponse:
    """Re-fetch Elexon data and hot-reload the in-memory snapshot."""
    if not settings.admin_token:
        raise UnauthorizedAppError("Admin endpoint is disabled (ADMIN_TOKEN not configured).")

    if x_admin_token != settings.admin_token:
        raise UnauthorizedAppError("Invalid X-Admin-Token header.")

    logger.info("Admin refresh triggered — re-fetching Elexon snapshot")

    try:
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        import pandas as pd

        client = ElexonClient(
            base_url=settings.elexon_base_url,
            chunk_days=settings.chunk_days,
        )

        actual_records = client.fetch_actuals_sync(settings.delivery_start, settings.delivery_end)
        df_actuals = pd.DataFrame(actual_records)
        if not df_actuals.empty:
            df_actuals = df_actuals[df_actuals["fuelType"] == "WIND"].copy()
            df_actuals["startTime"] = pd.to_datetime(df_actuals["startTime"], utc=True)
            if "publishTime" in df_actuals.columns:
                df_actuals["publishTime"] = pd.to_datetime(df_actuals["publishTime"], utc=True)
            df_actuals["generation"] = pd.to_numeric(df_actuals["generation"], errors="coerce")
            df_actuals = df_actuals.dropna(subset=["startTime", "generation"])
            df_actuals = df_actuals.drop_duplicates(subset=["startTime"]).sort_values("startTime")

        lookback_start = datetime.combine(
            settings.delivery_start, datetime.min.time(), tzinfo=timezone.utc
        ) - pd.Timedelta(days=settings.forecast_lookback_days)
        lookforward_end = datetime.combine(
            settings.delivery_end, datetime.max.time(), tzinfo=timezone.utc
        ) + pd.Timedelta(days=1)

        forecast_records = client.fetch_forecasts_sync(lookback_start, lookforward_end)
        df_forecasts = pd.DataFrame(forecast_records)
        if not df_forecasts.empty:
            df_forecasts["startTime"] = pd.to_datetime(df_forecasts["startTime"], utc=True)
            df_forecasts["publishTime"] = pd.to_datetime(df_forecasts["publishTime"], utc=True)
            df_forecasts["generation"] = pd.to_numeric(df_forecasts["generation"], errors="coerce")
            df_forecasts = df_forecasts.dropna(subset=["startTime", "publishTime", "generation"])
            start_bound = pd.Timestamp(settings.delivery_start, tz=timezone.utc)
            end_bound = pd.Timestamp(settings.delivery_end, tz=timezone.utc) + pd.Timedelta(
                hours=23, minutes=30
            )
            df_forecasts = df_forecasts[
                (df_forecasts["startTime"] >= start_bound)
                & (df_forecasts["startTime"] <= end_bound)
            ].copy()
            df_forecasts = df_forecasts.drop_duplicates(
                subset=["startTime", "publishTime"]
            ).sort_values(["startTime", "publishTime"])

        data_dir = Path(settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        df_actuals.to_parquet(data_dir / "actuals_wind.parquet", index=False)
        df_forecasts.to_parquet(data_dir / "forecasts_wind.parquet", index=False)

        meta = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "actual_rows": len(df_actuals),
            "forecast_rows": len(df_forecasts),
            "source": "Elexon BMRS FUELHH/WINDFOR",
        }
        with open(data_dir / "snapshot_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        repo.load()
        logger.info(
            f"Refresh complete: {len(df_actuals)} actuals, {len(df_forecasts)} forecasts loaded"
        )

        return RefreshResponse(
            status="ok",
            message="Snapshot refreshed and reloaded successfully.",
            actual_rows=len(df_actuals),
            forecast_rows=len(df_forecasts),
        )

    except Exception as exc:
        logger.error(f"Admin refresh failed: {exc}")
        raise
