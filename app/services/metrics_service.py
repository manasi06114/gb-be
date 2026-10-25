"""Service for computing accuracy metrics across delivery ranges (E8-E12)."""

from datetime import date

import pandas as pd

from app.core.config import Settings
from app.domain.aggregations import (
    aggregate_by_day,
    aggregate_by_horizon,
    aggregate_by_hour,
    compute_error_distribution,
)
from app.domain.decision_time import cutoff_for
from app.domain.forecast_selector import select_latest_forecasts
from app.domain.metrics import compute_kpi_summary
from app.repositories.data_repository import DataRepository
from app.schemas.metrics import (
    DailyMetricRow,
    DailyMetricsResponse,
    DistributionBin,
    ErrorDistributionResponse,
    HorizonMetricRow,
    HorizonMetricsResponse,
    HourlyHeatmapCell,
    HourlyMetricsResponse,
    HourlyProfileRow,
    KPIMetricsResponse,
)


class MetricsService:
    """Orchestrates computation of all accuracy metric endpoints (E8–E12)."""

    def __init__(self, repo: DataRepository, settings: Settings) -> None:
        """Initialise MetricsService.

        Args:
            repo: Data repository.
            settings: Application configuration.
        """
        self.repo = repo
        self.settings = settings

    def _build_paired_df(self, date_from: date, date_to: date, cutoff_str: str) -> pd.DataFrame:
        """Build paired actual+forecast DataFrame for date range using latest-at-cutoff.

        Args:
            date_from: Inclusive start delivery date.
            date_to: Inclusive end delivery date.
            cutoff_str: Decision cutoff time 'HH:MM'.

        Returns:
            DataFrame with startTime, actual_mw, forecast_mw, error_mw.
        """
        all_frames: list[pd.DataFrame] = []

        current = date_from
        while current <= date_to:
            cutoff_dt = cutoff_for(current, cutoff_str, self.settings.cutoff_timezone)
            actuals_df = self.repo.get_actuals(current, current)
            forecasts_df = self.repo.get_forecasts(date_from=current, date_to=current)

            if actuals_df.empty:
                current = current.fromordinal(current.toordinal() + 1)
                continue

            actuals = actuals_df[["startTime", "generation"]].rename(
                columns={"generation": "actual_mw"}
            )

            latest = select_latest_forecasts(forecasts_df, cutoff_dt)  # type: ignore[arg-type]

            if not latest.empty:
                merged = pd.merge(actuals, latest, on="startTime", how="left")
            else:
                merged = actuals.copy()
                merged["forecast_mw"] = float("nan")
                merged["forecast_publish_time"] = pd.NaT
                merged["horizon_hours"] = float("nan")

            merged["error_mw"] = merged["forecast_mw"] - merged["actual_mw"]
            all_frames.append(merged)
            current = current.fromordinal(current.toordinal() + 1)

        if not all_frames:
            return pd.DataFrame(columns=["startTime", "actual_mw", "forecast_mw", "error_mw"])

        combined = pd.concat(all_frames, ignore_index=True)
        return combined.sort_values("startTime").reset_index(drop=True)

    def get_kpi_metrics(
        self, date_from: date, date_to: date, cutoff_str: str
    ) -> KPIMetricsResponse:
        """Compute E8 /api/metrics KPI summary for a delivery date range.

        Args:
            date_from: Start of delivery range.
            date_to: End of delivery range.
            cutoff_str: Decision cutoff time.

        Returns:
            KPIMetricsResponse.
        """
        df = self._build_paired_df(date_from, date_to, cutoff_str)
        n_days = (date_to - date_from).days + 1
        expected_count = n_days * 48

        kpi = compute_kpi_summary(df, expected_count)

        return KPIMetricsResponse(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            cutoff_local=cutoff_str,
            **kpi,
        )

    def get_daily_metrics(
        self, date_from: date, date_to: date, cutoff_str: str
    ) -> DailyMetricsResponse:
        """Compute E9 /api/metrics/daily per-delivery-day breakdown.

        Args:
            date_from: Start of delivery range.
            date_to: End of delivery range.
            cutoff_str: Decision cutoff time.

        Returns:
            DailyMetricsResponse.
        """
        df = self._build_paired_df(date_from, date_to, cutoff_str)
        daily_rows = aggregate_by_day(df)
        return DailyMetricsResponse(rows=[DailyMetricRow(**r) for r in daily_rows])

    def get_hourly_metrics(
        self, date_from: date, date_to: date, cutoff_str: str
    ) -> HourlyMetricsResponse:
        """Compute E10 /api/metrics/by-hour heatmap cells and hourly profile.

        Args:
            date_from: Start of delivery range.
            date_to: End of delivery range.
            cutoff_str: Decision cutoff time.

        Returns:
            HourlyMetricsResponse.
        """
        df = self._build_paired_df(date_from, date_to, cutoff_str)
        cells_raw, by_hour_raw = aggregate_by_hour(df)

        cells = [HourlyHeatmapCell(**c) for c in cells_raw]
        by_hour = [HourlyProfileRow(**r) for r in by_hour_raw]

        return HourlyMetricsResponse(cells=cells, by_hour_of_day=by_hour)

    def get_horizon_metrics(
        self, date_from: date, date_to: date, bucket_hours: int = 3
    ) -> HorizonMetricsResponse:
        """Compute E11 /api/metrics/by-horizon using ALL forecast publish times (BR-3).

        Args:
            date_from: Start of delivery range.
            date_to: End of delivery range.
            bucket_hours: Horizon bin size in hours.

        Returns:
            HorizonMetricsResponse.
        """
        actuals_df = self.repo.get_actuals(date_from, date_to)
        forecasts_df = self.repo.get_forecasts(date_from=date_from, date_to=date_to)

        bucket_rows = aggregate_by_horizon(forecasts_df, actuals_df, bucket_hours)
        return HorizonMetricsResponse(
            bucket_hours=bucket_hours,
            rows=[HorizonMetricRow(**r) for r in bucket_rows],
        )

    def get_error_distribution(
        self, date_from: date, date_to: date, cutoff_str: str, num_bins: int = 20
    ) -> ErrorDistributionResponse:
        """Compute E12 /api/errors/distribution histogram and percentile summary.

        Args:
            date_from: Start of delivery range.
            date_to: End of delivery range.
            cutoff_str: Decision cutoff time.
            num_bins: Number of equal-width histogram bins.

        Returns:
            ErrorDistributionResponse.
        """
        df = self._build_paired_df(date_from, date_to, cutoff_str)
        valid = df.dropna(subset=["error_mw"])
        errors = valid["error_mw"] if not valid.empty else pd.Series([], dtype=float)

        bins_raw, summary = compute_error_distribution(errors, num_bins=num_bins)

        return ErrorDistributionResponse(
            bins=[DistributionBin(**b) for b in bins_raw],
            mean_mw=summary["mean_mw"],
            p05_mw=summary["p05_mw"],
            p50_mw=summary["p50_mw"],
            p95_mw=summary["p95_mw"],
            n=summary["n"],
        )
