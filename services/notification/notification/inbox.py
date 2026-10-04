import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from orders_v1 import (
    EVENT_DISPUTE_OPENED,
    EVENT_ORDER_CREATED,
    EVENT_ORDER_PAID,
    EVENT_ORDER_SHIPPED,
    OrderEventBase,
)
from pydantic import ValidationError
from sqlalchemy import Text, cast, literal, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from .tables import notifications, processed_events

CHANNEL_EMAIL = "EMAIL"
STATUS_PENDING = "PENDING"

TEMPLATES = {
    EVENT_ORDER_CREATED: "order-created",
    EVENT_ORDER_PAID: "order-paid",
    EVENT_ORDER_SHIPPED: "order-shipped",
    EVENT_DISPUTE_OPENED: "dispute-opened-seller",
}
TEMPLATE_STATUS_CHANGED = "order-status-changed"


class OffContract(Exception):
    pass


@dataclass(frozen=True)
class IncomingEvent:
    id: uuid.UUID
    type: str
    payload: bytes


@dataclass(frozen=True)
class Notification:
    id: uuid.UUID
    event_id: uuid.UUID
    event_type: str
    user_id: uuid.UUID
    channel: str
    template_key: str
    status: str
    created_at: datetime


class Clock(Protocol):
    def now(self) -> datetime: ...


class Processor:
    def __init__(self, sessions: async_sessionmaker, clock: Clock) -> None:
        self.sessions = sessions
        self.clock = clock

    async def process(self, event: IncomingEvent) -> bool:
        recipient = recipient_of(event)
        async with self.sessions() as session, session.begin():
            claimed = await session.execute(
                insert(processed_events)
                .values(event_id=event.id, event_type=event.type, processed_at=self.clock.now())
                .on_conflict_do_nothing(index_elements=[processed_events.c.event_id])
            )
            if claimed.rowcount == 0:
                return False
            await session.execute(
                insert(notifications).values(
                    id=uuid.uuid4(),
                    event_id=event.id,
                    event_type=event.type,
                    user_id=recipient,
                    channel=CHANNEL_EMAIL,
                    template_key=template_of(event.type),
                    status=STATUS_PENDING,
                    payload=cast(literal(event.payload.decode(), Text), JSONB),
                    created_at=self.clock.now(),
                )
            )
        return True

    async def list_by_user(self, user_id: uuid.UUID) -> list[Notification]:
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    select(notifications)
                    .where(notifications.c.user_id == user_id)
                    .order_by(notifications.c.created_at.desc())
                    .limit(100)
                )
            ).all()
        return [
            Notification(
                id=row.id,
                event_id=row.event_id,
                event_type=row.event_type,
                user_id=row.user_id,
                channel=row.channel,
                template_key=row.template_key,
                status=row.status,
                created_at=row.created_at,
            )
            for row in rows
        ]


def recipient_of(event: IncomingEvent) -> uuid.UUID:
    try:
        base = OrderEventBase.model_validate_json(event.payload)
    except ValidationError as error:
        raise OffContract(f"payload {event.type} не по контракту: {error}") from error
    if event.type == EVENT_DISPUTE_OPENED:
        return base.seller_id
    return base.customer_id


def template_of(event_type: str) -> str:
    return TEMPLATES.get(event_type, TEMPLATE_STATUS_CHANGED)
