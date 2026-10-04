import logging
import uuid

from aiokafka import AIOKafkaConsumer, ConsumerRecord, TopicPartition
from orders_v1 import HEADER_EVENT_ID, HEADER_EVENT_TYPE

from .inbox import IncomingEvent, Processor

log = logging.getLogger("notification.consumer")


class Consumer:
    def __init__(self, brokers: str, group: str, topic: str, processor: Processor) -> None:
        self.brokers = brokers
        self.group = group
        self.topic = topic
        self.processor = processor

    async def run(self) -> None:
        consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.brokers,
            group_id=self.group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await consumer.start()
        try:
            async for record in consumer:
                if await self.handle(record):
                    await consumer.commit({TopicPartition(record.topic, record.partition): record.offset + 1})
        finally:
            await consumer.stop()

    async def handle(self, record: ConsumerRecord) -> bool:
        event = incoming(record)
        if event is None:
            log.warning("сообщение без обязательных заголовков пропущено, offset %s", record.offset)
            return True
        try:
            processed = await self.processor.process(event)
        except Exception:
            log.exception(
                "событие %s %s не обработано, offset %s не сдвигаем", event.type, event.id, record.offset
            )
            return False
        if not processed:
            log.info("повторная доставка %s %s, второе уведомление не создаём", event.type, event.id)
        return True


def incoming(record: ConsumerRecord) -> IncomingEvent | None:
    headers = dict(record.headers)
    raw_id = headers.get(HEADER_EVENT_ID)
    raw_type = headers.get(HEADER_EVENT_TYPE)
    if not raw_id or not raw_type:
        return None
    try:
        event_id = uuid.UUID(raw_id.decode())
    except ValueError:
        return None
    return IncomingEvent(id=event_id, type=raw_type.decode(), payload=record.value)
