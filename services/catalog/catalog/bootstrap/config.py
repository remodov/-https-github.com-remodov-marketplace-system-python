from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    http_port: int = 8180
    database_url: str = "postgresql+asyncpg://catalog:catalog@localhost:5470/catalog"
    auth_mode: Literal["local", "jwt"] = "local"
    jwks_url: str = "http://localhost:8480/realms/marketplace/protocol/openid-connect/certs"
    jwt_issuer: str = "http://localhost:8480/realms/marketplace"
    jwt_audience: str = ""
