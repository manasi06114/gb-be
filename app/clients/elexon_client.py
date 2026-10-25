"""HTTP client for communicating with Elexon BMRS API."""

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ElexonClient:
    """Client for fetching generation and forecast data from Elexon BMRS."""

    def __init__(
        self,
        base_url: str = "https://data.elexon.co.uk/bmrs/api/v1",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        chunk_days: int = 7,
    ) -> None:
        """Initialise Elexon client with configuration."""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self.chunk_days = chunk_days

    def _request_with_retry(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a GET request with exponential back-off retries."""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                        return data["data"]
                    return []
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                wait_time = 2**attempt
                logger.warning(
                    f"Elexon API request failed (attempt {attempt}/{self.max_retries}): {exc}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

        raise RuntimeError(
            f"Failed to query Elexon API at {url} after {self.max_retries} attempts: {last_error}"
        ) from last_error

    def fetch_actuals_sync(self, date_from: date, date_to: date) -> list[dict[str, Any]]:
        """Fetch actual wind generation records (FUELHH) synchronously chunked by date."""
        url = f"{self.base_url}/datasets/FUELHH/stream"
        all_records: list[dict[str, Any]] = []

        current_from = date_from
        while current_from <= date_to:
            current_to = min(current_from + timedelta(days=self.chunk_days - 1), date_to)
            params = {
                "settlementDateFrom": current_from.isoformat(),
                "settlementDateTo": current_to.isoformat(),
                "fuelType": "WIND",
            }
            logger.info(f"Fetching FUELHH chunk: {current_from} to {current_to}")
            records = self._request_with_retry(url, params)
            all_records.extend(records)
            current_from = current_to + timedelta(days=1)

        return all_records

    def fetch_forecasts_sync(
        self, publish_from: datetime, publish_to: datetime
    ) -> list[dict[str, Any]]:
        """Fetch wind forecasts (WINDFOR) synchronously chunked by publish date."""
        url = f"{self.base_url}/datasets/WINDFOR/stream"
        all_records: list[dict[str, Any]] = []

        # Ensure UTC timezone
        if publish_from.tzinfo is None:
            publish_from = publish_from.replace(tzinfo=timezone.utc)
        if publish_to.tzinfo is None:
            publish_to = publish_to.replace(tzinfo=timezone.utc)

        current_from = publish_from
        delta = timedelta(days=self.chunk_days)
        while current_from < publish_to:
            current_to = min(current_from + delta, publish_to)
            params = {
                "publishDateTimeFrom": current_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publishDateTimeTo": current_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            logger.info(
                "Fetching WINDFOR chunk: %s to %s",
                params["publishDateTimeFrom"],
                params["publishDateTimeTo"],
            )
            records = self._request_with_retry(url, params)
            all_records.extend(records)
            current_from = current_to

        return all_records
