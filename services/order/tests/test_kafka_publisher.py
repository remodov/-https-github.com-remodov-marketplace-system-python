import asyncio
import os
import uuid

import pytest
from aiokafka import AIOKafkaConsumer
from conftest import NOW
from orders_v1 import EVENT_ORDER_CREATED, HEADER_EVENT_ID, HEADER_EVENT_TYPE, HEADER_EVENT_VERSION, TOPIC

from order.adapter.outbound.kafka.publisher import KafkaPublisher
from order.core.order.port.out import OutboxMessage


async def broker_reachable(broker: str) -> bool:
    host, _, port = broker.partition(":")
    try:
        async with asyncio.timeout(3):
            _, writer = await asyncio.open_connection(host, int(port))
    except (OSError, TimeoutError):
        return False
    writer.close()
    await writer.wait_closed()
    return True


async def test_kafka_publisher_delivers_payload_with_headers():
    broker = os.environ.get("KAFKA_BROKERS", "localhost:9097")
    if not await broker_reachable(broker):
        pytest.skip(
            f"Kafka на {broker} недоступна: подними стенд командой docker compose -f infra/compose.yaml up -d kafka"
        )
    topic = f"{TOPIC}.test-{uuid.uuid4()}"
    message = OutboxMessage(
        id=uuid.uuid4(),
        aggregate_type="Order",
        aggregate_id=uuid.uuid4(),
        event_type=EVENT_ORDER_CREATED,
        event_version=1,
        payload=b'{"orderId":"x"}',
        occurred_at=NOW,
    )

    publisher = KafkaPublisher(broker, topic)
    await publisher.start()
    try:
        await publisher.publish(message)
    finally:
        await publisher.aclose()

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=broker,
        group_id=f"test-{uuid.uuid4()}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        received = await asyncio.wait_for(consumer.getone(), 30)
    finally:
        await consumer.stop()

    headers = dict(received.headers)
    assert received.key == str(message.aggregate_id).encode(), f"ключ сообщения: {received.key}"
    assert received.value == b'{"orderId":"x"}', f"тело сообщения: {received.value}"
    assert headers[HEADER_EVENT_ID] == str(message.id).encode(), f"заголовки события: {headers}"
    assert headers[HEADER_EVENT_TYPE] == EVENT_ORDER_CREATED.encode(), f"заголовки события: {headers}"
    assert headers[HEADER_EVENT_VERSION] == b"1", f"заголовки события: {headers}"
