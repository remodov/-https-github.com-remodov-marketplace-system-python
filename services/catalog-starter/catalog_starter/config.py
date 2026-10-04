from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    http_port: int = 8182
    database_url: str = "postgresql+asyncpg://catalog:catalog@localhost:5470/catalog_starter"
    cache: Literal["memory", "redis"] = "redis"
    redis_url: str = "redis://localhost:6383"
    cache_ttl_seconds: int = 600
