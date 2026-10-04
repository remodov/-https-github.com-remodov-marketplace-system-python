import os
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from asgi_lifespan import LifespanManager

from payment.app import create_app
from payment.config import Settings

NOW = datetime(2026, 4, 28, 11, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def test_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "TEST_DATABASE_URL", "postgresql://catalog:catalog@localhost:5470/payments_test"
        )
    )


class Stand:
    def __init__(self, app, client: httpx.AsyncClient) -> None:
        self.app = app
        self.client = client

    async def call(self, method: str, path: str, body: str = "") -> httpx.Response:
        headers = {"Content-Type": "application/json"} if body else {}
        return await self.client.request(
            method, path, content=body.encode() if body else None, headers=headers
        )

    async def authorize(self, order_id: uuid.UUID) -> str:
        body = f'{{"orderId":"{order_id}","amount":1990.00,"currency":"RUB"}}'
        res = await self.call("POST", "/api/v1/payments", body)
        assert res.status_code == 201, res.text
        return res.json()["id"]

    async def clean(self) -> None:
        await self.app.state.database.started().execute("DELETE FROM payments")

    async def count_payments(self) -> int:
        return int(await self.app.state.database.started().fetchval("SELECT count(*) FROM payments"))


@pytest.fixture(scope="session")
async def app():
    app = create_app(test_settings(), FixedClock())
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def stand(app) -> Stand:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        stand = Stand(app, client)
        await stand.clean()
        yield stand


def expect(res: httpx.Response, status: int) -> dict:
    assert res.status_code == status, f"ожидали {status}, получили {res.status_code}: {res.text}"
    return res.json()
