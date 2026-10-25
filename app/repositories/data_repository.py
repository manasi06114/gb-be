"""Repository layer for thread-safe access to in-memory wind data snapshots."""

import json
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.errors import DataUnavailableError

logger = pd.core.common if hasattr(pd, "core") else None  # type: ignore


class DataRepository:
    """In-memory data repository serving cached Parquet snapshots."""

    def __init__(self, data_dir: Path | str = "data/snapshot") -> None:
        """Initialise repository with path to snapshot files."""
        self.data_dir = Path(data_dir)
        self._lock = threading.RLock()
        self._actuals_df: pd.DataFrame = pd.DataFrame()
        self._forecasts_df: pd.DataFrame = pd.DataFrame()
        self._meta: dict[str, Any] = {}
        self._loaded: bool = False
        self._custom_window: tuple[date, date] | None = None

    def is_loaded(self) -> bool:
        """Return True if snapshot data is loaded into memory."""
        with self._lock:
            return self._loaded and not self._actuals_df.empty

    def load(self) -> None:
        """Load Parquet files and metadata from disk into memory."""
        with self._lock:
            actuals_file = self.data_dir / "actuals_wind.parquet"
            forecasts_file = self.data_dir / "forecasts_wind.parquet"
            meta_file = self.data_dir / "snapshot_meta.json"

            if not actuals_file.exists() or not forecasts_file.exists():
                raise DataUnavailableError(
                    f"Snapshot files not found in {self.data_dir}. "
                    "Run scripts/fetch_snapshot.py to generate snapshot."
                )

            try:
                actuals = pd.read_parquet(actuals_file)
                forecasts = pd.read_parquet(forecasts_file)

                # Ensure timestamps are UTC tz-aware
                actuals["startTime"] = pd.to_datetime(actuals["startTime"], utc=True)
                if "publishTime" in actuals.columns:
                    actuals["publishTime"] = pd.to_datetime(actuals["publishTime"], utc=True)

                forecasts["startTime"] = pd.to_datetime(forecasts["startTime"], utc=True)
                forecasts["publishTime"] = pd.to_datetime(forecasts["publishTime"], utc=True)

                self._actuals_df = actuals
                self._forecasts_df = forecasts

                if meta_file.exists():
                    with open(meta_file, encoding="utf-8") as f:
                        self._meta = json.load(f)
                else:
                    self._meta = {
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "actual_rows": len(actuals),
                        "forecast_rows": len(forecasts),
                        "source": "Elexon BMRS FUELHH/WINDFOR",
                    }

                self._loaded = True
            except Exception as exc:
                raise DataUnavailableError(f"Failed to load snapshot data: {exc}") from exc

    def get_actuals(
        self, date_from: date | None = None, date_to: date | None = None
    ) -> pd.DataFrame:
        """Return actual generation records filtered by delivery date range."""
        with self._lock:
            if not self.is_loaded():
                raise DataUnavailableError("Snapshot data not loaded.")
            df = self._actuals_df
            if date_from is not None:
                start_ts = pd.Timestamp(date_from, tz=timezone.utc)
                df = df[df["startTime"] >= start_ts]
            if date_to is not None:
                end_ts = pd.Timestamp(date_to, tz=timezone.utc) + pd.Timedelta(days=1)
                df = df[df["startTime"] < end_ts]
            return df.copy()

    def get_forecasts(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        publish_from: datetime | None = None,
        publish_to: datetime | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> pd.DataFrame:
        """Return forecast records filtered by target or publish date range."""
        with self._lock:
            if not self.is_loaded():
                raise DataUnavailableError("Snapshot data not loaded.")
            df = self._forecasts_df

            if date_from is not None:
                start_ts = pd.Timestamp(date_from, tz=timezone.utc)
                df = df[df["startTime"] >= start_ts]
            if date_to is not None:
                end_ts = pd.Timestamp(date_to, tz=timezone.utc) + pd.Timedelta(days=1)
                df = df[df["startTime"] < end_ts]

            if publish_from is not None:
                if publish_from.tzinfo is None:
                    publish_from = publish_from.replace(tzinfo=timezone.utc)
                df = df[df["publishTime"] >= publish_from]
            if publish_to is not None:
                if publish_to.tzinfo is None:
                    publish_to = publish_to.replace(tzinfo=timezone.utc)
                df = df[df["publishTime"] <= publish_to]

            if offset > 0:
                df = df.iloc[offset:]
            if limit is not None and limit > 0:
                df = df.iloc[:limit]

            return df.copy()

    def get_all_actuals(self) -> pd.DataFrame:
        """Return complete actual generation DataFrame."""
        with self._lock:
            if not self.is_loaded():
                raise DataUnavailableError("Snapshot data not loaded.")
            return self._actuals_df.copy()

    def get_all_forecasts(self) -> pd.DataFrame:
        """Return complete forecasts DataFrame."""
        with self._lock:
            if not self.is_loaded():
                raise DataUnavailableError("Snapshot data not loaded.")
            return self._forecasts_df.copy()

    def get_snapshot_meta(self) -> dict[str, Any]:
        """Return metadata for the active snapshot."""
        with self._lock:
            return dict(self._meta)

    def get_delivery_bounds(self) -> tuple[date | None, date | None]:
        """Return custom delivery bounds if set by dynamic ingestion, else None."""
        with self._lock:
            if getattr(self, "_custom_window", None) is not None:
                return self._custom_window
            return None, None

    def update_data(
        self,
        actuals_df: pd.DataFrame,
        forecasts_df: pd.DataFrame,
        meta: dict[str, Any] | None = None,
        save_to_disk: bool = True,
    ) -> None:
        """Update in-memory data with new actuals and forecasts and optionally persist."""
        with self._lock:
            actuals = actuals_df.copy()
            forecasts = forecasts_df.copy()

            if not actuals.empty:
                actuals["startTime"] = pd.to_datetime(actuals["startTime"], utc=True)
                if "publishTime" in actuals.columns:
                    actuals["publishTime"] = pd.to_datetime(actuals["publishTime"], utc=True)
                self._custom_window = (
                    actuals["startTime"].min().date(),
                    actuals["startTime"].max().date(),
                )

            if not forecasts.empty:
                forecasts["startTime"] = pd.to_datetime(forecasts["startTime"], utc=True)
                forecasts["publishTime"] = pd.to_datetime(forecasts["publishTime"], utc=True)

            self._actuals_df = actuals
            self._forecasts_df = forecasts

            if meta is None:
                meta = {
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "actual_rows": len(actuals),
                    "forecast_rows": len(forecasts),
                    "source": "Dynamic Ingestion",
                }
            self._meta = meta
            self._loaded = True

            if save_to_disk:
                self.data_dir.mkdir(parents=True, exist_ok=True)
                actuals.to_parquet(self.data_dir / "actuals_wind.parquet", index=False)
                forecasts.to_parquet(self.data_dir / "forecasts_wind.parquet", index=False)
                with open(self.data_dir / "snapshot_meta.json", "w", encoding="utf-8") as f:
                    json.dump(self._meta, f, indent=2)
