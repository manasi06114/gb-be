"""Application configuration using Pydantic Settings."""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server options
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "development"
    log_level: str = "INFO"

    # Security & CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # Static Frontend Serving
    serve_frontend: bool = False
    frontend_static_dir: str = "static"

    # Storage paths
    data_dir: Path = Path("data/snapshot")

    # Delivery Window & Cutoff
    delivery_start: date = date(2026, 1, 1)
    delivery_end: date = date(2026, 1, 31)
    default_cutoff: str = "09:00"
    cutoff_timezone: str = "Europe/London"
    available_cutoffs: list[str] = ["06:00", "09:00", "10:00", "12:00"]

    # Elexon API Ingestion
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    chunk_days: int = 7
    forecast_lookback_days: int = 10

    # Admin Operations
    admin_token: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
