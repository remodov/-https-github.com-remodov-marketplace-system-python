import asyncio
import json
import os
import uuid
from collections.abc import Callable
from contextlib import AsyncExitStack
from http import HTTPStatus

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from redis.exceptions import RedisError

from bff.app import create_app
from bff.config import Settings

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6383/1")

Answer = Callable[[], tuple[int, str]]


class StubService:
    def __init__(self, answer: Answer) -> None:
        self.answer = answer
        self.calls = 0
        self.authorizations: list[str] = []
        self.url = ""
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"

    async def close(self) -> None:
        if self.server is None:
            return
        self.server.close()
        await self.server.wait_closed()
        self.server = None

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
        except asyncio.IncompleteReadError:
            writer.close()
            return
        self.calls += 1
        self.authorizations.append(header_of(head, "authorization"))
        status, body = self.answer()
        payload = body.encode()
        response_head = (
            f"HTTP/1.1 {status} {HTTPStatus(status).phrase}\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n"
        )
        writer.write(response_head.encode() + payload)
        await writer.drain()
        writer.close()


def header_of(head: bytes, name: str) -> str:
    for line in head.decode().split("\r\n")[1:]:
        key, _, value = line.partition(":")
        if key.strip().lower() == name:
            return value.strip()
    return ""


class Stubs:
    def __init__(self, payment_status: int) -> None:
        self.order_id = uuid.uuid4()
        self.product_id = uuid.uuid4()
        self.payment_id = uuid.uuid4()
        self.payment_status = payment_status
        self.order = StubService(self.order_answer)
        self.catalog = StubService(self.catalog_answer)
        self.payment = StubService(self.payment_answer)

    def order_answer(self) -> tuple[int, str]:
        order = {
            "id": str(self.order_id),
            "status": "PAID",
            "total": 3980.0,
            "paymentId": str(self.payment_id),
            "items": [{"productId": str(self.product_id), "quantity": 2}],
        }
        return 200, json.dumps(order)

    def catalog_answer(self) -> tuple[int, str]:
        card = {"id": str(self.product_id), "title": "Беспроводная мышь", "price": 1990.0, "currency": "RUB"}
        return 200, json.dumps(card, ensure_ascii=False)

    def payment_answer(self) -> tuple[int, str]:
        if self.payment_status != 200:
            return self.payment_status, '{"code":"PAYMENT_NOT_FOUND","status":404}'
        return 200, json.dumps({"id": str(self.payment_id), "status": "CAPTURED"})

    async def start(self) -> None:
        await asyncio.gather(self.order.start(), self.catalog.start(), self.payment.start())

    async def close(self) -> None:
        await asyncio.gather(self.order.close(), self.catalog.close(), self.payment.close())


class Stand:
    def __init__(self, stubs: Stubs, client: httpx.AsyncClient) -> None:
        self.stubs = stubs
        self.client = client
        self.authorization = f"Bearer customer.{uuid.uuid4()}"

    async def screen(self, client_id: str | None = None) -> httpx.Response:
        return await self.client.get(
            f"/api/v1/screens/order/{self.stubs.order_id}",
            headers={"X-Client-Id": client_id or str(uuid.uuid4()), "Authorization": self.authorization},
        )


@pytest.fixture(scope="session")
async def redis_ready() -> None:
    redis = Redis.from_url(TEST_REDIS_URL)
    try:
        await redis.ping()
    except RedisError as error:
        pytest.fail(
            f"Redis недоступен ({error}): подними стенд командой "
            "docker compose -f ../../infra/compose.yaml up -d redis"
        )
    await redis.flushdb()
    await redis.aclose()


@pytest.fixture
async def start_stand(redis_ready):
    async with AsyncExitStack() as stack:

        async def start(per_minute: int = 60, payment_status: int = 200) -> Stand:
            stubs = Stubs(payment_status)
            await stubs.start()
            stack.push_async_callback(stubs.close)
            settings = Settings(
                redis_url=TEST_REDIS_URL,
                order_url=stubs.order.url,
                catalog_url=stubs.catalog.url,
                payment_url=stubs.payment.url,
                rate_limit_per_minute=per_minute,
            )
            app = create_app(settings)
            await stack.enter_async_context(LifespanManager(app))
            client = await stack.enter_async_context(
                httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
            )
            return Stand(stubs, client)

        yield start


def expect(res: httpx.Response, status: int) -> dict:
    assert res.status_code == status, f"ожидали {status}, получили {res.status_code}: {res.text}"
    return res.json()
