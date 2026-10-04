import json
import uuid
from datetime import timedelta

import pytest
from conftest import NOW, RecordingPublisher, answering, customer_token, order_body, stand_catalog_settings
from orders_v1 import EVENT_ORDER_CONFIRMED, EVENT_ORDER_CREATED, OrderCreatedPayload

from order.adapter.outbound.catalog.client import CatalogClient
from order.core.order.usecase.relay_outbox import PublishFailed

CONTRACT_FIELDS = ["currency", "customerId", "itemsCount", "occurredAt", "orderId", "sellerId", "totalAmount"]


async def test_outbox_order_created_is_written_with_the_order(start_stand, start_catalog):
    fake = await start_catalog(answering("2490.50"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()

    res = await stand.post_order(customer_token(uuid.uuid4()), order_body(uuid.uuid4(), uuid.uuid4(), 2))

    assert res.status_code == 201, res.text
    rows = await stand.outbox_rows()
    assert len(rows) == 1, f"в outbox {len(rows)} строк, ожидали одну: {rows}"
    assert rows[0].event_type == EVENT_ORDER_CREATED, rows[0]
    assert str(rows[0].aggregate_id) == res.json()["id"], rows[0]
    assert not rows[0].published, rows[0]


async def test_outbox_payload_follows_external_contract(start_stand, start_catalog):
    fake = await start_catalog(answering("2490.50"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    customer, seller = uuid.uuid4(), uuid.uuid4()

    res = await stand.post_order(customer_token(customer), order_body(uuid.uuid4(), seller, 2))

    assert res.status_code == 201, res.text
    rows = await stand.outbox_rows()
    assert len(rows) == 1, f"в outbox {len(rows)} строк, ожидали одну"
    raw = json.loads(rows[0].payload)
    assert sorted(raw) == CONTRACT_FIELDS, f"поля payload {sorted(raw)}, контракт ждёт {CONTRACT_FIELDS}"
    assert raw["customerId"] == str(customer), f"адресаты должны уезжать строками UUID: {rows[0].payload}"
    assert raw["sellerId"] == str(seller), f"адресаты должны уезжать строками UUID: {rows[0].payload}"
    assert raw["totalAmount"] == "4981.00", f"сумма должна быть десятичной строкой: {rows[0].payload}"
    assert raw["currency"] == "RUB" and raw["itemsCount"] == 1, rows[0].payload
    payload = OrderCreatedPayload.model_validate_json(rows[0].payload)
    assert str(payload.order_id) == res.json()["id"], "потребитель не прочитает payload в контрактный тип"


async def test_outbox_nothing_leaks_when_the_transaction_rolls_back(start_stand, start_catalog):
    fake = await start_catalog(answering("100.00"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)))
    await stand.clear_tables()
    customer, key, body = uuid.uuid4(), str(uuid.uuid4()), order_body(uuid.uuid4(), uuid.uuid4(), 1)

    first = await stand.post_order(customer_token(customer), body, key)
    second = await stand.post_order(customer_token(customer), body, key)

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    rows = await stand.outbox_rows()
    assert len(rows) == 1, f"повтор не должен рождать второе событие: {rows}"


async def test_outbox_relay_publishes_and_marks_rows(start_stand, start_catalog):
    fake = await start_catalog(answering("100.00"))
    publisher = RecordingPublisher()
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)), publisher)
    await stand.clear_tables()
    first = await stand.given_outbox_row(EVENT_ORDER_CREATED, '{"orderId":"a"}', NOW)
    second = await stand.given_outbox_row(
        EVENT_ORDER_CONFIRMED, '{"orderId":"b"}', NOW + timedelta(seconds=1)
    )

    published = await stand.relay.once()
    again = await stand.relay.once()

    assert published == 2, f"ожидали две отправки, получили {published}"
    assert again == 0, f"второй круг не должен отправлять ничего: {again}"
    assert [message.id for message in publisher.messages] == [first, second], publisher.messages
    message = publisher.messages[0]
    assert message.event_type == EVENT_ORDER_CREATED and message.aggregate_type == "Order", message
    assert message.payload == b'{"orderId": "a"}', message
    rows = await stand.outbox_rows()
    assert all(row.published for row in rows), f"не все строки помечены отправленными: {rows}"


async def test_outbox_relay_keeps_row_when_broker_fails(start_stand, start_catalog):
    fake = await start_catalog(answering("100.00"))
    publisher = RecordingPublisher(fail=ConnectionError("брокер лежит"))
    stand = await start_stand(CatalogClient(stand_catalog_settings(fake.url)), publisher)
    await stand.clear_tables()
    await stand.given_outbox_row(EVENT_ORDER_CREATED, '{"orderId":"a"}')

    with pytest.raises(PublishFailed):
        await stand.relay.once()

    rows = await stand.outbox_rows()
    assert len(rows) == 1 and not rows[0].published, f"строка должна остаться неотправленной: {rows}"
