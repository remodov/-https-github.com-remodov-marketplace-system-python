from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    http_port: int = 8182
    database_url: str = "postgresql+asyncpg://catalog:catalog@localhost:5470/catalog_starter"
    cache: Literal["memory", "redis"] = "redis"
    redis_url: str = "redis://localhost:6383"
    cache_ttl_seconds: int = 600
    service_name: str = "catalog-starter"
    otel_exporter_otlp_endpoint: str = ""
    trace_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
