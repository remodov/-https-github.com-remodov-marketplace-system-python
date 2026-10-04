from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    http_port: int = 8185
    database_url: str = "postgresql+asyncpg://catalog:catalog@localhost:5470/notifications"
    kafka_brokers: str = "localhost:9097"
    kafka_group: str = "notification"
    kafka_topic: str = "marketplace.orders.v1"
    admin_token: str = "admin"
