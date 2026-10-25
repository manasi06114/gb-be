"""FastAPI application factory, lifespan, middleware, and router registration."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import deps
from app.api.routers import (
    actuals,
    admin,
    comparison,
    data_ingest,
    forecasts,
    health,
    meta,
    metrics,
)
from app.core.config import get_settings
from app.core.errors import setup_exception_handlers
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.repositories.data_repository import DataRepository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: load snapshot on startup, free resources on shutdown."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("Starting up — loading snapshot data...")
    repo = DataRepository(data_dir=settings.data_dir)
    try:
        repo.load()
        logger.info(
            f"Snapshot loaded: {repo.get_snapshot_meta().get('actual_rows')} actuals, "
            f"{repo.get_snapshot_meta().get('forecast_rows')} forecasts."
        )
    except Exception as exc:
        logger.error(f"Failed to load snapshot: {exc}")
        # App still starts; /health will report degraded state

    # Register the loaded repository into the DI system
    deps.set_repository(repo)

    yield

    logger.info("Shutting down application.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Renewable Energy Forecast Analysis API",
        description=(
            "API serving UK national wind generation actuals, decision-time forecasts "
            "at configurable cutoffs, and accuracy analytics (MAE, RMSE, bias) over "
            "January 2026. Built for a utility's day-ahead procurement team.\n\n"
            "**Key concept:** The *decision cutoff* is the latest moment on D-1 at which "
            "forecasts are visible to the buyer. All forecast selection respects this cutoff."
        ),
        version="1.0.0",
        openapi_tags=[
            {"name": "Health", "description": "Liveness and readiness probes"},
            {"name": "Metadata", "description": "API configuration and methodology"},
            {"name": "Data Series", "description": "Raw FUELHH actuals and WINDFOR forecasts"},
            {"name": "Forecasts", "description": "Forecast series with latest-at-cutoff selection"},
            {"name": "Comparison", "description": "Actual vs forecast paired comparisons"},
            {"name": "Metrics", "description": "Accuracy metrics, aggregations, and distributions"},
            {"name": "Admin", "description": "Administrative operations"},
        ],
        lifespan=lifespan,
    )

    # Exception handlers for standard error body
    setup_exception_handlers(app)

    # Request-ID and latency logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # CORS: Allow all origins and all Vercel deployments (*.vercel.app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins if isinstance(settings.cors_origins, list) else ["*"],
        allow_origin_regex=r"https?://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers under /api prefix
    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(meta.router, prefix=api_prefix)
    app.include_router(actuals.router, prefix=api_prefix)
    app.include_router(forecasts.router, prefix=api_prefix)
    app.include_router(comparison.router, prefix=api_prefix)
    app.include_router(metrics.router, prefix=api_prefix)
    app.include_router(data_ingest.router, prefix=api_prefix)
    app.include_router(admin.router, prefix=api_prefix)

    # Optionally serve pre-built frontend as static files
    if settings.serve_frontend:
        static_dir = Path(settings.frontend_static_dir)
        if static_dir.exists():
            app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")
            logger.info(f"Serving frontend from {static_dir}")
        else:
            logger.warning(f"SERVE_FRONTEND=true but static dir not found: {static_dir}")

    return app


app = create_app()
