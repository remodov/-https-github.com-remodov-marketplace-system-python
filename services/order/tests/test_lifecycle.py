import json
import uuid
from datetime import timedelta

import pytest
from aiokafka import ConsumerRecord
from conftest import (
    NOW,
    AdjustableClock,
    FakePayment,
    Stand,
    admin_token,
    answering,
    customer_token,
    expect_code,
    order_body,
    seller_token,
    stand_catalog_settings,
)
from orders_v1 import OrderCancelledPayload
from payments_v1 import (
    EVENT_PAYMENT_COMPLETED,
    HEADER_EVENT_ID,
    HEADER_EVENT_TYPE,
    TOPIC,
    PaymentCompletedPayload,
)

from order.adapter.inbound.kafka.payment_consumer import PaymentEventHandler
from order.adapter.outbound.catalog.client import CatalogClient
from order.adapter.outbound.payment.client import PaymentClient
from order.bootstrap.wire import payment_settings


class Scenario:
    def __init__(
        self,
        stand: Stand,
        payment: FakePayment,
        clock: AdjustableClock,
        customer: uuid.UUID,
        seller: uuid.UUID,
        order_id: str,
    ):
        self.stand = stand
        self.payment = payment
        self.clock = clock
        self.customer = customer
        self.seller = seller
        self.order_id = order_id

    def path(self, action: str = "") -> str:
        return f"/api/v1/orders/{self.order_id}{action}"

    async def confirm(self) -> "Scenario":
        res = await self.stand.post_json(self.path("/confirm"), customer_token(self.customer))
        assert res.status_code == 200, res.text
        return self

    async def pay(self, payment_id: uuid.UUID) -> "Scenario":
        res = await self.stand.post_json(self.path("/pay"), admin_token(uuid.uuid4()), pay_body(payment_id))
        assert res.status_code == 200, res.text
        return self

    async def current(self) -> dict:
        res = await self.stand.call("GET", self.path(), customer_token(self.customer))
        assert res.status_code == 200, res.text
        return res.json()


def pay_body(payment_id: uuid.UUID) -> str:
    return f'{{"paymentId":"{payment_id}"}}'


@pytest.fixture
async def given_order(start_stand, start_catalog, start_payment):
    async def given(price: str) -> Scenario:
        fake = await start_catalog(answering(price))
        payment = await start_payment()
        clock = AdjustableClock(NOW)
        stand = await start_stand(
            CatalogClient(stand_catalog_settings(fake.url)),
            payment=PaymentClient(payment_settings(payment.url)),
            clock=clock,
        )
        await stand.clear_tables()
        customer, seller = uuid.uuid4(), uuid.uuid4()
        created = await stand.post_order(customer_token(customer), order_body(uuid.uuid4(), seller, 1))
        assert created.status_code == 201, created.text
        return Scenario(stand, payment, clock, customer, seller, created.json()["id"])

    yield given


async def test_lifecycle_full_path_from_draft_to_delivered(given_order):
    s = await given_order("200.00")
    payment_id = uuid.uuid4()

    confirmed = (await s.stand.post_json(s.path("/confirm"), customer_token(s.customer))).json()
    paid = (await s.stand.post_json(s.path("/pay"), admin_token(uuid.uuid4()), pay_body(payment_id))).json()
    shipped = (
        await s.stand.post_json(s.path("/ship"), seller_token(s.seller), '{"trackingNumber":"TRACK-12345"}')
    ).json()
    delivered = (await s.stand.post_json(s.path("/deliver"), customer_token(s.customer))).json()

    statuses = [confirmed.get("status"), paid.get("status"), shipped.get("status"), delivered.get("status")]
    assert statuses == ["PENDING_PAYMENT", "PAID", "SHIPPED", "DELIVERED"], f"статусы по пути: {statuses}"
    assert paid["paymentId"] == str(payment_id) and paid["paidAt"] is not None, paid
    assert shipped["shippedAt"] is not None and delivered["deliveredAt"] is not None, delivered
    types = await s.stand.event_types()
    for expected in ["OrderCreated", "OrderConfirmed", "OrderPaid", "OrderShipped", "OrderDelivered"]:
        assert expected in types, f"в outbox нет {expected}: {types}"


async def test_lifecycle_pay_is_idempotent_for_the_same_payment(given_order):
    s = await (await given_order("200.00")).confirm()
    payment_id = uuid.uuid4()

    await (await s.pay(payment_id)).pay(payment_id)

    assert await s.stand.count_events("OrderPaid") == 1, (
        f"повторный вебхук с тем же платежом не должен рождать второе событие: {await s.stand.event_types()}"
    )


async def test_lifecycle_pay_from_draft_is_invalid_state(given_order):
    s = await given_order("200.00")

    res = await s.stand.post_json(s.path("/pay"), admin_token(uuid.uuid4()), pay_body(uuid.uuid4()))

    assert res.status_code == 409, res.text
    expect_code(res, "ORDER_INVALID_STATE")


async def test_lifecycle_confirm_below_minimum_is_rejected(given_order):
    s = await given_order("50.00")

    res = await s.stand.post_json(s.path("/confirm"), customer_token(s.customer))

    assert res.status_code == 400, res.text
    expect_code(res, "ORDER_BELOW_MINIMUM")
    assert await s.stand.count_events("OrderConfirmed") == 0, (
        "отклонённое подтверждение не должно рождать событие"
    )


