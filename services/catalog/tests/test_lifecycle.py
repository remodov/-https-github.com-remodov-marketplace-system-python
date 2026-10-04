import uuid

from conftest import expect_code, seller_token
from sqlalchemy import text


async def test_service_starts_migrated_and_healthy(stand):
    live = await stand.call("GET", "/health/live")
    assert live.status_code == 204
    ready = await stand.call("GET", "/health/ready")
    assert ready.status_code == 204, ready.text
    async with stand.engine.connect() as connection:
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = {
            row[0]
            for row in await connection.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
        }
    assert revision == "0002"
    assert {"products", "catalog_audit_log"} <= tables


async def test_create_publish_hide_as_seller(stand):
    await stand.clear_tables()
    seller = uuid.uuid4()

    created = await stand.call(
        "POST",
        "/api/v1/products",
        seller_token(seller),
        '{"title": "Кофемолка", "description": "ручная", "price": 2490.5, "currency": "RUB"}',
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "DRAFT", body
    assert body["price"] == 2490.5
    product_id = body["id"]
    assert created.headers["Location"] == f"/api/v1/products/{product_id}"

    hidden = await stand.call("GET", f"/api/v1/products/{product_id}")
    assert hidden.status_code == 404, hidden.text
    expect_code(hidden, "PRODUCT_NOT_FOUND")

    own = await stand.call("GET", f"/api/v1/products/{product_id}", seller_token(seller))
    assert own.status_code == 200, own.text

    published = await stand.call("POST", f"/api/v1/products/{product_id}/publish", seller_token(seller))
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "PUBLISHED"

    public = await stand.call("GET", f"/api/v1/products/{product_id}")
    assert public.status_code == 200, public.text

    again = await stand.call("POST", f"/api/v1/products/{product_id}/publish", seller_token(seller))
    assert again.status_code == 409, again.text
    expect_code(again, "INVALID_STATE_TRANSITION")

    hide = await stand.call("POST", f"/api/v1/products/{product_id}/hide", seller_token(seller))
    assert hide.status_code == 200, hide.text

    mine = await stand.call("GET", "/api/v1/products/my?status=HIDDEN", seller_token(seller))
    assert mine.status_code == 200, mine.text
    assert mine.json()["total"] == 1
    assert await stand.audit_actions() == [], "действия продавца попали в журнал администратора"


async def test_create_product_validation(stand):
    await stand.clear_tables()
    seller = uuid.uuid4()

    res = await stand.call(
        "POST", "/api/v1/products", seller_token(seller), '{"title": "", "price": -1, "currency": "USD"}'
    )
    assert res.status_code == 400, res.text
    expect_code(res, "VALIDATION_ERROR")
    assert set(res.json()["errors"]) == {"title", "price"}

    res = await stand.call(
        "POST",
        "/api/v1/products",
        seller_token(seller),
        '{"title": "Кружка", "price": 100, "currency": "USD"}',
    )
    assert res.status_code == 400, res.text
    expect_code(res, "INVALID_CURRENCY")

    res = await stand.call(
        "POST",
        "/api/v1/products",
        f"customer.{uuid.uuid4()}",
        '{"title": "Кружка", "price": 100, "currency": "RUB"}',
    )
    assert res.status_code == 403, res.text
    expect_code(res, "ACCESS_DENIED")

    res = await stand.call("POST", "/api/v1/products", seller_token(seller), "{не json")
    assert res.status_code == 400, res.text
    expect_code(res, "MALFORMED_REQUEST")

    res = await stand.call(
        "POST",
        "/api/v1/products",
        "seller.not-a-uuid",
        '{"title": "Кружка", "price": 100, "currency": "RUB"}',
    )
    assert res.status_code == 401, res.text
    expect_code(res, "TOKEN_INVALID")
    assert res.headers["www-authenticate"] == 'Bearer error="invalid_token"'
