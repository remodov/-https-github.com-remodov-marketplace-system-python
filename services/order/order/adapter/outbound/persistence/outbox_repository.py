import json
import uuid
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import Text, cast, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....core.order.aggregate.events import Event
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

    # TODO шаг 10: каждое событие строкой в outbox через session_in_scope, той же
    # транзакцией, что и заказ; payload через jsonb_of(payload_of(event)), published_at пустой.
    async def append(self, events: Sequence[Event]) -> None:
        return None

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


# TODO шаг 10: собрать payload по внешнему контракту из contracts/orders_v1
# (OrderCreatedPayload(...).encode()), а не отдавать наружу внутренний dataclass;
# событие, которого нет в контракте, - NotInContract.
def payload_of(event: Event) -> bytes:
    return json.dumps(asdict(event), default=str).encode()
