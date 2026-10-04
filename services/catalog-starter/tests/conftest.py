import os
import uuid
from decimal import Decimal

import httpx
import pytest
from asgi_lifespan import LifespanManager

from catalog_starter.config import Settings
from catalog_starter.main import create_app
from catalog_starter.product.model import Product
from catalog_starter.product.service import ProductService


def test_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "TEST_DATABASE_URL", "postgresql+asyncpg://catalog:catalog@localhost:5470/catalog_starter_test"
        ),
        cache="memory",
    )


class Stand:
    def __init__(self, app, client: httpx.AsyncClient) -> None:
        self.app = app
        self.client = client

    @property
    def service(self) -> ProductService:
        return self.app.state.products

    async def must_create(self, title: str, price: str, stock: int) -> Product:
        return await self.service.create(title, Decimal(price), stock)


@pytest.fixture(scope="session")
async def stand():
    app = create_app(test_settings())
    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield Stand(app, client)


def unique(title: str) -> str:
    return f"{title} {uuid.uuid4().hex[:8]}"
