"""E2: Metadata and methodology definitions endpoint."""

from fastapi import APIRouter, Depends

from app.api.deps import get_meta_service
from app.schemas.meta import MetaResponse
from app.services.meta_service import MetaService

router = APIRouter(tags=["Metadata"])


@router.get(
    "/meta",
    summary="API metadata and methodology",
    description=(
        "Returns delivery window configuration, available cutoff times, snapshot info, "
        "and human-readable definitions of all metrics and calculations."
    ),
    response_model=MetaResponse,
)
def get_meta(service: MetaService = Depends(get_meta_service)) -> MetaResponse:
    """Return API metadata, configuration and definitions."""
    return service.get_meta()
