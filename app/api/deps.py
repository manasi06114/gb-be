"""Dependency injection helpers for FastAPI routes."""

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.repositories.data_repository import DataRepository
from app.services.comparison_service import ComparisonService
from app.services.meta_service import MetaService
from app.services.metrics_service import MetricsService

# Global singleton repository instance
_repository: DataRepository | None = None


def get_repository() -> DataRepository:
    """Return the application-wide DataRepository singleton.

    The repository is expected to be set on startup by the app lifespan.
    """
    global _repository
    if _repository is None:
        _repository = DataRepository()
    return _repository


def set_repository(repo: DataRepository) -> None:
    """Set the global repository (used in startup and tests)."""
    global _repository
    _repository = repo


def get_meta_service(
    repo: DataRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> MetaService:
    """Provide a MetaService instance via DI."""
    return MetaService(repo=repo, settings=settings)


def get_comparison_service(
    repo: DataRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> ComparisonService:
    """Provide a ComparisonService instance via DI."""
    return ComparisonService(repo=repo, settings=settings)


def get_metrics_service(
    repo: DataRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> MetricsService:
    """Provide a MetricsService instance via DI."""
    return MetricsService(repo=repo, settings=settings)


def get_ingest_service(
    repo: DataRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
):
    """Provide an IngestService instance via DI."""
    from app.services.ingest_service import IngestService

    return IngestService(repo=repo, settings=settings)
