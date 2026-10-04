import uuid
from datetime import datetime, timedelta

from conftest import NOW, expect_code, seller_token

JPEG_UPLOAD = '{"contentType": "image/jpeg"}'


def upload_url_path(product_id: uuid.UUID) -> str:
    return f"/api/v1/products/{product_id}/image-upload-url"


async def test_image_upload_owner_gets_presigned_url(stand):
    await stand.clear_tables()
    seller = uuid.uuid4()
    product_id = await stand.given_product(seller, "PUBLISHED", "1000.00")

    res = await stand.call("POST", upload_url_path(product_id), seller_token(seller), JPEG_UPLOAD)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["key"].startswith(f"products/{product_id}/"), (
        f"ключ должен говорить, чей это файл: {body['key']}"
    )
    for part in (
        "marketplace-images",
        "X-Amz-Signature",
        "X-Amz-Expires",
        "X-Amz-SignedHeaders=content-type",
    ):
        assert part in body["url"], f"ссылка должна быть временной и подписанной, нет {part}: {body['url']}"
    ttl = timedelta(seconds=stand.app.state.settings.image_upload_url_ttl_seconds)
    assert datetime.fromisoformat(body["expiresAt"]) == NOW + ttl, body


async def test_image_upload_foreign_product_looks_missing(stand):
    await stand.clear_tables()
    owner = uuid.uuid4()
    product_id = await stand.given_product(owner, "PUBLISHED", "1000.00")

    res = await stand.call("POST", upload_url_path(product_id), seller_token(uuid.uuid4()), JPEG_UPLOAD)

    assert res.status_code == 404, res.text
    expect_code(res, "OWN_PRODUCT_REQUIRED")


async def test_image_upload_unknown_product_is_not_found(stand):
    await stand.clear_tables()

    res = await stand.call("POST", upload_url_path(uuid.uuid4()), seller_token(uuid.uuid4()), JPEG_UPLOAD)

    assert res.status_code == 404, res.text
    expect_code(res, "PRODUCT_NOT_FOUND")


async def test_image_upload_anonymous_is_rejected(stand):
    await stand.clear_tables()
    product_id = await stand.given_product(uuid.uuid4(), "PUBLISHED", "1000.00")

    res = await stand.call("POST", upload_url_path(product_id), "", JPEG_UPLOAD)

    assert res.status_code == 401, res.text
    expect_code(res, "TOKEN_MISSING")


async def test_image_upload_rejects_non_image_type(stand):
    await stand.clear_tables()
    seller = uuid.uuid4()
    product_id = await stand.given_product(seller, "PUBLISHED", "1000.00")

    res = await stand.call(
        "POST", upload_url_path(product_id), seller_token(seller), '{"contentType": "application/zip"}'
    )

    assert res.status_code == 400, res.text
    expect_code(res, "VALIDATION_ERROR")
    assert "contentType" in res.json()["errors"], res.text
