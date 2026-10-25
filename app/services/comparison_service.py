"""Service for building actual vs latest-at-cutoff forecast comparisons."""

from datetime import date

import pandas as pd

from app.core.config import Settings
from app.domain.decision_time import cutoff_for
from app.domain.forecast_selector import select_latest_forecasts
from app.domain.metrics import compute_bias, compute_mae, compute_rmse
from app.repositories.data_repository import DataRepository
from app.schemas.comparison import (
    ComparisonPoint,
    ComparisonRangeResponse,
    ComparisonResponse,
    ComparisonSummary,
    UncertaintyBand,
)


class ComparisonService:
    """Builds paired actual vs forecast comparison frames for delivery days."""

    def __init__(self, repo: DataRepository, settings: Settings) -> None:
        """Initialise ComparisonService.

        Args:
            repo: Data repository.
            settings: Application configuration.
        """
        self.repo = repo
        self.settings = settings

    def _build_comparison_points(
        self,
        actuals_df: pd.DataFrame,
        forecasts_df: pd.DataFrame,
        cutoff_dt: object,
    ) -> tuple[list[ComparisonPoint], pd.DataFrame]:
        """Merge actuals with latest-at-cutoff forecasts into comparison points.

        Args:
            actuals_df: Actual wind records with startTime, generation.
            forecasts_df: Forecast records with startTime, publishTime, generation.
            cutoff_dt: UTC cutoff datetime.

        Returns:
            Tuple of (ComparisonPoint list, paired_df with error_mw column).
        """
        latest = select_latest_forecasts(forecasts_df, cutoff_dt)  # type: ignore[arg-type]

        # Normalise actual column names
        actuals = actuals_df[["startTime", "generation"]].rename(
            columns={"generation": "actual_mw"}
        )

        # Merge on startTime with outer join to capture all target periods
        if not latest.empty:
            merged = pd.merge(actuals, latest, on="startTime", how="outer").sort_values("startTime")
        else:
            merged = actuals.copy()
            merged["forecast_mw"] = float("nan")
            merged["forecast_publish_time"] = pd.NaT
            merged["horizon_hours"] = float("nan")

        # Forward-fill null forecasts: Elexon WINDFOR is published hourly, so
        # the :30 half-hour periods have no matching forecast record.  We carry
        # the most-recent published forecast forward — this is correct domain
        # behaviour and ensures a continuous line on the chart.
        for col in ["forecast_mw", "forecast_publish_time", "horizon_hours"]:
            if col in merged.columns:
                merged[col] = merged[col].ffill()

        merged["error_mw"] = merged["forecast_mw"] - merged["actual_mw"]
        merged["abs_error_mw"] = merged["error_mw"].abs()

        def fmt_ts(ts: object) -> str | None:
            if pd.isna(ts):  # type: ignore[arg-type]
                return None
            return str(ts).replace("+00:00", "Z").replace(" ", "T")

        points: list[ComparisonPoint] = []
        for _, row in merged.iterrows():
            points.append(
                ComparisonPoint(
                    start_time=fmt_ts(row["startTime"]) or "",
                    actual_mw=None if pd.isna(row.get("actual_mw")) else float(row["actual_mw"]),
                    forecast_mw=None
                    if pd.isna(row.get("forecast_mw"))
                    else float(row["forecast_mw"]),
                    forecast_publish_time=fmt_ts(row.get("forecast_publish_time")),
                    horizon_hours=None
                    if pd.isna(row.get("horizon_hours"))
                    else float(row["horizon_hours"]),
                    error_mw=None if pd.isna(row.get("error_mw")) else float(row["error_mw"]),
                    abs_error_mw=None
                    if pd.isna(row.get("abs_error_mw"))
                    else float(row["abs_error_mw"]),
                )
            )

        return points, merged

    def get_comparison_for_day(self, delivery_date: date, cutoff_str: str) -> ComparisonResponse:
        """Build the E6 /api/comparison response for a single delivery day.

        Args:
            delivery_date: The delivery date D.
            cutoff_str: Cutoff time string 'HH:MM' in Europe/London timezone.

        Returns:
            ComparisonResponse with 48 half-hourly comparison points and summary.
        """
        cutoff_dt = cutoff_for(delivery_date, cutoff_str, self.settings.cutoff_timezone)

        actuals_df = self.repo.get_actuals(delivery_date, delivery_date)
        forecasts_df = self.repo.get_forecasts(date_from=delivery_date, date_to=delivery_date)

        points, paired_df = self._build_comparison_points(actuals_df, forecasts_df, cutoff_dt)

        valid = paired_df.dropna(subset=["actual_mw", "forecast_mw", "error_mw"])
        n = len(valid)
        total = max(len(paired_df), 1)

        errors = valid["error_mw"].to_numpy() if n > 0 else []
        mae = compute_mae(errors) or 0.0  # type: ignore[arg-type]
        rmse = compute_rmse(errors) or 0.0  # type: ignore[arg-type]
        bias = compute_bias(errors) or 0.0  # type: ignore[arg-type]
        coverage = round(float(n / total) * 100.0, 2)

        summary = ComparisonSummary(
            mae_mw=mae,
            rmse_mw=rmse,
            bias_mw=bias,
            coverage_pct=coverage,
            n=n,
        )

        uncertainty = UncertaintyBand(
            basis="historical_rmse",
            rmse_mw=rmse,
            lower_offset_mw=-rmse,
            upper_offset_mw=rmse,
        )

        cutoff_utc_str = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return ComparisonResponse(
            delivery_date=delivery_date.isoformat(),
            cutoff_local=cutoff_str,
            cutoff_utc=cutoff_utc_str,
            points=points,
            summary=summary,
            uncertainty=uncertainty,
        )

    def get_comparison_for_range(
        self, date_from: date, date_to: date, cutoff_str: str
    ) -> ComparisonRangeResponse:
        """Build the E7 /api/comparison/range response across a range of delivery days.

        Args:
            date_from: Inclusive start delivery date.
            date_to: Inclusive end delivery date.
            cutoff_str: Cutoff time string 'HH:MM' in Europe/London timezone.

        Returns:
            ComparisonRangeResponse with all comparison points for the range.
        """
        all_points: list[ComparisonPoint] = []

        current = date_from
        while current <= date_to:
            cutoff_dt = cutoff_for(current, cutoff_str, self.settings.cutoff_timezone)
            actuals_df = self.repo.get_actuals(current, current)
            forecasts_df = self.repo.get_forecasts(date_from=current, date_to=current)
            points, _ = self._build_comparison_points(actuals_df, forecasts_df, cutoff_dt)
            all_points.extend(points)
            current = current.fromordinal(current.toordinal() + 1)

        return ComparisonRangeResponse(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            cutoff_local=cutoff_str,
            points=all_points,
        )
