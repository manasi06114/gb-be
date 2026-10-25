"""Service for building the /api/meta response."""

from app.core.config import Settings
from app.core.constants import METRIC_DEFINITIONS
from app.repositories.data_repository import DataRepository
from app.schemas.common import DeliveryWindow
from app.schemas.meta import MetaResponse, SnapshotMeta


class MetaService:
    """Builds metadata and methodology documentation response."""

    def __init__(self, repo: DataRepository, settings: Settings) -> None:
        """Initialise MetaService.

        Args:
            repo: Data repository containing snapshot metadata.
            settings: Application configuration settings.
        """
        self.repo = repo
        self.settings = settings

    def get_meta(self) -> MetaResponse:
        """Build and return /api/meta payload.

        Returns:
            MetaResponse with delivery window, cutoff configuration, snapshot info, and definitions.
        """
        raw_meta = self.repo.get_snapshot_meta()

        snapshot = SnapshotMeta(
            fetched_at=raw_meta.get("fetched_at", "unknown"),
            actual_rows=raw_meta.get("actual_rows", 0),
            forecast_rows=raw_meta.get("forecast_rows", 0),
            source=raw_meta.get("source", "Elexon BMRS FUELHH/WINDFOR"),
        )

        min_d, max_d = self.repo.get_delivery_bounds()
        delivery_window = DeliveryWindow(
            start=(min_d or self.settings.delivery_start).isoformat(),
            end=(max_d or self.settings.delivery_end).isoformat(),
        )

        return MetaResponse(
            delivery_window=delivery_window,
            default_cutoff=self.settings.default_cutoff,
            cutoff_timezone=self.settings.cutoff_timezone,
            available_cutoffs=self.settings.available_cutoffs,
            snapshot=snapshot,
            definitions=METRIC_DEFINITIONS,
        )
