import uuid

import pytest
from conftest import NOW, order_created, processed_count
from orders_v1 import EVENT_DISPUTE_OPENED, EVENT_ORDER_CREATED, OrderCreatedPayload

from notification.inbox import STATUS_PENDING, IncomingEvent, OffContract


async def test_process_same_event_twice_creates_one_notification(processor):
    customer = uuid.uuid4()
    event = IncomingEvent(uuid.uuid4(), EVENT_ORDER_CREATED, order_created(customer, uuid.uuid4()))

    first = await processor.process(event)
    second = await processor.process(event)

    assert first is True, "первая доставка должна обработаться"
    assert second is False, "повторная доставка должна быть пропущена"
    items = await processor.list_by_user(customer)
    assert len(items) == 1, f"ожидали одно уведомление покупателю: {items}"
    assert items[0].template_key == "order-created" and items[0].status == STATUS_PENDING, items[0]


async def test_process_dispute_opened_goes_to_seller(processor):
    customer, seller = uuid.uuid4(), uuid.uuid4()
    event = IncomingEvent(uuid.uuid4(), EVENT_DISPUTE_OPENED, order_created(customer, seller))

    assert await processor.process(event) is True

    to_seller = await processor.list_by_user(seller)
    to_customer = await processor.list_by_user(customer)
    assert len(to_seller) == 1 and len(to_customer) == 0, (
        f"спор адресуется продавцу: продавцу {len(to_seller)}, покупателю {len(to_customer)}"
    )
    assert to_seller[0].template_key == "dispute-opened-seller"


async def test_process_payload_off_contract_is_rejected_without_marking(processor, engine):
    event = IncomingEvent(uuid.uuid4(), EVENT_ORDER_CREATED, b'{"customerId":{"value":"abc"}}')

    with pytest.raises(OffContract):
        await processor.process(event)

    assert await processed_count(engine) == 0, "событие с плохим payload не должно помечаться обработанным"


async def test_process_without_recipient_is_rejected_without_marking(processor, engine):
    event = IncomingEvent(uuid.uuid4(), EVENT_ORDER_CREATED, f'{{"orderId":"{uuid.uuid4()}"}}'.encode())

    with pytest.raises(OffContract):
        await processor.process(event)

    assert await processed_count(engine) == 0


async def test_process_order_created_from_contract_is_handled(processor):
    customer = uuid.uuid4()
    payload = OrderCreatedPayload(
        order_id=uuid.uuid4(),
        customer_id=customer,
        seller_id=uuid.uuid4(),
        occurred_at=NOW,
        total_amount="4981.00",
        currency="RUB",
        items_count=1,
    ).encode()

    assert await processor.process(IncomingEvent(uuid.uuid4(), EVENT_ORDER_CREATED, payload)) is True

    items = await processor.list_by_user(customer)
    assert len(items) == 1 and items[0].event_type == EVENT_ORDER_CREATED, items
