import logging
import uuid
from dataclasses import dataclass

from aiokafka import AIOKafkaConsumer, ConsumerRecord, TopicPartition
from payments_v1 import EVENT_PAYMENT_COMPLETED, HEADER_EVENT_ID, HEADER_EVENT_TYPE, PaymentCompletedPayload
from pydantic import ValidationError

from ....core.order.usecase.lifecycle import LifecycleHandler, PayOrder

log = logging.getLogger("order.payments")


class OffContract(Exception):
    pass


@dataclass(frozen=True)
class IncomingEvent:
    id: uuid.UUID
    type: str
    payload: bytes


class PaymentEventHandler:
    def __init__(self, lifecycle: LifecycleHandler) -> None:
        self.lifecycle = lifecycle

    async def handle(self, record: ConsumerRecord) -> None:
        event = incoming(record)
        if event is None:
            log.warning(
                "событие платежа без заголовков event-id и event-type пропущено, offset %s", record.offset
            )
            return
        if event.type != EVENT_PAYMENT_COMPLETED:
            return
        try:
            payload = PaymentCompletedPayload.model_validate_json(event.payload)
        except ValidationError as error:
            raise OffContract(f"payload PaymentCompleted {event.id} не по контракту: {error}") from error
        handled = await self.lifecycle.pay_from_event(
            event.id, event.type, PayOrder(order_id=payload.order_id, payment_id=payload.payment_id)
        )
        if not handled:
            log.info("повторная доставка PaymentCompleted %s пропущена", event.id)


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
    return IncomingEvent(id=event_id, type=raw_type.decode(), payload=record.value or b"")


class PaymentConsumer:
    def __init__(self, brokers: str, group: str, topic: str, handler: PaymentEventHandler) -> None:
        self.brokers = brokers
        self.group = group
        self.topic = topic
        self.handler = handler

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
                try:
                    await self.handler.handle(record)
                except Exception:
                    log.exception("событие платежа не обработано, offset %s не сдвигаем", record.offset)
                    continue
                await consumer.commit({TopicPartition(record.topic, record.partition): record.offset + 1})
        finally:
            await consumer.stop()
