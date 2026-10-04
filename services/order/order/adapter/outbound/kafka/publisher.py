from datetime import UTC

from aiokafka import AIOKafkaProducer
from orders_v1 import (
    HEADER_AGGREGATE_ID,
    HEADER_AGGREGATE_TYPE,
    HEADER_EVENT_ID,
    HEADER_EVENT_TYPE,
    HEADER_EVENT_VERSION,
    HEADER_OCCURRED_AT,
)

from ....core.order.port.out import OutboxMessage


class PublisherNotStarted(Exception):
    pass


class KafkaPublisher:
    def __init__(self, brokers: str, topic: str) -> None:
        self.brokers = brokers
        self.topic = topic
        self.producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self.producer = AIOKafkaProducer(bootstrap_servers=self.brokers, acks="all")
        await self.producer.start()

    async def publish(self, message: OutboxMessage) -> None:
        if self.producer is None:
            raise PublisherNotStarted("издатель Kafka не запущен: нужен start() в lifespan")
        await self.producer.send_and_wait(
            self.topic,
            value=message.payload,
            key=str(message.aggregate_id).encode(),
            headers=headers_of(message),
        )

    async def aclose(self) -> None:
        if self.producer is not None:
            await self.producer.stop()
            self.producer = None


def headers_of(message: OutboxMessage) -> list[tuple[str, bytes]]:
    return [
        (HEADER_EVENT_ID, str(message.id).encode()),
        (HEADER_EVENT_TYPE, message.event_type.encode()),
        (HEADER_EVENT_VERSION, str(message.event_version).encode()),
        (HEADER_AGGREGATE_TYPE, message.aggregate_type.encode()),
        (HEADER_AGGREGATE_ID, str(message.aggregate_id).encode()),
        (HEADER_OCCURRED_AT, message.occurred_at.astimezone(UTC).isoformat().encode()),
    ]
