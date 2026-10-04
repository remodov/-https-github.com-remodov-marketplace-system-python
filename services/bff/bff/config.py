from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    http_port: int = 8190
    redis_url: str = "redis://localhost:6383"
    order_url: str = "http://localhost:8181"
    catalog_url: str = "http://localhost:8180"
    payment_url: str = "http://localhost:8186"
    rate_limit_per_minute: int = 60
