from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .order import CancellationReason, Item, Money, Status


@runtime_checkable
class Event(Protocol):
    @property
    def event_type(self) -> str: ...

    @property
    def aggregate_id(self) -> uuid.UUID: ...

    @property
    def occurred_at(self) -> datetime: ...


@dataclass(frozen=True)
class ItemSnapshot:
    product_id: uuid.UUID
    quantity: int
    unit_price: Money


@dataclass(frozen=True, kw_only=True)
class OrderEvent:
    order_id: uuid.UUID
    customer_id: uuid.UUID
    seller_id: uuid.UUID
    at: datetime

    @property
    def aggregate_id(self) -> uuid.UUID:
        return self.order_id

    @property
    def occurred_at(self) -> datetime:
        return self.at


@dataclass(frozen=True, kw_only=True)
class OrderCreated(OrderEvent):
    total: Money
    items: tuple[ItemSnapshot, ...]

    @property
    def event_type(self) -> str:
        return "OrderCreated"


@dataclass(frozen=True, kw_only=True)
class OrderConfirmed(OrderEvent):
    total: Money

    @property
    def event_type(self) -> str:
        return "OrderConfirmed"


@dataclass(frozen=True, kw_only=True)
class OrderPaid(OrderEvent):
    payment_id: uuid.UUID
    total: Money

    @property
    def event_type(self) -> str:
        return "OrderPaid"


@dataclass(frozen=True, kw_only=True)
class OrderCancelled(OrderEvent):
    previous_status: Status
    reason: CancellationReason
    refund_id: uuid.UUID | None

    @property
    def event_type(self) -> str:
        return "OrderCancelled"


@dataclass(frozen=True, kw_only=True)
class OrderExpired(OrderEvent):
    @property
    def event_type(self) -> str:
        return "OrderExpired"


@dataclass(frozen=True, kw_only=True)
class OrderShipped(OrderEvent):
    tracking_number: str

    @property
    def event_type(self) -> str:
        return "OrderShipped"


@dataclass(frozen=True, kw_only=True)
class OrderDelivered(OrderEvent):
    @property
    def event_type(self) -> str:
        return "OrderDelivered"


def snapshots_of(items: Sequence[Item]) -> tuple[ItemSnapshot, ...]:
    return tuple(ItemSnapshot(item.product_id, item.quantity, item.unit_price) for item in items)
