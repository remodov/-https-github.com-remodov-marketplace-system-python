from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    http_port: int = 8181
    database_url: str = "postgresql+asyncpg://catalog:catalog@localhost:5470/orders"
    catalog_url: str = "http://localhost:8180"
    payment_url: str = "http://localhost:8186"
    kafka_brokers: str = "localhost:9097"
    kafka_topic: str = "marketplace.orders.v1"
    kafka_group: str = "order"
    payments_topic: str = "marketplace.payments.v1"
    event_publisher: Literal["kafka", "log"] = "kafka"
    outbox_relay_enabled: bool = True
    outbox_relay_interval_seconds: float = 1.0
    payment_consumer_enabled: bool = True
    expire_unpaid_enabled: bool = True
    expire_unpaid_after_seconds: float = 900.0
    expire_interval_seconds: float = 60.0
    auth_mode: Literal["local", "jwt"] = "local"
    jwks_url: str = "http://localhost:8480/realms/marketplace/protocol/openid-connect/certs"
    jwt_issuer: str = "http://localhost:8480/realms/marketplace"
    jwt_audience: str = ""
