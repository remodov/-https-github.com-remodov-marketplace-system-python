import uuid

from conftest import (
    admin_token,
    answering,
    answering_not_found,
    customer_token,
    expect_code,
    order_body,
    stand_catalog_settings,
)

from order.adapter.outbound.catalog.client import CatalogClient


async def test_create_order_when_catalog_answers_stores_order_with_catalog_prices(start_stand, start_catalog):
    fake = await start_catalog(answering("2490.50"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    customer, seller, product = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    res = await stand.call("POST", "/api/v1/orders", customer_token(customer), order_body(product, seller, 2))

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "DRAFT" and body["total"] == 4981.0, res.text
    assert res.headers["location"] == f"/api/v1/orders/{body['id']}"
    assert await stand.stored_order(body["id"]) == ("DRAFT", "4981.00", "2490.50")
    assert fake.hits == 1


async def test_create_order_when_product_unknown_returns_404_without_retry(start_stand, start_catalog):
    fake = await start_catalog(answering_not_found)
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()

    res = await stand.call(
        "POST", "/api/v1/orders", customer_token(uuid.uuid4()), order_body(uuid.uuid4(), uuid.uuid4(), 1)
    )

    assert res.status_code == 404, res.text
    expect_code(res, "PRODUCT_NOT_FOUND")
    assert await stand.orders_in_db() == 0
    assert fake.hits == 1


async def test_create_order_when_two_sellers_is_rejected_before_catalog(start_stand, start_catalog):
    fake = await start_catalog(answering("100.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    body = (
        f'{{"items":[{{"productId":"{uuid.uuid4()}","sellerId":"{uuid.uuid4()}","quantity":1}},'
        f'{{"productId":"{uuid.uuid4()}","sellerId":"{uuid.uuid4()}","quantity":1}}],'
        '"shippingAddress":{"country":"RU","city":"Москва","street":"Тверская, 1","postalCode":"125009"}}'
    )

    res = await stand.call("POST", "/api/v1/orders", customer_token(uuid.uuid4()), body)

    assert res.status_code == 400, res.text
    expect_code(res, "MULTI_SELLER_NOT_SUPPORTED")
    assert await stand.orders_in_db() == 0
    assert fake.hits == 0


async def test_create_order_when_anonymous_is_rejected(start_stand, start_catalog):
    fake = await start_catalog(answering("100.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))

    res = await stand.call("POST", "/api/v1/orders", "", order_body(uuid.uuid4(), uuid.uuid4(), 1))

    assert res.status_code == 401, res.text
    expect_code(res, "TOKEN_MISSING")
    assert fake.hits == 0


async def test_get_order_when_foreign_customer_returns_404_but_admin_sees(start_stand, start_catalog):
    fake = await start_catalog(answering("100.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    owner = uuid.uuid4()
    created = await stand.call(
        "POST", "/api/v1/orders", customer_token(owner), order_body(uuid.uuid4(), uuid.uuid4(), 1)
    )
    assert created.status_code == 201, created.text
    path = f"/api/v1/orders/{created.json()['id']}"

    own = await stand.call("GET", path, customer_token(owner))
    foreign = await stand.call("GET", path, customer_token(uuid.uuid4()))
    admin = await stand.call("GET", path, admin_token(uuid.uuid4()))

    assert own.status_code == 200, own.text
    assert own.json()["total"] == 100.0
    assert foreign.status_code == 404, foreign.text
    expect_code(foreign, "ORDER_NOT_FOUND")
    assert admin.status_code == 200, admin.text
