import time
import uuid
from dataclasses import replace

from conftest import (
    Exchange,
    customer_token,
    dropping_connection,
    expect_code,
    order_body,
    stand_catalog_settings,
)

from order.adapter.outbound.catalog.client import CatalogClient


def new_order() -> str:
    return order_body(uuid.uuid4(), uuid.uuid4(), 1)


async def test_catalog_when_first_answer_hangs_retry_saves_the_order(start_stand, start_catalog):
    async def hanging_once(hit: int, exchange: Exchange) -> None:
        if hit == 1 and not await exchange.hold_for(2.5):
            return
        await exchange.answer_price("100.00")

    fake = await start_catalog(hanging_once)
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()

    res = await stand.post_order(customer_token(uuid.uuid4()), new_order())

    assert res.status_code == 201, res.text
    assert await stand.orders_in_db() == 1
    assert fake.hits == 2, f"к каталогу ушло {fake.hits} запросов, ожидали 2"


async def test_catalog_when_down_order_is_not_created_and_error_is_domain(start_stand, start_catalog):
    fake = await start_catalog(dropping_connection)
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()

    res = await stand.post_order(customer_token(uuid.uuid4()), new_order())

    assert res.status_code == 503, res.text
    expect_code(res, "SERVICE_DEGRADED")
    assert await stand.orders_in_db() == 0
    assert fake.hits == 2, f"к каталогу ушло {fake.hits} запросов, ожидали 2"


async def test_catalog_when_slow_is_cut_off_by_timeout(start_stand, start_catalog):
    async def slow(hit: int, exchange: Exchange) -> None:
        if await exchange.hold_for(4):
            await exchange.answer_price("100.00")

    fake = await start_catalog(slow)
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()

    started = time.monotonic()
    res = await stand.post_order(customer_token(uuid.uuid4()), new_order())
    spent = time.monotonic() - started

    assert res.status_code == 503, res.text
    expect_code(res, "SERVICE_DEGRADED")
    assert spent < 4, f"ждали ответа {spent:.2f} с: обе попытки должны упереться в таймаут раньше"
    assert await stand.orders_in_db() == 0


async def test_catalog_when_down_repeatedly_breaker_stops_calling_it(start_stand, start_catalog):
    fake = await start_catalog(dropping_connection)
    settings = replace(stand_catalog_settings(fake.url), breaker_failures=3)
    stand = await start_stand(CatalogClient(settings))
    await stand.clear_tables()

    for _ in range(3):
        res = await stand.post_order(customer_token(uuid.uuid4()), new_order())
        assert res.status_code == 503, res.text
    assert fake.hits == 6, f"к каталогу ушло {fake.hits} запросов, ожидали 6"

    res = await stand.post_order(customer_token(uuid.uuid4()), new_order())

    assert res.status_code == 503, res.text
    expect_code(res, "SERVICE_DEGRADED")
    assert fake.hits == 6, f"размыкатель открыт, а к каталогу ушло {fake.hits} запросов"
    assert await stand.orders_in_db() == 0