async def test_lifecycle_foreign_seller_cannot_ship_and_deliver_needs_shipped(given_order):
    s = await (await (await given_order("200.00")).confirm()).pay(uuid.uuid4())

    foreign = await s.stand.post_json(
        s.path("/ship"), seller_token(uuid.uuid4()), '{"trackingNumber":"TRACK-99"}'
    )
    early = await s.stand.post_json(s.path("/deliver"), customer_token(s.customer))

    assert foreign.status_code == 404, foreign.text
    expect_code(foreign, "ORDER_NOT_FOUND")
    assert early.status_code == 409, early.text
    expect_code(early, "ORDER_INVALID_STATE")


async def test_lifecycle_cancel_paid_order_refunds_through_payment(given_order):
    payment_id = uuid.uuid4()
    s = await (await (await given_order("200.00")).confirm()).pay(payment_id)

    res = await s.stand.post_json(
        s.path("/cancel"), customer_token(s.customer), '{"reasonCode":"changed_mind","comment":"передумал"}'
    )

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED", res.text
    requests = s.payment.requests
    assert len(requests) == 1, f"в платежи должен уйти ровно один возврат: {requests}"
    assert requests[0].path == f"/api/v1/payments/{payment_id}/refund", requests[0]
    assert requests[0].headers.get("idempotency-key") == f"refund-{s.order_id}", requests[0]
    cancelled = [row for row in await s.stand.outbox_rows() if row.event_type == "OrderCancelled"]
    assert len(cancelled) == 1, await s.stand.event_types()
    payload = OrderCancelledPayload.model_validate_json(cancelled[0].payload)
    assert payload.previous_status == "PAID" and payload.reason == "CHANGED_MIND", cancelled[0].payload
    assert payload.refund_id == payment_id, f"OrderCancelled должен нести возврат: {cancelled[0].payload}"


async def test_lifecycle_cancel_paid_order_when_payment_is_down_keeps_it_paid(given_order):
    s = await (await (await given_order("200.00")).confirm()).pay(uuid.uuid4())
    s.payment.go_down()

    res = await s.stand.post_json(
        s.path("/cancel"), customer_token(s.customer), '{"reasonCode":"changed_mind"}'
    )

    assert res.status_code == 503, res.text
    expect_code(res, "SERVICE_DEGRADED")
    current = await s.current()
    assert current["status"] == "PAID", f"без возврата отмены быть не должно: {current}"
    assert await s.stand.count_events("OrderCancelled") == 0, await s.stand.event_types()


async def test_lifecycle_cancel_draft_needs_no_refund(given_order):
    s = await given_order("200.00")

    res = await s.stand.post_json(s.path("/cancel"), customer_token(s.customer), '{"reasonCode":"mistake"}')

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED", res.text
    assert s.payment.requests == [], "черновик отменяется без похода в платежи"


async def test_lifecycle_unpaid_order_expires_after_timeout(given_order):
    s = await (await given_order("200.00")).confirm()

    s.clock.advance(timedelta(minutes=14))
    early = await s.stand.expirer.once()
    s.clock.advance(timedelta(minutes=2))
    expired = await s.stand.expirer.once()

    assert early == 0, f"до таймаута ничего не истекает, закрыто {early}"
    assert expired == 1, f"ожидали один просроченный заказ: {expired}"
    current = await s.current()
    assert current["status"] == "EXPIRED" and current["closedAt"] is not None, current
    assert await s.stand.count_events("OrderExpired") == 1, await s.stand.event_types()


async def test_payment_consumer_payment_completed_marks_paid_once(given_order):
    s = await (await given_order("200.00")).confirm()
    payment_id, event_id = uuid.uuid4(), uuid.uuid4()
    payload = PaymentCompletedPayload(
        payment_id=payment_id,
        order_id=uuid.UUID(s.order_id),
        amount="200.00",
        currency="RUB",
        occurred_at=NOW,
    ).encode()
    record = payment_record(payload, event_id, EVENT_PAYMENT_COMPLETED)
    handler = PaymentEventHandler(s.stand.lifecycle)

    await handler.handle(record)
    await handler.handle(record)

    current = await s.current()
    assert current["status"] == "PAID" and current["paymentId"] == str(payment_id), current
    assert await s.stand.count_events("OrderPaid") == 1, (
        f"событие платежа переводит заказ в PAID ровно один раз: {await s.stand.event_types()}"
    )
    assert json.loads(payload)["orderId"] == s.order_id


def payment_record(payload: bytes, event_id: uuid.UUID, event_type: str) -> ConsumerRecord:
    return ConsumerRecord(
        topic=TOPIC,
        partition=0,
        offset=0,
        timestamp=0,
        timestamp_type=0,
        key=None,
        value=payload,
        checksum=None,
        serialized_key_size=-1,
        serialized_value_size=len(payload),
        headers=[(HEADER_EVENT_ID, str(event_id).encode()), (HEADER_EVENT_TYPE, event_type.encode())],
    )
