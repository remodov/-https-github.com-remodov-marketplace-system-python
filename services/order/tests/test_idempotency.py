import asyncio
import uuid

from conftest import answering, customer_token, expect_code, order_body, stand_catalog_settings

from order.adapter.outbound.catalog.client import CatalogClient


async def test_idempotency_same_key_same_body_returns_same_order(start_stand, start_catalog):
    fake = await start_catalog(answering("200.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    customer, key, body = uuid.uuid4(), str(uuid.uuid4()), order_body(uuid.uuid4(), uuid.uuid4(), 1)

    first = await stand.post_order(customer_token(customer), body, key)
    second = await stand.post_order(customer_token(customer), body, key)

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"], f"повтор должен вернуть тот же заказ: {second.text}"
    assert await stand.orders_in_db() == 1
    assert fake.hits == 1, f"к каталогу ушло {fake.hits} запросов, ожидали 1"


async def test_idempotency_same_key_different_body_is_conflict(start_stand, start_catalog):
    fake = await start_catalog(answering("200.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    customer, key, product, seller = uuid.uuid4(), str(uuid.uuid4()), uuid.uuid4(), uuid.uuid4()

    first = await stand.post_order(customer_token(customer), order_body(product, seller, 1), key)
    assert first.status_code == 201, first.text
    res = await stand.post_order(customer_token(customer), order_body(product, seller, 5), key)

    assert res.status_code == 409, res.text
    expect_code(res, "IDEMPOTENCY_KEY_CONFLICT")
    assert await stand.orders_in_db() == 1


async def test_idempotency_different_keys_create_different_orders(start_stand, start_catalog):
    fake = await start_catalog(answering("200.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    customer, body = uuid.uuid4(), order_body(uuid.uuid4(), uuid.uuid4(), 1)

    first = await stand.post_order(customer_token(customer), body)
    second = await stand.post_order(customer_token(customer), body)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert await stand.orders_in_db() == 2


async def test_idempotency_same_key_at_once_creates_one_order(start_stand, start_catalog):
    fake = await start_catalog(answering("200.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    customer, key, body = uuid.uuid4(), str(uuid.uuid4()), order_body(uuid.uuid4(), uuid.uuid4(), 1)

    responses = await asyncio.gather(
        *(stand.post_order(customer_token(customer), body, key) for _ in range(8))
    )

    for res in responses:
        assert res.status_code in (200, 201), res.text
    ids = {res.json()["id"] for res in responses}
    assert len(ids) == 1, f"клиенты получили разные заказы: {ids}"
    assert await stand.orders_in_db() == 1


async def test_create_order_without_idempotency_key_is_rejected(start_stand, start_catalog):
    fake = await start_catalog(answering("200.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))

    res = await stand.call(
        "POST", "/api/v1/orders", customer_token(uuid.uuid4()), order_body(uuid.uuid4(), uuid.uuid4(), 1)
    )

    assert res.status_code == 400, res.text
    expect_code(res, "VALIDATION_ERROR")
    assert res.json()["errors"] == {"Idempotency-Key": "обязательное поле"}, res.text
    assert fake.hits == 0
