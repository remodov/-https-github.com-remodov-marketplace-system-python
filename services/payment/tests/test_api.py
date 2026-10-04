import uuid

from conftest import expect


async def test_authorize_creates_payment_in_authorized(stand):
    order_id = uuid.uuid4()
    payment_id = await stand.authorize(order_id)

    body = expect(await stand.call("GET", f"/api/v1/payments/{payment_id}"), 200)

    assert body["status"] == "AUTHORIZED", body
    assert body["orderId"] == str(order_id) and body["amount"] == 1990.0, body


async def test_authorize_is_idempotent_per_order(stand):
    order_id = uuid.uuid4()

    first = await stand.authorize(order_id)
    second = await stand.authorize(order_id)

    assert first == second, f"повторная авторизация обязана вернуть прежний платёж: {first} и {second}"
    assert await stand.count_payments() == 1, "повторная авторизация не должна рождать второй платёж"


async def test_capture_moves_to_captured(stand):
    payment_id = await stand.authorize(uuid.uuid4())

    body = expect(await stand.call("POST", f"/api/v1/payments/{payment_id}/capture"), 200)

    assert body["status"] == "CAPTURED", body


async def test_refund_after_capture_is_allowed(stand):
    payment_id = await stand.authorize(uuid.uuid4())
    expect(await stand.call("POST", f"/api/v1/payments/{payment_id}/capture"), 200)

    body = expect(await stand.call("POST", f"/api/v1/payments/{payment_id}/refund"), 200)

    assert body["status"] == "REFUNDED", body


async def test_refund_repeat_is_safe(stand):
    payment_id = await stand.authorize(uuid.uuid4())
    first = expect(await stand.call("POST", f"/api/v1/payments/{payment_id}/refund"), 200)

    second = expect(await stand.call("POST", f"/api/v1/payments/{payment_id}/refund"), 200)

    assert second["status"] == "REFUNDED" and second["updatedAt"] == first["updatedAt"], (
        f"повторный возврат это тот же ответ, а не второй возврат: {first} и {second}"
    )


async def test_capture_after_refund_is_rejected(stand):
    payment_id = await stand.authorize(uuid.uuid4())
    expect(await stand.call("POST", f"/api/v1/payments/{payment_id}/refund"), 200)

    rejected = expect(await stand.call("POST", f"/api/v1/payments/{payment_id}/capture"), 409)

    assert rejected["code"] == "INVALID_PAYMENT_TRANSITION", rejected
    current = expect(await stand.call("GET", f"/api/v1/payments/{payment_id}"), 200)
    assert current["status"] == "REFUNDED", f"запрещённый переход не должен портить данные: {current}"


async def test_payment_unknown_is_not_found(stand):
    body = expect(await stand.call("GET", f"/api/v1/payments/{uuid.uuid4()}"), 404)

    assert body["code"] == "PAYMENT_NOT_FOUND", body


async def test_authorize_zero_amount_is_rejected(stand):
    body = f'{{"orderId":"{uuid.uuid4()}","amount":0,"currency":"RUB"}}'

    rejected = expect(await stand.call("POST", "/api/v1/payments", body), 400)

    assert rejected["code"] == "VALIDATION_ERROR", rejected
