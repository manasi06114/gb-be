"""Router for dynamic data ingestion with custom field mappings from the frontend."""

from fastapi import APIRouter, Depends

from app.api.deps import get_ingest_service
from app.schemas.data_ingest import DynamicIngestRequest, DynamicIngestResponse

router = APIRouter(tags=["Data Ingestion"])


@router.post(
    "/data/fetch",
    summary="Fetch and ingest data dynamically with custom field mappings",
    description=(
        "Allows the frontend to specify API URLs or stream endpoints, date boundaries, "
        "and dynamic field names (e.g. for 'startTime', 'publishTime', 'generation') "
        "to fetch, clean, and hot-reload data into the backend."
    ),
    response_model=DynamicIngestResponse,
)
def fetch_and_ingest_dynamic_data(
    payload: DynamicIngestRequest,
    service=Depends(get_ingest_service),
) -> DynamicIngestResponse:
    """Fetch and process data dynamically according to frontend-specified field mappings."""
    return service.process_and_ingest(payload)
