"""Service for fetching, processing, and dynamically mapping actual and forecast datasets."""

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import pandas as pd

from app.clients.elexon_client import ElexonClient
from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.repositories.data_repository import DataRepository
from app.schemas.common import DeliveryWindow
from app.schemas.data_ingest import (
    DynamicIngestRequest,
    DynamicIngestResponse,
)

logger = logging.getLogger(__name__)


class IngestService:
    """Coordinates dynamic data fetching, column mapping, and repository updates."""

    def __init__(self, repo: DataRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def _fetch_records_from_url(
        self, url: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch records from a given URL using httpx."""
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                return data["data"]
            return []

    def _get_actual_records(self, req: DynamicIngestRequest) -> list[dict[str, Any]]:
        """Retrieve actual records from payload or remote URL."""
        if req.actuals.records is not None:
            return req.actuals.records

        if not req.actuals.url:
            raise ValidationAppError(
                "Actuals data source must provide either 'records' list or 'url'."
            )

        parsed = urlparse(req.actuals.url)
        has_query_params = bool(parsed.query)

        if has_query_params:
            return self._fetch_records_from_url(req.actuals.url)

        # Standard Elexon stream URL without query parameters -> chunked query
        d_from = req.actuals.date_from or self.settings.delivery_start
        d_to = req.actuals.date_to or self.settings.delivery_end
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        if "/datasets/" in parsed.path:
            client = ElexonClient(base_url=f"{base_url}/bmrs/api/v1")
            return client.fetch_actuals_sync(d_from, d_to)

        return self._fetch_records_from_url(
            req.actuals.url,
            {
                "settlementDateFrom": d_from.isoformat(),
                "settlementDateTo": d_to.isoformat(),
                "fuelType": req.actuals.fields.fuel_type_value or "WIND",
            },
        )

    def _get_forecast_records(self, req: DynamicIngestRequest) -> list[dict[str, Any]]:
        """Retrieve forecast records from payload or remote URL."""
        if req.forecasts.records is not None:
            return req.forecasts.records

        if not req.forecasts.url:
            raise ValidationAppError(
                "Forecast data source must provide either 'records' list or 'url'."
            )

        parsed = urlparse(req.forecasts.url)
        has_query_params = bool(parsed.query)

        if has_query_params:
            return self._fetch_records_from_url(req.forecasts.url)

        # Standard Elexon stream URL without query parameters
        p_from = req.forecasts.publish_from or datetime(2025, 12, 22, 0, 0, tzinfo=timezone.utc)
        p_to = req.forecasts.publish_to or datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        if "/datasets/" in parsed.path:
            client = ElexonClient(base_url=f"{base_url}/bmrs/api/v1")
            return client.fetch_forecasts_sync(p_from, p_to)

        return self._fetch_records_from_url(
            req.forecasts.url,
            {
                "publishDateTimeFrom": p_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publishDateTimeTo": p_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    def process_and_ingest(self, req: DynamicIngestRequest) -> DynamicIngestResponse:
        """Process incoming dynamic requests, map columns, and update repository."""
        actual_records = self._get_actual_records(req)
        forecast_records = self._get_forecast_records(req)

        # 1. Process actuals with dynamic field mapping
        f_act = req.actuals.fields
        df_actuals_raw = pd.DataFrame(actual_records)
        if df_actuals_raw.empty:
            raise ValidationAppError("No actual records retrieved from source.")

        # Check required fields exist in incoming data
        cols = list(df_actuals_raw.columns)
        if f_act.start_time not in df_actuals_raw.columns:
            raise ValidationAppError(
                f"Field '{f_act.start_time}' not found in actuals. Available columns: {cols}"
            )
        if f_act.generation not in df_actuals_raw.columns:
            raise ValidationAppError(
                f"Field '{f_act.generation}' not found in actuals. Available columns: {cols}"
            )

        # Apply fuel type filter if present
        if (
            f_act.fuel_type_field
            and f_act.fuel_type_field in df_actuals_raw.columns
            and f_act.fuel_type_value
        ):
            df_actuals_raw = df_actuals_raw[
                df_actuals_raw[f_act.fuel_type_field] == f_act.fuel_type_value
            ].copy()

        df_actuals = pd.DataFrame()
        df_actuals["startTime"] = pd.to_datetime(df_actuals_raw[f_act.start_time], utc=True)
        df_actuals["generation"] = pd.to_numeric(df_actuals_raw[f_act.generation], errors="coerce")
        df_actuals = df_actuals.dropna(subset=["startTime", "generation"])
        df_actuals = df_actuals.drop_duplicates(subset=["startTime"]).sort_values("startTime")

        if df_actuals.empty:
            raise ValidationAppError("Actuals processing yielded 0 valid rows after filtering.")

        # 2. Process forecasts with dynamic field mapping
        f_fc = req.forecasts.fields
        df_fc_raw = pd.DataFrame(forecast_records)
        if df_fc_raw.empty:
            raise ValidationAppError("No forecast records retrieved from source.")

        fc_cols = list(df_fc_raw.columns)
        for col, col_name in [
            (f_fc.start_time, "start_time"),
            (f_fc.publish_time, "publish_time"),
            (f_fc.generation, "generation"),
        ]:
            if col not in df_fc_raw.columns:
                raise ValidationAppError(
                    f"Field '{col}' ({col_name}) not found in forecasts. Columns: {fc_cols}"
                )

        df_forecasts = pd.DataFrame()
        df_forecasts["startTime"] = pd.to_datetime(df_fc_raw[f_fc.start_time], utc=True)
        df_forecasts["publishTime"] = pd.to_datetime(df_fc_raw[f_fc.publish_time], utc=True)
        df_forecasts["generation"] = pd.to_numeric(df_fc_raw[f_fc.generation], errors="coerce")
        df_forecasts = df_forecasts.dropna(subset=["startTime", "publishTime", "generation"])
        df_forecasts = df_forecasts.drop_duplicates(
            subset=["startTime", "publishTime"]
        ).sort_values(["startTime", "publishTime"])

        if df_forecasts.empty:
            raise ValidationAppError("Forecasts processing yielded 0 valid rows after filtering.")

        # Update repository
        now_utc = datetime.now(timezone.utc).isoformat()
        meta = {
            "fetched_at": now_utc,
            "actual_rows": len(df_actuals),
            "forecast_rows": len(df_forecasts),
            "source": "Dynamic Ingestion (Frontend)",
            "fields_mapped": {
                "actuals": {
                    "start_time": f_act.start_time,
                    "generation": f_act.generation,
                },
                "forecasts": {
                    "start_time": f_fc.start_time,
                    "publish_time": f_fc.publish_time,
                    "generation": f_fc.generation,
                },
            },
        }

        self.repo.update_data(
            actuals_df=df_actuals,
            forecasts_df=df_forecasts,
            meta=meta,
            save_to_disk=req.save_as_snapshot,
        )

        min_d = df_actuals["startTime"].min().date()
        max_d = df_actuals["startTime"].max().date()

        return DynamicIngestResponse(
            status="success",
            message=f"Ingested {len(df_actuals)} actual and {len(df_forecasts)} forecast records.",
            actual_rows=len(df_actuals),
            forecast_rows=len(df_forecasts),
            delivery_window=DeliveryWindow(
                start=min_d.isoformat(),
                end=max_d.isoformat(),
            ),
            actual_fields_mapped={
                "startTime": f_act.start_time,
                "generation": f_act.generation,
            },
            forecast_fields_mapped={
                "startTime": f_fc.start_time,
                "publishTime": f_fc.publish_time,
                "generation": f_fc.generation,
            },
            fetched_at=now_utc,
        )
