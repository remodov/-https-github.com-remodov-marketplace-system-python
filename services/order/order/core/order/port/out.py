import uuid
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ..aggregate.events import Event
from ..aggregate.order import Money, Order


@runtime_checkable
class OrderRepository(Protocol):
    async def insert(self, order: Order) -> None: ...
    async def by_id(self, order_id: uuid.UUID) -> Order: ...
    async def by_id_for_update(self, order_id: uuid.UUID) -> Order: ...
    async def update(self, order: Order) -> None: ...
    async def pending_payment_before(self, before: datetime, limit: int) -> list[uuid.UUID]: ...


@runtime_checkable
class CatalogGateway(Protocol):
    async def prices(self, product_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Money]: ...


@runtime_checkable
class PaymentGateway(Protocol):
    async def request_refund(
        self, order_id: uuid.UUID, payment_id: uuid.UUID, amount: Money, idempotency_key: str
    ) -> uuid.UUID: ...


@runtime_checkable
class ProcessedEvents(Protocol):
    async def mark_processed(self, event_id: uuid.UUID, event_type: str, now: datetime) -> bool: ...


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class IdGenerator(Protocol):
    def new_id(self) -> uuid.UUID: ...


@runtime_checkable
class UnitOfWork(Protocol):
    def begin(self) -> AbstractAsyncContextManager[None]: ...


@runtime_checkable
class IdempotencyKeys(Protocol):
    async def find(self, key: str, request_hash: str) -> uuid.UUID | None: ...
    async def claim(self, key: str, request_hash: str, order_id: uuid.UUID, now: datetime) -> bool: ...


@dataclass(frozen=True)
class OutboxMessage:
    id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    event_type: str
    event_version: int
    payload: bytes
    occurred_at: datetime


@runtime_checkable
class EventOutbox(Protocol):
    async def append(self, events: Sequence[Event]) -> None: ...
    async def unpublished(self, limit: int) -> list[OutboxMessage]: ...
    async def mark_published(self, message_id: uuid.UUID, at: datetime) -> None: ...


@runtime_checkable
class ExternalEventPublisher(Protocol):
    async def publish(self, message: OutboxMessage) -> None: ...
