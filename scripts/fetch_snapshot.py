"""CLI script to fetch, clean, validate, and write Elexon snapshot files."""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Add backend root to sys.path so app modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.elexon_client import ElexonClient
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_snapshot")


def fetch_and_save_snapshot() -> None:
    """Fetch actuals and forecasts from Elexon, clean, validate, and save to Parquet."""
    settings = get_settings()
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    client = ElexonClient(
        base_url=settings.elexon_base_url,
        chunk_days=settings.chunk_days,
    )

    logger.info(
        f"Ingesting FUELHH actuals from {settings.delivery_start} to {settings.delivery_end}"
    )
    actual_records = client.fetch_actuals_sync(settings.delivery_start, settings.delivery_end)
    logger.info(f"Fetched {len(actual_records)} raw FUELHH records")

    df_actuals = pd.DataFrame(actual_records)
    if not df_actuals.empty:
        # Filter for WIND
        df_actuals = df_actuals[df_actuals["fuelType"] == "WIND"].copy()
        df_actuals["startTime"] = pd.to_datetime(df_actuals["startTime"], utc=True)
        if "publishTime" in df_actuals.columns:
            df_actuals["publishTime"] = pd.to_datetime(df_actuals["publishTime"], utc=True)
        df_actuals["generation"] = pd.to_numeric(df_actuals["generation"], errors="coerce")
        df_actuals = df_actuals.dropna(subset=["startTime", "generation"])
        df_actuals = df_actuals.drop_duplicates(subset=["startTime"]).sort_values("startTime")

        # Validation check for negative generation
        negative_gen = (df_actuals["generation"] < 0).sum()
        if negative_gen > 0:
            logger.warning(f"Found {negative_gen} rows with negative actual generation!")

        # Check 48 periods per day
        expected_periods = (settings.delivery_end - settings.delivery_start).days + 1
        expected_rows = expected_periods * 48
        logger.info(f"Actuals processed: {len(df_actuals)} rows (expected: {expected_rows})")

    # Ingest WINDFOR forecasts
    lookback_start = datetime.combine(
        settings.delivery_start, datetime.min.time(), tzinfo=timezone.utc
    ) - pd.Timedelta(days=settings.forecast_lookback_days)
    lookforward_end = datetime.combine(
        settings.delivery_end, datetime.max.time(), tzinfo=timezone.utc
    ) + pd.Timedelta(days=1)

    logger.info(
        f"Ingesting WINDFOR forecasts published between {lookback_start} and {lookforward_end}"
    )
    forecast_records = client.fetch_forecasts_sync(lookback_start, lookforward_end)
    logger.info(f"Fetched {len(forecast_records)} raw WINDFOR records")

    df_forecasts = pd.DataFrame(forecast_records)
    if not df_forecasts.empty:
        df_forecasts["startTime"] = pd.to_datetime(df_forecasts["startTime"], utc=True)
        df_forecasts["publishTime"] = pd.to_datetime(df_forecasts["publishTime"], utc=True)
        df_forecasts["generation"] = pd.to_numeric(df_forecasts["generation"], errors="coerce")
        df_forecasts = df_forecasts.dropna(subset=["startTime", "publishTime", "generation"])

        # Filter target times to delivery window (1 Jan 2026 00:00 to 31 Jan 2026 23:30 UTC)
        start_bound = pd.Timestamp(settings.delivery_start, tz=timezone.utc)
        end_bound = pd.Timestamp(settings.delivery_end, tz=timezone.utc) + pd.Timedelta(
            hours=23, minutes=30
        )
        df_forecasts = df_forecasts[
            (df_forecasts["startTime"] >= start_bound) & (df_forecasts["startTime"] <= end_bound)
        ].copy()

        df_forecasts = df_forecasts.drop_duplicates(
            subset=["startTime", "publishTime"]
        ).sort_values(["startTime", "publishTime"])

        negative_fore = (df_forecasts["generation"] < 0).sum()
        if negative_fore > 0:
            logger.warning(f"Found {negative_fore} rows with negative forecast generation!")

        logger.info(f"Forecasts processed for delivery window: {len(df_forecasts)} rows")

    # Save to Parquet
    actuals_path = data_dir / "actuals_wind.parquet"
    forecasts_path = data_dir / "forecasts_wind.parquet"
    df_actuals.to_parquet(actuals_path, index=False)
    df_forecasts.to_parquet(forecasts_path, index=False)
    logger.info(f"Saved actuals to {actuals_path}")
    logger.info(f"Saved forecasts to {forecasts_path}")

    # Write snapshot metadata
    meta = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "delivery_start": settings.delivery_start.isoformat(),
        "delivery_end": settings.delivery_end.isoformat(),
        "actual_rows": len(df_actuals),
        "forecast_rows": len(df_forecasts),
        "source": "Elexon BMRS FUELHH/WINDFOR",
        "actuals_file": "actuals_wind.parquet",
        "forecasts_file": "forecasts_wind.parquet",
    }
    meta_path = data_dir / "snapshot_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    logger.info(f"Saved metadata to {meta_path}")


if __name__ == "__main__":
    fetch_and_save_snapshot()
