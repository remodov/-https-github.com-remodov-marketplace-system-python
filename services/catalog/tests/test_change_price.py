import uuid

from conftest import admin_token, expect_code, seller_token


async def test_change_price_when_owner_returns_200_and_updates_database(stand):
    await stand.clear_tables()
    seller = uuid.uuid4()
    product_id = await stand.given_product(seller, "PUBLISHED", "89990.00")

    res = await stand.call(
        "PATCH", f"/api/v1/products/{product_id}/price", seller_token(seller), '{"price": 79990.00}'
    )

    assert res.status_code == 200, res.text
    assert res.json()["price"] == 79990.0
    assert await stand.price_in_db(product_id) == "79990.00"


async def test_change_price_when_not_positive_returns_400(stand):
    await stand.clear_tables()
    seller = uuid.uuid4()
    product_id = await stand.given_product(seller, "PUBLISHED", "89990.00")

    res = await stand.call(
        "PATCH", f"/api/v1/products/{product_id}/price", seller_token(seller), '{"price": 0}'
    )

    assert res.status_code == 400, res.text
    expect_code(res, "VALIDATION_ERROR")
    assert "price" in res.json()["errors"]
    assert await stand.price_in_db(product_id) == "89990.00", "цена в базе изменилась"


async def test_change_price_when_foreign_product_returns_404(stand):
    await stand.clear_tables()
    seller, other = uuid.uuid4(), uuid.uuid4()
    product_id = await stand.given_product(other, "PUBLISHED", "89990.00")

    res = await stand.call(
        "PATCH", f"/api/v1/products/{product_id}/price", seller_token(seller), '{"price": 79990.00}'
    )

    assert res.status_code == 404, res.text
    expect_code(res, "OWN_PRODUCT_REQUIRED")
    assert await stand.price_in_db(product_id) == "89990.00", "цена в базе изменилась"


async def test_change_price_when_unknown_product_returns_404(stand):
    await stand.clear_tables()

    res = await stand.call(
        "PATCH", f"/api/v1/products/{uuid.uuid4()}/price", seller_token(uuid.uuid4()), '{"price": 79990.00}'
    )

    assert res.status_code == 404, res.text
    expect_code(res, "PRODUCT_NOT_FOUND")


async def test_change_price_when_admin_returns_200_and_writes_audit(stand):
    await stand.clear_tables()
    admin, other = uuid.uuid4(), uuid.uuid4()
    product_id = await stand.given_product(other, "PUBLISHED", "89990.00")

    res = await stand.call(
        "PATCH", f"/api/v1/products/{product_id}/price", admin_token(admin), '{"price": 1000.00}'
    )

    assert res.status_code == 200, res.text
    assert res.json()["price"] == 1000.0
    assert "PRODUCT_PRICE_CHANGED" in await stand.audit_actions(), "в журнале нет PRODUCT_PRICE_CHANGED"


async def test_change_price_when_anonymous_is_rejected(stand):
    await stand.clear_tables()
    product_id = await stand.given_product(uuid.uuid4(), "PUBLISHED", "89990.00")

    res = await stand.call("PATCH", f"/api/v1/products/{product_id}/price", "", '{"price": 1.00}')

    assert res.status_code == 401, res.text
    expect_code(res, "TOKEN_MISSING")
    assert res.headers["www-authenticate"] == "Bearer"
    assert await stand.price_in_db(product_id) == "89990.00", "цена в базе изменилась"
