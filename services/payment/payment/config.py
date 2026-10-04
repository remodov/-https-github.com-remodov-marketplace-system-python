from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    http_port: int = 8186
    database_url: str = "postgresql://catalog:catalog@localhost:5470/payments"
