"""E1: Health liveness/readiness endpoint."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_repository
from app.repositories.data_repository import DataRepository

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    data_loaded: bool
    snapshot_fetched_at: str | None


@router.get(
    "/health",
    summary="Liveness & readiness check",
    description="Returns API status and whether the snapshot data has been loaded into memory.",
    response_model=HealthResponse,
)
def health_check(repo: DataRepository = Depends(get_repository)) -> HealthResponse:
    """Return API health status and data readiness."""
    loaded = repo.is_loaded()
    fetched_at: str | None = None
    if loaded:
        meta = repo.get_snapshot_meta()
        fetched_at = meta.get("fetched_at")

    return HealthResponse(
        status="ok" if loaded else "degraded",
        data_loaded=loaded,
        snapshot_fetched_at=fetched_at,
    )
