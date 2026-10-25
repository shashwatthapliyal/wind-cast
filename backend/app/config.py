from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Wind Forecast Intelligence"
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    analysis_start: str = "2026-01-01"
    analysis_end: str = "2026-01-31"
    decision_cutoff_minutes_before_delivery: int = Field(default=24 * 60, ge=0, le=10080)
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_retries: int = Field(default=3, ge=0, le=5)
    cache_path: Path = Path("data/cache")
    refresh_cache: bool = False
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    app_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_prefix="WIND_", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
