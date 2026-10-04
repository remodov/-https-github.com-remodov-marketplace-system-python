import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Self

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from order.adapter.outbound.catalog.client import CatalogSettings
from order.bootstrap.app import create_app
from order.bootstrap.config import Settings
from order.bootstrap.wire import Deps, catalog_settings
from order.core.order.port.out import CatalogGateway

NOW = datetime(2026, 4, 28, 11, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def test_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "TEST_DATABASE_URL", "postgresql+asyncpg://catalog:catalog@localhost:5470/orders_test"
        ),
        auth_mode="local",
    )


def stand_catalog_settings(base_url: str) -> CatalogSettings:
    return replace(catalog_settings(base_url), breaker_failures=100)


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
            await connection.execute(text("TRUNCATE order_items, orders"))

    async def orders_in_db(self) -> int:
        async with self.engine.connect() as connection:
            return int(await connection.scalar(text("SELECT count(*) FROM orders")) or 0)

    async def stored_order(self, order_id: str) -> tuple[str, str, str]:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT CAST(o.status AS text), CAST(o.total_amount AS text), CAST(i.unit_price AS text)
                        FROM orders o JOIN order_items i ON i.order_id = o.id
                        WHERE o.id = :id
                        """
                    ),
                    {"id": uuid.UUID(order_id)},
                )
            ).one()
        return (row[0], row[1], row[2])


StandFactory = Callable[[CatalogGateway], Awaitable[Stand]]


@pytest.fixture
async def start_stand():
    async with AsyncExitStack() as stack:

        async def start(gateway: CatalogGateway) -> Stand:
            app = create_app(test_settings(), Deps(clock=FixedClock(), catalog=gateway))
            await stack.enter_async_context(LifespanManager(app))
            client = await stack.enter_async_context(
                httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
            )
            return Stand(app, client)

        yield start


class Exchange:
    def __init__(self, path: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.path = path
        self.reader = reader
        self.writer = writer

    @property
    def product_id(self) -> str:
        return self.path.removeprefix("/api/v1/products/")

    async def hold_for(self, seconds: float) -> bool:
        client_gone = asyncio.ensure_future(self.reader.read(1))
        done, _ = await asyncio.wait({client_gone}, timeout=seconds)
        if client_gone in done:
            return False
        client_gone.cancel()
        return True

    async def answer_price(self, price: str) -> None:
        await self._answer(
            200,
            "application/json",
            f'{{"id":"{self.product_id}","title":"Кофемолка","price":{price},"currency":"RUB","status":"PUBLISHED"}}',
        )

    async def answer_not_found(self) -> None:
        await self._answer(404, "application/problem+json", '{"code":"PRODUCT_NOT_FOUND","status":404}')

    def drop_connection(self) -> None:
        self.writer.close()

    async def _answer(self, status: int, content_type: str, body: str) -> None:
        payload = body.encode()
        head = (
            f"HTTP/1.1 {status} {HTTPStatus(status).phrase}\r\n"
            f"Content-Type: {content_type}\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n"
        )
        self.writer.write(head.encode() + payload)
        await self.writer.drain()
        self.writer.close()


Script = Callable[[int, Exchange], Awaitable[None]]


class FakeCatalog:
    def __init__(self, script: Script) -> None:
        self.script = script
        self.hits = 0
        self.url = ""
        self.server: asyncio.Server | None = None
        self.handlers: set[asyncio.Task] = set()

    async def __aenter__(self) -> Self:
        self.server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        return self

    async def __aexit__(self, *exc_info) -> None:
        assert self.server is not None
        self.server.close()
        for handler in list(self.handlers):
            handler.cancel()
        await self.server.wait_closed()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        self.handlers.add(task)
        try:
            head = await reader.readuntil(b"\r\n\r\n")
        except asyncio.IncompleteReadError:
            writer.close()
            self.handlers.discard(task)
            return
        self.hits += 1
        path = head.split(b" ", 2)[1].decode()
        try:
            await self.script(self.hits, Exchange(path, reader, writer))
        finally:
            writer.close()
            self.handlers.discard(task)


@pytest.fixture
async def start_catalog():
    async with AsyncExitStack() as stack:

        async def start(script: Script) -> FakeCatalog:
            return await stack.enter_async_context(FakeCatalog(script))

        yield start


def answering(price: str) -> Script:
    async def script(hit: int, exchange: Exchange) -> None:
        await exchange.answer_price(price)

    return script


async def answering_not_found(hit: int, exchange: Exchange) -> None:
    await exchange.answer_not_found()


async def dropping_connection(hit: int, exchange: Exchange) -> None:
    exchange.drop_connection()


def customer_token(customer: uuid.UUID) -> str:
    return f"customer.{customer}"


def admin_token(admin: uuid.UUID) -> str:
    return f"admin.{admin}"


def order_body(product_id: uuid.UUID, seller_id: uuid.UUID, quantity: int) -> str:
    return (
        f'{{"items":[{{"productId":"{product_id}","sellerId":"{seller_id}","quantity":{quantity}}}],'
        '"shippingAddress":{"country":"RU","city":"Москва","street":"Тверская, 1","postalCode":"125009"}}'
    )


def expect_code(response: httpx.Response, code: str) -> None:
    assert response.json().get("code") == code, response.text
