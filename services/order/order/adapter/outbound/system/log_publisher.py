import logging

from ....core.order.port.out import OutboxMessage

log = logging.getLogger("order.events")


class LogPublisher:
    async def publish(self, message: OutboxMessage) -> None:
        log.info(
            "событие ушло бы в брокер: %s %s, агрегат %s, payload %s",
            message.event_type,
            message.id,
            message.aggregate_id,
            message.payload.decode(),
        )
