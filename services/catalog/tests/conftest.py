import os
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from catalog.bootstrap.app import create_app
from catalog.bootstrap.config import Settings
from catalog.bootstrap.wire import Deps

NOW = datetime(2026, 4, 28, 11, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def test_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "TEST_DATABASE_URL", "postgresql+asyncpg://catalog:catalog@localhost:5470/catalog_test"
        ),
        auth_mode="local",
    )


class Stand:
    def __init__(self, app, client: httpx.AsyncClient) -> None:
        self.app = app
        self.client = client

    @property
    def engine(self) -> AsyncEngine:
        return self.app.state.engine

    async def call(self, method: str, path: str, token: str = "", body: str = "") -> httpx.Response:
        headers = {}
        if body:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return await self.client.request(
            method, path, content=body.encode() if body else None, headers=headers
        )

    async def clear_tables(self) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(text("TRUNCATE catalog_audit_log, products"))

    async def given_product(self, seller: uuid.UUID, status: str, price: str) -> uuid.UUID:
        product_id = uuid.uuid4()
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO products (id, title, description, price, currency, seller_id, status, created_at, updated_at)
                    VALUES (:id, 'Ноутбук', 'Тестовый товар', CAST(:price AS numeric), 'RUB', :seller,
                            CAST(:status AS product_status), :now, :now)
                    """
                ),
                {"id": product_id, "price": price, "seller": seller, "status": status, "now": NOW},
            )
        return product_id

    async def price_in_db(self, product_id: uuid.UUID) -> str:
        async with self.engine.connect() as connection:
            found = await connection.scalar(
                text("SELECT CAST(price AS text) FROM products WHERE id = :id"), {"id": product_id}
            )
        return str(found)

    async def audit_actions(self) -> list[str]:
        async with self.engine.connect() as connection:
            rows = await connection.execute(text("SELECT action FROM catalog_audit_log ORDER BY occurred_at"))
            return [row[0] for row in rows]


@pytest.fixture(scope="session")
async def stand():
    app = create_app(test_settings(), Deps(clock=FixedClock()))
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield Stand(app, client)


def seller_token(seller: uuid.UUID) -> str:
    return f"seller.{seller}"


def admin_token(admin: uuid.UUID) -> str:
    return f"admin.{admin}"


def expect_code(response: httpx.Response, code: str) -> None:
    assert response.json().get("code") == code, response.text
