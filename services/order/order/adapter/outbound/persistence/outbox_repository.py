import uuid
from collections.abc import Sequence
from datetime import datetime

from orders_v1 import OrderCreatedPayload
from sqlalchemy import Text, cast, insert, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....core.order.aggregate.events import Event, OrderCreated
from ....core.order.port.out import IdGenerator, OutboxMessage
from .tables import outbox
from .unit_of_work import session_in_scope

AGGREGATE_ORDER = "Order"
EVENT_VERSION = 1


class NotInContract(Exception):
    pass


class SqlAlchemyOutbox:
    def __init__(self, sessions: async_sessionmaker, ids: IdGenerator) -> None:
        self.sessions = sessions
        self.ids = ids

    async def append(self, events: Sequence[Event]) -> None:
        async with session_in_scope(self.sessions) as session:
            for event in events:
                await session.execute(
                    insert(outbox).values(
                        id=self.ids.new_id(),
                        aggregate_id=event.aggregate_id,
                        aggregate_type=AGGREGATE_ORDER,
                        event_type=event.event_type,
                        event_version=EVENT_VERSION,
                        payload=jsonb_of(payload_of(event)),
                        occurred_at=event.occurred_at,
                    )
                )

    async def unpublished(self, limit: int) -> list[OutboxMessage]:
        async with session_in_scope(self.sessions) as session:
            rows = (
                await session.execute(
                    select(
                        outbox.c.id,
                        outbox.c.aggregate_type,
                        outbox.c.aggregate_id,
                        outbox.c.event_type,
                        outbox.c.event_version,
                        cast(outbox.c.payload, Text).label("payload"),
                        outbox.c.occurred_at,
                    )
                    .where(outbox.c.published_at.is_(None))
                    .order_by(outbox.c.occurred_at, outbox.c.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        return [
            OutboxMessage(
                id=row.id,
                aggregate_type=row.aggregate_type,
                aggregate_id=row.aggregate_id,
                event_type=row.event_type,
                event_version=row.event_version,
                payload=row.payload.encode(),
                occurred_at=row.occurred_at,
            )
            for row in rows
        ]

    async def mark_published(self, message_id: uuid.UUID, at: datetime) -> None:
        async with session_in_scope(self.sessions) as session:
            await session.execute(update(outbox).where(outbox.c.id == message_id).values(published_at=at))


def jsonb_of(payload: bytes):
    return cast(literal(payload.decode(), Text), JSONB)


def payload_of(event: Event) -> bytes:
    match event:
        case OrderCreated():
            return OrderCreatedPayload(
                order_id=event.order_id,
                customer_id=event.customer_id,
                seller_id=event.seller_id,
                occurred_at=event.at,
                total_amount=f"{event.total.amount:.2f}",
                currency=event.total.currency,
                items_count=len(event.items),
            ).encode()
    raise NotInContract(f"событие {event.event_type} не описано во внешнем контракте")
